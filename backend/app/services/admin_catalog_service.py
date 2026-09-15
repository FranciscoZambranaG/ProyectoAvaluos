from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from io import BytesIO
from pathlib import Path

from fastapi import HTTPException, UploadFile
from PIL import Image
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    CharacteristicGroup,
    CharacteristicOption,
    CharacteristicOptionOrderRule,
    DocumentFile,
    MediaType,
    User,
)
from app.services.auth_service import _roles_of
from app.services.media_service import UPLOAD_ROOT


ADMIN_ROLES = {"system_admin", "catalog_admin"}


def require_admin(db: Session, user: User) -> list[str]:
    roles = _roles_of(db, user.id)
    if not ADMIN_ROLES.intersection(roles):
        raise HTTPException(403, "Se requiere rol de administrador de catálogos")
    return roles


# ---- schemas ----

class GroupIn(BaseModel):
    code: str | None = Field(default=None, max_length=80)
    name: str = Field(min_length=2, max_length=150)
    sort_order: int = 0
    applies_to: str = Field(default="block", pattern="^(block|improvement|both)$")
    max_percent: Decimal = Field(default=Decimal("100"), ge=0, le=100)
    icon: str | None = None
    is_active: bool = True


class GroupOut(GroupIn):
    id: uuid.UUID
    options_count: int = 0


class OptionIn(BaseModel):
    code: str | None = Field(default=None, max_length=80)
    label: str = Field(min_length=1, max_length=200)
    description: str | None = None
    sort_order: int = 0
    base_score: Decimal | None = Field(default=None, ge=0)
    is_active: bool = True


class OrderRuleIn(BaseModel):
    sort_order: int
    year_from: int = Field(default=1800, ge=1800, le=2100)
    year_to: int | None = Field(default=None, ge=1800, le=2100)
    notes: str | None = None
    is_active: bool = True


class OrderRuleOut(OrderRuleIn):
    id: uuid.UUID
    option_id: uuid.UUID


class OptionAdminOut(BaseModel):
    id: uuid.UUID
    group_id: uuid.UUID
    code: str
    label: str
    description: str | None = None
    sort_order: int
    base_score: Decimal
    is_active: bool
    image_url: str | None = None
    order_rules: list[OrderRuleOut] = []


class ValueRowOut(BaseModel):
    group_id: uuid.UUID
    group_code: str
    group_name: str
    group_sort: int
    option_id: uuid.UUID
    option_code: str
    option_label: str
    option_sort: int
    base_score: Decimal
    is_active: bool
    image_url: str | None = None


def _slug(text: str) -> str:
    import re
    import unicodedata

    n = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^A-Za-z0-9]+", "-", n).strip("-").upper()
    return (s or "ITEM")[:40]


def list_groups_admin(db: Session) -> list[GroupOut]:
    rows = db.execute(
        select(CharacteristicGroup).options(selectinload(CharacteristicGroup.options)).order_by(CharacteristicGroup.sort_order)
    ).scalars().all()
    return [
        GroupOut(
            id=g.id,
            code=g.code,
            name=g.name,
            sort_order=g.sort_order,
            applies_to=g.applies_to,
            max_percent=g.max_percent,
            icon=g.icon,
            is_active=g.is_active,
            options_count=len(g.options),
        )
        for g in rows
    ]


def create_group(db: Session, data: GroupIn) -> GroupOut:
    code = (data.code or _slug(data.name)).lower().replace("-", "_")[:80]
    # Reactivar si existe inactivo con mismo código o mismo nombre
    existing = db.execute(
        select(CharacteristicGroup).where(
            (CharacteristicGroup.code == code) | (CharacteristicGroup.name.ilike(data.name.strip()))
        )
    ).scalars().first()
    if existing:
        if existing.is_active:
            raise HTTPException(409, "Ya existe un tipo activo con ese nombre/código")
        existing.is_active = True
        existing.name = data.name.strip()
        existing.sort_order = data.sort_order
        existing.applies_to = data.applies_to
        existing.max_percent = data.max_percent
        existing.icon = data.icon
        db.commit()
        db.refresh(existing)
        return GroupOut(
            id=existing.id,
            code=existing.code,
            name=existing.name,
            sort_order=existing.sort_order,
            applies_to=existing.applies_to,
            max_percent=existing.max_percent,
            icon=existing.icon,
            is_active=existing.is_active,
            options_count=0,
        )
    g = CharacteristicGroup(
        code=code,
        name=data.name.strip(),
        sort_order=data.sort_order,
        applies_to=data.applies_to,
        max_percent=data.max_percent,
        icon=data.icon,
        is_active=True,
    )
    db.add(g)
    db.commit()
    db.refresh(g)
    return GroupOut(id=g.id, code=g.code, name=g.name, sort_order=g.sort_order, applies_to=g.applies_to, max_percent=g.max_percent, icon=g.icon, is_active=g.is_active, options_count=0)


