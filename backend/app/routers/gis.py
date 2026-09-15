from __future__ import annotations

import re
from decimal import Decimal
from typing import Any
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import CatalogItem, CatalogType, User
from app.services.auth_service import get_current_user
from app.services.gis_layers import DEFAULT_GIS_LAYERS, get_gis_layers

router = APIRouter(prefix="/api/v1/gis", tags=["gis"])

WMS_URL = DEFAULT_GIS_LAYERS["parcels"]["wms_url"]
IDENTIFY_URL = DEFAULT_GIS_LAYERS["parcels"]["identify_url"]
QUERY_URL = DEFAULT_GIS_LAYERS["parcels"]["query_url"]
GIS_HTTP_HEADERS = {"User-Agent": "NuevoAvaluo2026/1.0 (https://avaluos.am2ps.com.bo)"}


class ParcelHit(BaseModel):
    cadastral_code: str
    subdistrict: str
    block_code: str
    plot_code: str
    use_code: str = "0"
    building_code: str = "0"
    floor_code: str = "0"
    unit_code: str = "0"
    property_number: str | None = None
    district: str | None = None
    commune: str | None = None
    subdistrict_name: str | None = None
    area_m2: Decimal | None = None
    zone_code: str | None = None
    zone_item_id: UUID | None = None
    zone_label: str | None = None
    slope_raw: str | None = None
    topography_code: str | None = None
    topography_item_id: UUID | None = None
    topography_label: str | None = None
    road_material_code: str | None = None
    road_material_item_id: UUID | None = None
    road_material_label: str | None = None
    shape_code: str | None = None
    shape_item_id: UUID | None = None
    shape_label: str | None = None
    address: str | None = None
    rings: list[list[list[float]]] = Field(default_factory=list)
    centroid_lat: float | None = None
    centroid_lng: float | None = None
    raw_attributes: dict[str, Any] = Field(default_factory=dict)


class IdentifyOut(BaseModel):
    found: bool
    parcel: ParcelHit | None = None
    candidates: list[ParcelHit] = []
    wms_url: str = WMS_URL
    layer: str = "0"


