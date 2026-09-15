from datetime import datetime, timezone
from uuid import UUID
import re

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Appraisal,
    CatalogItem,
    CatalogType,
    ConstructionUnit,
    Owner,
    Property,
    PropertyDetail,
    PropertyEquipment,
    PropertyService,
    User,
    WorkflowStatus,
)
from app.schemas.appraisal import (
    AppraisalCreateIn,
    AppraisalDetailOut,
    AppraisalListItem,
    CadastralCodeIn,
    CatalogOption,
    ConstructionUnitIn,
    ConstructionUnitOut,
    OwnerIn,
    OwnerOut,
    OwnerPutIn,
    PropertyDetailIn,
    PropertyDetailOut,
)
from app.services import media_service as media_svc


def _status(db: Session, code: str) -> WorkflowStatus:
    row = db.execute(select(WorkflowStatus).where(WorkflowStatus.code == code)).scalar_one_or_none()
    if not row:
        raise HTTPException(500, f"Estado de workflow '{code}' no configurado")
    return row


def _current_year(db: Session) -> int:
    year = db.execute(select(func.max(Appraisal.fiscal_year))).scalar()
    # Prefer config current year via catalog fiscal; fallback 2026
    from sqlalchemy import text

    cur = db.execute(text("SELECT year FROM config.fiscal_years WHERE is_current = TRUE LIMIT 1")).scalar()
    return int(cur or year or 2026)


def _next_form_number(db: Session, year: int) -> str:
    like = f"AV-{year}-%"
    last = db.execute(
        select(Appraisal.form_number)
        .where(Appraisal.form_number.like(like))
        .order_by(Appraisal.form_number.desc())
        .limit(1)
    ).scalar_one_or_none()
    seq = 1
    if last and last.split("-")[-1].isdigit():
        seq = int(last.split("-")[-1]) + 1
    return f"AV-{year}-{seq:06d}"


def _compose_cadastral(data: CadastralCodeIn) -> str:
    parts = [
        data.subdistrict.zfill(2)[:2],
        data.block_code.zfill(3)[:11],
        data.plot_code.zfill(3)[:11],
        (data.use_code or "0").zfill(1)[:2],
        (data.building_code or "0").zfill(1)[:2],
        (data.floor_code or "0").zfill(1)[:2],
        (data.unit_code or "0").zfill(1)[:2],
    ]
    # Compatible con legacy: subdistrito(2)+manzana+predio+uso+bloque+planta+unidad
    return f"{parts[0]}{parts[1].zfill(3)}{parts[2].zfill(3)}{(data.use_code or '0').zfill(1)}{(data.building_code or '0').zfill(1)}{(data.floor_code or '0').zfill(1)}{(data.unit_code or '0').zfill(1)}".ljust(17, "0")[:17]


REVIEWER_ROLES = {"system_admin", "technical_architect"}


def _get_owned_appraisal(db: Session, appraisal_id: UUID, user: User) -> Appraisal:
    appraisal = db.execute(
        select(Appraisal)
        .options(
            selectinload(Appraisal.property).selectinload(Property.owners),
            selectinload(Appraisal.property).selectinload(Property.detail).selectinload(PropertyDetail.services),
            selectinload(Appraisal.property).selectinload(Property.detail).selectinload(PropertyDetail.equipments),
            selectinload(Appraisal.property)
            .selectinload(Property.units)
            .selectinload(ConstructionUnit.characteristic_values),
            selectinload(Appraisal.status),
        )
        .where(Appraisal.id == appraisal_id)
    ).scalar_one_or_none()
    if not appraisal:
        raise HTTPException(404, "Formulario no encontrado")
    from app.services.auth_service import _roles_of

    user_roles = _roles_of(db, user.id)
    if appraisal.owner_user_id != user.id and not REVIEWER_ROLES.intersection(user_roles):
        raise HTTPException(403, "No tiene permiso sobre este formulario")
    return appraisal


