from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, select, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship, selectinload

from app.db import Base
from app.models import User
from app.services.auth_service import _roles_of


ADMIN_ROLES = {"system_admin", "catalog_admin"}


def require_admin(db: Session, user: User) -> list[str]:
    roles = _roles_of(db, user.id)
    if not ADMIN_ROLES.intersection(roles):
        raise HTTPException(403, "Se requiere rol de administrador")
    return roles


class SystemParameter(Base):
    __tablename__ = "system_parameters"
    __table_args__ = {"schema": "config"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    value_json: Mapped[Any] = mapped_column(JSONB, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    value_type: Mapped[str] = mapped_column(String(30), nullable=False, server_default=text("'json'"))
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("FALSE"))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("auth.users.id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))


class FormulaDefinition(Base):
    __tablename__ = "formula_definitions"
    __table_args__ = {"schema": "config"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    code: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    output_type: Mapped[str] = mapped_column(String(30), nullable=False, server_default=text("'decimal'"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("TRUE"))

    versions: Mapped[list["FormulaVersion"]] = relationship(back_populates="formula", cascade="all, delete-orphan")


class FormulaVersion(Base):
    __tablename__ = "formula_versions"
    __table_args__ = {"schema": "config"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    formula_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("config.formula_definitions.id", ondelete="CASCADE"))
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    expression: Mapped[str] = mapped_column(Text, nullable=False)
    variables_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    conditions_json: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    fiscal_year: Mapped[int | None] = mapped_column(Integer)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False, server_default=text("CURRENT_DATE"))
    valid_to: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("TRUE"))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))

    formula: Mapped[FormulaDefinition] = relationship(back_populates="versions")


class ParamOut(BaseModel):
    key: str
    value_json: Any
    description: str | None = None
    value_type: str
    is_public: bool


class ParamUpdateIn(BaseModel):
    value_json: Any
    description: str | None = None
    is_public: bool | None = None


class BrandingOut(BaseModel):
    org: str = "Gobierno Autónomo Municipal de Cochabamba"
    unit: str = "Dirección de Administración Geográfica y Catastro"
    portal: str = "Portal de Catastro Municipal"
    slogan: str = "Trámite claro y cercano para el avalúo de su predio."
    tagline: str = "Cocha es progreso"
    colors: dict[str, str] = Field(
        default_factory=lambda: {
            "navy": "#00A7D6",
            "navy2": "#0078A8",
            "blue": "#00A7D6",
            "blueSoft": "#E8F7FB",
            "ink": "#12323C",
            "muted": "#4A6B75",
            "bg": "#F3FAFC",
        }
    )
    logo_url: str | None = "/brand/cocha-cyan.png"


class FormulaVersionOut(BaseModel):
    id: uuid.UUID
    version: int
    expression: str
    variables_json: dict
    fiscal_year: int | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    is_active: bool
    notes: str | None = None


class FormulaOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    description: str | None = None
    output_type: str
    is_active: bool
    versions: list[FormulaVersionOut] = []


