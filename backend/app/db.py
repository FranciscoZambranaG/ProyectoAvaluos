from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

settings = get_settings()

engine = create_engine(settings.operativo_database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@lru_cache
def get_municipal_engine() -> Engine:
    return create_engine(settings.municipal_database_url, pool_pre_ping=True)


@lru_cache
def get_idec_erp_engine() -> Engine | None:
    """Conexión a idec_erp (appraisal_review). None si no está configurada.

    Solo se usa para lectura (SELECT) en app.services.erp_review_service; esta app
    nunca escribe en idec_erp. No se fuerza read-only a nivel de conexión porque el
    servidor está detrás de un pooler (pgbouncer) que rechaza el startup param
    "options" usado para eso.
    """
    if not settings.idec_erp_database_url:
        return None
    return create_engine(settings.idec_erp_database_url, pool_pre_ping=True)