def soft_delete_group(db: Session, group_id: uuid.UUID) -> GroupOut:
    g = db.get(CharacteristicGroup, group_id)
    if not g:
        raise HTTPException(404, "Tipo no encontrado")
    g.is_active = False
    db.commit()
    return GroupOut(id=g.id, code=g.code, name=g.name, sort_order=g.sort_order, applies_to=g.applies_to, max_percent=g.max_percent, icon=g.icon, is_active=g.is_active, options_count=0)


def update_group(db: Session, group_id: uuid.UUID, data: GroupIn) -> GroupOut:
    g = db.get(CharacteristicGroup, group_id)
    if not g:
        raise HTTPException(404, "Tipo no encontrado")
    # Los códigos no se editan desde la UI de administración
    g.name = data.name.strip()
    g.sort_order = data.sort_order
    g.applies_to = data.applies_to
    g.max_percent = data.max_percent
    g.icon = data.icon
    g.is_active = data.is_active
    db.commit()
    return GroupOut(id=g.id, code=g.code, name=g.name, sort_order=g.sort_order, applies_to=g.applies_to, max_percent=g.max_percent, icon=g.icon, is_active=g.is_active, options_count=0)


def reorder_groups(db: Session, ordered_ids: list[uuid.UUID]) -> list[GroupOut]:
    for i, gid in enumerate(ordered_ids, start=1):
        g = db.get(CharacteristicGroup, gid)
        if g:
            g.sort_order = i * 10
    db.commit()
    return list_groups_admin(db)


def _option_out(o: CharacteristicOption) -> OptionAdminOut:
    return OptionAdminOut(
        id=o.id,
        group_id=o.group_id,
        code=o.code,
        label=o.label,
        description=o.description,
        sort_order=o.sort_order,
        base_score=o.base_score,
        is_active=o.is_active,
        image_url=f"/api/v1/media/{o.image_file_id}" if o.image_file_id else None,
        order_rules=[
            OrderRuleOut(
                id=r.id,
                option_id=r.option_id,
                sort_order=r.sort_order,
                year_from=r.year_from,
                year_to=r.year_to,
                notes=r.notes,
                is_active=r.is_active,
            )
            for r in sorted(o.order_rules, key=lambda x: (x.year_from, x.sort_order))
            if r.is_active or True
        ],
    )


def list_options_admin(db: Session, group_id: uuid.UUID) -> list[OptionAdminOut]:
    rows = db.execute(
        select(CharacteristicOption)
        .options(selectinload(CharacteristicOption.order_rules))
        .where(CharacteristicOption.group_id == group_id)
        .order_by(CharacteristicOption.sort_order)
    ).scalars().all()
    return [_option_out(o) for o in rows]


def create_option(db: Session, group_id: uuid.UUID, data: OptionIn) -> OptionAdminOut:
    g = db.get(CharacteristicGroup, group_id)
    if not g:
        raise HTTPException(404, "Tipo no encontrado")
    code = (data.code or f"{g.code[:8].upper()}-{_slug(data.label)[:12]}")[:80]
    existing = db.execute(
        select(CharacteristicOption)
        .options(selectinload(CharacteristicOption.order_rules))
        .where(
            CharacteristicOption.group_id == group_id,
            (CharacteristicOption.code == code) | (CharacteristicOption.label.ilike(data.label.strip())),
        )
    ).scalars().first()
    if existing:
        if existing.is_active:
            raise HTTPException(409, "Ya existe un subtipo activo con ese nombre/código")
        existing.is_active = True
        existing.label = data.label.strip()
        existing.description = data.description
        existing.sort_order = data.sort_order
        if data.base_score is not None:
            existing.base_score = data.base_score
        db.commit()
        db.refresh(existing)
        return _option_out(existing)
    o = CharacteristicOption(
        group_id=group_id,
        code=code,
        label=data.label.strip(),
        description=data.description,
        sort_order=data.sort_order,
        base_score=data.base_score if data.base_score is not None else Decimal("0"),
        is_active=True,
    )
    db.add(o)
    db.commit()
    o = db.execute(
        select(CharacteristicOption).options(selectinload(CharacteristicOption.order_rules)).where(CharacteristicOption.id == o.id)
    ).scalar_one()
    return _option_out(o)