def _ensure_editable(appraisal: Appraisal, user: User, user_roles: list[str] | None = None) -> None:
    """Editable en borrador / requiere corrección: dueño, o funcionario tras habilitar corrección."""
    if appraisal.status.code == "migrated":
        raise HTTPException(
            409,
            "El formulario ya fue migrado y no puede editarse. Un funcionario debe habilitarlo para corrección.",
        )

    from app.services.auth_service import _roles_of
    from sqlalchemy.orm import object_session

    if user_roles is None:
        sess = object_session(appraisal)
        roles = set(_roles_of(sess, user.id)) if sess is not None else set()
    else:
        roles = set(user_roles)

    is_reviewer = bool(REVIEWER_ROLES.intersection(roles))
    is_owner = appraisal.owner_user_id == user.id

    if appraisal.status.code == "draft" and is_owner:
        return
    if appraisal.status.code == "needs_correction" and (is_owner or is_reviewer):
        return
    if not is_owner and not is_reviewer:
        raise HTTPException(403, "Solo lectura: no puede editar formularios de otros usuarios")
    raise HTTPException(409, "El formulario ya no se puede editar en este estado")


def _owner_display_name(owner: Owner | None) -> str | None:
    if not owner:
        return None
    if owner.person_type == "legal":
        return owner.legal_name
    return " ".join(x for x in [owner.first_name, owner.last_name_1, owner.last_name_2] if x) or None


def _list_item(a: Appraisal, user: User) -> AppraisalListItem:
    prop = a.property
    owner = prop.owners[0] if prop and prop.owners else None
    return AppraisalListItem(
        id=a.id,
        form_number=a.form_number,
        status_code=a.status.code,
        status_name=a.status.name,
        address=prop.address if prop else None,
        owner_name=_owner_display_name(owner),
        owner_document=owner.document_number if owner else None,
        approved_area=prop.detail.approved_area if prop and prop.detail else None,
        created_at=a.created_at.isoformat() if a.created_at else "",
        cadastral_code=prop.cadastral_code if prop else None,
        is_own=a.owner_user_id == user.id,
    )


