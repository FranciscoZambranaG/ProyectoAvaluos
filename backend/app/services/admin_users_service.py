from __future__ import annotations

import re
import uuid
from datetime import date, datetime, timezone

from fastapi import HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.models import Role, User, UserRole
from app.security import hash_password
from app.services.auth_service import _roles_of

PASSWORD_POLICY = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$")

ADMIN_ONLY = {"system_admin"}
MANAGE_ROLES = {"system_admin"}  # solo admin asigna roles / inhabilita

# Códigos internos → etiqueta UI
ROLE_LABELS = {
    "citizen": "Contribuyente",
    "technical_architect": "Funcionario",
    "system_admin": "Administrador",
    "catalog_admin": "Admin de catálogos",
}

ASSIGNABLE = ("citizen", "technical_architect", "system_admin", "catalog_admin")


def require_system_admin(db: Session, user: User) -> None:
    roles = _roles_of(db, user.id)
    if not ADMIN_ONLY.intersection(roles):
        raise HTTPException(403, "Solo el administrador puede gestionar usuarios")


class RoleOut(BaseModel):
    code: str
    name: str
    description: str | None = None


class UserAdminOut(BaseModel):
    id: uuid.UUID
    email: str
    username: str | None = None
    first_name: str
    last_name: str
    document_number: str | None = None
    professional_reg: str | None = None
    auxiliary_email: str | None = None
    phone: str | None = None
    is_active: bool
    roles: list[str]
    role_labels: list[str]
    expires_at: datetime | None = None
    deleted_at: datetime | None = None
    created_at: datetime | None = None
    last_login_at: datetime | None = None
    must_change_password: bool = False


class UserRolesIn(BaseModel):
    roles: list[str] = Field(min_length=1)
    expires_on: date | None = None  # obligatorio si incluye funcionario


class ExtendExpiryIn(BaseModel):
    expires_on: date


class AdminUserProfileIn(BaseModel):
    first_name: str = Field(min_length=2, max_length=120)
    last_name: str = Field(min_length=2, max_length=120)


class AdminPasswordIn(BaseModel):
    password: str = Field(min_length=8)
    password_confirm: str = Field(min_length=8)

    @field_validator("password")
    @classmethod
    def password_policy(cls, v: str) -> str:
        if not PASSWORD_POLICY.match(v):
            raise ValueError(
                "La contraseña debe tener al menos 8 caracteres, mayúsculas, minúsculas, números y un carácter especial"
            )
        return v

    @model_validator(mode="after")
    def passwords_match(self) -> "AdminPasswordIn":
        if self.password != self.password_confirm:
            raise ValueError("Las contraseñas no coinciden")
        return self


def _to_out(db: Session, u: User) -> UserAdminOut:
    roles = _roles_of(db, u.id)
    return UserAdminOut(
        id=u.id,
        email=u.email,
        username=u.username,
        first_name=u.first_name,
        last_name=u.last_name,
        document_number=u.document_number,
        professional_reg=u.professional_reg,
        auxiliary_email=u.auxiliary_email,
        phone=u.phone,
        is_active=u.is_active,
        roles=roles,
        role_labels=[ROLE_LABELS.get(r, r) for r in roles],
        expires_at=u.expires_at,
        deleted_at=u.deleted_at,
        created_at=u.created_at,
        last_login_at=u.last_login_at,
        must_change_password=bool(getattr(u, "must_change_password", False)),
    )


def list_roles(db: Session) -> list[RoleOut]:
    rows = db.execute(select(Role).order_by(Role.name)).scalars().all()
    return [
        RoleOut(code=r.code, name=ROLE_LABELS.get(r.code, r.name), description=r.description)
        for r in rows
        if r.code in ASSIGNABLE
    ]


def search_users(db: Session, q: str, limit: int = 30) -> list[UserAdminOut]:
    term = (q or "").strip()
    if len(term) < 2:
        return []
    like = f"%{term}%"
    rows = db.execute(
        select(User)
        .where(
            User.deleted_at.is_(None),
            or_(
                User.email.ilike(like),
                User.username.ilike(like),
                User.auxiliary_email.ilike(like),
                User.first_name.ilike(like),
                User.last_name.ilike(like),
                func.concat(User.first_name, " ", User.last_name).ilike(like),
                User.document_number.ilike(like),
                User.professional_reg.ilike(like),
            ),
        )
        .order_by(User.last_name, User.first_name)
        .limit(min(limit, 50))
    ).scalars().all()
    return [_to_out(db, u) for u in rows]


def get_user(db: Session, user_id: uuid.UUID) -> UserAdminOut:
    u = db.get(User, user_id)
    if not u or u.deleted_at is not None:
        raise HTTPException(404, "Usuario no encontrado")
    return _to_out(db, u)


def update_profile(db: Session, admin: User, user_id: uuid.UUID, data: AdminUserProfileIn) -> UserAdminOut:
    u = db.get(User, user_id)
    if not u or u.deleted_at is not None:
        raise HTTPException(404, "Usuario no encontrado")
    u.first_name = data.first_name.strip()
    u.last_name = data.last_name.strip()
    u.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(u)
    return _to_out(db, u)


