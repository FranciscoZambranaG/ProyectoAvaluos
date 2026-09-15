from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Role, User, UserRole
from app.schemas.auth import RegisterIn, UserPublic, is_municipal_email
from app.security import TokenError, create_access_token, get_subject, hash_password, verify_password

bearer = HTTPBearer(auto_error=False)


def _roles_of(db: Session, user_id: UUID) -> list[str]:
    rows = db.execute(
        select(Role.code)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id)
    ).scalars().all()
    return list(rows)


def to_public(db: Session, user: User) -> UserPublic:
    return UserPublic(
        id=user.id,
        email=user.email,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        document_number=user.document_number,
        professional_reg=user.professional_reg,
        auxiliary_email=user.auxiliary_email,
        roles=_roles_of(db, user.id),
        must_have_professional_reg=user.must_have_professional_reg,
        must_change_password=bool(getattr(user, "must_change_password", False)),
    )


def find_user_by_login(db: Session, login: str) -> User | None:
    key = login.strip()
    return db.execute(
        select(User).where(
            or_(
                func.lower(User.email) == key.lower(),
                func.lower(User.username) == key.lower(),
                func.lower(User.auxiliary_email) == key.lower(),
            )
        )
    ).scalar_one_or_none()


def authenticate(db: Session, login: str, password: str) -> User:
    user = find_user_by_login(db, login)
    if not user or not user.password_hash or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales incorrectas")
    if getattr(user, "deleted_at", None) is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario eliminado")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario inhabilitado")
    expires = getattr(user, "expires_at", None)
    if expires is not None:
        now = datetime.now(timezone.utc)
        exp = expires if expires.tzinfo else expires.replace(tzinfo=timezone.utc)
        if exp < now:
            roles = _roles_of(db, user.id)
            if "technical_architect" in roles and "system_admin" not in roles:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="La vigencia del usuario funcionario ha vencido. Solicite una renovación.",
                )
    user.last_login_at = datetime.now(timezone.utc)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def issue_token(db: Session, user: User) -> str:
    roles = _roles_of(db, user.id)
    return create_access_token(str(user.id), {"roles": roles, "email": user.email})


def register_citizen(db: Session, data: RegisterIn) -> User:
    email = str(data.email).lower()
    municipal = is_municipal_email(email)
    username = email
    reg = (data.professional_reg or "").strip() or None

    if db.execute(select(User).where(func.lower(User.email) == email)).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Ya existe un usuario con ese correo electrónico")
    if db.execute(select(User).where(func.lower(User.username) == username)).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Ya existe un usuario con ese correo electrónico")
    if reg and db.execute(select(User).where(User.professional_reg == reg)).scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="Ya existe un usuario con ese número de registro del Colegio de Arquitectos",
        )
    if db.execute(select(User).where(func.lower(User.auxiliary_email) == email)).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Ese correo ya está registrado como auxiliar")

    role_code = "technical_architect" if municipal else "citizen"
    role = db.execute(select(Role).where(Role.code == role_code)).scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=500, detail=f"Rol {role_code} no configurado en la base de datos")

    expires_at = None
    if municipal:
        # Vigencia hasta el 31 de diciembre del año de registro (fin del día UTC).
        expires_at = datetime.combine(date(date.today().year, 12, 31), datetime.max.time()).replace(
            tzinfo=timezone.utc
        )

    user = User(
        email=email,
        username=username,
        password_hash=hash_password(data.password),
        first_name=data.first_name.strip(),
        last_name=data.last_name.strip(),
        document_number=data.document_number.strip(),
        professional_reg=reg,
        must_have_professional_reg=not municipal,
        is_active=True,
        expires_at=expires_at,
        email_verified_at=datetime.now(timezone.utc),  # verificación por mail en siguiente iteración
    )
    db.add(user)
    db.flush()
    db.add(
        UserRole(
            user_id=user.id,
            role_id=role.id,
            expires_at=expires_at if municipal else None,
        )
    )
    db.commit()
    db.refresh(user)
    return user


def update_profile(db: Session, user: User, data) -> User:
    from app.schemas.auth import ProfileUpdateIn

    assert isinstance(data, ProfileUpdateIn)
    aux = str(data.auxiliary_email).lower() if data.auxiliary_email else None
    if aux:
        clash = db.execute(
            select(User).where(
                User.id != user.id,
                or_(
                    func.lower(User.email) == aux,
                    func.lower(User.auxiliary_email) == aux,
                ),
            )
        ).scalar_one_or_none()
        if clash:
            raise HTTPException(409, "Ese correo auxiliar ya está en uso")
    doc = data.document_number.strip()
    clash_doc = db.execute(
        select(User).where(User.id != user.id, User.document_number == doc)
    ).scalar_one_or_none()
    if clash_doc:
        raise HTTPException(409, "Ya existe un usuario con ese C.I.")
    user.first_name = data.first_name.strip()
    user.last_name = data.last_name.strip()
    user.document_number = doc
    user.auxiliary_email = aux
    user.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    return user


def change_password(db: Session, user: User, data) -> User:
    from app.schemas.auth import PasswordChangeIn

    assert isinstance(data, PasswordChangeIn)
    if not user.password_hash or not verify_password(data.current_password, user.password_hash):
        raise HTTPException(400, "La contraseña actual es incorrecta")
    if data.password == data.current_password:
        raise HTTPException(400, "La nueva contraseña debe ser distinta a la actual")
    user.password_hash = hash_password(data.password)
    user.must_change_password = False
    user.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    return user


def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if not creds or not creds.credentials:
        raise HTTPException(status_code=401, detail="No autenticado")
    try:
        user_id = get_subject(creds.credentials)
    except TokenError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    user = db.get(User, UUID(user_id))
    if not user or not user.is_active or getattr(user, "deleted_at", None) is not None:
        raise HTTPException(status_code=401, detail="Usuario no válido")
    expires = getattr(user, "expires_at", None)
    if expires is not None:
        now = datetime.now(timezone.utc)
        exp = expires if expires.tzinfo else expires.replace(tzinfo=timezone.utc)
        if exp < now:
            roles = _roles_of(db, user.id)
            if "technical_architect" in roles and "system_admin" not in roles:
                raise HTTPException(status_code=401, detail="Vigencia del funcionario vencida")
    if bool(getattr(user, "must_change_password", False)):
        # Solo puede consultar su perfil y cambiar la contraseña.
        path = request.url.path.rstrip("/")
        method = request.method.upper()
        allowed = (method == "GET" and path.endswith("/auth/me")) or (
            method == "PUT" and path.endswith("/auth/me/password")
        )
        if not allowed:
            raise HTTPException(
                status_code=403,
                detail="Debe cambiar su contraseña antes de continuar",
            )
    return user