def serialize_appraisal(appraisal: Appraisal, db: Session | None = None, user: User | None = None) -> AppraisalDetailOut:
    prop = appraisal.property
    owner = prop.owners[0] if prop and prop.owners else None
    detail = prop.detail if prop else None
    blocks_out: list[ConstructionUnitOut] = []
    for u in prop.units if prop else []:
        if u.status != "active":
            continue
        chars = media_svc.serialize_unit_characteristics(u, db) if db is not None else []
        blocks_out.append(
            ConstructionUnitOut(
                id=u.id,
                unit_kind=u.unit_kind,
                unit_number=u.unit_number,
                area=u.area,
                floors_count=u.floors_count,
                construction_year=u.construction_year,
                modification_year=u.modification_year,
                observations=u.observations,
                characteristics=chars,
                total_score=u.total_score,
                use_coeff_item_id=u.use_coeff_item_id,
                depreciation_item_id=u.depreciation_item_id,
                improvement_type_item_id=u.improvement_type_item_id,
                unit_value=u.unit_value,
            )
        )
    photos = media_svc.list_photos(db, appraisal.id) if db is not None else []
    is_own = user is not None and appraisal.owner_user_id == user.id
    roles: set[str] = set()
    if db is not None and user is not None:
        from app.services.auth_service import _roles_of

        roles = set(_roles_of(db, user.id))
    is_reviewer = bool(REVIEWER_ROLES.intersection(roles))
    status_code = appraisal.status.code
    can_edit = (is_own and status_code in {"draft", "needs_correction"}) or (
        is_reviewer and status_code == "needs_correction"
    )
    can_enable_correction = is_reviewer and status_code == "migrated"
    can_migrate = is_reviewer and status_code in {"draft", "approved", "needs_correction"}
    is_remigration = False
    if can_migrate and db is not None:
        try:
            from app.services import migration_service as mig_svc

            is_remigration = mig_svc.count_municipal_versions(appraisal.id, appraisal.form_number) > 0
        except Exception:
            is_remigration = status_code == "needs_correction"
    return AppraisalDetailOut(
        id=appraisal.id,
        form_number=appraisal.form_number,
        status_code=appraisal.status.code,
        status_name=appraisal.status.name,
        fiscal_year=appraisal.fiscal_year,
        address=prop.address if prop else "",
        door_number=prop.door_number if prop else None,
        building_name=prop.building_name if prop else None,
        block_label=prop.block_label if prop else None,
        floor_label=prop.floor_label if prop else None,
        apartment_label=prop.apartment_label if prop else None,
        cadastral_code=prop.cadastral_code if prop else None,
        subdistrict=prop.subdistrict if prop else None,
        block_code=prop.block_code if prop else None,
        plot_code=prop.plot_code if prop else None,
        use_code=prop.use_code if prop else None,
        building_code=prop.building_code if prop else None,
        floor_code=prop.floor_code if prop else None,
        unit_code=prop.unit_code if prop else None,
        latitude=prop.latitude if prop else None,
        longitude=prop.longitude if prop else None,
        owner=OwnerOut(
            id=owner.id,
            person_type=owner.person_type,
            first_name=owner.first_name,
            last_name_1=owner.last_name_1,
            last_name_2=owner.last_name_2,
            legal_name=owner.legal_name,
            document_number=owner.document_number,
            ownership_percent=owner.ownership_percent or 100,
            registry_matricula=owner.registry_matricula,
            registry_asiento=owner.registry_asiento,
            registry_fojas=owner.registry_fojas,
            registry_partida=owner.registry_partida,
            deed_number=owner.deed_number,
            deed_date=owner.deed_date,
            registry_ddr_date=owner.registry_ddr_date,
            notary_name=owner.notary_name,
            phone=owner.phone,
            email=owner.email,
        )
        if owner
        else None,
        detail=PropertyDetailOut(
            approved_area=detail.approved_area,
            front_length=detail.front_length,
            depth_length=detail.depth_length,
            zone_item_id=detail.zone_item_id,
            topography_item_id=detail.topography_item_id,
            shape_item_id=detail.shape_item_id,
            location_item_id=detail.location_item_id,
            road_material_item_id=detail.road_material_item_id,
            service_item_ids=[s.service_item_id for s in detail.services],
            equipment_item_ids=[e.equipment_item_id for e in detail.equipments],
            observations=detail.observations,
            latitude=prop.latitude if prop else None,
            longitude=prop.longitude if prop else None,
            registry_matricula=owner.registry_matricula if owner else None,
            registry_asiento=owner.registry_asiento if owner else None,
            registry_ddr_date=owner.registry_ddr_date if owner else None,
            building_name=prop.building_name if prop else None,
            block_label=prop.block_label if prop else None,
            floor_label=prop.floor_label if prop else None,
            apartment_label=prop.apartment_label if prop else None,
        )
        if detail
        else None,
        blocks=blocks_out,
        photos=photos,
        created_at=appraisal.created_at.isoformat() if appraisal.created_at else "",
        can_edit=can_edit,
        is_own=is_own,
        can_enable_correction=can_enable_correction,
        can_migrate=can_migrate,
        is_remigration=is_remigration,
    )


def list_appraisals(db: Session, user: User) -> list[AppraisalListItem]:
    """Lista solo los formularios del usuario autenticado."""
    rows = db.execute(
        select(Appraisal)
        .options(
            selectinload(Appraisal.property).selectinload(Property.owners),
            selectinload(Appraisal.property).selectinload(Property.detail),
            selectinload(Appraisal.status),
        )
        .where(Appraisal.owner_user_id == user.id)
        .order_by(Appraisal.created_at.desc())
    ).scalars().all()
    return [_list_item(a, user) for a in rows]


