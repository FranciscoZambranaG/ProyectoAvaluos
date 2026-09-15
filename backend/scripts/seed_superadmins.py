"""Crea los dos superadministradores del sistema."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Role, User, UserRole
from app.security import hash_password

SUPERS = [
    {
        "username": "SuperAdmin",
        "email": "superadmin@catastrocbba.com",
        "auxiliary_email": None,
        "password": "r3b0rn*666",
        "first_name": "Super",
        "last_name": "Administrador",
        "document_number": "ADMIN-001",
    },
    {
        "username": "jpolo",
        "email": "jpolo@catastrocbba.com",
        "auxiliary_email": "llantas4@gmail.com",
        "password": "r3b0rn*666",
        "first_name": "Juan",
        "last_name": "Polo",
        "document_number": "ADMIN-002",
    },
]


def upsert_super(db, data: dict, role: Role) -> None:
    user = db.execute(
        select(User).where(
            (User.email == data["email"]) | (User.username == data["username"])
        )
    ).scalar_one_or_none()
    if not user:
        user = User(
            email=data["email"],
            username=data["username"],
            first_name=data["first_name"],
            last_name=data["last_name"],
            document_number=data["document_number"],
            professional_reg=None,
            auxiliary_email=data["auxiliary_email"],
            must_have_professional_reg=False,
            is_active=True,
            password_hash=hash_password(data["password"]),
        )
        db.add(user)
        db.flush()
        print(f"Creado: {data['username']} <{data['email']}>")
    else:
        user.password_hash = hash_password(data["password"])
        user.auxiliary_email = data["auxiliary_email"]
        user.must_have_professional_reg = False
        user.professional_reg = None
        user.is_active = True
        user.username = data["username"]
        user.email = data["email"]
        print(f"Actualizado: {data['username']} <{data['email']}>")

    link = db.execute(
        select(UserRole).where(UserRole.user_id == user.id, UserRole.role_id == role.id)
    ).scalar_one_or_none()
    if not link:
        db.add(UserRole(user_id=user.id, role_id=role.id))


def main() -> None:
    db = SessionLocal()
    try:
        role = db.execute(select(Role).where(Role.code == "system_admin")).scalar_one_or_none()
        if not role:
            raise SystemExit("Falta el rol system_admin. Ejecuta primero db/03_seed.sql")
        for item in SUPERS:
            upsert_super(db, item, role)
        db.commit()
        print("Superadmins listos.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
