import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import CITEXT, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Role(Base):
    __tablename__ = "roles"
    __table_args__ = {"schema": "auth"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": "auth"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    email: Mapped[str] = mapped_column(CITEXT, unique=True, nullable=False)
    username: Mapped[str | None] = mapped_column(CITEXT, unique=True)
    password_hash: Mapped[str | None] = mapped_column(Text)
    first_name: Mapped[str] = mapped_column(String(120), nullable=False)
    last_name: Mapped[str] = mapped_column(String(120), nullable=False)
    document_number: Mapped[str | None] = mapped_column(String(40))
    professional_reg: Mapped[str | None] = mapped_column(String(40))
    auxiliary_email: Mapped[str | None] = mapped_column(CITEXT)
    phone: Mapped[str | None] = mapped_column(String(40))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    must_have_professional_reg: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    must_change_password: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))


class UserRole(Base):
    __tablename__ = "user_roles"
    __table_args__ = (UniqueConstraint("user_id", "role_id"), {"schema": "auth"})

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("auth.users.id", ondelete="CASCADE"), primary_key=True)
    role_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("auth.roles.id", ondelete="CASCADE"), primary_key=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assigned_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("auth.users.id"))


class WorkflowStatus(Base):
    __tablename__ = "workflow_statuses"
    __table_args__ = {"schema": "config"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class CatalogType(Base):
    __tablename__ = "catalog_types"
    __table_args__ = {"schema": "config"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    code: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))


class CatalogItem(Base):
    __tablename__ = "catalog_items"
    __table_args__ = {"schema": "config"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    catalog_type_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("config.catalog_types.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    numeric_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    description: Mapped[str | None] = mapped_column(Text)
    attributes_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))


class Appraisal(Base):
    __tablename__ = "appraisals"
    __table_args__ = {"schema": "catastro"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    form_number: Mapped[str | None] = mapped_column(String(40), unique=True)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("auth.users.id"), nullable=False)
    status_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("config.workflow_statuses.id"), nullable=False)
    fiscal_year: Mapped[int | None] = mapped_column(Integer)
    land_area: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default=text("0"))
    blocks_area: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default=text("0"))
    improvements_area: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default=text("0"))
    land_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, server_default=text("0"))
    blocks_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, server_default=text("0"))
    improvements_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, server_default=text("0"))
    total_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, server_default=text("0"))
    valuation_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))

    property: Mapped["Property | None"] = relationship(back_populates="appraisal", uselist=False)
    status: Mapped[WorkflowStatus] = relationship()


class Property(Base):
    __tablename__ = "properties"
    __table_args__ = {"schema": "catastro"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    appraisal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("catastro.appraisals.id", ondelete="CASCADE"))
    cadastral_code: Mapped[str | None] = mapped_column(String(30))
    subdistrict: Mapped[str | None] = mapped_column(String(10))
    block_code: Mapped[str | None] = mapped_column(String(20))
    plot_code: Mapped[str | None] = mapped_column(String(20))
    use_code: Mapped[str | None] = mapped_column(String(10))
    building_code: Mapped[str | None] = mapped_column(String(10))
    floor_code: Mapped[str | None] = mapped_column(String(10))
    unit_code: Mapped[str | None] = mapped_column(String(10))
    property_number: Mapped[str | None] = mapped_column(String(40))
    address: Mapped[str] = mapped_column(Text, nullable=False)
    door_number: Mapped[str | None] = mapped_column(String(30))
    building_name: Mapped[str | None] = mapped_column(String(100))
    block_label: Mapped[str | None] = mapped_column(String(50))
    floor_label: Mapped[str | None] = mapped_column(String(50))
    apartment_label: Mapped[str | None] = mapped_column(String(50))
    pmc: Mapped[str | None] = mapped_column(String(30))
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    map_meta_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'active'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))

    appraisal: Mapped[Appraisal] = relationship(back_populates="property")
    detail: Mapped["PropertyDetail | None"] = relationship(back_populates="property", uselist=False)
    owners: Mapped[list["Owner"]] = relationship(back_populates="property")
    units: Mapped[list["ConstructionUnit"]] = relationship(back_populates="property", cascade="all, delete-orphan")


class PropertyDetail(Base):
    __tablename__ = "property_details"
    __table_args__ = {"schema": "catastro"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    property_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("catastro.properties.id", ondelete="CASCADE"), unique=True)
    zone_item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("config.catalog_items.id"))
    topography_item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("config.catalog_items.id"))
    shape_item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("config.catalog_items.id"))
    location_item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("config.catalog_items.id"))
    road_material_item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("config.catalog_items.id"))
    approved_area: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    front_length: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    depth_length: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    observations: Mapped[str | None] = mapped_column(Text)
    dynamic_values_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))

    property: Mapped[Property] = relationship(back_populates="detail")
    services: Mapped[list["PropertyService"]] = relationship(back_populates="detail", cascade="all, delete-orphan")
    equipments: Mapped[list["PropertyEquipment"]] = relationship(back_populates="detail", cascade="all, delete-orphan")


class PropertyService(Base):
    __tablename__ = "property_services"
    __table_args__ = {"schema": "catastro"}

    property_detail_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("catastro.property_details.id", ondelete="CASCADE"), primary_key=True
    )
    service_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("config.catalog_items.id"), primary_key=True
    )

    detail: Mapped[PropertyDetail] = relationship(back_populates="services")


