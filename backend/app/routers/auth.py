from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.auth import AuthResponse, LoginIn, PasswordChangeIn, ProfileUpdateIn, RegisterIn, TokenOut, UserPublic
from app.services.auth_service import (
    authenticate,
    change_password,
    get_current_user,
    issue_token,
    register_citizen,
    to_public,
    update_profile,
)
from app.models import User

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginIn, db: Session = Depends(get_db)) -> AuthResponse:
    user = authenticate(db, payload.login, payload.password)
    token = issue_token(db, user)
    return AuthResponse(token=TokenOut(access_token=token), user=to_public(db, user))


@router.post("/register", response_model=AuthResponse, status_code=201)
def register(payload: RegisterIn, db: Session = Depends(get_db)) -> AuthResponse:
    user = register_citizen(db, payload)
    token = issue_token(db, user)
    return AuthResponse(token=TokenOut(access_token=token), user=to_public(db, user))


@router.get("/me", response_model=UserPublic)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> UserPublic:
    return to_public(db, user)


@router.put("/me", response_model=UserPublic)
def update_me(payload: ProfileUpdateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> UserPublic:
    updated = update_profile(db, user, payload)
    return to_public(db, updated)


@router.put("/me/password", response_model=UserPublic)
def update_password(
    payload: PasswordChangeIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserPublic:
    updated = change_password(db, user, payload)
    return to_public(db, updated)
