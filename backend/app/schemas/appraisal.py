from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class CatalogOption(BaseModel):
    id: UUID
    code: str
    label: str
    numeric_value: Decimal | None = None
    description: str | None = None


class OwnerIn(BaseModel):
    person_type: str = Field(default="natural", pattern="^(natural|legal)$")
    first_name: str | None = None
    last_name_1: str | None = None
    last_name_2: str | None = None
    legal_name: str | None = None
    document_number: str | None = Field(default=None, min_length=5, max_length=40)
    ownership_percent: Decimal = Field(default=Decimal("100"), ge=0, le=100)
    phone: str | None = Field(default=None, max_length=40, description="Teléfono / WhatsApp")
    email: EmailStr | None = None
    registry_matricula: str | None = None
    registry_asiento: str | None = None
    registry_fojas: int | None = None
    registry_partida: int | None = None
    deed_number: str | None = None
    deed_date: date | None = None
    registry_ddr_date: date | None = None
    notary_name: str | None = None


class OwnerPutIn(OwnerIn):
    address: str | None = Field(default=None, max_length=300)
    door_number: str | None = None


class PropertyDetailIn(BaseModel):
    approved_area: Decimal = Field(gt=0)
    front_length: Decimal = Field(ge=0)
    depth_length: Decimal | None = Field(default=None, ge=0)
    zone_item_id: UUID
    topography_item_id: UUID
    shape_item_id: UUID
    location_item_id: UUID
    road_material_item_id: UUID
    service_item_ids: list[UUID] = []
    equipment_item_ids: list[UUID] = []
    observations: str | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    registry_matricula: str | None = None
    registry_asiento: str | None = None
    registry_ddr_date: date | None = None
    building_name: str | None = Field(default=None, max_length=100)
    block_label: str | None = Field(default=None, max_length=50)
    floor_label: str | None = Field(default=None, max_length=50)
    apartment_label: str | None = Field(default=None, max_length=50)


class CadastralCodeIn(BaseModel):
    subdistrict: str = Field(min_length=1, max_length=10)
    block_code: str = Field(min_length=1, max_length=20)
    plot_code: str = Field(min_length=1, max_length=20)
    use_code: str | None = Field(default="0", max_length=10)
    building_code: str | None = Field(default="0", max_length=10)
    floor_code: str | None = Field(default="0", max_length=10)
    unit_code: str | None = Field(default="0", max_length=10)
    door_number: str | None = None
    building_name: str | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    address: str | None = Field(default=None, max_length=300)


class AppraisalCreateIn(BaseModel):
    address: str = Field(min_length=3, max_length=300)
    door_number: str | None = None
    owner: OwnerIn
    latitude: Decimal | None = Field(default=Decimal("-17.3935"))
    longitude: Decimal | None = Field(default=Decimal("-66.1570"))


class OwnerOut(OwnerIn):
    id: UUID


class PropertyDetailOut(BaseModel):
    approved_area: Decimal | None = None
    front_length: Decimal | None = None
    depth_length: Decimal | None = None
    zone_item_id: UUID | None = None
    topography_item_id: UUID | None = None
    shape_item_id: UUID | None = None
    location_item_id: UUID | None = None
    road_material_item_id: UUID | None = None
    service_item_ids: list[UUID] = []
    equipment_item_ids: list[UUID] = []
    observations: str | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    registry_matricula: str | None = None
    registry_asiento: str | None = None
    registry_ddr_date: date | None = None
    building_name: str | None = None
    block_label: str | None = None
    floor_label: str | None = None
    apartment_label: str | None = None


class AppraisalListItem(BaseModel):
    id: UUID
    form_number: str | None
    status_code: str
    status_name: str
    address: str | None = None
    owner_name: str | None = None
    owner_document: str | None = None
    approved_area: Decimal | None = None
    created_at: str
    cadastral_code: str | None = None
    is_own: bool = True


class ConstructionUnitOut(BaseModel):
    id: UUID
    unit_kind: str
    unit_number: str
    area: Decimal
    floors_count: int
    construction_year: int
    modification_year: int | None = None
    observations: str | None = None
    characteristics: list["UnitCharacteristicOut"] = []
    total_score: Decimal | None = None
    use_coeff_item_id: UUID | None = None
    depreciation_item_id: UUID | None = None
    improvement_type_item_id: UUID | None = None
    unit_value: Decimal | None = None


class ConstructionUnitIn(BaseModel):
    unit_kind: str = Field(default="block", pattern="^(block|improvement)$")
    unit_number: str = Field(min_length=1, max_length=20)
    area: Decimal = Field(gt=0)
    floors_count: int = Field(default=1, ge=1, le=100)
    construction_year: int = Field(ge=1800, le=2100)
    modification_year: int | None = Field(default=None, ge=1800, le=2100)
    observations: str | None = None
    use_coeff_item_id: UUID | None = None
    depreciation_item_id: UUID | None = None
    improvement_type_item_id: UUID | None = None


class CharacteristicOptionOut(BaseModel):
    id: UUID
    code: str
    label: str
    description: str | None = None
    sort_order: int
    image_url: str | None = None
    # base_score NO se expone al contribuyente (evita declaración a la baja)


class CharacteristicGroupOut(BaseModel):
    id: UUID
    code: str
    name: str
    sort_order: int
    applies_to: str
    max_percent: Decimal
    options: list[CharacteristicOptionOut] = []


class UnitCharacteristicOut(BaseModel):
    group_id: UUID
    group_code: str
    group_name: str
    option_id: UUID
    option_label: str
    percentage: Decimal
    score: Decimal
    base_score: Decimal


class UnitCharacteristicIn(BaseModel):
    option_id: UUID
    percentage: Decimal = Field(default=Decimal("100"), ge=0, le=100)


class UnitCharacteristicsSaveIn(BaseModel):
    items: list[UnitCharacteristicIn]


class MediaTypeOut(BaseModel):
    id: UUID
    code: str
    name: str
    category: str


class PhotoTypeUpdateIn(BaseModel):
    media_type_code: str = Field(min_length=1, max_length=50)


class PhotoOut(BaseModel):
    id: UUID
    media_type_code: str
    media_type_name: str
    original_name: str | None = None
    url: str
    width_px: int | None = None
    height_px: int | None = None
    created_at: str


class ObservationBatchOut(BaseModel):
    id: UUID
    observations: list[str]
    reviewed_by: str
    reviewed_at: datetime


class AppraisalDetailOut(BaseModel):
    id: UUID
    form_number: str | None
    status_code: str
    status_name: str
    fiscal_year: int | None
    address: str
    door_number: str | None = None
    building_name: str | None = None
    block_label: str | None = None
    floor_label: str | None = None
    apartment_label: str | None = None
    cadastral_code: str | None = None
    subdistrict: str | None = None
    block_code: str | None = None
    plot_code: str | None = None
    use_code: str | None = None
    building_code: str | None = None
    floor_code: str | None = None
    unit_code: str | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    owner: OwnerOut | None = None
    detail: PropertyDetailOut | None = None
    blocks: list[ConstructionUnitOut] = []
    photos: list[PhotoOut] = []
    created_at: str
    can_edit: bool = True
    is_own: bool = True
    can_enable_correction: bool = False
    can_migrate: bool = False
    is_remigration: bool = False
