from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Appraisal,
    CatalogItem,
    CatalogType,
    CharacteristicGroup,
    CharacteristicOption,
    ConstructionUnit,
    Property,
    PropertyDetail,
)
from app.services.formula_engine import FormulaError, eval_expression


def _dec(v) -> Decimal:
    if v is None:
        return Decimal("0")
    return Decimal(str(v))


def _coef(item: CatalogItem | None, key: str = "coeficiente") -> Decimal:
    if not item:
        return Decimal("1")
    attrs = item.attributes_json or {}
    if key in attrs:
        return _dec(attrs[key])
    if item.numeric_value is not None:
        return _dec(item.numeric_value)
    return Decimal("1")


def _label(item: CatalogItem | None) -> str:
    return item.label if item else "—"


def _item(db: Session, item_id: UUID | None) -> CatalogItem | None:
    if not item_id:
        return None
    return db.get(CatalogItem, item_id)


def _param_number(db: Session, key: str, default: Decimal) -> Decimal:
    from sqlalchemy import text

    row = db.execute(
        text("SELECT value_json FROM config.system_parameters WHERE key = :k"),
        {"k": key},
    ).scalar()
    if row is None:
        return default
    try:
        return _dec(row)
    except Exception:
        return default


def load_active_formula(db: Session, code: str) -> tuple[str | None, dict]:
    from sqlalchemy import text

    row = db.execute(
        text(
            """
            SELECT fv.expression, fv.variables_json
            FROM config.formula_versions fv
            JOIN config.formula_definitions fd ON fd.id = fv.formula_id
            WHERE fd.code = :code AND fd.is_active AND fv.is_active
            ORDER BY fv.version DESC
            LIMIT 1
            """
        ),
        {"code": code},
    ).first()
    if not row:
        return None, {}
    return row[0], (row[1] or {})


def eval_formula(db: Session, code: str, variables: dict, fallback: str) -> Decimal:
    expression, _meta = load_active_formula(db, code)
    expr = expression or fallback
    try:
        return eval_expression(expr, variables).quantize(Decimal("0.01"))
    except FormulaError:
        return eval_expression(fallback, variables).quantize(Decimal("0.01"))


def typology_for_score(db: Session, score: Decimal) -> dict:
    rows = db.execute(
        select(CatalogItem)
        .join(CatalogType, CatalogType.id == CatalogItem.catalog_type_id)
        .where(CatalogType.code == "construction_typology", CatalogItem.is_active.is_(True))
    ).scalars().all()
    scored = []
    for r in rows:
        attrs = r.attributes_json or {}
        vmin = _dec(attrs.get("puntaje_min", r.numeric_value or 0))
        scored.append((vmin, r))
    scored.sort(key=lambda x: x[0], reverse=True)
    chosen = None
    for vmin, r in scored:
        if score >= vmin:
            chosen = r
            break
    if not chosen and scored:
        chosen = sorted(scored, key=lambda x: x[0])[0][1]
    if not chosen:
        return {"code": None, "label": "—", "valor_m2": 0.0, "valor_m2_ph": 0.0, "puntaje_min": 0}
    attrs = chosen.attributes_json or {}
    return {
        "code": chosen.code,
        "label": chosen.label,
        "valor_m2": float(_dec(attrs.get("valor_m2", chosen.numeric_value or 0))),
        "valor_m2_ph": float(_dec(attrs.get("valor_m2_ph", 0))),
        "puntaje_min": int(attrs.get("puntaje_min", 0) or 0),
    }