def set_password(db: Session, admin: User, user_id: uuid.UUID, data: AdminPasswordIn) -> UserAdminOut:
    u = db.get(User, user_id)
    if not u or u.deleted_at is not None:
        raise HTTPException(404, "Usuario no encontrado")
    u.password_hash = hash_password(data.password)
    u.must_change_password = True
    u.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(u)
    return _to_out(db, u)


def set_roles(db: Session, admin: User, user_id: uuid.UUID, data: UserRolesIn) -> UserAdminOut:
    u = db.get(User, user_id)
    if not u or u.deleted_at is not None:
        raise HTTPException(404, "Usuario no encontrado")
    if u.id == admin.id and "system_admin" not in data.roles:
        raise HTTPException(400, "No puede quitarse el rol de administrador a sí mismo")

    codes = []
    for c in data.roles:
        c = c.strip()
        if c not in ASSIGNABLE:
            raise HTTPException(400, f"Rol no permitido: {c}")
        if c not in codes:
            codes.append(c)
    if not codes:
        codes = ["citizen"]

    needs_expiry = "technical_architect" in codes
    if needs_expiry and not data.expires_on:
        raise HTTPException(400, "El rol Funcionario requiere fecha de vencimiento")
    if needs_expiry and data.expires_on < date.today():
        raise HTTPException(400, "La fecha de vencimiento debe ser hoy o posterior")

    role_rows = {
        r.code: r
        for r in db.execute(select(Role).where(Role.code.in_(codes))).scalars().all()
    }
    if len(role_rows) != len(codes):
        raise HTTPException(400, "Uno o más roles no existen en el sistema")

    db.execute(delete(UserRole).where(UserRole.user_id == u.id))
    expiry_dt = None
    if needs_expiry and data.expires_on:
        expiry_dt = datetime.combine(data.expires_on, datetime.max.time()).replace(tzinfo=timezone.utc)

    for code in codes:
        db.add(
            UserRole(
                user_id=u.id,
                role_id=role_rows[code].id,
                assigned_by=admin.id,
                expires_at=expiry_dt if code == "technical_architect" else None,
            )
        )

    u.expires_at = expiry_dt if needs_expiry else None
    if u.is_active is False and needs_expiry:
        u.is_active = True
    u.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(u)
    return _to_out(db, u)


def _add_one_year(d: date) -> date:
    try:
        return d.replace(year=d.year + 1)
    except ValueError:
        return d.replace(year=d.year + 1, day=28)


def extend_expiry(db: Session, admin: User, user_id: uuid.UUID, data: ExtendExpiryIn) -> UserAdminOut:
    u = db.get(User, user_id)
    if not u or u.deleted_at is not None:
        raise HTTPException(404, "Usuario no encontrado")
    roles = _roles_of(db, u.id)
    if "technical_architect" not in roles:
        raise HTTPException(400, "Solo aplica a usuarios con rol Funcionario")
    if data.expires_on < date.today():
        raise HTTPException(400, "La fecha de vencimiento debe ser hoy o posterior")
    expiry_dt = datetime.combine(data.expires_on, datetime.max.time()).replace(tzinfo=timezone.utc)
    u.expires_at = expiry_dt
    u.is_active = True
    role = db.execute(select(Role).where(Role.code == "technical_architect")).scalar_one()
    ur = db.execute(
        select(UserRole).where(UserRole.user_id == u.id, UserRole.role_id == role.id)
    ).scalar_one_or_none()
    if ur:
        ur.expires_at = expiry_dt
        ur.assigned_by = admin.id
    u.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(u)
    return _to_out(db, u)


def extend_one_year(db: Session, admin: User, user_id: uuid.UUID) -> UserAdminOut:
    """Extiende la vigencia del funcionario un año más desde la fecha de vencimiento (o desde hoy)."""
    u = db.get(User, user_id)
    if not u or u.deleted_at is not None:
        raise HTTPException(404, "Usuario no encontrado")
    roles = _roles_of(db, u.id)
    if "technical_architect" not in roles:
        raise HTTPException(400, "Solo aplica a usuarios con rol Funcionario")
    today = date.today()
    if u.expires_at is not None:
        current = u.expires_at.date() if hasattr(u.expires_at, "date") else u.expires_at
        base = current if current > today else today
    else:
        base = today
    new_date = _add_one_year(base)
    return extend_expiry(db, admin, user_id, ExtendExpiryIn(expires_on=new_date))


def set_active(db: Session, admin: User, user_id: uuid.UUID, active: bool) -> UserAdminOut:
    u = db.get(User, user_id)
    if not u or u.deleted_at is not None:
        raise HTTPException(404, "Usuario no encontrado")
    if u.id == admin.id and not active:
        raise HTTPException(400, "No puede inhabilitarse a sí mismo")
    u.is_active = active
    u.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(u)
    return _to_out(db, u)


def soft_delete(db: Session, admin: User, user_id: uuid.UUID) -> UserAdminOut:
    u = db.get(User, user_id)
    if not u or u.deleted_at is not None:
        raise HTTPException(404, "Usuario no encontrado")
    if u.id == admin.id:
        raise HTTPException(400, "No puede eliminarse a sí mismo")
    u.deleted_at = datetime.now(timezone.utc)
    u.is_active = False
    u.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(u)
    return _to_out(db, u)


def restore_user(db: Session, user_id: uuid.UUID) -> UserAdminOut:
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "Usuario no encontrado")
    u.deleted_at = None
    u.is_active = True
    u.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(u)
    return _to_out(db, u)