def update_option(db: Session, option_id: uuid.UUID, data: OptionIn) -> OptionAdminOut:
    o = db.execute(
        select(CharacteristicOption).options(selectinload(CharacteristicOption.order_rules)).where(CharacteristicOption.id == option_id)
    ).scalar_one_or_none()
    if not o:
        raise HTTPException(404, "Subtipo no encontrado")
    o.label = data.label.strip()
    o.description = data.description
    o.sort_order = data.sort_order
    if data.base_score is not None:
        o.base_score = data.base_score
    o.is_active = data.is_active
    db.commit()
    o = db.execute(
        select(CharacteristicOption)
        .options(selectinload(CharacteristicOption.order_rules))
        .where(CharacteristicOption.id == option_id)
    ).scalar_one()
    return _option_out(o)


def soft_delete_option(db: Session, option_id: uuid.UUID) -> OptionAdminOut:
    o = db.execute(
        select(CharacteristicOption).options(selectinload(CharacteristicOption.order_rules)).where(CharacteristicOption.id == option_id)
    ).scalar_one_or_none()
    if not o:
        raise HTTPException(404, "Subtipo no encontrado")
    o.is_active = False
    db.commit()
    db.refresh(o)
    return _option_out(o)


def reorder_options(db: Session, group_id: uuid.UUID, ordered_ids: list[uuid.UUID]) -> list[OptionAdminOut]:
    for i, oid in enumerate(ordered_ids, start=1):
        o = db.get(CharacteristicOption, oid)
        if o and o.group_id == group_id:
            o.sort_order = i * 10
    db.commit()
    return list_options_admin(db, group_id)


async def upload_option_image(db: Session, option_id: uuid.UUID, user: User, upload: UploadFile) -> OptionAdminOut:
    o = db.execute(
        select(CharacteristicOption).options(selectinload(CharacteristicOption.order_rules)).where(CharacteristicOption.id == option_id)
    ).scalar_one_or_none()
    if not o:
        raise HTTPException(404, "Subtipo no encontrado")
    mt = db.execute(select(MediaType).where(MediaType.code == "catalog_material")).scalar_one_or_none()
    if not mt:
        raise HTTPException(500, "media_type catalog_material no configurado")

    raw = await upload.read()
    if not raw:
        raise HTTPException(400, "Archivo vacío")
    try:
        img = Image.open(BytesIO(raw))
        img.load()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, "Imagen inválida") from exc
    if img.mode == "RGBA":
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[-1])
        img = bg
    elif img.mode != "RGB":
        img = img.convert("RGB")

    buf = BytesIO()
    img.save(buf, format="WEBP", quality=82, method=4)
    data = buf.getvalue()
    checksum = hashlib.sha256(data).hexdigest()

    # Siempre un file_id nuevo: cambia la URL /media/{id} y evita que el navegador
    # reutilice la miniatura anterior en caché (síntoma: «se guarda y vuelve la vieja»).
    old_id = o.image_file_id
    old_row = db.get(DocumentFile, old_id) if old_id else None
    old_key = (old_row.storage_key or "").replace("\\", "/") if old_row else None

    file_id = uuid.uuid4()
    rel = f"catalog/materials/{o.code}-{file_id}.webp".replace("\\", "/")
    dest = UPLOAD_ROOT / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)

    row = DocumentFile(
        id=file_id,
        entity_type="characteristic_option",
        entity_id=o.id,
        media_type_id=mt.id,
        storage_backend="local",
        storage_key=rel,
        original_name=upload.filename,
        mime_type="image/webp",
        size_bytes=len(data),
        checksum_sha256=checksum,
        width_px=img.width,
        height_px=img.height,
        uploaded_by=user.id,
    )
    db.add(row)
    # Flush del INSERT antes del UPDATE de image_file_id (no hay relationship ORM → FK).
    db.flush()
    o.image_file_id = file_id
    db.flush()
    if old_row is not None:
        db.delete(old_row)
    db.commit()

    if old_key:
        old_path = UPLOAD_ROOT / old_key
        try:
            if old_path.exists() and old_path.resolve() != dest.resolve():
                old_path.unlink(missing_ok=True)
        except OSError:
            pass

    o = db.execute(
        select(CharacteristicOption)
        .options(selectinload(CharacteristicOption.order_rules))
        .where(CharacteristicOption.id == option_id)
    ).scalar_one()
    out = _option_out(o)
    if out.image_url:
        out = out.model_copy(update={"image_url": f"{out.image_url}?v={checksum[:12]}"})
    return out


