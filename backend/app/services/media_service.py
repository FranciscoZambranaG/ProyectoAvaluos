from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from io import BytesIO
from pathlib import Path

from fastapi import HTTPException, UploadFile
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    CharacteristicGroup,
    CharacteristicOption,
    ConstructionUnit,
    DocumentFile,
    MediaType,
    UnitCharacteristicValue,
    User,
)
from app.schemas.appraisal import (
    CharacteristicGroupOut,
    CharacteristicOptionOut,
    MediaTypeOut,
    PhotoOut,
    UnitCharacteristicIn,
    UnitCharacteristicOut,
)

UPLOAD_ROOT = Path(__file__).resolve().parents[2] / "uploads"


def list_characteristic_catalog(db: Session, construction_year: int | None = None) -> list[CharacteristicGroupOut]:
    from app.services.admin_catalog_service import effective_sort

    groups = db.execute(
        select(CharacteristicGroup)
        .options(
            selectinload(CharacteristicGroup.options).selectinload(CharacteristicOption.order_rules)
        )
        .where(CharacteristicGroup.is_active.is_(True))
        .order_by(CharacteristicGroup.sort_order)
    ).scalars().all()
    out: list[CharacteristicGroupOut] = []
    for g in groups:
        opts_sorted = sorted(
            [o for o in g.options if o.is_active],
            key=lambda o: (effective_sort(o, construction_year), o.label),
        )
        opts = [
            CharacteristicOptionOut(
                id=o.id,
                code=o.code,
                label=o.label,
                description=o.description,
                sort_order=effective_sort(o, construction_year),
                image_url=f"/api/v1/media/{o.image_file_id}" if o.image_file_id else None,
            )
            for o in opts_sorted
        ]
        out.append(
            CharacteristicGroupOut(
                id=g.id,
                code=g.code,
                name=g.name,
                sort_order=g.sort_order,
                applies_to=g.applies_to,
                max_percent=g.max_percent,
                options=opts,
            )
        )
    return out


def list_media_types(db: Session, category: str = "photo") -> list[MediaTypeOut]:
    rows = db.execute(
        select(MediaType)
        .where(MediaType.is_active.is_(True), MediaType.category == category)
        .order_by(MediaType.sort_order)
    ).scalars().all()
    return [MediaTypeOut(id=r.id, code=r.code, name=r.name, category=r.category) for r in rows]


def save_unit_characteristics(
    db: Session,
    appraisal_id: uuid.UUID,
    block_id: uuid.UUID,
    user: User,
    items: list[UnitCharacteristicIn],
):
    from app.services.appraisal_service import _ensure_editable, _get_owned_appraisal, get_appraisal

    appraisal = _get_owned_appraisal(db, appraisal_id, user)
    _ensure_editable(appraisal, user)
    unit = next((u for u in (appraisal.property.units if appraisal.property else []) if u.id == block_id), None)
    if not unit or unit.status != "active":
        raise HTTPException(404, "Bloque no encontrado")

    unit = db.execute(
        select(ConstructionUnit)
        .options(selectinload(ConstructionUnit.characteristic_values))
        .where(ConstructionUnit.id == block_id)
    ).scalar_one()

    option_ids = [i.option_id for i in items]
    options = {
        o.id: o
        for o in db.execute(
            select(CharacteristicOption).where(CharacteristicOption.id.in_(option_ids))
        ).scalars().all()
    } if option_ids else {}

    # Varios subtipos por grupo; solo % > 0 se calculan y persisten
    group_sums: dict[uuid.UUID, Decimal] = {}
    seen_options: set[uuid.UUID] = set()
    unit.characteristic_values.clear()
    db.flush()
    total = Decimal("0")
    idx = 0
    for item in items:
        if item.percentage <= 0:
            continue
        opt = options.get(item.option_id)
        if not opt:
            raise HTTPException(400, f"Opción inválida: {item.option_id}")
        # Subtipos deshabilitados en admin siguen siendo válidos en trámites que ya los usan;
        # si se rechazan, el guardado de otras características falla con «Opción inválida».
        if item.option_id in seen_options:
            raise HTTPException(400, "Subtipo duplicado en la misma selección")
        seen_options.add(item.option_id)
        group_sums[opt.group_id] = group_sums.get(opt.group_id, Decimal("0")) + item.percentage
        if group_sums[opt.group_id] > Decimal("100"):
            raise HTTPException(400, "La carga de porcentajes de un tipo no puede superar 100%")
        score = (opt.base_score * item.percentage) / Decimal("100")
        total += score
        db.add(
            UnitCharacteristicValue(
                construction_unit_id=unit.id,
                characteristic_group_id=opt.group_id,
                characteristic_option_id=opt.id,
                percentage=item.percentage,
                score=score,
                sort_order=idx,
            )
        )
        idx += 1
    unit.total_score = total
    unit.updated_at = datetime.now(timezone.utc)
    appraisal.updated_at = datetime.now(timezone.utc)
    db.commit()
    return get_appraisal(db, appraisal_id, user)


def list_photos(db: Session, appraisal_id: uuid.UUID) -> list[PhotoOut]:
    rows = db.execute(
        select(DocumentFile, MediaType)
        .join(MediaType, MediaType.id == DocumentFile.media_type_id, isouter=True)
        .where(DocumentFile.entity_type == "appraisal", DocumentFile.entity_id == appraisal_id)
        .order_by(DocumentFile.created_at.desc())
    ).all()
    photos: list[PhotoOut] = []
    for f, mt in rows:
        if mt and mt.category != "photo":
            continue
        photos.append(
            PhotoOut(
                id=f.id,
                media_type_code=mt.code if mt else "photo_other",
                media_type_name=mt.name if mt else "Foto",
                original_name=f.original_name,
                url=f"/api/v1/media/{f.id}",
                width_px=f.width_px,
                height_px=f.height_px,
                created_at=f.created_at.isoformat() if f.created_at else "",
            )
        )
    return photos