def search_appraisals(db: Session, user: User, q: str, limit: int = 40) -> list[AppraisalListItem]:
    """Búsqueda inteligente (solo funcionario / administrador)."""
    from app.services.auth_service import _roles_of

    roles = _roles_of(db, user.id)
    if not REVIEWER_ROLES.intersection(roles):
        raise HTTPException(403, "La búsqueda de formularios es solo para funcionario o administrador")

    term = (q or "").strip()
    if len(term) < 2:
        return []

    like = f"%{term}%"
    digits = re.sub(r"\D", "", term)
    filters = [
        Appraisal.form_number.ilike(like),
        Property.cadastral_code.ilike(like),
        Property.address.ilike(like),
        Owner.document_number.ilike(like),
        Owner.nit.ilike(like),
        Owner.first_name.ilike(like),
        Owner.last_name_1.ilike(like),
        Owner.last_name_2.ilike(like),
        Owner.legal_name.ilike(like),
        func.concat(func.coalesce(Owner.first_name, ""), " ", func.coalesce(Owner.last_name_1, "")).ilike(like),
        func.concat(
            func.coalesce(Owner.first_name, ""),
            " ",
            func.coalesce(Owner.last_name_1, ""),
            " ",
            func.coalesce(Owner.last_name_2, ""),
        ).ilike(like),
    ]
    if digits:
        filters.append(Property.cadastral_code.ilike(f"%{digits}%"))
        filters.append(Owner.document_number.ilike(f"%{digits}%"))
        filters.append(Appraisal.form_number.ilike(f"%{digits}%"))

    rows = db.execute(
        select(Appraisal)
        .join(Property, Property.appraisal_id == Appraisal.id)
        .outerjoin(Owner, Owner.property_id == Property.id)
        .options(
            selectinload(Appraisal.property).selectinload(Property.owners),
            selectinload(Appraisal.property).selectinload(Property.detail),
            selectinload(Appraisal.status),
        )
        .where(or_(*filters))
        .order_by(Appraisal.created_at.desc())
        .limit(min(limit, 50))
    ).scalars().unique().all()
    return [_list_item(a, user) for a in rows]


def create_appraisal(db: Session, user: User, data: AppraisalCreateIn) -> AppraisalDetailOut:
    if data.owner.person_type == "natural" and (not data.owner.first_name or not data.owner.last_name_1):
        raise HTTPException(422, "Nombres y primer apellido son obligatorios para persona natural")
    if data.owner.person_type == "legal" and not data.owner.legal_name:
        raise HTTPException(422, "La razón social es obligatoria para persona jurídica")
    if not data.owner.document_number:
        raise HTTPException(422, "El C.I./NIT es obligatorio")

    year = _current_year(db)
    draft = _status(db, "draft")
    form_number = _next_form_number(db, year)

    appraisal = Appraisal(
        form_number=form_number,
        owner_user_id=user.id,
        status_id=draft.id,
        fiscal_year=year,
    )
    db.add(appraisal)
    db.flush()

    prop = Property(
        appraisal_id=appraisal.id,
        address=data.address.strip(),
        door_number=data.door_number,
        latitude=data.latitude,
        longitude=data.longitude,
    )
    db.add(prop)
    db.flush()

    owner = Owner(
        property_id=prop.id,
        person_type=data.owner.person_type,
        first_name=data.owner.first_name,
        last_name_1=data.owner.last_name_1,
        last_name_2=data.owner.last_name_2,
        legal_name=data.owner.legal_name,
        document_number=data.owner.document_number,
        ownership_percent=data.owner.ownership_percent,
        registry_matricula=data.owner.registry_matricula,
        registry_asiento=data.owner.registry_asiento,
        registry_fojas=data.owner.registry_fojas,
        registry_partida=data.owner.registry_partida,
        deed_number=data.owner.deed_number,
        deed_date=data.owner.deed_date,
        registry_ddr_date=data.owner.registry_ddr_date,
        notary_name=data.owner.notary_name,
        phone=data.owner.phone,
        email=str(data.owner.email) if data.owner.email else None,
    )
    db.add(owner)
    db.commit()
    return get_appraisal(db, appraisal.id, user)


def get_appraisal(db: Session, appraisal_id: UUID, user: User) -> AppraisalDetailOut:
    appraisal = _get_owned_appraisal(db, appraisal_id, user)
    return serialize_appraisal(appraisal, db, user)


def update_owner(db: Session, appraisal_id: UUID, user: User, data: OwnerPutIn) -> AppraisalDetailOut:
    appraisal = _get_owned_appraisal(db, appraisal_id, user)
    _ensure_editable(appraisal, user)
    prop = appraisal.property
    if not prop:
        raise HTTPException(404, "Predio no encontrado")
    owner = prop.owners[0] if prop.owners else None
    if not owner:
        owner = Owner(property_id=prop.id)
        db.add(owner)
    dumped = data.model_dump(exclude={"address", "door_number"})
    for field, value in dumped.items():
        setattr(owner, field, value)
    if data.address:
        prop.address = data.address.strip()
    if data.door_number is not None:
        prop.door_number = data.door_number
    appraisal.updated_at = datetime.now(timezone.utc)
    db.commit()
    return get_appraisal(db, appraisal_id, user)


