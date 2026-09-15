"""Crea usuarios con rol technical_architect (arquitecto / funcionario)."""

from __future__ import annotations

import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Role, User, UserRole
from app.security import hash_password

ARCHITECTS = [
    {
        "first_name": "Evi Yerald",
        "last_name": "Pizarro Barrios",
        "email": "yepizarro@gmail.com",
        "password": "tempo123",
        "professional_reg": "123456",
        "document_number": "CI-123456",
    },
    {
        "first_name": "Adela Cristina",
        "last_name": "Soliz Gutierrez",
        "email": "crissoliz@gmail.com",
        "password": "tempo456",
        "professional_reg": "789456",
        "document_number": "CI-789456",
    },
    {
        "first_name": "Cinthia",
        "last_name": "Oilos Rios",
        "email": "coilos@gmail.com",
        "password": "tempo789",
        "professional_reg": "753159",
        "document_number": "CI-753159",
    },
    {
        "first_name": "Hugo Daniel",
        "last_name": "Peña Ferreira",
        "email": "hpenia@gmail.com",
        "password": "tempo159",
        "professional_reg": "852456",
        "document_number": "CI-852456",
    },
]


def year_end_expires() -> datetime:
    return datetime.combine(date(date.today().year, 12, 31), datetime.max.time()).replace(
        tzinfo=timezone.utc
    )


def upsert_architect(db, data: dict, role: Role, expires_at: datetime) -> None:
    email = data["email"].lower()
    user = db.execute(
        select(User).where((User.email == email) | (User.username == email))
    ).scalar_one_or_none()

    if not user:
        user = User(
            email=email,
            username=email,
            first_name=data["first_name"],
            last_name=data["last_name"],
            document_number=data["document_number"],
            professional_reg=data["professional_reg"],
            must_have_professional_reg=True,
            is_active=True,
            must_change_password=True,
            password_hash=hash_password(data["password"]),
            expires_at=expires_at,
            email_verified_at=datetime.now(timezone.utc),
        )
        db.add(user)
        db.flush()
        print(f"Creado: {data['first_name']} {data['last_name']} <{email}>")
    else:
        user.password_hash = hash_password(data["password"])
        user.first_name = data["first_name"]
        user.last_name = data["last_name"]
        user.document_number = data["document_number"]
        user.professional_reg = data["professional_reg"]
        user.must_have_professional_reg = True
        user.is_active = True
        user.must_change_password = True
        user.expires_at = expires_at
        user.username = email
        user.email = email
        user.deleted_at = None
        print(f"Actualizado: {data['first_name']} {data['last_name']} <{email}>")

    link = db.execute(
        select(UserRole).where(UserRole.user_id == user.id, UserRole.role_id == role.id)
    ).scalar_one_or_none()
    if not link:
        db.add(UserRole(user_id=user.id, role_id=role.id, expires_at=expires_at))
    else:
        link.expires_at = expires_at


def main() -> None:
    db = SessionLocal()
    try:
        role = db.execute(
            select(Role).where(Role.code == "technical_architect")
        ).scalar_one_or_none()
        if not role:
            raise SystemExit("Falta el rol technical_architect. Ejecuta primero db/03_seed.sql")

        expires_at = year_end_expires()
        for item in ARCHITECTS:
            upsert_architect(db, item, role, expires_at)
        db.commit()
        print("Arquitectos listos.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
