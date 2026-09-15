from uuid import UUID
from decimal import Decimal

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.services import admin_catalog_service as svc
from app.services import admin_config_service as cfg
from app.services import admin_users_service as users_svc
from app.services import template_service as tpl_svc
from app.services.admin_catalog_service import (
    GroupIn,
    GroupOut,
    OptionAdminOut,
    OptionIn,
    OrderRuleIn,
    OrderRuleOut,
    ValueRowOut,
)
from app.services.admin_config_service import (
    BrandingOut,
    CatalogItemIn,
    CatalogItemOut,
    CatalogTypeOut,
    FormulaOut,
    FormulaUpdateIn,
    FormulaVersionIn,
    MediaTypeAdminIn,
    MediaTypeAdminOut,
    ParamOut,
    ParamUpdateIn,
)
from app.services.admin_users_service import (
    AdminPasswordIn,
    AdminUserProfileIn,
    ExtendExpiryIn,
    RoleOut,
    UserAdminOut,
    UserRolesIn,
)
from app.services.auth_service import get_current_user
from app.services.template_service import TemplateInfo


router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


class ReorderIn(BaseModel):
    ordered_ids: list[UUID]


class ValueUpdateIn(BaseModel):
    base_score: Decimal = Field(ge=0)


def _admin(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    svc.require_admin(db, user)
    return user


@router.get("/characteristic-groups", response_model=list[GroupOut])
def admin_groups(db: Session = Depends(get_db), _: User = Depends(_admin)):
    return svc.list_groups_admin(db)


@router.post("/characteristic-groups", response_model=GroupOut, status_code=201)
def admin_create_group(payload: GroupIn, db: Session = Depends(get_db), _: User = Depends(_admin)):
    return svc.create_group(db, payload)


@router.post("/characteristic-groups/reorder", response_model=list[GroupOut])
def admin_reorder_groups(payload: ReorderIn, db: Session = Depends(get_db), _: User = Depends(_admin)):
    return svc.reorder_groups(db, payload.ordered_ids)


@router.put("/characteristic-groups/{group_id}", response_model=GroupOut)
def admin_update_group(group_id: UUID, payload: GroupIn, db: Session = Depends(get_db), _: User = Depends(_admin)):
    return svc.update_group(db, group_id, payload)


@router.get("/characteristic-groups/{group_id}/options", response_model=list[OptionAdminOut])
def admin_options(group_id: UUID, db: Session = Depends(get_db), _: User = Depends(_admin)):
    return svc.list_options_admin(db, group_id)


@router.post("/characteristic-groups/{group_id}/options", response_model=OptionAdminOut, status_code=201)
def admin_create_option(group_id: UUID, payload: OptionIn, db: Session = Depends(get_db), _: User = Depends(_admin)):
    return svc.create_option(db, group_id, payload)


@router.post("/characteristic-groups/{group_id}/options/reorder", response_model=list[OptionAdminOut])
def admin_reorder_options(group_id: UUID, payload: ReorderIn, db: Session = Depends(get_db), _: User = Depends(_admin)):
    return svc.reorder_options(db, group_id, payload.ordered_ids)


@router.put("/characteristic-options/{option_id}", response_model=OptionAdminOut)
def admin_update_option(option_id: UUID, payload: OptionIn, db: Session = Depends(get_db), _: User = Depends(_admin)):
    return svc.update_option(db, option_id, payload)


@router.delete("/characteristic-groups/{group_id}", response_model=GroupOut)
def admin_soft_delete_group(group_id: UUID, db: Session = Depends(get_db), _: User = Depends(_admin)):
    return svc.soft_delete_group(db, group_id)


@router.delete("/characteristic-options/{option_id}", response_model=OptionAdminOut)
def admin_soft_delete_option(option_id: UUID, db: Session = Depends(get_db), _: User = Depends(_admin)):
    return svc.soft_delete_option(db, option_id)


@router.post("/characteristic-options/{option_id}/image", response_model=OptionAdminOut)
async def admin_option_image(
    option_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(_admin),
):
    return await svc.upload_option_image(db, option_id, user, file)


@router.post("/characteristic-options/{option_id}/order-rules", response_model=OrderRuleOut, status_code=201)
def admin_create_rule(option_id: UUID, payload: OrderRuleIn, db: Session = Depends(get_db), _: User = Depends(_admin)):
    return svc.upsert_order_rule(db, option_id, payload)


@router.put("/characteristic-options/{option_id}/order-rules/{rule_id}", response_model=OrderRuleOut)
def admin_update_rule(
    option_id: UUID,
    rule_id: UUID,
    payload: OrderRuleIn,
    db: Session = Depends(get_db),
    _: User = Depends(_admin),
):
    return svc.upsert_order_rule(db, option_id, payload, rule_id)


@router.delete("/order-rules/{rule_id}", status_code=204)
def admin_delete_rule(rule_id: UUID, db: Session = Depends(get_db), _: User = Depends(_admin)):
    svc.delete_order_rule(db, rule_id)
    return None


@router.get("/characteristic-values", response_model=list[ValueRowOut])
def admin_values(db: Session = Depends(get_db), _: User = Depends(_admin)):
    return svc.list_values(db)


@router.put("/characteristic-values/{option_id}", response_model=ValueRowOut)
def admin_update_value(option_id: UUID, payload: ValueUpdateIn, db: Session = Depends(get_db), _: User = Depends(_admin)):
    return svc.update_value(db, option_id, payload.base_score)


@router.get("/parameters", response_model=list[ParamOut])
def admin_list_parameters(db: Session = Depends(get_db), _: User = Depends(_admin)):
    return cfg.list_parameters(db)


@router.put("/parameters/{key}", response_model=ParamOut)
def admin_update_parameter(key: str, payload: ParamUpdateIn, db: Session = Depends(get_db), user: User = Depends(_admin)):
    return cfg.update_parameter(db, key, payload, user)


@router.get("/branding", response_model=BrandingOut)
def admin_get_branding(db: Session = Depends(get_db), _: User = Depends(_admin)):
    return cfg.get_branding(db)


@router.put("/branding", response_model=BrandingOut)
def admin_save_branding(payload: BrandingOut, db: Session = Depends(get_db), user: User = Depends(_admin)):
    return cfg.save_branding(db, payload, user)


@router.get("/formulas", response_model=list[FormulaOut])
def admin_list_formulas(db: Session = Depends(get_db), _: User = Depends(_admin)):
    return cfg.list_formulas(db)


@router.put("/formulas/{formula_id}", response_model=FormulaOut)
def admin_update_formula(formula_id: UUID, payload: FormulaUpdateIn, db: Session = Depends(get_db), _: User = Depends(_admin)):
    return cfg.update_formula(db, formula_id, payload)


@router.post("/formulas/{formula_id}/versions", response_model=FormulaOut, status_code=201)
def admin_add_formula_version(formula_id: UUID, payload: FormulaVersionIn, db: Session = Depends(get_db), _: User = Depends(_admin)):
    return cfg.add_formula_version(db, formula_id, payload)


@router.get("/catalogs", response_model=list[CatalogTypeOut])
def admin_catalog_types(db: Session = Depends(get_db), _: User = Depends(_admin)):
    return cfg.list_catalog_types(db)


@router.get("/catalogs/{type_code}/items", response_model=list[CatalogItemOut])
def admin_catalog_items(type_code: str, db: Session = Depends(get_db), _: User = Depends(_admin)):
    return cfg.list_catalog_items_admin(db, type_code)


@router.post("/catalogs/{type_code}/items", response_model=CatalogItemOut, status_code=201)
def admin_create_catalog_item(type_code: str, payload: CatalogItemIn, db: Session = Depends(get_db), _: User = Depends(_admin)):
    return cfg.upsert_catalog_item(db, type_code, payload)


@router.put("/catalogs/{type_code}/items/{item_id}", response_model=CatalogItemOut)
def admin_update_catalog_item(
    type_code: str,
    item_id: UUID,
    payload: CatalogItemIn,
    db: Session = Depends(get_db),
    _: User = Depends(_admin),
):
    return cfg.upsert_catalog_item(db, type_code, payload, item_id)


def _sysadmin(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    users_svc.require_system_admin(db, user)
    return user


@router.get("/roles", response_model=list[RoleOut])
def admin_roles(db: Session = Depends(get_db), _: User = Depends(_sysadmin)):
    return users_svc.list_roles(db)


@router.get("/users/search", response_model=list[UserAdminOut])
def admin_search_users(
    q: str = Query(..., min_length=2),
    limit: int = Query(30, ge=1, le=50),
    db: Session = Depends(get_db),
    _: User = Depends(_sysadmin),
):
    return users_svc.search_users(db, q, limit)


@router.get("/users/{user_id}", response_model=UserAdminOut)
def admin_get_user(user_id: UUID, db: Session = Depends(get_db), _: User = Depends(_sysadmin)):
    return users_svc.get_user(db, user_id)


@router.put("/users/{user_id}/roles", response_model=UserAdminOut)
def admin_set_roles(user_id: UUID, payload: UserRolesIn, db: Session = Depends(get_db), admin: User = Depends(_sysadmin)):
    return users_svc.set_roles(db, admin, user_id, payload)


@router.put("/users/{user_id}/extend", response_model=UserAdminOut)
def admin_extend_user(user_id: UUID, payload: ExtendExpiryIn, db: Session = Depends(get_db), admin: User = Depends(_sysadmin)):
    return users_svc.extend_expiry(db, admin, user_id, payload)


@router.put("/users/{user_id}/extend-year", response_model=UserAdminOut)
def admin_extend_user_one_year(user_id: UUID, db: Session = Depends(get_db), admin: User = Depends(_sysadmin)):
    return users_svc.extend_one_year(db, admin, user_id)


@router.put("/users/{user_id}/profile", response_model=UserAdminOut)
def admin_update_user_profile(
    user_id: UUID,
    payload: AdminUserProfileIn,
    db: Session = Depends(get_db),
    admin: User = Depends(_sysadmin),
):
    return users_svc.update_profile(db, admin, user_id, payload)


@router.put("/users/{user_id}/password", response_model=UserAdminOut)
def admin_set_user_password(
    user_id: UUID,
    payload: AdminPasswordIn,
    db: Session = Depends(get_db),
    admin: User = Depends(_sysadmin),
):
    return users_svc.set_password(db, admin, user_id, payload)


@router.put("/users/{user_id}/active", response_model=UserAdminOut)
def admin_set_active(user_id: UUID, active: bool = Query(...), db: Session = Depends(get_db), admin: User = Depends(_sysadmin)):
    return users_svc.set_active(db, admin, user_id, active)


@router.delete("/users/{user_id}", response_model=UserAdminOut)
def admin_soft_delete_user(user_id: UUID, db: Session = Depends(get_db), admin: User = Depends(_sysadmin)):
    return users_svc.soft_delete(db, admin, user_id)


@router.get("/media-types", response_model=list[MediaTypeAdminOut])
def admin_list_media_types(
    category: str | None = Query(default="photo"),
    db: Session = Depends(get_db),
    _: User = Depends(_admin),
):
    return cfg.list_media_types_admin(db, category)


@router.post("/media-types", response_model=MediaTypeAdminOut, status_code=201)
def admin_create_media_type(payload: MediaTypeAdminIn, db: Session = Depends(get_db), _: User = Depends(_admin)):
    return cfg.create_media_type(db, payload)


@router.put("/media-types/{type_id}", response_model=MediaTypeAdminOut)
def admin_update_media_type(
    type_id: UUID,
    payload: MediaTypeAdminIn,
    db: Session = Depends(get_db),
    _: User = Depends(_admin),
):
    return cfg.update_media_type(db, type_id, payload)


@router.delete("/media-types/{type_id}", response_model=MediaTypeAdminOut)
def admin_deactivate_media_type(type_id: UUID, db: Session = Depends(get_db), _: User = Depends(_admin)):
    return cfg.deactivate_media_type(db, type_id)


# ── Plantillas Word ──────────────────────────────────────────────────────────


@router.get("/templates", response_model=list[TemplateInfo])
def admin_list_templates(_: User = Depends(_admin)):
    return tpl_svc.list_templates()


@router.get("/templates/{code}", response_model=TemplateInfo)
def admin_get_template(code: str, _: User = Depends(_admin)):
    return tpl_svc.get_template(code)


@router.get("/templates/{code}/download")
def admin_download_template(code: str, _: User = Depends(_admin)):
    data, filename = tpl_svc.read_active_bytes(code)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/templates/{code}/blank")
def admin_download_blank_template(code: str, _: User = Depends(_admin)):
    data, filename = tpl_svc.read_blank_bytes(code)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/templates/{code}", response_model=TemplateInfo)
async def admin_upload_template(
    code: str,
    file: UploadFile = File(...),
    _: User = Depends(_admin),
):
    return await tpl_svc.upload_template(code, file)


@router.delete("/templates/{code}", response_model=TemplateInfo)
def admin_restore_template(code: str, _: User = Depends(_admin)):
    return tpl_svc.restore_builtin(code)