def update_detail(db: Session, appraisal_id: UUID, user: User, data: PropertyDetailIn) -> AppraisalDetailOut:
    appraisal = _get_owned_appraisal(db, appraisal_id, user)
    _ensure_editable(appraisal, user)
    prop = appraisal.property
    if not prop:
        raise HTTPException(404, "Predio no encontrado")

    detail = prop.detail
    if not detail:
        detail = PropertyDetail(property_id=prop.id)
        db.add(detail)
        db.flush()

    detail.approved_area = data.approved_area
    detail.front_length = data.front_length
    detail.depth_length = data.depth_length
    detail.zone_item_id = data.zone_item_id
    detail.topography_item_id = data.topography_item_id
    detail.shape_item_id = data.shape_item_id
    detail.location_item_id = data.location_item_id
    detail.road_material_item_id = data.road_material_item_id
    detail.observations = data.observations
    detail.updated_at = datetime.now(timezone.utc)

    owner = prop.owners[0] if prop.owners else None
    if owner:
        if data.registry_matricula is not None:
            owner.registry_matricula = data.registry_matricula
        if data.registry_asiento is not None:
            owner.registry_asiento = data.registry_asiento
        if data.registry_ddr_date is not None:
            owner.registry_ddr_date = data.registry_ddr_date

    if data.building_name is not None:
        prop.building_name = data.building_name.strip() or None
    if data.block_label is not None:
        prop.block_label = data.block_label.strip() or None
    if data.floor_label is not None:
        prop.floor_label = data.floor_label.strip() or None
    if data.apartment_label is not None:
        prop.apartment_label = data.apartment_label.strip() or None

    prop.latitude = data.latitude
    prop.longitude = data.longitude
    appraisal.land_area = data.approved_area

    detail.services.clear()
    db.flush()
    for sid in data.service_item_ids:
        db.add(PropertyService(property_detail_id=detail.id, service_item_id=sid))

    detail.equipments.clear()
    db.flush()
    for eid in data.equipment_item_ids:
        db.add(PropertyEquipment(property_detail_id=detail.id, equipment_item_id=eid))

    appraisal.updated_at = datetime.now(timezone.utc)
    db.commit()
    return get_appraisal(db, appraisal_id, user)


def update_cadastral(db: Session, appraisal_id: UUID, user: User, data: CadastralCodeIn) -> AppraisalDetailOut:
    appraisal = _get_owned_appraisal(db, appraisal_id, user)
    _ensure_editable(appraisal, user)
    prop = appraisal.property
    if not prop:
        raise HTTPException(404, "Predio no encontrado")

    prop.subdistrict = data.subdistrict
    prop.block_code = data.block_code
    prop.plot_code = data.plot_code
    prop.use_code = data.use_code
    prop.building_code = data.building_code
    prop.floor_code = data.floor_code
    prop.unit_code = data.unit_code
    prop.door_number = data.door_number or prop.door_number
    prop.building_name = data.building_name
    prop.cadastral_code = _compose_cadastral(data)
    if data.latitude is not None:
        prop.latitude = data.latitude
    if data.longitude is not None:
        prop.longitude = data.longitude
    if data.address:
        prop.address = data.address.strip()
    from app.routers.gis import point_in_parcel_rings, resolve_parcel_map

    user_lat = float(prop.latitude) if prop.latitude is not None else None
    user_lng = float(prop.longitude) if prop.longitude is not None else None
    meta = resolve_parcel_map(
        cadastral_code=prop.cadastral_code,
        lat=user_lat,
        lng=user_lng,
    )
    if meta.get("rings"):
        prop.map_meta_json = meta
        rings = meta.get("rings") or []
        keep_pin = (
            user_lat is not None
            and user_lng is not None
            and point_in_parcel_rings(user_lng, user_lat, rings)
        )
        if not keep_pin:
            if meta.get("centroid_lat") is not None:
                prop.latitude = meta["centroid_lat"]
            if meta.get("centroid_lng") is not None:
                prop.longitude = meta["centroid_lng"]
    appraisal.updated_at = datetime.now(timezone.utc)
    db.commit()
    return get_appraisal(db, appraisal_id, user)