def _attr(attrs: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        if key in attrs and attrs[key] not in (None, "", "Null"):
            return str(attrs[key]).strip()
    lower_map = {str(k).lower(): v for k, v in attrs.items()}
    for key in keys:
        v = lower_map.get(key.lower())
        if v not in (None, "", "Null"):
            return str(v).strip()
    for k, v in attrs.items():
        kl = str(k).lower()
        for key in keys:
            if key.lower() in kl and v not in (None, "", "Null"):
                return str(v).strip()
    return None


def _parse_code(code: str) -> tuple[str, str, str, str, str, str, str]:
    digits = "".join(ch for ch in code if ch.isalnum()).ljust(17, "0")[:17]
    return (
        digits[0:2],
        digits[2:5],
        digits[5:8],
        digits[8:9] or "0",
        digits[9:10] or "0",
        digits[10:11] or "0",
        digits[11:12] or "0",
    )


def _map_zone_code(raw: str | None) -> str | None:
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return None
    n = int(digits)
    if 1 <= n <= 11:
        return f"ZH-{n}"
    return None


def looks_like_slope_class(raw: str | None) -> bool:
    """True si el valor parece pendiente (< 10°, 0-10º). False para píxeles DEM."""
    if not raw:
        return False
    s = str(raw).strip().lower()
    if any(token in s for token in ("°", "º", "plano", "pendiente", "accident", "menor", "superior", "<", ">")):
        return True
    if re.search(r"\d+\s*[-–/]\s*\d+", s):
        return True
    compact = s.replace(",", ".").replace(" ", "")
    if re.fullmatch(r"\d+(\.\d+)?", compact):
        return False
    return False


def _map_topography_code(raw: str | None) -> str | None:
    if not raw or not looks_like_slope_class(raw):
        return None
    s = raw.lower().replace("°", "").replace("º", "")
    # ejemplos WMS: "< 10°", "0-10", "11-15", "> 15"
    nums = [int(x) for x in re.findall(r"\d+", s)]
    if "<" in s or "menor" in s or (nums and max(nums) <= 10 and ">" not in s and "superior" not in s):
        if not nums or max(nums) <= 10:
            return "IPRT-PLA"
    if "accident" in s or (nums and min(nums) >= 45):
        return "IPRT-ACC"
    if "superior" in s or ">" in s or (nums and min(nums) >= 16):
        return "IPRT-ALT"
    if nums and (11 in nums or 15 in nums or (min(nums) >= 11 and max(nums) <= 15)):
        return "IPRT-BAJ"
    if nums:
        hi = max(nums)
        if hi <= 10:
            return "IPRT-PLA"
        if hi <= 15:
            return "IPRT-BAJ"
        if hi <= 45:
            return "IPRT-ALT"
        return "IPRT-ACC"
    return "IPRT-PLA"


def map_road_material_code(raw: str | None) -> str | None:
    if not raw:
        return None
    s = (
        raw.lower()
        .replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
        .replace("ñ", "n")
    )
    rules = [
        ("adoquin", "IPV-ADO"),
        ("pavimento", "IPV-PAV"),
        ("rigido", "IPV-PAV"),
        ("asfalt", "IPV-ASF"),
        ("loseta", "IPV-LOS"),
        ("cemento", "IPV-CEM"),
        ("concreto", "IPV-CEM"),
        ("hormigon", "IPV-CEM"),
        ("ripio", "IPV-RIP"),
        ("ripiado", "IPV-RIP"),
        ("grava", "IPV-RIP"),
        ("piedra", "IPV-PIE"),
        ("empedrado", "IPV-PIE"),
        ("tierra", "IPV-TIE"),
        ("suelo", "IPV-TIE"),
    ]
    for needle, code in rules:
        if needle in s:
            return code
    return None


def _catalog_by_code(db: Session, type_code: str, item_code: str) -> CatalogItem | None:
    return db.execute(
        select(CatalogItem)
        .join(CatalogType, CatalogType.id == CatalogItem.catalog_type_id)
        .where(
            CatalogType.code == type_code,
            CatalogItem.code == item_code,
            CatalogItem.is_active.is_(True),
        )
    ).scalar_one_or_none()


def _to_parcel(attrs: dict[str, Any], display_value: str | None = None) -> ParcelHit | None:
    code = (
        _attr(attrs, "Código Catastral", "Codigo Catastral", "CodCat", "CODIGO_CATASTRAL", "codigo_catastral")
        or display_value
    )
    if not code:
        return None
    digits = "".join(ch for ch in code if ch.isalnum()).ljust(17, "0")[:17]
    sub, block, plot, use, building, floor, unit = _parse_code(digits)
    sub = _attr(attrs, "Nro. Subdistro ", "Nro. Subdistro", "Nro Subdistro", "SUBDISTRITO_NRO") or sub
    block = _attr(attrs, "Nro. manzana", "Nro manzana", "MANZANA") or block
    plot = _attr(attrs, "Nro. predio", "Nro predio", "PREDIO") or plot
    area_raw = _attr(attrs, "SHAPE.STArea()", "SHAPE.AREA", "AREA")
    area = None
    if area_raw:
        try:
            area = Decimal(area_raw.replace(",", ".").replace(" ", ""))
        except Exception:
            area = None
    zone_raw = _attr(attrs, "ZTributari", "Zona Tributaria", "ZONA", "zona")
    slope_raw = _attr(attrs, "pendiente", "Pendiente", "PENDIENTE")
    return ParcelHit(
        cadastral_code=digits,
        subdistrict=str(sub).zfill(2)[:2],
        block_code=str(block).zfill(3)[:11],
        plot_code=str(plot).zfill(3)[:11],
        use_code=use,
        building_code=building,
        floor_code=floor,
        unit_code=unit,
        property_number=_attr(attrs, "Nro. Inmueble", "Nro Inmueble", "NRO_INMUEBLE"),
        district=_attr(attrs, "Distrito"),
        commune=_attr(attrs, "comuna", "Comuna"),
        subdistrict_name=_attr(attrs, "Subdistrito"),
        area_m2=area,
        zone_code=_map_zone_code(zone_raw),
        slope_raw=slope_raw,
        topography_code=_map_topography_code(slope_raw),
        raw_attributes=attrs,
    )


def _rings_from_esri(geom: dict[str, Any] | None) -> list[list[list[float]]]:
    if not geom:
        return []
    out: list[list[list[float]]] = []
    for ring in geom.get("rings") or []:
        pts: list[list[float]] = []
        for pt in ring:
            if len(pt) < 2:
                continue
            pts.append([float(pt[0]), float(pt[1])])
        if len(pts) >= 3:
            out.append(pts)
    return out


def _ring_points(ring: list[list[float]]) -> list[tuple[float, float]]:
    if not ring:
        return []
    pts = [(float(p[0]), float(p[1])) for p in ring if len(p) >= 2]
    if len(pts) >= 2 and pts[0] == pts[-1]:
        pts = pts[:-1]
    return pts


def _point_in_ring(lng: float, lat: float, ring: list[list[float]]) -> bool:
    pts = _ring_points(ring)
    n = len(pts)
    if n < 3:
        return False
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = pts[i]
        xj, yj = pts[j]
        intersects = (yi > lat) != (yj > lat)
        if intersects:
            denom = yj - yi
            if abs(denom) < 1e-18:
                continue
            x_cross = (xj - xi) * (lat - yi) / denom + xi
            if lng < x_cross:
                inside = not inside
        j = i
    return inside


def point_in_parcel_rings(lng: float, lat: float, rings: list[list[list[float]]] | None) -> bool:
    """Punto [lng, lat] dentro del anillo exterior, fuera de huecos."""
    if not rings:
        return False
    if not _point_in_ring(lng, lat, rings[0]):
        return False
    for hole in rings[1:]:
        if _point_in_ring(lng, lat, hole):
            return False
    return True


def _outer_ring_area(rings: list[list[list[float]]]) -> float:
    pts = _ring_points(rings[0]) if rings else []
    if len(pts) < 3:
        return 0.0
    area = 0.0
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


def _centroid_from_rings(rings: list[list[list[float]]]) -> tuple[float | None, float | None]:
    """Centroide de área (shoelace). Evita el promedio de vértices, que tira el pin al sur."""
    if not rings:
        return None, None
    pts = _ring_points(rings[0])
    if not pts:
        return None, None
    if len(pts) < 3:
        lng = sum(p[0] for p in pts) / len(pts)
        lat = sum(p[1] for p in pts) / len(pts)
        return lat, lng
    area2 = 0.0
    cx = 0.0
    cy = 0.0
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        cross = x1 * y2 - x2 * y1
        area2 += cross
        cx += (x1 + x2) * cross
        cy += (y1 + y2) * cross
    if abs(area2) < 1e-18:
        lng = sum(p[0] for p in pts) / len(pts)
        lat = sum(p[1] for p in pts) / len(pts)
        return lat, lng
    inv = 1.0 / (3.0 * area2)
    return cy * inv, cx * inv


def geometry_on_parcel(
    building_rings: list[list[list[float]]] | None,
    parcel_rings: list[list[list[float]]] | None,
) -> bool:
    """True si la construcción pertenece al predio (centroide o mayoría de vértices dentro)."""
    if not building_rings or not parcel_rings:
        return False
    lat, lng = _centroid_from_rings(building_rings)
    if lat is not None and lng is not None and point_in_parcel_rings(lng, lat, parcel_rings):
        return True
    pts = [p for ring in building_rings for p in ring if len(p) >= 2]
    if len(pts) < 3:
        return False
    inside = sum(1 for p in pts if point_in_parcel_rings(float(p[0]), float(p[1]), parcel_rings))
    return inside * 2 >= len(pts)


def pick_identify_candidate(
    candidates: list[ParcelHit],
    lat: float,
    lng: float,
) -> ParcelHit | None:
    """Elige el predio que contiene el clic; si hay varios, el de menor área."""
    if not candidates:
        return None
    containing = [c for c in candidates if point_in_parcel_rings(lng, lat, c.rings)]
    pool = containing or list(candidates)

    def sort_key(hit: ParcelHit) -> tuple[float, str]:
        if hit.area_m2 is not None:
            area = abs(float(hit.area_m2))
        elif hit.rings:
            area = _outer_ring_area(hit.rings)
        else:
            area = 1e18
        return (area if area > 0 else 1e18, hit.cadastral_code or "")

    return min(pool, key=sort_key)


def _attach_geometry(hit: ParcelHit, geom: dict[str, Any] | None) -> ParcelHit:
    rings = _rings_from_esri(geom)
    if rings:
        hit.rings = rings
        lat, lng = _centroid_from_rings(rings)
        hit.centroid_lat = lat
        hit.centroid_lng = lng
    return hit


def parcel_map_meta(hit: ParcelHit) -> dict[str, Any]:
    return {
        "cadastral_code": hit.cadastral_code,
        "rings": hit.rings,
        "centroid_lat": hit.centroid_lat,
        "centroid_lng": hit.centroid_lng,
        "area_m2": float(hit.area_m2) if hit.area_m2 is not None else None,
    }


def normalize_cadastral_digits(code: str) -> str:
    return "".join(ch for ch in code if ch.isalnum()).upper().ljust(17, "0")[:17]


def cadastral_where_clauses(digits: str) -> list[str]:
    if len(digits) < 8:
        return []
    prefix8 = digits[:8]
    prefix11 = digits[:11]
    return [
        f"CodCat='{digits}'",
        f"CodCat='{prefix11}'",
        f"CodCat LIKE '{prefix8}%'",
    ]


def select_arcgis_feature(feats: list[dict[str, Any]], digits: str) -> dict[str, Any] | None:
    if not feats:
        return None

    def cod(feat: dict[str, Any]) -> str:
        raw = str((feat.get("attributes") or {}).get("CodCat") or "")
        return "".join(ch for ch in raw if ch.isalnum()).upper()

    exact = [feat for feat in feats if cod(feat) == digits]
    if exact:
        return exact[0]
    prefix8 = digits[:8]
    prefixed = [feat for feat in feats if cod(feat).startswith(prefix8)]
    if len(prefixed) == 1:
        return prefixed[0]
    if len(feats) == 1:
        return feats[0]
    return None


def _query_by_code(
    code: str,
    query_url: str | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    digits = normalize_cadastral_digits(code)
    clauses = cadastral_where_clauses(digits)
    if not clauses:
        return None, None
    url = query_url or QUERY_URL
    try:
        with httpx.Client(timeout=20.0, follow_redirects=True) as client:
            for where in clauses:
                resp = client.get(
                    url,
                    headers=GIS_HTTP_HEADERS,
                    params={
                        "where": where,
                        "outFields": "*",
                        "returnGeometry": "true",
                        "outSR": 4326,
                        "resultRecordCount": 12,
                        "f": "json",
                    },
                )
                resp.raise_for_status()
                payload = resp.json()
                chosen = select_arcgis_feature(payload.get("features") or [], digits)
                if not chosen:
                    continue
                return chosen.get("attributes") or {}, chosen.get("geometry")
    except Exception:
        return None, None
    return None, None


def _identify_attrs(
    identify_url: str,
    lat: float,
    lng: float,
    tolerance: int = 8,
    prefer_fields: list[str] | None = None,
) -> dict[str, Any]:
    pad = 0.006
    params = {
        "geometry": f"{lng},{lat}",
        "geometryType": "esriGeometryPoint",
        "sr": 4326,
        "layers": "all",
        "tolerance": tolerance,
        "mapExtent": f"{lng - pad},{lat - pad},{lng + pad},{lat + pad}",
        "imageDisplay": "800,600,96",
        "returnGeometry": "false",
        "f": "json",
    }
    try:
        with httpx.Client(timeout=20.0, follow_redirects=True, headers=GIS_HTTP_HEADERS) as client:
            resp = client.get(identify_url, params=params)
            resp.raise_for_status()
            payload = resp.json()
    except Exception:
        return {}
    results = payload.get("results") or []
    if not results:
        return {}
    if prefer_fields:
        for item in results:
            attrs = item.get("attributes") or {}
            if _attr(attrs, *prefer_fields):
                return attrs
    return results[0].get("attributes") or {}


def compose_address(hit: ParcelHit, extra_attrs: dict[str, Any] | None = None) -> str | None:
    attrs = {**(hit.raw_attributes or {}), **(extra_attrs or {})}
    street = _attr(attrs, "Calle", "Direccion", "Dirección", "Via", "Vía", "nombre_via", "direccion")
    parts: list[str] = []
    if street:
        parts.append(street)
    if hit.commune:
        parts.append(str(hit.commune).title())
    if hit.subdistrict_name:
        parts.append(f"Subdistrito {str(hit.subdistrict_name).title()}")
    if hit.property_number and hit.property_number not in ("0", "NULL"):
        parts.append(f"Nº {hit.property_number}")
    if not parts:
        return None
    return ", ".join(parts)


def overlay_enrich(
    db: Session,
    hit: ParcelHit,
    lat: float | None = None,
    lng: float | None = None,
) -> ParcelHit:
    layers = get_gis_layers(db)
    qlat = lat if lat is not None else hit.centroid_lat
    qlng = lng if lng is not None else hit.centroid_lng
    if qlat is None or qlng is None:
        return _enrich(db, hit)

    zone_cfg = layers.get("zone_homogeneous") or {}
    zone_fields = list(zone_cfg.get("value_fields") or ["zona"])
    if zone_cfg.get("identify_url"):
        zattrs = _identify_attrs(str(zone_cfg["identify_url"]), qlat, qlng, prefer_fields=zone_fields)
        raw = _attr(zattrs, *zone_fields)
        mapped = _map_zone_code(raw)
        if mapped:
            hit.zone_code = mapped

    road_cfg = layers.get("road_material") or {}
    road_fields = list(road_cfg.get("value_fields") or ["material"])
    if road_cfg.get("identify_url"):
        road_url = str(road_cfg["identify_url"])
        road_attrs = _identify_attrs(road_url, qlat, qlng, tolerance=22, prefer_fields=road_fields)
        if not road_attrs and hit.centroid_lat is not None and hit.centroid_lng is not None:
            road_attrs = _identify_attrs(
                road_url,
                hit.centroid_lat,
                hit.centroid_lng,
                tolerance=22,
                prefer_fields=road_fields,
            )
        raw = _attr(road_attrs, *road_fields)
        mapped_road = map_road_material_code(raw)
        if mapped_road:
            hit.road_material_code = mapped_road
        slope_via = _attr(road_attrs, "pendiente", "Pendiente")
        if slope_via:
            hit.slope_raw = slope_via or hit.slope_raw
            mapped_from_road = _map_topography_code(slope_via)
            if mapped_from_road:
                hit.topography_code = mapped_from_road

    topo_cfg = layers.get("topography") or {}
    topo_fields = list(topo_cfg.get("value_fields") or ["pendiente", "Pendiente"])
    if topo_cfg.get("identify_url"):
        tattrs = _identify_attrs(str(topo_cfg["identify_url"]), qlat, qlng, prefer_fields=topo_fields)
        raw = _attr(tattrs, *topo_fields)
        # Relieve GAMC es DEM (píxel/elevación): no sustituye la pendiente clasificada.
        mapped_topo = _map_topography_code(raw) if looks_like_slope_class(raw) else None
        if mapped_topo:
            hit.topography_code = mapped_topo
            hit.slope_raw = raw or hit.slope_raw

    if not hit.topography_code:
        hit.topography_code = _map_topography_code(hit.slope_raw)

    parcel_cfg = layers.get("parcels") or {}
    extra = {}
    if parcel_cfg.get("address_fields") and isinstance(hit.raw_attributes, dict):
        extra = {k: hit.raw_attributes.get(k) for k in parcel_cfg["address_fields"]}
    hit.address = compose_address(hit, extra)
    return _enrich(db, hit)


def resolve_parcel_map(
    *,
    cadastral_code: str | None = None,
    lat: float | None = None,
    lng: float | None = None,
) -> dict[str, Any]:
    """Geometría WGS84 del predio por código catastral o por punto.

    Si hay lat/lng, se prioriza el predio que contiene el pin (evita saltar al vecino
    cuando la búsqueda por código es ambigua).
    """
    hit_by_code: ParcelHit | None = None
    if cadastral_code:
        attrs, geom = _query_by_code(cadastral_code)
        if attrs:
            hit = _to_parcel(attrs, cadastral_code)
            if hit:
                _attach_geometry(hit, geom)
                hit_by_code = hit
                if (
                    hit.rings
                    and lat is not None
                    and lng is not None
                    and point_in_parcel_rings(lng, lat, hit.rings)
                ):
                    return parcel_map_meta(hit)
                if hit.rings and (lat is None or lng is None):
                    return parcel_map_meta(hit)
    if lat is not None and lng is not None:
        pad = 0.004
        params = {
            "geometry": f"{lng},{lat}",
            "geometryType": "esriGeometryPoint",
            "sr": 4326,
            "layers": "all:0",
            "tolerance": 3,
            "mapExtent": f"{lng - pad},{lat - pad},{lng + pad},{lat + pad}",
            "imageDisplay": "800,600,96",
            "returnGeometry": "true",
            "outSR": 4326,
            "f": "json",
        }
        try:
            with httpx.Client(timeout=20.0, follow_redirects=True, headers=GIS_HTTP_HEADERS) as client:
                resp = client.get(IDENTIFY_URL, params=params)
                resp.raise_for_status()
                payload = resp.json()
        except Exception:
            payload = {}
        point_hits: list[ParcelHit] = []
        for item in payload.get("results") or []:
            hit = _to_parcel(item.get("attributes") or {}, item.get("value"))
            if not hit:
                continue
            _attach_geometry(hit, item.get("geometry"))
            point_hits.append(hit)
        picked = pick_identify_candidate(point_hits, lat, lng)
        if picked and picked.rings:
            return parcel_map_meta(picked)
    if hit_by_code and hit_by_code.rings:
        return parcel_map_meta(hit_by_code)
    return {}


def infer_shape_code(rings: list[list[list[float]]] | None) -> str | None:
    """Clasifica forma del predio: SHAPE-REG / SHAPE-IRR / SHAPE-MIR según rectangularidad."""
    if not rings:
        return None
    pts = _ring_points(rings[0])
    if len(pts) < 3:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    # Área (shoelace) en coords geográficas; solo se usa como ratio, no como m².
    area = 0.0
    peri = 0.0
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        area += x1 * y2 - x2 * y1
        peri += ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
    area = abs(area) / 2.0
    if area <= 0 or peri <= 0:
        return None
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    bbox = max((max_x - min_x) * (max_y - min_y), 1e-18)
    rectangularity = area / bbox
    # Compactness isoperimétrica (círculo=1); predios rectangulares suelen ~0.6–0.8.
    compactness = (4.0 * 3.141592653589793 * area) / (peri * peri) if peri else 0.0
    if rectangularity >= 0.82 and n <= 6:
        return "SHAPE-REG"
    if rectangularity >= 0.55 or (compactness >= 0.45 and n <= 10):
        return "SHAPE-IRR"
    return "SHAPE-MIR"


def _enrich(db: Session, hit: ParcelHit) -> ParcelHit:
    if not hit.shape_code and hit.rings:
        hit.shape_code = infer_shape_code(hit.rings)
    if hit.zone_code:
        zone = _catalog_by_code(db, "zone_homogeneous", hit.zone_code)
        if zone:
            hit.zone_item_id = zone.id
            hit.zone_label = zone.label
    if hit.topography_code:
        topo = _catalog_by_code(db, "topography", hit.topography_code)
        if topo:
            hit.topography_item_id = topo.id
            hit.topography_label = topo.label
    if hit.road_material_code:
        road = _catalog_by_code(db, "road_material", hit.road_material_code)
        if road:
            hit.road_material_item_id = road.id
            hit.road_material_label = road.label
    if hit.shape_code:
        shape = _catalog_by_code(db, "parcel_shape", hit.shape_code)
        if shape:
            hit.shape_item_id = shape.id
            hit.shape_label = shape.label
    return hit


@router.get("/parcel-identify", response_model=IdentifyOut)
def parcel_identify(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Identifica el predio WMS/ArcGIS bajo el clic del mapa."""
    layers = get_gis_layers(db)
    identify_url = str((layers.get("parcels") or {}).get("identify_url") or IDENTIFY_URL)
    wms_url = str((layers.get("parcels") or {}).get("wms_url") or WMS_URL)
    pad = 0.004
    params = {
        "geometry": f"{lng},{lat}",
        "geometryType": "esriGeometryPoint",
        "sr": 4326,
        "layers": "all:0",
        "tolerance": 3,
        "mapExtent": f"{lng - pad},{lat - pad},{lng + pad},{lat + pad}",
        "imageDisplay": "800,600,96",
        "returnGeometry": "true",
        "outSR": 4326,
        "f": "json",
    }
    try:
        with httpx.Client(timeout=20.0, follow_redirects=True, headers=GIS_HTTP_HEADERS) as client:
            resp = client.get(identify_url, params=params)
            resp.raise_for_status()
            payload = resp.json()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"No se pudo consultar el servicio de predios: {exc}") from exc

    results = payload.get("results") or []
    candidates: list[ParcelHit] = []
    for item in results:
        attrs = item.get("attributes") or {}
        hit = _to_parcel(attrs, item.get("value"))
        if hit:
            _attach_geometry(hit, item.get("geometry"))
            candidates.append(hit)

    picked = pick_identify_candidate(candidates, lat, lng)
    if not picked:
        return IdentifyOut(found=False, wms_url=wms_url)

    parcel = overlay_enrich(db, picked, lat, lng)
    return IdentifyOut(found=True, parcel=parcel, candidates=[parcel], wms_url=wms_url)


@router.get("/parcel-by-code", response_model=IdentifyOut)
def parcel_by_code(
    code: str = Query(..., min_length=5, max_length=40),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Busca el predio en la capa ArcGIS/WMS por código catastral (subdistrito-manzana-predio)."""
    digits = normalize_cadastral_digits(code)
    if len("".join(ch for ch in digits if ch != "0")) < 3:
        raise HTTPException(400, "Indique al menos subdistrito, manzana y predio")
    layers = get_gis_layers(db)
    query_url = str((layers.get("parcels") or {}).get("query_url") or QUERY_URL)
    wms_url = str((layers.get("parcels") or {}).get("wms_url") or WMS_URL)
    attrs, geom = _query_by_code(digits, query_url)
    if not attrs:
        return IdentifyOut(found=False, wms_url=wms_url)
    hit = _to_parcel(attrs, digits)
    if not hit:
        return IdentifyOut(found=False, wms_url=wms_url)
    _attach_geometry(hit, geom)
    parcel = overlay_enrich(db, hit)
    return IdentifyOut(found=True, parcel=parcel, candidates=[parcel], wms_url=wms_url)
