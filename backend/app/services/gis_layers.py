from __future__ import annotations

from copy import deepcopy
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

DEFAULT_GIS_LAYERS: dict[str, dict[str, Any]] = {
    "satellite": {
        "code": "satellite",
        "name": "Imagen satelital",
        "visible": True,
        "layer_type": "xyz",
        "tile_url": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        "attribution": "Teselas © Esri — Source: Esri, Maxar, Earthstar Geographics",
        "max_zoom": 19,
        "z_index": 0,
    },
    "municipal_limits": {
        "code": "municipal_limits",
        "name": "Límites de Cercado",
        "visible": True,
        "layer_type": "wms",
        "wms_url": "https://gs.catastrocbba.com/arcgis/services/planificacion/limites_cba/MapServer/WMSServer",
        "wms_layer": "0",
        "min_zoom": 12,
        "z_index": 40,
        "color": "#FFD400",
        "constrain_map": True,
        "bounds": {
            "south": -17.53119,
            "west": -66.28070,
            "north": -17.25731,
            "east": -66.06952,
        },
    },
    "parcels": {
        "code": "parcels",
        "name": "Predios",
        "visible": True,
        "layer_type": "wms",
        "wms_url": "https://gs.catastrocbba.com/arcgis/services/catastro/predios_cba/MapServer/WMSServer",
        "identify_url": "https://gs.catastrocbba.com/arcgis/rest/services/catastro/predios_cba/MapServer/identify",
        "query_url": "https://gs.catastrocbba.com/arcgis/rest/services/catastro/predios_cba/MapServer/0/query",
        "wms_layer": "0",
        "min_zoom": 16,
        "z_index": 30,
        "address_fields": ["Calle", "Direccion", "Dirección", "Via", "Vía", "nombre_via"],
    },
    "zone_homogeneous": {
        "code": "zone_homogeneous",
        "name": "Zonas homogéneas",
        "visible": False,
        "layer_type": "wms",
        "wms_url": "https://gs.catastrocbba.com/arcgis/services/catastro/zonas_homogeneas/MapServer/WMSServer",
        "identify_url": "https://gs.catastrocbba.com/arcgis/rest/services/catastro/zonas_homogeneas/MapServer/identify",
        "wms_layer": "0",
        "z_index": 10,
        "catalog_type": "zone_homogeneous",
        "value_fields": ["zona", "descripcion", "ZTributari"],
    },
    "road_material": {
        "code": "road_material",
        "name": "Material de vía",
        "visible": False,
        "layer_type": "wms",
        "wms_url": "https://gs.catastrocbba.com/arcgis/services/coeficientes/materialVias/MapServer/WMSServer",
        "identify_url": "https://gs.catastrocbba.com/arcgis/rest/services/coeficientes/materialVias/MapServer/identify",
        "wms_layer": "0",
        "z_index": 20,
        "catalog_type": "road_material",
        "value_fields": ["material"],
    },
    "topography": {
        "code": "topography",
        "name": "Relieve topográfico",
        "visible": False,
        "layer_type": "wms",
        "wms_url": "https://gs.catastrocbba.com/arcgis/services/catastro/Relieve/MapServer/WMSServer",
        "identify_url": "https://gs.catastrocbba.com/arcgis/rest/services/catastro/Relieve/MapServer/identify",
        "wms_layer": "0",
        "z_index": 15,
        "catalog_type": "topography",
        "value_fields": ["pendiente", "Pendiente"],
    },
    "constructions": {
        "code": "constructions",
        "name": "Construcciones (solo impresión)",
        "visible": False,
        "print_only": True,
        "layer_type": "wms",
        "wms_url": "https://gs.catastrocbba.com/arcgis/services/catastro/construcciones/MapServer/WMSServer",
        "query_url": "https://gs.catastrocbba.com/arcgis/rest/services/catastro/construcciones/MapServer/0/query",
        "wms_layer": "0",
        "z_index": 35,
        "fill_color": "#4EB8D8",
        "outline_color": "#0078A8",
        "label_color": "#064660",
    },
}


def get_gis_layers(db: Session | None = None) -> dict[str, dict[str, Any]]:
    merged = deepcopy(DEFAULT_GIS_LAYERS)
    if db is None:
        return merged
    try:
        from app.services.admin_config_service import SystemParameter

        row = db.execute(select(SystemParameter).where(SystemParameter.key == "gis_layers")).scalar_one_or_none()
    except Exception:
        return merged
    raw = row.value_json if row else None
    if not isinstance(raw, dict):
        return merged
    for key, value in raw.items():
        if isinstance(value, dict):
            merged[key] = {**(merged.get(key) or {}), **value}
        else:
            merged[key] = value
    return merged


def visible_wms_layers(layers: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for item in layers.values():
        if not isinstance(item, dict):
            continue
        if item.get("print_only"):
            continue
        if item.get("visible") and item.get("wms_url"):
            out.append(item)
    return out