def add_block(db: Session, appraisal_id: UUID, user: User, data: ConstructionUnitIn) -> AppraisalDetailOut:
    appraisal = _get_owned_appraisal(db, appraisal_id, user)
    _ensure_editable(appraisal, user)
    prop = appraisal.property
    if not prop:
        raise HTTPException(404, "Predio no encontrado")

    unit = ConstructionUnit(
        property_id=prop.id,
        unit_kind=data.unit_kind,
        unit_number=data.unit_number,
        area=data.area,
        floors_count=data.floors_count,
        construction_year=data.construction_year,
        modification_year=data.modification_year,
        observations=data.observations,
        fiscal_year=appraisal.fiscal_year,
        use_coeff_item_id=data.use_coeff_item_id,
        depreciation_item_id=data.depreciation_item_id,
        improvement_type_item_id=data.improvement_type_item_id,
    )
    db.add(unit)
    appraisal.updated_at = datetime.now(timezone.utc)
    db.commit()
    return get_appraisal(db, appraisal_id, user)


def update_block(
    db: Session,
    appraisal_id: UUID,
    user: User,
    block_id: UUID,
    data: ConstructionUnitIn,
) -> AppraisalDetailOut:
    appraisal = _get_owned_appraisal(db, appraisal_id, user)
    _ensure_editable(appraisal, user)
    prop = appraisal.property
    if not prop:
        raise HTTPException(404, "Predio no encontrado")

    unit = next((u for u in prop.units if u.id == block_id and u.status == "active"), None)
    if not unit:
        raise HTTPException(404, "Bloque no encontrado")

    unit.unit_kind = data.unit_kind
    unit.unit_number = data.unit_number
    unit.area = data.area
    unit.floors_count = data.floors_count
    unit.construction_year = data.construction_year
    unit.modification_year = data.modification_year
    unit.observations = data.observations
    unit.use_coeff_item_id = data.use_coeff_item_id
    unit.depreciation_item_id = data.depreciation_item_id
    unit.improvement_type_item_id = data.improvement_type_item_id
    unit.updated_at = datetime.now(timezone.utc)
    appraisal.updated_at = datetime.now(timezone.utc)
    db.commit()
    return get_appraisal(db, appraisal_id, user)


def delete_block(db: Session, appraisal_id: UUID, user: User, block_id: UUID) -> AppraisalDetailOut:
    appraisal = _get_owned_appraisal(db, appraisal_id, user)
    _ensure_editable(appraisal, user)
    prop = appraisal.property
    if not prop:
        raise HTTPException(404, "Predio no encontrado")

    unit = next((u for u in prop.units if u.id == block_id), None)
    if not unit:
        raise HTTPException(404, "Bloque no encontrado")
    unit.status = "deleted"
    unit.updated_at = datetime.now(timezone.utc)
    appraisal.updated_at = datetime.now(timezone.utc)
    db.commit()
    return get_appraisal(db, appraisal_id, user)


def list_catalog(db: Session, type_code: str) -> list[CatalogOption]:
    rows = db.execute(
        select(CatalogItem)
        .join(CatalogType, CatalogType.id == CatalogItem.catalog_type_id)
        .where(CatalogType.code == type_code, CatalogItem.is_active.is_(True))
        .order_by(CatalogItem.sort_order)
    ).scalars().all()
    return [
        CatalogOption(
            id=r.id,
            code=r.code,
            label=r.label,
            numeric_value=r.numeric_value,
            description=r.description,
        )
        for r in rows
    ]


def enable_appraisal_correction(db: Session, appraisal_id: UUID, user: User) -> AppraisalDetailOut:
    appraisal = _get_owned_appraisal(db, appraisal_id, user)
    from app.services import migration_service as mig_svc

    mig_svc.enable_correction(db, appraisal, user)
    return get_appraisal(db, appraisal_id, user)


def migrate_appraisal_to_municipal(db: Session, appraisal_id: UUID, user: User) -> AppraisalDetailOut:
    appraisal = _get_owned_appraisal(db, appraisal_id, user)
    from app.services import migration_service as mig_svc

    mig_svc.migrate_appraisal(db, appraisal, user)
    return get_appraisal(db, appraisal_id, user)