class FormulaUpdateIn(BaseModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None


class FormulaVersionIn(BaseModel):
    expression: str = Field(min_length=1)
    variables_json: dict = Field(default_factory=dict)
    fiscal_year: int | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    notes: str | None = None
    is_active: bool = True


def list_parameters(db: Session, public_only: bool = False) -> list[ParamOut]:
    from app.services.gis_layers import get_gis_layers

    q = select(SystemParameter).order_by(SystemParameter.key)
    if public_only:
        q = q.where(SystemParameter.is_public.is_(True))
    rows = db.execute(q).scalars().all()
    out: list[ParamOut] = []
    for r in rows:
        value = r.value_json
        if r.key == "gis_layers":
            value = get_gis_layers(db)
        out.append(
            ParamOut(
                key=r.key,
                value_json=value,
                description=r.description,
                value_type=r.value_type,
                is_public=r.is_public,
            )
        )
    return out


def update_parameter(db: Session, key: str, data: ParamUpdateIn, user: User) -> ParamOut:
    row = db.execute(select(SystemParameter).where(SystemParameter.key == key)).scalar_one_or_none()
    if not row:
        raise HTTPException(404, f"Parámetro '{key}' no encontrado")
    row.value_json = data.value_json
    if data.description is not None:
        row.description = data.description
    if data.is_public is not None:
        row.is_public = data.is_public
    row.updated_by = user.id
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    return ParamOut(key=row.key, value_json=row.value_json, description=row.description, value_type=row.value_type, is_public=row.is_public)


def get_branding(db: Session) -> BrandingOut:
    row = db.execute(select(SystemParameter).where(SystemParameter.key == "branding")).scalar_one_or_none()
    base = BrandingOut()
    if not row or not isinstance(row.value_json, dict):
        return base
    data = dict(row.value_json)
    colors = {**base.colors, **(data.get("colors") or {})}
    return BrandingOut(
        org=data.get("org") or base.org,
        unit=data.get("unit") or base.unit,
        portal=data.get("portal") or base.portal,
        slogan=data.get("slogan") or base.slogan,
        tagline=data.get("tagline") or base.tagline,
        colors=colors,
        logo_url=data.get("logo_url"),
    )


def save_branding(db: Session, branding: BrandingOut, user: User) -> BrandingOut:
    payload = branding.model_dump()
    row = db.execute(select(SystemParameter).where(SystemParameter.key == "branding")).scalar_one_or_none()
    if not row:
        row = SystemParameter(
            key="branding",
            value_json=payload,
            description="Identidad institucional del portal",
            value_type="json",
            is_public=True,
        )
        db.add(row)
    else:
        row.value_json = payload
        row.is_public = True
        row.updated_by = user.id
        row.updated_at = datetime.now(timezone.utc)
    db.commit()
    return get_branding(db)


def list_formulas(db: Session) -> list[FormulaOut]:
    rows = db.execute(
        select(FormulaDefinition).options(selectinload(FormulaDefinition.versions)).order_by(FormulaDefinition.code)
    ).scalars().all()
    out: list[FormulaOut] = []
    for f in rows:
        versions = sorted(f.versions, key=lambda v: v.version, reverse=True)
        out.append(
            FormulaOut(
                id=f.id,
                code=f.code,
                name=f.name,
                description=f.description,
                output_type=f.output_type,
                is_active=f.is_active,
                versions=[
                    FormulaVersionOut(
                        id=v.id,
                        version=v.version,
                        expression=v.expression,
                        variables_json=v.variables_json or {},
                        fiscal_year=v.fiscal_year,
                        valid_from=v.valid_from,
                        valid_to=v.valid_to,
                        is_active=v.is_active,
                        notes=v.notes,
                    )
                    for v in versions
                ],
            )
        )
    return out


def update_formula(db: Session, formula_id: uuid.UUID, data: FormulaUpdateIn) -> FormulaOut:
    f = db.get(FormulaDefinition, formula_id)
    if not f:
        raise HTTPException(404, "Fórmula no encontrada")
    if data.name is not None:
        f.name = data.name
    if data.description is not None:
        f.description = data.description
    if data.is_active is not None:
        f.is_active = data.is_active
    db.commit()
    return next(x for x in list_formulas(db) if x.id == formula_id)


def add_formula_version(db: Session, formula_id: uuid.UUID, data: FormulaVersionIn) -> FormulaOut:
    f = db.execute(
        select(FormulaDefinition).options(selectinload(FormulaDefinition.versions)).where(FormulaDefinition.id == formula_id)
    ).scalar_one_or_none()
    if not f:
        raise HTTPException(404, "Fórmula no encontrada")
    next_ver = (max((v.version for v in f.versions), default=0) + 1)
    # desactivar anteriores activas
    for v in f.versions:
        if v.is_active:
            v.is_active = False
    db.add(
        FormulaVersion(
            formula_id=f.id,
            version=next_ver,
            expression=data.expression,
            variables_json=data.variables_json,
            fiscal_year=data.fiscal_year,
            valid_from=data.valid_from or date.today(),
            valid_to=data.valid_to,
            notes=data.notes,
            is_active=data.is_active,
        )
    )
    db.commit()
    return next(x for x in list_formulas(db) if x.id == formula_id)


CATALOG_CODES = [
    "zone_homogeneous",
    "utility_service",
    "ipes_factor",
    "topography",
    "road_material",
    "parcel_location",
    "parcel_shape",
    "construction_typology",
    "land_use",
    "depreciation",
    "improvement_type",
    "improvement_typology",
]


class CatalogTypeOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    is_active: bool
    items_count: int = 0


class CatalogItemOut(BaseModel):
    id: uuid.UUID
    catalog_type_id: uuid.UUID
    type_code: str
    code: str
    label: str
    sort_order: int
    numeric_value: float | None = None
    attributes_json: dict = Field(default_factory=dict)
    description: str | None = None
    is_active: bool


class CatalogItemIn(BaseModel):
    code: str | None = Field(default=None, max_length=80)
    label: str = Field(min_length=1, max_length=200)
    sort_order: int = 0
    numeric_value: float | None = None
    attributes_json: dict | None = None
    description: str | None = None
    is_active: bool = True


def list_catalog_types(db: Session) -> list[CatalogTypeOut]:
    from sqlalchemy import func

    from app.models import CatalogItem, CatalogType

    counts = dict(
        db.execute(
            select(CatalogItem.catalog_type_id, func.count()).group_by(CatalogItem.catalog_type_id)
        ).all()
    )
    rows = db.execute(select(CatalogType).order_by(CatalogType.name)).scalars().all()
    preferred = {c: i for i, c in enumerate(CATALOG_CODES)}
    rows = sorted(rows, key=lambda r: (preferred.get(r.code, 99), r.name))
    return [
        CatalogTypeOut(
            id=r.id,
            code=r.code,
            name=r.name,
            is_active=r.is_active,
            items_count=int(counts.get(r.id, 0)),
        )
        for r in rows
    ]


def list_catalog_items_admin(db: Session, type_code: str) -> list[CatalogItemOut]:
    from app.models import CatalogItem, CatalogType

    t = db.execute(select(CatalogType).where(CatalogType.code == type_code)).scalar_one_or_none()
    if not t:
        raise HTTPException(404, f"Catálogo '{type_code}' no encontrado")
    rows = db.execute(
        select(CatalogItem)
        .where(CatalogItem.catalog_type_id == t.id)
        .order_by(CatalogItem.sort_order, CatalogItem.label)
    ).scalars().all()
    return [
        CatalogItemOut(
            id=r.id,
            catalog_type_id=r.catalog_type_id,
            type_code=t.code,
            code=r.code,
            label=r.label,
            sort_order=r.sort_order,
            numeric_value=float(r.numeric_value) if r.numeric_value is not None else None,
            attributes_json=r.attributes_json or {},
            description=r.description,
            is_active=r.is_active,
        )
        for r in rows
    ]


def upsert_catalog_item(
    db: Session, type_code: str, data: CatalogItemIn, item_id: uuid.UUID | None = None
) -> CatalogItemOut:
    from app.models import CatalogItem, CatalogType

    t = db.execute(select(CatalogType).where(CatalogType.code == type_code)).scalar_one_or_none()
    if not t:
        raise HTTPException(404, f"Catálogo '{type_code}' no encontrado")
    if item_id:
        row = db.get(CatalogItem, item_id)
        if not row or row.catalog_type_id != t.id:
            raise HTTPException(404, "Ítem no encontrado")
    else:
        code = (data.code or "").strip() or data.label.upper().replace(" ", "-")[:80]
        row = CatalogItem(catalog_type_id=t.id, code=code)
        db.add(row)
    if data.code:
        row.code = data.code.strip()
    row.label = data.label.strip()
    row.sort_order = data.sort_order
    row.numeric_value = data.numeric_value
    attrs = dict(data.attributes_json or row.attributes_json or {})
    if data.numeric_value is not None and "coeficiente" not in attrs and t.code != "zone_homogeneous":
        attrs["coeficiente"] = data.numeric_value
    if data.numeric_value is not None and t.code == "zone_homogeneous":
        attrs.setdefault("valor_catastral_m2", data.numeric_value)
    row.attributes_json = attrs
    row.description = data.description
    row.is_active = data.is_active
    db.commit()
    db.refresh(row)
    return CatalogItemOut(
        id=row.id,
        catalog_type_id=row.catalog_type_id,
        type_code=t.code,
        code=row.code,
        label=row.label,
        sort_order=row.sort_order,
        numeric_value=float(row.numeric_value) if row.numeric_value is not None else None,
        attributes_json=row.attributes_json or {},
        description=row.description,
        is_active=row.is_active,
    )


class MediaTypeAdminOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    category: str
    sort_order: int
    is_active: bool
    config_json: dict = {}


class MediaTypeAdminIn(BaseModel):
    code: str | None = None
    name: str = Field(min_length=2, max_length=100)
    category: str = Field(default="photo", pattern="^(photo|document|pdf|catalog|other)$")
    sort_order: int = 0
    is_active: bool = True


def _media_type_code(name: str, category: str) -> str:
    import re
    import unicodedata

    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-zA-Z0-9]+", "_", s).strip("_").lower()[:40] or "tipo"
    if category == "photo" and not s.startswith("photo_"):
        s = f"photo_{s}"
    return s[:50]