def _improvement_m2_and_typ(db: Session, unit: ConstructionUnit) -> tuple[Decimal, dict | None]:
    """Valor m² de una mejora: tipo explícito, tipología de mejora o, si no hay, la misma que bloques."""
    if unit.improvement_type_item_id:
        it = _item(db, unit.improvement_type_item_id)
        if it:
            attrs = it.attributes_json or {}
            valor = Decimal("0")
            if "valor_m2" in attrs:
                valor = _dec(attrs["valor_m2"])
            elif it.numeric_value is not None:
                valor = _dec(it.numeric_value)
            if valor > 0:
                return valor, {
                    "code": it.code,
                    "label": it.label,
                    "valor_m2": float(valor),
                    "valor_m2_ph": 0.0,
                    "puntaje_min": 0,
                }
    rows = db.execute(
        select(CatalogItem)
        .join(CatalogType, CatalogType.id == CatalogItem.catalog_type_id)
        .where(CatalogType.code == "improvement_typology", CatalogItem.is_active.is_(True))
        .order_by(CatalogItem.sort_order)
    ).scalars().all()
    total = _dec(unit.total_score)
    scored: list[tuple[Decimal, CatalogItem]] = []
    for r in rows:
        attrs = r.attributes_json or {}
        scored.append((_dec(attrs.get("puntaje", 0)), r))
    scored.sort(key=lambda x: x[0], reverse=True)
    for vmin, r in scored:
        if total >= vmin:
            attrs = r.attributes_json or {}
            valor = _dec(attrs.get("valor_m2", r.numeric_value or 0))
            if valor > 0:
                return valor, {
                    "code": r.code,
                    "label": r.label,
                    "valor_m2": float(valor),
                    "valor_m2_ph": 0.0,
                    "puntaje_min": int(vmin),
                }
    # Mismas 13 características que el bloque → misma tabla de tipología constructiva
    typ = typology_for_score(db, total)
    return Decimal(str(typ.get("valor_m2") or 0)), typ


