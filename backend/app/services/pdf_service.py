from __future__ import annotations

import io
import math
from datetime import date
from pathlib import Path

import httpx
from PIL import Image, ImageDraw
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image as RLImage,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.services.media_service import UPLOAD_ROOT


NAVY = colors.HexColor("#00A7D6")
MUTED = colors.HexColor("#4A6B75")
LINE = colors.HexColor("#C5E4EE")
BRAND_LOGO = Path(__file__).resolve().parents[3] / "frontend" / "public" / "brand" / "cocha-cyan.png"


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "t", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=11, textColor=NAVY, alignment=1, spaceAfter=2
        ),
        "sub": ParagraphStyle(
            "s", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=9, alignment=1, spaceAfter=6
        ),
        "h": ParagraphStyle("h", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=9, textColor=NAVY, spaceBefore=6, spaceAfter=3),
        "n": ParagraphStyle("n", parent=base["Normal"], fontName="Helvetica", fontSize=8, leading=11),
        "sm": ParagraphStyle("sm", parent=base["Normal"], fontName="Helvetica", fontSize=7, leading=9, textColor=MUTED),
        "decl": ParagraphStyle("d", parent=base["Normal"], fontName="Helvetica", fontSize=7, leading=9, alignment=4),
    }


def _fetch_static_map(lat: float, lng: float, w: int = 420, h: int = 280) -> bytes | None:
    """Descarga mapa OSM estático centrado en el pin del predio."""
    urls = [
        f"https://staticmap.openstreetmap.de/staticmap.php?center={lat},{lng}&zoom=18&size={w}x{h}&maptype=mapnik&markers={lat},{lng},red-pushpin",
        f"https://maps.geoapify.com/v1/staticmap?style=osm-carto&width={w}&height={h}&center=lonlat:{lng},{lat}&zoom=17&marker=lonlat:{lng},{lat};color:%23ff0000;size:small",
    ]
    for url in urls:
        try:
            with httpx.Client(timeout=12.0, follow_redirects=True) as client:
                r = client.get(url, headers={"User-Agent": "NuevoAvaluoCatastro/1.0"})
                if r.status_code == 200 and r.content[:4] in (b"\x89PNG", b"\xff\xd8\xff", b"RIFF"):
                    return r.content
                if r.status_code == 200 and len(r.content) > 2000:
                    return r.content
        except Exception:
            continue
    return None


def _mercator_xy(lat: float, lng: float, zoom: int) -> tuple[float, float]:
    n = 2**zoom
    xt = (lng + 180.0) / 360.0 * n
    lat_rad = math.radians(lat)
    yt = (1.0 - math.log(math.tan(lat_rad) + (1 / math.cos(lat_rad))) / math.pi) / 2.0 * n
    return xt, yt


