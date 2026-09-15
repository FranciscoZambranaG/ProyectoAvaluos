from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.services import admin_config_service as cfg
from app.services.admin_config_service import BrandingOut, ParamOut

router = APIRouter(prefix="/api/v1/public", tags=["public"])


@router.get("/branding", response_model=BrandingOut)
def public_branding(db: Session = Depends(get_db)):
    return cfg.get_branding(db)


@router.get("/parameters", response_model=list[ParamOut])
def public_parameters(db: Session = Depends(get_db)):
    return cfg.list_parameters(db, public_only=True)