def compute_appraisal_valuation(db: Session, appraisal: Appraisal) -> dict:
    prop = appraisal.property
    detail = prop.detail if prop else None
    owner = prop.owners[0] if prop and prop.owners else None

    zone = _item(db, detail.zone_item_id if detail else None)
    iprt_item = _item(db, detail.topography_item_id if detail else None)
    shape = _item(db, detail.shape_item_id if detail else None)
    location = _item(db, detail.location_item_id if detail else None)
    ipv_item = _item(db, detail.road_material_item_id if detail else None)

    area = _dec(detail.approved_area if detail else 0)
    zone_m2 = _dec((zone.attributes_json or {}).get("valor_catastral_m2", zone.numeric_value if zone else 0))

    ipiu_base = _param_number(db, "ipiu_base", Decimal("1"))
    ipes_base = _param_number(db, "ipes_base", Decimal("1"))

    ipiu_sum = Decimal("0")
    ipiu_labels: list[str] = []
    if detail:
        for s in detail.services:
            it = _item(db, s.service_item_id)
            if it:
                ipiu_sum += _coef(it)
                ipiu_labels.append(it.label)
    ipiu = ipiu_base + ipiu_sum

    ipes_sum = Decimal("0")
    ipes_labels: list[str] = []
    if detail:
        for e in getattr(detail, "equipments", []) or []:
            it = _item(db, e.equipment_item_id)
            if it:
                ipes_sum += _coef(it)
                ipes_labels.append(it.label)
    ipes = ipes_base + ipes_sum

    iprt = _coef(iprt_item)
    ipv = _coef(ipv_item)
    location_coef = _coef(location)
    shape_coef = _coef(shape)

    land_vars = {
        "approved_area": area,
        "zone_m2": zone_m2,
        "ipiu": ipiu,
        "ipes": ipes,
        "iprt": iprt,
        "ipv": ipv,
        "location_coef": location_coef,
        "shape_coef": shape_coef,
        "vb": zone_m2,
    }
    land_value = eval_formula(
        db,
        "land_value",
        land_vars,
        "approved_area * zone_m2 * ipiu * ipes * iprt * ipv * location_coef * shape_coef",
    )
    vsz = (zone_m2 * ipiu * ipes * iprt).quantize(Decimal("0.0001"))
    vsvia = (vsz * ipv).quantize(Decimal("0.0001"))

    groups = {
        g.id: g
        for g in db.execute(select(CharacteristicGroup).order_by(CharacteristicGroup.sort_order)).scalars().all()
    }

    blocks_out = []
    blocks_value = Decimal("0")
    improvements_value = Decimal("0")

    units = [u for u in (prop.units if prop else []) if u.status == "active"]
    for u in units:
        total = _dec(u.total_score)
        if not total and u.characteristic_values:
            total = sum((_dec(cv.score) for cv in u.characteristic_values), Decimal("0"))

        use_coef = _coef(_item(db, u.use_coeff_item_id))
        dep_item = _item(db, u.depreciation_item_id)
        unit_area = _dec(u.area)

        chars = []
        for cv in sorted(u.characteristic_values, key=lambda x: x.sort_order):
            g = groups.get(cv.characteristic_group_id)
            opt = db.get(CharacteristicOption, cv.characteristic_option_id)
            chars.append(
                {
                    "group_id": str(cv.characteristic_group_id),
                    "group_code": g.code if g else "",
                    "group_name": g.name if g else "",
                    "group_sort": g.sort_order if g else 0,
                    "option_label": opt.label if opt else "",
                    "base_score": float(_dec(opt.base_score if opt else 0)),
                    "percentage": float(_dec(cv.percentage)),
                    "score": float(_dec(cv.score)),
                }
            )

        if u.unit_kind == "improvement":
            valor_m2, typ = _improvement_m2_and_typ(db, u)
            dep_coef = _coef(dep_item, "coeficiente_mejora") if dep_item else _coef(dep_item)
            unit_value = eval_formula(
                db,
                "improvement_value",
                {"area": unit_area, "valor_m2": valor_m2, "dep_coef": dep_coef},
                "area * valor_m2 * dep_coef",
            )
            improvements_value += unit_value
        else:
            typ = typology_for_score(db, total)
            valor_m2 = Decimal(str((typ or {}).get("valor_m2") or 0))
            dep_coef = _coef(dep_item, "coeficiente_bloque") if dep_item else _coef(dep_item)
            unit_value = eval_formula(
                db,
                "block_value",
                {"area": unit_area, "valor_m2": valor_m2, "use_coef": use_coef, "dep_coef": dep_coef},
                "area * valor_m2 * use_coef * dep_coef",
            )
            blocks_value += unit_value

        u.total_score = total
        u.unit_value = unit_value
        if typ and typ.get("code"):
            typ_row = db.execute(
                select(CatalogItem)
                .join(CatalogType, CatalogType.id == CatalogItem.catalog_type_id)
                .where(CatalogType.code == "construction_typology", CatalogItem.code == typ["code"])
            ).scalars().first()
            if typ_row:
                u.typology_item_id = typ_row.id

        blocks_out.append(
            {
                "id": str(u.id),
                "unit_kind": u.unit_kind,
                "unit_number": u.unit_number,
                "area": float(unit_area),
                "floors_count": u.floors_count,
                "construction_year": u.construction_year,
                "modification_year": u.modification_year,
                "total_score": float(total),
                "typology": typ,
                "use_coef": float(use_coef),
                "dep_coef": float(dep_coef),
                "valor_m2": float(valor_m2),
                "unit_value": float(unit_value),
                "observations": u.observations,
                "characteristics": chars,
            }
        )

    total_value = eval_formula(
        db,
        "appraisal_total",
        {
            "land_value": land_value,
            "blocks_value": blocks_value,
            "improvements_value": improvements_value,
        },
        "land_value + blocks_value + improvements_value",
    )

    snapshot = {
        "land_value": float(land_value),
        "blocks_value": float(blocks_value),
        "improvements_value": float(improvements_value),
        "total_value": float(total_value),
        "zone_m2": float(zone_m2),
        "area": float(area),
        "vsz": float(vsz),
        "vsvia": float(vsvia),
        "indices": {
            "ipiu": float(ipiu),
            "ipes": float(ipes),
            "iprt": float(iprt),
            "ipv": float(ipv),
            "ipiu_base": float(ipiu_base),
            "ipes_base": float(ipes_base),
            "ipiu_sum": float(ipiu_sum),
            "ipes_sum": float(ipes_sum),
            "location_coef": float(location_coef),
            "shape_coef": float(shape_coef),
        },
        "coefficients": {
            "topo": float(iprt),
            "shape": float(shape_coef),
            "location": float(location_coef),
            "road": float(ipv),
            "services_sum": float(ipiu_sum),
        },
        "blocks": blocks_out,
    }
    appraisal.land_value = land_value
    appraisal.blocks_value = blocks_value
    appraisal.improvements_value = improvements_value
    appraisal.total_value = total_value
    appraisal.land_area = area
    appraisal.valuation_snapshot = snapshot

    from app.routers.gis import resolve_parcel_map

    map_meta = dict(prop.map_meta_json or {}) if prop else {}
    if not map_meta.get("rings"):
        fetched = resolve_parcel_map(
            cadastral_code=prop.cadastral_code if prop else None,
            lat=float(prop.latitude) if prop and prop.latitude is not None else None,
            lng=float(prop.longitude) if prop and prop.longitude is not None else None,
        )
        if fetched.get("rings"):
            map_meta = fetched
            if prop is not None:
                prop.map_meta_json = fetched

    lat_out = map_meta.get("centroid_lat")
    lng_out = map_meta.get("centroid_lng")
    if lat_out is None and prop and prop.latitude is not None:
        lat_out = float(prop.latitude)
    if lng_out is None and prop and prop.longitude is not None:
        lng_out = float(prop.longitude)

    owner_name = "—"
    if owner:
        if owner.person_type == "legal":
            owner_name = owner.legal_name or "—"
        else:
            owner_name = " ".join(x for x in [owner.first_name, owner.last_name_1, owner.last_name_2] if x) or "—"

    return {
        "form_number": appraisal.form_number,
        "status_code": appraisal.status.code if appraisal.status else "",
        "status_name": appraisal.status.name if appraisal.status else "",
        "cadastral_code": prop.cadastral_code if prop else None,
        "address": prop.address if prop else "",
        "door_number": prop.door_number if prop else None,
        "latitude": lat_out,
        "longitude": lng_out,
        "owner_name": owner_name,
        "owner_document": owner.document_number if owner else None,
        "owner_phone": owner.phone if owner else None,
        "registry_matricula": owner.registry_matricula if owner else None,
        "registry_asiento": owner.registry_asiento if owner else None,
        "registry_ddr_date": owner.registry_ddr_date.isoformat() if owner and owner.registry_ddr_date else None,
        "deed_number": owner.deed_number if owner else None,
        "notary_name": owner.notary_name if owner else None,
        "front_length": float(_dec(detail.front_length if detail else 0)),
        "depth_length": float(_dec(detail.depth_length if detail else 0)),
        "approved_area": float(area),
        "zone_label": _label(zone),
        "topo_label": _label(iprt_item),
        "shape_label": _label(shape),
        "location_label": _label(location),
        "road_label": _label(ipv_item),
        "iprt_label": _label(iprt_item),
        "ipv_label": _label(ipv_item),
        "services": ipiu_labels,
        "equipments": ipes_labels,
        "observations": detail.observations if detail else None,
        "land_value": float(land_value),
        "blocks_value": float(blocks_value),
        "improvements_value": float(improvements_value),
        "total_value": float(total_value),
        "zone_m2": float(zone_m2),
        "vsz": float(vsz),
        "vsvia": float(vsvia),
        "indices": snapshot["indices"],
        "coefficients": snapshot["coefficients"],
        "blocks": blocks_out,
        "migrated": (appraisal.status.code == "migrated") if appraisal.status else False,
        "map_meta": map_meta,
        "formula": {
            "land_value": load_active_formula(db, "land_value")[0],
            "block_value": load_active_formula(db, "block_value")[0],
            "appraisal_total": load_active_formula(db, "appraisal_total")[0],
        },
    }


def load_appraisal_for_pdf(db: Session, appraisal_id: UUID) -> Appraisal | None:
    return db.execute(
        select(Appraisal)
        .options(
            selectinload(Appraisal.status),
            selectinload(Appraisal.property).selectinload(Property.owners),
            selectinload(Appraisal.property).selectinload(Property.detail).selectinload(PropertyDetail.services),
            selectinload(Appraisal.property).selectinload(Property.detail).selectinload(PropertyDetail.equipments),
            selectinload(Appraisal.property)
            .selectinload(Property.units)
            .selectinload(ConstructionUnit.characteristic_values),
        )
        .where(Appraisal.id == appraisal_id)
    ).scalar_one_or_none()