async def upload_photo(
    db: Session,
    appraisal_id: uuid.UUID,
    user: User,
    media_type_code: str,
    upload: UploadFile,
):
    from app.services.appraisal_service import _ensure_editable, _get_owned_appraisal, get_appraisal

    appraisal = _get_owned_appraisal(db, appraisal_id, user)
    _ensure_editable(appraisal, user)

    mt = db.execute(select(MediaType).where(MediaType.code == media_type_code, MediaType.is_active.is_(True))).scalar_one_or_none()
    if not mt or mt.category != "photo":
        raise HTTPException(400, "Tipo de fotografía inválido")

    raw = await upload.read()
    if not raw:
        raise HTTPException(400, "Archivo vacío")
    if len(raw) > 25 * 1024 * 1024:
        raise HTTPException(400, "La imagen supera 25 MB")

    try:
        img = Image.open(BytesIO(raw))
        img.load()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, "El archivo no es una imagen válida") from exc

    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")
    elif img.mode == "RGBA":
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[-1])
        img = background

    buf = BytesIO()
    img.save(buf, format="WEBP", quality=82, method=4)
    data = buf.getvalue()
    checksum = hashlib.sha256(data).hexdigest()
    file_id = uuid.uuid4()
    rel = Path("appraisals") / str(appraisal_id) / f"{file_id}.webp"
    dest = UPLOAD_ROOT / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)

    row = DocumentFile(
        id=file_id,
        entity_type="appraisal",
        entity_id=appraisal_id,
        media_type_id=mt.id,
        storage_backend="local",
        storage_key=str(rel).replace("\\", "/"),
        original_name=upload.filename,
        mime_type="image/webp",
        size_bytes=len(data),
        checksum_sha256=checksum,
        width_px=img.width,
        height_px=img.height,
        uploaded_by=user.id,
    )
    db.add(row)
    appraisal.updated_at = datetime.now(timezone.utc)
    db.commit()
    return get_appraisal(db, appraisal_id, user)


def update_photo_type(
    db: Session,
    appraisal_id: uuid.UUID,
    photo_id: uuid.UUID,
    user: User,
    media_type_code: str,
):
    from app.services.appraisal_service import _ensure_editable, _get_owned_appraisal, get_appraisal

    appraisal = _get_owned_appraisal(db, appraisal_id, user)
    _ensure_editable(appraisal, user)
    row = db.execute(
        select(DocumentFile).where(
            DocumentFile.id == photo_id,
            DocumentFile.entity_type == "appraisal",
            DocumentFile.entity_id == appraisal_id,
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(404, "Fotografía no encontrada")
    mt = db.execute(
        select(MediaType).where(MediaType.code == media_type_code, MediaType.is_active.is_(True))
    ).scalar_one_or_none()
    if not mt or mt.category != "photo":
        raise HTTPException(400, "Tipo de fotografía inválido")
    row.media_type_id = mt.id
    appraisal.updated_at = datetime.now(timezone.utc)
    db.commit()
    return get_appraisal(db, appraisal_id, user)


def delete_photo(db: Session, appraisal_id: uuid.UUID, photo_id: uuid.UUID, user: User):
    from app.services.appraisal_service import _ensure_editable, _get_owned_appraisal, get_appraisal

    appraisal = _get_owned_appraisal(db, appraisal_id, user)
    _ensure_editable(appraisal, user)
    row = db.execute(
        select(DocumentFile).where(
            DocumentFile.id == photo_id,
            DocumentFile.entity_type == "appraisal",
            DocumentFile.entity_id == appraisal_id,
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(404, "Fotografía no encontrada")
    path = UPLOAD_ROOT / row.storage_key
    if path.exists():
        path.unlink(missing_ok=True)
    db.delete(row)
    appraisal.updated_at = datetime.now(timezone.utc)
    db.commit()
    return get_appraisal(db, appraisal_id, user)


def get_media_file(db: Session, file_id: uuid.UUID) -> DocumentFile:
    row = db.execute(select(DocumentFile).where(DocumentFile.id == file_id)).scalar_one_or_none()
    if not row:
        raise HTTPException(404, "Archivo no encontrado")
    return row


def serialize_unit_characteristics(unit: ConstructionUnit, db: Session) -> list[UnitCharacteristicOut]:
    if not unit.characteristic_values:
        return []
    group_ids = {v.characteristic_group_id for v in unit.characteristic_values}
    option_ids = {v.characteristic_option_id for v in unit.characteristic_values}
    groups = {
        g.id: g
        for g in db.execute(select(CharacteristicGroup).where(CharacteristicGroup.id.in_(group_ids))).scalars().all()
    } if group_ids else {}
    options = {
        o.id: o
        for o in db.execute(select(CharacteristicOption).where(CharacteristicOption.id.in_(option_ids))).scalars().all()
    } if option_ids else {}
    out: list[UnitCharacteristicOut] = []
    for v in unit.characteristic_values:
        g = groups.get(v.characteristic_group_id)
        o = options.get(v.characteristic_option_id)
        if not g or not o:
            continue
        out.append(
            UnitCharacteristicOut(
                group_id=g.id,
                group_code=g.code,
                group_name=g.name,
                option_id=o.id,
                option_label=o.label,
                percentage=v.percentage,
                score=v.score,
                base_score=o.base_score,
            )
        )
    return out