class PropertyEquipment(Base):
    __tablename__ = "property_equipments"
    __table_args__ = {"schema": "catastro"}

    property_detail_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("catastro.property_details.id", ondelete="CASCADE"), primary_key=True
    )
    equipment_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("config.catalog_items.id"), primary_key=True
    )

    detail: Mapped[PropertyDetail] = relationship(back_populates="equipments")


class Owner(Base):
    __tablename__ = "owners"
    __table_args__ = {"schema": "catastro"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    property_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("catastro.properties.id", ondelete="CASCADE"))
    person_type: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'natural'"))
    first_name: Mapped[str | None] = mapped_column(String(120))
    last_name_1: Mapped[str | None] = mapped_column(String(120))
    last_name_2: Mapped[str | None] = mapped_column(String(120))
    legal_name: Mapped[str | None] = mapped_column(String(200))
    document_number: Mapped[str | None] = mapped_column(String(40))
    document_issued_in: Mapped[int | None] = mapped_column(Integer)
    nit: Mapped[str | None] = mapped_column(String(30))
    ownership_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), server_default=text("100"))
    registry_matricula: Mapped[str | None] = mapped_column(String(30))
    registry_asiento: Mapped[str | None] = mapped_column(String(20))
    registry_fojas: Mapped[int | None] = mapped_column(Integer)
    registry_partida: Mapped[int | None] = mapped_column(Integer)
    deed_number: Mapped[str | None] = mapped_column(String(50))
    deed_date: Mapped[date | None] = mapped_column(Date)
    registry_ddr_date: Mapped[date | None] = mapped_column(Date)
    notary_name: Mapped[str | None] = mapped_column(String(150))
    phone: Mapped[str | None] = mapped_column(String(40))
    email: Mapped[str | None] = mapped_column(CITEXT)
    extra_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))

    property: Mapped[Property] = relationship(back_populates="owners")


class ConstructionUnit(Base):
    __tablename__ = "construction_units"
    __table_args__ = {"schema": "catastro"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    property_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("catastro.properties.id", ondelete="CASCADE"))
    unit_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    unit_number: Mapped[str] = mapped_column(String(20), nullable=False)
    area: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    floors_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    construction_year: Mapped[int] = mapped_column(Integer, nullable=False)
    modification_year: Mapped[int | None] = mapped_column(Integer)
    fiscal_year: Mapped[int | None] = mapped_column(Integer)
    use_coeff_item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("config.catalog_items.id"))
    depreciation_item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("config.catalog_items.id"))
    improvement_type_item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("config.catalog_items.id"))
    typology_item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("config.catalog_items.id"))
    total_score: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), server_default=text("0"))
    unit_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), server_default=text("0"))
    observations: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'active'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))

    property: Mapped[Property] = relationship(back_populates="units")
    characteristic_values: Mapped[list["UnitCharacteristicValue"]] = relationship(
        back_populates="unit", cascade="all, delete-orphan"
    )


class CharacteristicGroup(Base):
    __tablename__ = "characteristic_groups"
    __table_args__ = {"schema": "config"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    code: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    applies_to: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'block'"))
    max_percent: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False, server_default=text("100"))
    icon: Mapped[str | None] = mapped_column(String(50))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("TRUE"))

    options: Mapped[list["CharacteristicOption"]] = relationship(back_populates="group")


class CharacteristicOption(Base):
    __tablename__ = "characteristic_options"
    __table_args__ = {"schema": "config"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    group_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("config.characteristic_groups.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    base_score: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False, server_default=text("0"))
    image_file_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("TRUE"))

    group: Mapped[CharacteristicGroup] = relationship(back_populates="options")
    order_rules: Mapped[list["CharacteristicOptionOrderRule"]] = relationship(
        back_populates="option", cascade="all, delete-orphan"
    )


class CharacteristicOptionOrderRule(Base):
    __tablename__ = "characteristic_option_order_rules"
    __table_args__ = {"schema": "config"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    option_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("config.characteristic_options.id", ondelete="CASCADE")
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    year_from: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1800"))
    year_to: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("TRUE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))

    option: Mapped[CharacteristicOption] = relationship(back_populates="order_rules")


class UnitCharacteristicValue(Base):
    __tablename__ = "unit_characteristic_values"
    __table_args__ = {"schema": "catastro"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    construction_unit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("catastro.construction_units.id", ondelete="CASCADE")
    )
    characteristic_group_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("config.characteristic_groups.id"))
    characteristic_option_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("config.characteristic_options.id"))
    percentage: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False, server_default=text("0"))
    score: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False, server_default=text("0"))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    unit: Mapped[ConstructionUnit] = relationship(back_populates="characteristic_values")


class MediaType(Base):
    __tablename__ = "media_types"
    __table_args__ = {"schema": "config"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False, server_default=text("'photo'"))
    config_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("TRUE"))


class DocumentFile(Base):
    __tablename__ = "files"
    __table_args__ = {"schema": "documents"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    media_type_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("config.media_types.id"))
    storage_backend: Mapped[str] = mapped_column(String(30), nullable=False, server_default=text("'local'"))
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    original_name: Mapped[str | None] = mapped_column(String(255))
    mime_type: Mapped[str | None] = mapped_column(String(100))
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64))
    width_px: Mapped[int | None] = mapped_column(Integer)
    height_px: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("auth.users.id"))
    is_migrated: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("FALSE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
