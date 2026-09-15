from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.services.auth_service import get_current_user, to_public

router = APIRouter(prefix="/api/v1", tags=["app"])


@router.get("/dashboard/summary")
def dashboard_summary(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from sqlalchemy import func, select

    from app.models import Appraisal
    from app.services.auth_service import _roles_of

    public = to_public(db, user)
    roles = _roles_of(db, user.id)
    q = select(func.count()).select_from(Appraisal)
    if "system_admin" not in roles and "technical_architect" not in roles:
        q = q.where(Appraisal.owner_user_id == user.id)
    total = db.execute(q).scalar() or 0
    return {
        "welcome": f"Hola, {public.first_name}",
        "user": public,
        "stats": {
            "formularios": total,
            "borradores": total,
            "enviados": 0,
            "migrados": 0,
        },
        "next_steps": [
            "Crear un nuevo formulario de avalúo",
            "Completar propietario, detalle y código catastral",
            "Adjuntar fotografías (próximo módulo)",
        ],
    }