def _media_out(row) -> MediaTypeAdminOut:
    return MediaTypeAdminOut(
        id=row.id,
        code=row.code,
        name=row.name,
        category=row.category,
        sort_order=row.sort_order,
        is_active=row.is_active,
        config_json=row.config_json or {},
    )


def list_media_types_admin(db: Session, category: str | None = None) -> list[MediaTypeAdminOut]:
    from app.models import MediaType

    q = select(MediaType).order_by(MediaType.category, MediaType.sort_order, MediaType.name)
    if category:
        q = q.where(MediaType.category == category)
    return [_media_out(r) for r in db.execute(q).scalars().all()]


def create_media_type(db: Session, data: MediaTypeAdminIn) -> MediaTypeAdminOut:
    from app.models import MediaType

    code = (data.code or "").strip() or _media_type_code(data.name, data.category)
    exists = db.execute(select(MediaType).where(MediaType.code == code)).scalar_one_or_none()
    if exists:
        raise HTTPException(400, f"Ya existe un tipo con código '{code}'")
    row = MediaType(
        code=code,
        name=data.name.strip(),
        category=data.category,
        sort_order=data.sort_order,
        is_active=data.is_active,
        config_json={"accept": ["image/jpeg", "image/png", "image/webp"], "max_mb": 8},
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _media_out(row)


def update_media_type(db: Session, type_id: uuid.UUID, data: MediaTypeAdminIn) -> MediaTypeAdminOut:
    from app.models import MediaType

    row = db.get(MediaType, type_id)
    if not row:
        raise HTTPException(404, "Tipo de fotografía no encontrado")
    new_code = (data.code or "").strip() or row.code
    if new_code != row.code:
        exists = db.execute(select(MediaType).where(MediaType.code == new_code, MediaType.id != row.id)).scalar_one_or_none()
        if exists:
            raise HTTPException(400, f"Ya existe un tipo con código '{new_code}'")
        row.code = new_code
    row.name = data.name.strip()
    row.category = data.category
    row.sort_order = data.sort_order
    row.is_active = data.is_active
    db.commit()
    db.refresh(row)
    return _media_out(row)


def deactivate_media_type(db: Session, type_id: uuid.UUID) -> MediaTypeAdminOut:
    from app.models import MediaType

    row = db.get(MediaType, type_id)
    if not row:
        raise HTTPException(404, "Tipo de fotografía no encontrado")
    row.is_active = False
    db.commit()
    db.refresh(row)
    return _media_out(row)
