from app.routers.gis import (
    cadastral_where_clauses,
    compose_address,
    map_road_material_code,
    normalize_cadastral_digits,
    pick_identify_candidate,
    point_in_parcel_rings,
    geometry_on_parcel,
    select_arcgis_feature,
    ParcelHit,
    _centroid_from_rings,
)
from app.routers.gis import _map_zone_code, _map_topography_code, looks_like_slope_class
from app.services.gis_layers import DEFAULT_GIS_LAYERS, get_gis_layers


def test_normalize_cadastral_digits_pads_to_seventeen():
    assert normalize_cadastral_digits("01-023-045") == "01023045000000000"
    assert len(normalize_cadastral_digits("1-23-45")) == 17


def test_cadastral_where_clauses_use_prefix():
    digits = normalize_cadastral_digits("01023045")
    clauses = cadastral_where_clauses(digits)
    assert f"CodCat='{digits}'" in clauses
    assert "CodCat LIKE '01023045%'" in clauses


def test_select_arcgis_feature_prefers_exact_code():
    digits = "01023045000000000"
    feats = [
        {"attributes": {"CodCat": "01023045999999999"}},
        {"attributes": {"CodCat": digits}},
    ]
    chosen = select_arcgis_feature(feats, digits)
    assert chosen is not None
    assert chosen["attributes"]["CodCat"] == digits


def test_select_arcgis_feature_single_prefix_match():
    feats = [{"attributes": {"CodCat": "01023045123000000"}}]
    chosen = select_arcgis_feature(feats, "01023045000000000")
    assert chosen is not None
    assert chosen["attributes"]["CodCat"].startswith("01023045")


def test_map_road_material_and_zone():
    assert map_road_material_code("Asfalto") == "IPV-ASF"
    assert map_road_material_code("Ripio") == "IPV-RIP"
    assert map_road_material_code("Tierra") == "IPV-TIE"
    assert _map_zone_code("11") == "ZH-11"
    assert _map_zone_code("zona 3") == "ZH-3"
    assert _map_topography_code("< 10°") == "IPRT-PLA"
    assert _map_topography_code("0-10º") == "IPRT-PLA"
    assert _map_topography_code("184") is None  # píxel DEM, no pendiente
    assert _map_topography_code("Valor de píxel 154") is None


def test_compose_address_from_commune():
    hit = ParcelHit(
        cadastral_code="07093001000000000",
        subdistrict="07",
        block_code="093",
        plot_code="001",
        commune="ADELA ZAMUDIO",
        subdistrict_name="NOROESTE",
    )
    addr = compose_address(hit)
    assert addr is not None
    assert "Adela Zamudio" in addr
    assert "Noroeste" in addr


def test_looks_like_slope_class():
    assert looks_like_slope_class("< 10°")
    assert looks_like_slope_class("0-10º")
    assert not looks_like_slope_class("184")
    assert not looks_like_slope_class("154")


def test_satellite_layer_is_basemap_below_parcels():
    sat = DEFAULT_GIS_LAYERS["satellite"]
    parcels = DEFAULT_GIS_LAYERS["parcels"]
    roads = DEFAULT_GIS_LAYERS["road_material"]
    assert sat["visible"] is True
    assert sat["layer_type"] == "xyz"
    assert "{z}" in sat["tile_url"]
    assert sat["z_index"] < roads["z_index"] < parcels["z_index"]
    merged = get_gis_layers(None)
    assert "satellite" in merged
    assert merged["satellite"]["tile_url"] == sat["tile_url"]


def test_municipal_limits_constrain_cercado():
    limits = DEFAULT_GIS_LAYERS["municipal_limits"]
    assert limits["visible"] is True
    assert limits["constrain_map"] is True
    assert "limites_cba" in limits["wms_url"]
    bounds = limits["bounds"]
    assert bounds["west"] < bounds["east"]
    assert bounds["south"] < bounds["north"]
    assert -17.4 < bounds["north"] < -17.2
    assert -66.3 < bounds["west"] < -66.2


def test_constructions_layer_is_print_only():
    cons = DEFAULT_GIS_LAYERS["constructions"]
    assert cons["visible"] is False
    assert cons["print_only"] is True
    assert cons["fill_color"] == "#4EB8D8"
    assert cons["outline_color"] == "#0078A8"
    assert "construcciones" in cons["wms_url"]
    assert cons["wms_layer"] == "0"
    from app.services.gis_layers import visible_wms_layers

    vis = visible_wms_layers(DEFAULT_GIS_LAYERS)
    assert all(item.get("code") != "constructions" for item in vis)


def _rect(west: float, south: float, east: float, north: float) -> list[list[float]]:
    return [
        [west, south],
        [east, south],
        [east, north],
        [west, north],
        [west, south],
    ]


def test_point_in_parcel_rings_and_centroid_inside():
    ring = _rect(-66.16, -17.40, -66.15, -17.39)
    assert point_in_parcel_rings(-66.155, -17.395, [ring])
    assert not point_in_parcel_rings(-66.155, -17.405, [ring])
    lat, lng = _centroid_from_rings([ring])
    assert lat is not None and lng is not None
    assert abs(lat - (-17.395)) < 1e-6
    assert abs(lng - (-66.155)) < 1e-6
    # Promedio de vértices tiraría al sur si hay más puntos en el lado inferior.
    dense_south = (
        [[-66.16, -17.40], [-66.158, -17.40], [-66.156, -17.40], [-66.154, -17.40], [-66.152, -17.40], [-66.15, -17.40]]
        + [[-66.15, -17.39], [-66.16, -17.39], [-66.16, -17.40]]
    )
    clat, clng = _centroid_from_rings([dense_south])
    assert clat is not None
    assert abs(clat - (-17.395)) < 0.001


def test_pick_identify_prefers_containing_smaller_parcel():
    north = ParcelHit(
        cadastral_code="N",
        subdistrict="01",
        block_code="001",
        plot_code="001",
        rings=[_rect(-66.16, -17.395, -66.15, -17.39)],
        area_m2=400,
    )
    south = ParcelHit(
        cadastral_code="S",
        subdistrict="01",
        block_code="001",
        plot_code="002",
        rings=[_rect(-66.16, -17.40, -66.15, -17.395)],
        area_m2=400,
    )
    # Clic en el predio norte: no debe devolver el del sur aunque venga primero.
    picked = pick_identify_candidate([south, north], lat=-17.3925, lng=-66.155)
    assert picked is not None
    assert picked.cadastral_code == "N"


def test_geometry_on_parcel_excludes_neighboring_buildings():
    parcel = [_rect(-66.16, -17.40, -66.15, -17.39)]
    own = [_rect(-66.158, -17.398, -66.152, -17.392)]
    neighbor = [_rect(-66.148, -17.398, -66.142, -17.392)]
    assert geometry_on_parcel(own, parcel) is True
    assert geometry_on_parcel(neighbor, parcel) is False