def upsert_order_rule(db: Session, option_id: uuid.UUID, data: OrderRuleIn, rule_id: uuid.UUID | None = None) -> OrderRuleOut:
    o = db.get(CharacteristicOption, option_id)
    if not o:
        raise HTTPException(404, "Subtipo no encontrado")
    if data.year_to is not None and data.year_to < data.year_from:
        raise HTTPException(400, "year_to debe ser >= year_from")
    if rule_id:
        rule = db.get(CharacteristicOptionOrderRule, rule_id)
        if not rule or rule.option_id != option_id:
            raise HTTPException(404, "Regla no encontrada")
    else:
        rule = CharacteristicOptionOrderRule(option_id=option_id)
        db.add(rule)
    rule.sort_order = data.sort_order
    rule.year_from = data.year_from
    rule.year_to = data.year_to
    rule.notes = data.notes
    rule.is_active = data.is_active
    rule.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(rule)
    return OrderRuleOut(
        id=rule.id,
        option_id=rule.option_id,
        sort_order=rule.sort_order,
        year_from=rule.year_from,
        year_to=rule.year_to,
        notes=rule.notes,
        is_active=rule.is_active,
    )


def delete_order_rule(db: Session, rule_id: uuid.UUID) -> None:
    rule = db.get(CharacteristicOptionOrderRule, rule_id)
    if not rule:
        raise HTTPException(404, "Regla no encontrada")
    db.delete(rule)
    db.commit()


def list_values(db: Session) -> list[ValueRowOut]:
    groups = db.execute(
        select(CharacteristicGroup)
        .options(selectinload(CharacteristicGroup.options))
        .order_by(CharacteristicGroup.sort_order)
    ).scalars().all()
    out: list[ValueRowOut] = []
    for g in groups:
        for o in sorted(g.options, key=lambda x: x.sort_order):
            out.append(
                ValueRowOut(
                    group_id=g.id,
                    group_code=g.code,
                    group_name=g.name,
                    group_sort=g.sort_order,
                    option_id=o.id,
                    option_code=o.code,
                    option_label=o.label,
                    option_sort=o.sort_order,
                    base_score=o.base_score,
                    is_active=o.is_active,
                    image_url=f"/api/v1/media/{o.image_file_id}" if o.image_file_id else None,
                )
            )
    return out


def update_value(db: Session, option_id: uuid.UUID, base_score: Decimal) -> ValueRowOut:
    o = db.get(CharacteristicOption, option_id)
    if not o:
        raise HTTPException(404, "Subtipo no encontrado")
    o.base_score = base_score
    db.commit()
    g = db.get(CharacteristicGroup, o.group_id)
    assert g
    return ValueRowOut(
        group_id=g.id,
        group_code=g.code,
        group_name=g.name,
        group_sort=g.sort_order,
        option_id=o.id,
        option_code=o.code,
        option_label=o.label,
        option_sort=o.sort_order,
        base_score=o.base_score,
        is_active=o.is_active,
        image_url=f"/api/v1/media/{o.image_file_id}" if o.image_file_id else None,
    )


def effective_sort(option: CharacteristicOption, construction_year: int | None) -> int:
    if construction_year is None:
        return option.sort_order
    matched = [
        r
        for r in option.order_rules
        if r.is_active and r.year_from <= construction_year and (r.year_to is None or construction_year <= r.year_to)
    ]
    if not matched:
        return option.sort_order
    # regla más específica: mayor year_from
    matched.sort(key=lambda r: r.year_from, reverse=True)
    return matched[0].sort_order
