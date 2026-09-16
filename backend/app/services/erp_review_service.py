"""Lectura de observaciones que el ERP (idec_erp.appraisal_review) manda sobre un avalúo.

Conexión de solo lectura: este backend nunca escribe en idec_erp.
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
                FROM appraisal_review.observation_batches
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