def _compose_tile_map(lat: float, lng: float, zoom: int = 17, size: int = 360) -> bytes:
    """Fallback: arma un mapa con teselas OSM + marcador (PIL)."""
    img, project = _compose_tile_canvas(lat, lng, zoom=zoom, width=size, height=size)
    draw = ImageDraw.Draw(img)
    mx, my = project(lat, lng)
    r = 7
    draw.ellipse((mx - r, my - r, mx + r, my + r), fill=(220, 38, 38), outline=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _compose_tile_canvas(
    lat: float, lng: float, zoom: int = 17, width: int = 420, height: int = 280
) -> tuple[Image.Image, object]:
    xt, yt = _mercator_xy(lat, lng, zoom)
    tile_size = 256
    cols = max(3, math.ceil(width / tile_size) + 2)
    rows = max(3, math.ceil(height / tile_size) + 2)
    cx = int(xt) - cols // 2
    cy = int(yt) - rows // 2
    canvas = Image.new("RGB", (tile_size * cols, tile_size * rows), (230, 235, 240))
    with httpx.Client(timeout=10.0, follow_redirects=True) as client:
        for dy in range(rows):
            for dx in range(cols):
                x, y = cx + dx, cy + dy
                url = f"https://tile.openstreetmap.org/{zoom}/{x}/{y}.png"
                try:
                    r = client.get(url, headers={"User-Agent": "NuevoAvaluoCatastro/1.0 (municipal)"})
                    if r.status_code == 200:
                        tile = Image.open(io.BytesIO(r.content)).convert("RGB")
                        canvas.paste(tile, (dx * tile_size, dy * tile_size))
                except Exception:
                    pass
    origin_px = (xt - cx) * tile_size
    origin_py = (yt - cy) * tile_size
    left = int(origin_px - width / 2)
    top = int(origin_py - height / 2)
    left = max(0, min(left, canvas.width - width))
    top = max(0, min(top, canvas.height - height))
    box = canvas.crop((left, top, left + width, top + height))

    def project(plat: float, plng: float) -> tuple[float, float]:
        pxt, pyt = _mercator_xy(plat, plng, zoom)
        return (pxt - cx) * tile_size - left, (pyt - cy) * tile_size - top

    return box, project


def _bbox_from_rings(rings: list, pad_ratio: float = 0.18) -> tuple[float, float, float, float] | None:
    xs: list[float] = []
    ys: list[float] = []
    for ring in rings or []:
        for pt in ring:
            if len(pt) >= 2:
                xs.append(float(pt[0]))
                ys.append(float(pt[1]))
    if not xs or not ys:
        return None
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    dx = max(maxx - minx, 0.00008)
    dy = max(maxy - miny, 0.00008)
    pad_x = dx * pad_ratio
    pad_y = dy * pad_ratio
    return minx - pad_x, miny - pad_y, maxx + pad_x, maxy + pad_y


def _location_view_bbox(
    rings: list,
    width: int,
    height: int,
    *,
    parcel_span: float = 0.32,
    min_view_m: float = 70.0,
) -> tuple[float, float, float, float] | None:
    """Recuadro WGS84 para el croquis de ubicación: predio al centro, manzana y calles alrededor."""
    xs: list[float] = []
    ys: list[float] = []
    for ring in rings or []:
        for pt in ring:
            if len(pt) >= 2:
                xs.append(float(pt[0]))
                ys.append(float(pt[1]))
    if not xs or not ys:
        return None
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    clat = (miny + maxy) / 2.0
    clng = (minx + maxx) / 2.0
    m_per_lng = 111320.0 * math.cos(math.radians(clat))
    m_per_lat = 110540.0
    pw = max((maxx - minx) * m_per_lng, 12.0)
    ph = max((maxy - miny) * m_per_lat, 12.0)
    span = max(parcel_span, 0.12)
    view_w = pw / span
    view_h = ph / span
    aspect = width / max(height, 1)
    if view_w / view_h < aspect:
        view_w = view_h * aspect
    else:
        view_h = view_w / aspect
    short = min(view_w, view_h)
    if short < min_view_m:
        scale = min_view_m / short
        view_w *= scale
        view_h *= scale
    half_lng = (view_w / 2.0) / max(m_per_lng, 1e-6)
    half_lat = (view_h / 2.0) / max(m_per_lat, 1e-6)
    return clng - half_lng, clat - half_lat, clng + half_lng, clat + half_lat


def _lnglat_to_px(lng: float, lat: float, bbox: tuple[float, float, float, float], w: int, h: int) -> tuple[float, float]:
    minx, miny, maxx, maxy = bbox
    x = (lng - minx) / max(maxx - minx, 1e-12) * w
    y = (maxy - lat) / max(maxy - miny, 1e-12) * h
    return x, y


def _fetch_wms_bbox(
    bbox: tuple[float, float, float, float],
    w: int,
    h: int,
    *,
    url: str,
    layer: str = "0",
) -> Image.Image | None:
    minx, miny, maxx, maxy = bbox
    params = {
        "SERVICE": "WMS",
        "VERSION": "1.1.1",
        "REQUEST": "GetMap",
        "LAYERS": layer,
        "STYLES": "",
        "FORMAT": "image/png",
        "TRANSPARENT": "TRUE",
        "SRS": "EPSG:4326",
        "BBOX": f"{minx},{miny},{maxx},{maxy}",
        "WIDTH": w,
        "HEIGHT": h,
    }
    try:
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            r = client.get(
                url,
                params=params,
                headers={"User-Agent": "NuevoAvaluoCatastro/1.0 (municipal)"},
            )
            if r.status_code == 200 and r.content[:8] == b"\x89PNG\r\n\x1a\n":
                return Image.open(io.BytesIO(r.content)).convert("RGBA")
    except Exception:
        return None
    return None


def _fetch_construction_features(bbox: tuple[float, float, float, float], query_url: str) -> list[dict]:
    """Polígonos de construcciones (WGS84) que intersectan el recuadro del croquis."""
    minx, miny, maxx, maxy = bbox
    params = {
        "f": "json",
        "geometry": f"{minx},{miny},{maxx},{maxy}",
        "geometryType": "esriGeometryEnvelope",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "bloque,pisos,identificador",
        "returnGeometry": "true",
        "outSR": "4326",
        "resultRecordCount": 80,
    }
    try:
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            r = client.get(
                query_url,
                params=params,
                headers={"User-Agent": "NuevoAvaluoCatastro/1.0 (municipal)"},
            )
            if r.status_code != 200:
                return []
            data = r.json()
    except Exception:
        return []
    out: list[dict] = []
    for feat in data.get("features") or []:
        geom = feat.get("geometry") or {}
        rings = []
        for ring in geom.get("rings") or []:
            pts = [[float(p[0]), float(p[1])] for p in ring if len(p) >= 2]
            if len(pts) >= 3:
                rings.append(pts)
        if not rings:
            continue
        attrs = feat.get("attributes") or {}
        out.append({"rings": rings, "bloque": attrs.get("bloque"), "pisos": attrs.get("pisos")})
    return out


def _centroid_px(rings: list, bbox: tuple[float, float, float, float], w: int, h: int) -> tuple[float, float] | None:
    xs: list[float] = []
    ys: list[float] = []
    for ring in rings:
        for lng, lat in ring:
            x, y = _lnglat_to_px(lng, lat, bbox, w, h)
            xs.append(x)
            ys.append(y)
    if not xs:
        return None
    return sum(xs) / len(xs), sum(ys) / len(ys)


def _croquis_font(size: int):
    from PIL import ImageFont

    for path in (
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _print_gis_layers() -> dict:
    try:
        from app.db import SessionLocal
        from app.services.gis_layers import get_gis_layers

        db = SessionLocal()
        try:
            return get_gis_layers(db)
        finally:
            db.close()
    except Exception:
        from app.services.gis_layers import DEFAULT_GIS_LAYERS

        return DEFAULT_GIS_LAYERS


def _hex_rgba(hex_color: str, alpha: int = 255) -> tuple[int, int, int, int]:
    raw = str(hex_color or "").replace("#", "").strip()
    if len(raw) == 3:
        raw = "".join(ch * 2 for ch in raw)
    if len(raw) < 6:
        return (78, 184, 216, alpha)
    try:
        n = int(raw[:6], 16)
    except ValueError:
        return (78, 184, 216, alpha)
    return ((n >> 16) & 255, (n >> 8) & 255, n & 255, max(0, min(255, alpha)))


def _draw_rings(draw: ImageDraw.ImageDraw, rings: list, bbox: tuple[float, float, float, float], w: int, h: int, fill, outline, width: int = 3) -> None:
    for ring in rings or []:
        pts = [_lnglat_to_px(float(p[0]), float(p[1]), bbox, w, h) for p in ring if len(p) >= 2]
        if len(pts) >= 3:
            draw.polygon(pts, fill=fill, outline=outline)
            if width > 1:
                draw.line(pts + [pts[0]], fill=outline, width=width)


def _hatch_polygon(base: Image.Image, pts: list[tuple[float, float]], color=(40, 55, 70, 200), spacing: int = 7) -> Image.Image:
    if len(pts) < 3:
        return base
    w, h = base.size
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).polygon(pts, fill=255)
    hatch = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    hd = ImageDraw.Draw(hatch)
    for i in range(-h, w + h, spacing):
        hd.line([(i, 0), (i + h, h)], fill=color, width=1)
    clipped = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    clipped.paste(hatch, mask=mask)
    out = base.convert("RGBA")
    return Image.alpha_composite(out, clipped)


def build_location_croquis(lat: float | None, lng: float | None, rings: list | None = None) -> bytes:
    c_lat, c_lng = lat, lng
    if (c_lat is None or c_lng is None) and rings:
        xs = [float(p[0]) for ring in rings for p in ring if len(p) >= 2]
        ys = [float(p[1]) for ring in rings for p in ring if len(p) >= 2]
        if xs and ys:
            c_lng = sum(xs) / len(xs)
            c_lat = sum(ys) / len(ys)
    if c_lat is None or c_lng is None:
        img = Image.new("RGB", (420, 280), (240, 244, 248))
        d = ImageDraw.Draw(img)
        d.rectangle((10, 10, 410, 270), outline=(120, 140, 160))
        d.text((120, 130), "Sin coordenadas de mapa", fill=(90, 100, 110))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    w, h = 840, 560
    bbox = _location_view_bbox(rings or [], w, h) if rings else None
    img: Image.Image | None = None
    if bbox:
        layers = _print_gis_layers()
        parcels = layers.get("parcels") or {}
        img = Image.new("RGBA", (w, h), (255, 255, 255, 255))
        parcels_wms = _fetch_wms_bbox(
            bbox,
            w,
            h,
            url=str(parcels.get("wms_url") or "https://gs.catastrocbba.com/arcgis/services/catastro/predios_cba/MapServer/WMSServer"),
            layer=str(parcels.get("wms_layer") or "0"),
        )
        if parcels_wms:
            img = Image.alpha_composite(img, parcels_wms)
        draw = ImageDraw.Draw(img, "RGBA")
        for ring in rings or []:
            pts = [_lnglat_to_px(float(p[0]), float(p[1]), bbox, w, h) for p in ring if len(p) >= 2]
            if len(pts) < 3:
                continue
            draw.polygon(pts, fill=(180, 228, 247, 70))
            img = _hatch_polygon(img, pts, color=(35, 45, 55, 210), spacing=8)
            draw = ImageDraw.Draw(img, "RGBA")
            draw.line(pts + [pts[0]], fill=(20, 20, 20, 255), width=4)
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="PNG")
        return buf.getvalue()

    try:
        img, project = _compose_tile_canvas(c_lat, c_lng, zoom=19, width=w, height=h)
    except Exception:
        img = Image.new("RGB", (w, h), (232, 247, 251))

        def project(plat: float, plng: float) -> tuple[float, float]:
            return w / 2, h / 2

    if rings:
        img = img.convert("RGBA")
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        for ring in rings:
            pts = [project(float(p[1]), float(p[0])) for p in ring if len(p) >= 2]
            if len(pts) >= 3:
                od.polygon(pts, fill=(0, 167, 214, 80), outline=(20, 20, 20, 255))
                od.line(pts + [pts[0]], fill=(20, 20, 20, 255), width=4)
        img = Image.alpha_composite(img, overlay).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def build_parcel_croquis(
    front: float,
    depth: float,
    area: float,
    cadastral: str | None,
    rings: list | None = None,
) -> bytes:
    canvas_w, canvas_h = 840, 560
    if rings:
        bbox = _bbox_from_rings(rings, pad_ratio=0.22)
        if bbox:
            img = Image.new("RGBA", (canvas_w, canvas_h), (255, 255, 255, 255))
            layers = _print_gis_layers()
            parcels = layers.get("parcels") or {}
            constructions = layers.get("constructions") or {}
            parcels_wms = _fetch_wms_bbox(
                bbox,
                canvas_w,
                canvas_h,
                url=str(parcels.get("wms_url") or "https://gs.catastrocbba.com/arcgis/services/catastro/predios_cba/MapServer/WMSServer"),
                layer=str(parcels.get("wms_layer") or "0"),
            )
            if parcels_wms:
                img = Image.alpha_composite(img, parcels_wms)
            draw = ImageDraw.Draw(img, "RGBA")
            _draw_rings(
                draw,
                rings,
                bbox,
                canvas_w,
                canvas_h,
                fill=(180, 228, 247, 210),
                outline=(0, 167, 214, 255),
                width=3,
            )
            query_url = str(
                constructions.get("query_url")
                or "https://gs.catastrocbba.com/arcgis/rest/services/catastro/construcciones/MapServer/0/query"
            )
            from app.routers.gis import geometry_on_parcel

            buildings = [
                bld
                for bld in _fetch_construction_features(bbox, query_url)
                if geometry_on_parcel(bld.get("rings") or [], rings)
            ]
            font = _croquis_font(15)
            font_sm = _croquis_font(13)
            bld_fill = _hex_rgba(str(constructions.get("fill_color") or "#4EB8D8"), 230)
            bld_outline = _hex_rgba(str(constructions.get("outline_color") or "#0078A8"), 255)
            bld_label = _hex_rgba(str(constructions.get("label_color") or "#064660"), 255)[:3]
            for bld in buildings:
                _draw_rings(
                    draw,
                    bld["rings"],
                    bbox,
                    canvas_w,
                    canvas_h,
                    fill=bld_fill,
                    outline=bld_outline,
                    width=3,
                )
                center = _centroid_px(bld["rings"], bbox, canvas_w, canvas_h)
                if not center:
                    continue
                cx, cy = center
                bloque = str(bld.get("bloque") or "").strip()
                pisos = bld.get("pisos")
                if bloque:
                    draw.text((cx - 28, cy - 16), f"BLOQUE {bloque}", fill=bld_label, font=font)
                if pisos not in (None, "", 0):
                    draw.text((cx - 32, cy + 2), f"{int(pisos)} PLANTAS", fill=bld_label, font=font_sm)
            label = cadastral or "Predio"
            draw.rectangle((8, 8, 8 + min(len(label) * 7 + 16, 260), 48 if area else 30), fill=(255, 255, 255, 210))
            draw.text((14, 12), label[:28], fill=(0, 167, 214))
            if area:
                draw.text((14, 28), f"Sup. {area:.2f} m2", fill=(90, 100, 110))
            draw.polygon([(canvas_w - 30, 24), (canvas_w - 22, 40), (canvas_w - 38, 40)], fill=(0, 167, 214))
            draw.text((canvas_w - 38, 44), "N", fill=(0, 167, 214))
            buf = io.BytesIO()
            img.convert("RGB").save(buf, format="PNG")
            return buf.getvalue()
    w = front if front > 0 else 12.0
    h = depth if depth > 0 else (area / w if area > 0 and w > 0 else 18.0)
    img = Image.new("RGB", (canvas_w, canvas_h), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, canvas_w - 1, canvas_h - 1), outline=(180, 190, 200))
    margin = 36
    scale = min((canvas_w - 2 * margin) / max(w, 0.1), (canvas_h - 2 * margin) / max(h, 0.1))
    rw, rh = w * scale, h * scale
    x0 = (canvas_w - rw) / 2
    y0 = (canvas_h - rh) / 2
    d.rectangle((x0, y0, x0 + rw, y0 + rh), outline=(0, 167, 214), width=3, fill=(232, 247, 251))
    d.line((x0, y0 + rh + 12, x0 + rw, y0 + rh + 12), fill=(0, 167, 214))
    d.text((x0 + rw / 2 - 20, y0 + rh + 14), f"Frente {w:.2f} m", fill=(0, 167, 214))
    d.line((x0 - 12, y0, x0 - 12, y0 + rh), fill=(0, 167, 214))
    d.text((8, y0 + rh / 2 - 6), f"{h:.2f} m", fill=(0, 167, 214))
    label = cadastral or "Predio"
    d.text((x0 + 8, y0 + 8), label[:28], fill=(0, 167, 214))
    if area:
        d.text((x0 + 8, y0 + 26), f"Sup. {area:.2f} m2", fill=(90, 100, 110))
    d.polygon([(canvas_w - 30, 24), (canvas_w - 22, 40), (canvas_w - 38, 40)], fill=(0, 167, 214))
    d.text((canvas_w - 38, 44), "N", fill=(0, 167, 214))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def image_bytes_to_png(raw: bytes, max_edge: int = 1600) -> bytes:
    """Normaliza cualquier imagen (incl. WebP) a PNG acotado para Word/PDF."""
    img = Image.open(io.BytesIO(raw))
    img.load()
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")
    elif img.mode == "RGBA":
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[-1])
        img = background
    w, h = img.size
    if max(w, h) > max_edge and max(w, h) > 0:
        img.thumbnail((max_edge, max_edge))
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def image_file_to_png(path: Path, max_edge: int = 1600) -> bytes:
    return image_bytes_to_png(path.read_bytes(), max_edge=max_edge)


