"""Lectura de observaciones que el ERP (idec_erp.avaluos.appraisal_observations) manda
sobre un avalúo.

Conexión de solo lectura: este backend nunca escribe en idec_erp. Nombre de schema/tabla
según la base real (ver esquema_avaluos.sql en el repo de idec) -- no coincide con
`appraisal_review.observation_batches`, que era el diseño original antes de confirmar el
esquema con el equipo de BD.
"""

from __future__ import annotations

from sqlalchemy import text

from app.db import get_idec_erp_engine
from app.schemas.appraisal import ObservationBatchOut


def list_observation_batches(form_number: str | None) -> list[ObservationBatchOut]:
    if not form_number:
        return []
    engine = get_idec_erp_engine()
    if engine is None:
        return []
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id, observations, reviewed_by, reviewed_at
                FROM avaluos.appraisal_observations
                WHERE form_number = :fn
                ORDER BY reviewed_at DESC
                """
            ),
            {"fn": form_number},
        ).mappings().all()
    return [
        ObservationBatchOut(
            id=row["id"],
            observations=list(row["observations"] or []),
            reviewed_by=row["reviewed_by"],
            reviewed_at=row["reviewed_at"],
        )
        for row in rows
    ]