def _rl_image(png_bytes: bytes, width: float, height: float) -> RLImage:
    return RLImage(io.BytesIO(png_bytes), width=width, height=height, kind="proportional")


def _watermark(canvas, doc, text: str):
    canvas.saveState()
    canvas.setFont("Helvetica-Bold", 28)
    canvas.setFillColor(colors.Color(0.7, 0.1, 0.1, alpha=0.18))
    canvas.translate(letter[0] / 2, letter[1] / 2)
    canvas.rotate(32)
    canvas.drawCentredString(0, 0, text)
    canvas.restoreState()


def generate_appraisal_pdf(data: dict, photo_paths: list[tuple[str, Path]] | None = None) -> bytes:
    """Genera PDF tipo legacy: Formulario para actualización de datos técnicos."""
    styles = _styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
        title=f"Formulario {data.get('form_number') or ''}",
    )

    story = []
    if BRAND_LOGO.exists():
        story.append(RLImage(str(BRAND_LOGO), width=22 * mm, height=24 * mm, kind="proportional"))
        story.append(Spacer(1, 3))
    story.append(Paragraph("GOBIERNO AUTÓNOMO MUNICIPAL DE COCHABAMBA", styles["title"]))
    story.append(Paragraph("Cocha es progreso", styles["sm"]))
    story.append(Paragraph("FORMULARIO PARA ACTUALIZACIÓN DE DATOS TÉCNICOS", styles["sub"]))
    story.append(Paragraph("DECLARACIÓN JURADA", styles["sub"]))

    meta = [
        [
            Paragraph(f"<b>Código catastral:</b> {data.get('cadastral_code') or '—'}", styles["n"]),
            Paragraph(f"<b>Formulario N°:</b> {data.get('form_number') or '—'}", styles["n"]),
        ],
        [
            Paragraph(f"<b>Fecha:</b> {date.today().strftime('%d/%m/%Y')}", styles["n"]),
            Paragraph(f"<b>Estado:</b> {data.get('status_name') or '—'}", styles["n"]),
        ],
    ]
    story.append(Table(meta, colWidths=[95 * mm, 95 * mm]))
    story.append(Spacer(1, 4))

    story.append(Paragraph("1.- Información del propietario", styles["h"]))
    story.append(
        Paragraph(
            f"{data.get('owner_name') or '—'} &nbsp;&nbsp; <b>C.I./NIT:</b> {data.get('owner_document') or '—'} "
            f"&nbsp;&nbsp; <b>Tel:</b> {data.get('owner_phone') or '—'}",
            styles["n"],
        )
    )

    story.append(Paragraph("2.- Información legal", styles["h"]))
    story.append(
        Paragraph(
            f"<b>Matrícula:</b> {data.get('registry_matricula') or '—'} &nbsp; "
            f"<b>Asiento:</b> {data.get('registry_asiento') or '—'} &nbsp; "
            f"<b>Fecha DDRR:</b> {data.get('registry_ddr_date') or '—'} &nbsp; "
            f"<b>Escritura:</b> {data.get('deed_number') or '—'} &nbsp; "
            f"<b>Notario:</b> {data.get('notary_name') or '—'}",
            styles["n"],
        )
    )

    # Croquis
    story.append(Paragraph("Croquis del predio / Croquis de ubicación", styles["h"]))
    rings = (data.get("map_meta") or {}).get("rings") or []
    parcel_png = build_parcel_croquis(
        float(data.get("front_length") or 0),
        float(data.get("depth_length") or 0),
        float(data.get("approved_area") or 0),
        data.get("cadastral_code"),
        rings=rings,
    )
    loc_png = build_location_croquis(data.get("latitude"), data.get("longitude"), rings=rings)
    croquis = Table(
        [
            [
                Paragraph("<b>Croquis del predio</b>", styles["sm"]),
                Paragraph("<b>Croquis de ubicación (mapa)</b>", styles["sm"]),
            ],
            [_rl_image(parcel_png, 88 * mm, 58 * mm), _rl_image(loc_png, 88 * mm, 58 * mm)],
        ],
        colWidths=[95 * mm, 95 * mm],
    )
    croquis.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOX", (0, 1), (0, 1), 0.5, LINE), ("BOX", (1, 1), (1, 1), 0.5, LINE)]))
    story.append(croquis)

    # Fotos (si hay). Se convierten a PNG con tamaño fijo para evitar celdas enormes (WebP).
    if photo_paths:
        story.append(Paragraph("Fotografías del predio", styles["h"]))
        cells: list = []
        row: list = []
        for name, path in photo_paths[:8]:
            try:
                png = image_file_to_png(path)
                inner = Table(
                    [
                        [Paragraph(name, styles["sm"])],
                        [_rl_image(png, 42 * mm, 32 * mm)],
                    ],
                    colWidths=[90 * mm],
                )
            except Exception:
                continue
            row.append(inner)
            if len(row) == 2:
                cells.append(row)
                row = []
        if row:
            while len(row) < 2:
                row.append(Paragraph("", styles["sm"]))
            cells.append(row)
        if cells:
            tphotos = Table(cells, colWidths=[95 * mm, 95 * mm])
            tphotos.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
            story.append(tphotos)

    story.append(Paragraph("3.- Descripción del predio", styles["h"]))
    story.append(
        Paragraph(
            f"<b>Calle:</b> {data.get('address') or '—'} &nbsp; <b>N°:</b> {data.get('door_number') or '—'}<br/>"
            f"<b>Ltd.:</b> {data.get('latitude') if data.get('latitude') is not None else '—'}, "
            f"<b>Lgt.:</b> {data.get('longitude') if data.get('longitude') is not None else '—'}<br/>"
            f"<b>Frente:</b> {data.get('front_length') or 0:.2f} m &nbsp; "
            f"<b>Fondo:</b> {data.get('depth_length') or 0:.2f} m &nbsp; "
            f"<b>Superficie lote:</b> {data.get('approved_area') or 0:.2f} m²<br/>"
            f"<b>Ubicación:</b> {data.get('location_label') or '—'} &nbsp; "
            f"<b>Zona homogénea:</b> {data.get('zone_label') or '—'} ({data.get('zone_m2') or 0:.2f} Bs/m²)<br/>"
            f"<b>Material vía:</b> {data.get('road_label') or '—'} &nbsp; "
            f"<b>Topografía:</b> {data.get('topo_label') or '—'} &nbsp; "
            f"<b>Forma:</b> {data.get('shape_label') or '—'}<br/>"
            f"<b>Servicios:</b> {', '.join(data.get('services') or []) or '—'}",
            styles["n"],
        )
    )

    # Valores calculados
    coef = data.get("coefficients") or {}
    story.append(Paragraph("4.- Valores calculados (parametrizados)", styles["h"]))
    story.append(
        Paragraph(
            f"<b>Valor terreno:</b> {data.get('land_value') or 0:,.2f} Bs &nbsp; "
            f"(sup × zona × topo {coef.get('topo', 1)} × forma {coef.get('shape', 1)} × "
            f"ubic. {coef.get('location', 1)} × vía {coef.get('road', 1)} × (1+serv {coef.get('services_sum', 0)}))<br/>"
            f"<b>Valor bloques:</b> {data.get('blocks_value') or 0:,.2f} Bs &nbsp; "
            f"<b>Valor mejoras:</b> {data.get('improvements_value') or 0:,.2f} Bs &nbsp; "
            f"<b>TOTAL:</b> {data.get('total_value') or 0:,.2f} Bs",
            styles["n"],
        )
    )

    story.append(Paragraph("5.- Características de la(s) construcciones", styles["h"]))
    rows = [["Nro", "Año", "Bloque", "Sup. m²", "Pisos", "Tipología", "Puntaje", "Valor Bs"]]
    for b in data.get("blocks") or []:
        typ = (b.get("typology") or {}).get("label") or ("Mejora" if b.get("unit_kind") == "improvement" else "—")
        rows.append(
            [
                str(b.get("unit_number") or ""),
                str(b.get("construction_year") or ""),
                "Mejora" if b.get("unit_kind") == "improvement" else "Bloque",
                f"{b.get('area') or 0:.2f}",
                str(b.get("floors_count") or ""),
                typ or "—",
                f"{b.get('total_score') or 0:.2f}",
                f"{b.get('unit_value') or 0:,.2f}",
            ]
        )
    if len(rows) == 1:
        rows.append(["—", "—", "—", "—", "—", "—", "—", "—"])
    t = Table(rows, colWidths=[12 * mm, 14 * mm, 22 * mm, 18 * mm, 14 * mm, 32 * mm, 20 * mm, 28 * mm])
    t.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8f1fb")),
                ("GRID", (0, 0), (-1, -1), 0.4, LINE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.append(t)

    # Detalle ponderados por bloque (página / sección)
    for b in data.get("blocks") or []:
        story.append(Spacer(1, 6))
        title = f"Característica {('Mejora' if b.get('unit_kind')=='improvement' else 'Bloque')} {b.get('unit_number')}"
        if b.get("typology"):
            title += f" — Tipología: {b['typology'].get('label')} (mín. {b['typology'].get('puntaje_min')}) · Valor m² {b['typology'].get('valor_m2')}"
        story.append(Paragraph(title, styles["h"]))
        crow = [["#", "Característica", "Subtipo", "Puntaje base", "%", "Ponderado"]]
        for i, c in enumerate(sorted(b.get("characteristics") or [], key=lambda x: x.get("group_sort", 0)), start=1):
            crow.append(
                [
                    str(i),
                    c.get("group_name") or "",
                    c.get("option_label") or "",
                    f"{c.get('base_score') or 0:.2f}",
                    f"{c.get('percentage') or 0:.0f}",
                    f"{c.get('score') or 0:.2f}",
                ]
            )
        if len(crow) == 1:
            crow.append(["—", "Sin características", "—", "—", "—", "—"])
        ct = Table(crow, colWidths=[8 * mm, 45 * mm, 55 * mm, 22 * mm, 14 * mm, 22 * mm])
        ct.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 7),
                    ("GRID", (0, 0), (-1, -1), 0.35, LINE),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                ]
            )
        )
        story.append(ct)
        story.append(
            Paragraph(
                f"<b>Puntaje total:</b> {b.get('total_score') or 0:.2f} &nbsp; "
                f"(suma de ponderados = puntaje_base × porcentaje / 100)",
                styles["sm"],
            )
        )

    story.append(Paragraph("6.- Observaciones", styles["h"]))
    story.append(Paragraph(data.get("observations") or "—", styles["n"]))

    story.append(Spacer(1, 8))
    story.append(
        Paragraph(
            "En mi calidad de sujeto pasivo y/o tercero responsable, declaro que la información "
            "proporcionada en la determinación del IPBI, fiel y exactamente refleja la verdad, por lo que "
            "juro a la exactitud de la presente declaración (Art.78,I, Ley 2492).",
            styles["decl"],
        )
    )
    story.append(Spacer(1, 14))
    signs = Table(
        [
            [
                Paragraph("_______________________<br/>Firma del propietario<br/>" + (data.get("owner_name") or ""), styles["sm"]),
                Paragraph("_______________________<br/>Firma del profesional", styles["sm"]),
            ]
        ],
        colWidths=[95 * mm, 95 * mm],
    )
    story.append(signs)

    migrated = bool(data.get("migrated"))

    def on_page(canvas, doc_):
        if migrated:
            _watermark(canvas, doc_, "Formulario aprobado y Migrado")
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(MUTED)
        canvas.drawRightString(letter[0] - 12 * mm, 8 * mm, f"Página {doc_.page}")

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    return buf.getvalue()
