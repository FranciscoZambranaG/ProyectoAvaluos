"""Migración / remigración operativo → municipal.

Al remigrar: se inactiva el registro municipal activo (is_active=false) y se inserta uno nuevo.
No se actualizan tuplas históricas.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_municipal_engine
from app.models import Appraisal, User
from app.services.auth_service import _roles_of

REVIEWER_ROLES = {"system_admin", "technical_architect"}
MIGRATE_FROM = {"draft", "approved", "needs_correction"}


def _jsonable(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def _require_reviewer(db: Session, user: User) -> set[str]:
    roles = set(_roles_of(db, user.id))
    if not REVIEWER_ROLES.intersection(roles):
        raise HTTPException(403, "Solo funcionario o administrador puede gestionar la migración")
    return roles


def count_municipal_versions(source_appraisal_id: UUID, form_number: str | None) -> int:
    engine = get_municipal_engine()
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT COUNT(*)::int AS n
                FROM catastro.appraisals
                WHERE source_appraisal_id = :sid
                   OR (:fn IS NOT NULL AND form_number = :fn)
                """
            ),
            {"sid": str(source_appraisal_id), "fn": form_number},
        ).mappings().one()
        return int(row["n"] or 0)


def deactivate_previous_municipal(conn, source_appraisal_id: UUID, form_number: str | None) -> list[str]:
    rows = conn.execute(
        text(
            """
            UPDATE catastro.appraisals
            SET is_active = FALSE,
                superseded_at = NOW(),
                updated_at = NOW()
            WHERE is_active IS TRUE
              AND (
                    source_appraisal_id = :sid
                 OR (:fn IS NOT NULL AND form_number = :fn)
              )
            RETURNING id::text AS id
            """
        ),
        {"sid": str(source_appraisal_id), "fn": form_number},
    ).mappings().all()
    return [r["id"] for r in rows]


def _status_id(conn, code: str) -> str:
    row = conn.execute(
        text("SELECT id::text AS id FROM config.workflow_statuses WHERE code = :c"),
        {"c": code},
    ).mappings().first()
    if not row:
        raise HTTPException(500, f"Estado '{code}' no existe en BD municipal")
    return row["id"]


def _ensure_user_exists(conn, user_id: UUID) -> None:
    row = conn.execute(
        text("SELECT 1 FROM auth.users WHERE id = :id"),
        {"id": str(user_id)},
    ).first()
    if not row:
        raise HTTPException(
            409,
            "El usuario dueño del formulario no existe en la BD municipal. Sincronice auth.users antes de migrar.",
        )


def _copy_appraisal_tree(conn, appraisal: Appraisal, actor_id: UUID) -> str:
    """Inserta un árbol completo nuevo. Devuelve municipal appraisal id."""
    new_appraisal_id = str(uuid.uuid4())
    new_property_id = str(uuid.uuid4())
    migrated_status = _status_id(conn, "migrated")
    now = datetime.now(timezone.utc)

    _ensure_user_exists(conn, appraisal.owner_user_id)

    prop = appraisal.property
    if not prop:
        raise HTTPException(409, "El formulario no tiene predio para migrar")

    conn.execute(
        text(
            """
            INSERT INTO catastro.appraisals (
              id, form_number, owner_user_id, status_id, fiscal_year,
              land_area, blocks_area, improvements_area,
              land_value, blocks_value, improvements_value, total_value,
              valuation_snapshot, migrated_at, approved_at, approved_by,
              is_active, source_appraisal_id, created_at, updated_at
            ) VALUES (
              :id, :form_number, :owner_user_id, :status_id, :fiscal_year,
              :land_area, :blocks_area, :improvements_area,
              :land_value, :blocks_value, :improvements_value, :total_value,
              CAST(:valuation_snapshot AS jsonb), :migrated_at, :approved_at, :approved_by,
              TRUE, :source_appraisal_id, :created_at, :updated_at
            )
            """
        ),
        {
            "id": new_appraisal_id,
            "form_number": appraisal.form_number,
            "owner_user_id": str(appraisal.owner_user_id),
            "status_id": migrated_status,
            "fiscal_year": appraisal.fiscal_year,
            "land_area": appraisal.land_area or 0,
            "blocks_area": appraisal.blocks_area or 0,
            "improvements_area": appraisal.improvements_area or 0,
            "land_value": appraisal.land_value or 0,
            "blocks_value": appraisal.blocks_value or 0,
            "improvements_value": appraisal.improvements_value or 0,
            "total_value": appraisal.total_value or 0,
            "valuation_snapshot": json.dumps(_jsonable(appraisal.valuation_snapshot or {})),
            "migrated_at": now,
            "approved_at": now,
            "approved_by": str(actor_id),
            "source_appraisal_id": str(appraisal.id),
            "created_at": now,
            "updated_at": now,
        },
    )

    conn.execute(
        text(
            """
            INSERT INTO catastro.properties (
              id, appraisal_id, cadastral_code, subdistrict, block_code, plot_code,
              use_code, building_code, floor_code, unit_code, property_number,
              address, door_number, building_name, block_label, floor_label, apartment_label,
              latitude, longitude, map_meta_json, status, created_at, updated_at
            ) VALUES (
              :id, :appraisal_id, :cadastral_code, :subdistrict, :block_code, :plot_code,
              :use_code, :building_code, :floor_code, :unit_code, :property_number,
              :address, :door_number, :building_name, :block_label, :floor_label, :apartment_label,
              :latitude, :longitude, CAST(:map_meta_json AS jsonb), :status, :created_at, :updated_at
            )
            """
        ),
        {
            "id": new_property_id,
            "appraisal_id": new_appraisal_id,
            "cadastral_code": prop.cadastral_code,
            "subdistrict": prop.subdistrict,
            "block_code": prop.block_code,
            "plot_code": prop.plot_code,
            "use_code": prop.use_code,
            "building_code": prop.building_code,
            "floor_code": prop.floor_code,
            "unit_code": prop.unit_code,
            "property_number": prop.property_number,
            "address": prop.address,
            "door_number": prop.door_number,
            "building_name": prop.building_name,
            "block_label": prop.block_label,
            "floor_label": prop.floor_label,
            "apartment_label": prop.apartment_label,
            "latitude": prop.latitude,
            "longitude": prop.longitude,
            "map_meta_json": json.dumps(_jsonable(prop.map_meta_json or {})),
            "status": prop.status or "active",
            "created_at": now,
            "updated_at": now,
        },
    )

    for owner in prop.owners or []:
        conn.execute(
            text(
                """
                INSERT INTO catastro.owners (
                  id, property_id, person_type, first_name, last_name_1, last_name_2, legal_name,
                  document_number, document_issued_in, nit, ownership_percent,
                  registry_matricula, registry_asiento, registry_fojas, registry_partida,
                  deed_number, deed_date, registry_ddr_date, notary_name, phone, email,
                  extra_json, created_at
                ) VALUES (
                  :id, :property_id, :person_type, :first_name, :last_name_1, :last_name_2, :legal_name,
                  :document_number, :document_issued_in, :nit, :ownership_percent,
                  :registry_matricula, :registry_asiento, :registry_fojas, :registry_partida,
                  :deed_number, :deed_date, :registry_ddr_date, :notary_name, :phone, :email,
                  CAST(:extra_json AS jsonb), :created_at
                )
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "property_id": new_property_id,
                "person_type": owner.person_type,
                "first_name": owner.first_name,
                "last_name_1": owner.last_name_1,
                "last_name_2": owner.last_name_2,
                "legal_name": owner.legal_name,
                "document_number": owner.document_number,
                "document_issued_in": owner.document_issued_in,
                "nit": owner.nit,
                "ownership_percent": owner.ownership_percent,
                "registry_matricula": owner.registry_matricula,
                "registry_asiento": owner.registry_asiento,
                "registry_fojas": owner.registry_fojas,
                "registry_partida": owner.registry_partida,
                "deed_number": owner.deed_number,
                "deed_date": owner.deed_date,
                "registry_ddr_date": owner.registry_ddr_date,
                "notary_name": owner.notary_name,
                "phone": owner.phone,
                "email": owner.email,
                "extra_json": json.dumps(_jsonable(owner.extra_json or {})),
                "created_at": now,
            },
        )

    detail = prop.detail
    if detail:
        new_detail_id = str(uuid.uuid4())
        conn.execute(
            text(
                """
                INSERT INTO catastro.property_details (
                  id, property_id, zone_item_id, topography_item_id, shape_item_id,
                  location_item_id, road_material_item_id, approved_area, front_length,
                  depth_length, observations, dynamic_values_json, updated_at
                ) VALUES (
                  :id, :property_id, :zone_item_id, :topography_item_id, :shape_item_id,
                  :location_item_id, :road_material_item_id, :approved_area, :front_length,
                  :depth_length, :observations, CAST(:dynamic_values_json AS jsonb), :updated_at
                )
                """
            ),
            {
                "id": new_detail_id,
                "property_id": new_property_id,
                "zone_item_id": str(detail.zone_item_id) if detail.zone_item_id else None,
                "topography_item_id": str(detail.topography_item_id) if detail.topography_item_id else None,
                "shape_item_id": str(detail.shape_item_id) if detail.shape_item_id else None,
                "location_item_id": str(detail.location_item_id) if detail.location_item_id else None,
                "road_material_item_id": str(detail.road_material_item_id) if detail.road_material_item_id else None,
                "approved_area": detail.approved_area,
                "front_length": detail.front_length,
                "depth_length": detail.depth_length,
                "observations": detail.observations,
                "dynamic_values_json": json.dumps(_jsonable(detail.dynamic_values_json or {})),
                "updated_at": now,
            },
        )
        for svc in detail.services or []:
            conn.execute(
                text(
                    """
                    INSERT INTO catastro.property_services (property_detail_id, service_item_id)
                    VALUES (:d, :s)
                    ON CONFLICT DO NOTHING
                    """
                ),
                {"d": new_detail_id, "s": str(svc.service_item_id)},
            )
        for eq in detail.equipments or []:
            conn.execute(
                text(
                    """
                    INSERT INTO catastro.property_equipments (property_detail_id, equipment_item_id)
                    VALUES (:d, :e)
                    ON CONFLICT DO NOTHING
                    """
                ),
                {"d": new_detail_id, "e": str(eq.equipment_item_id)},
            )

    for unit in prop.units or []:
        if getattr(unit, "status", "active") != "active":
            continue
        new_unit_id = str(uuid.uuid4())
        conn.execute(
            text(
                """
                INSERT INTO catastro.construction_units (
                  id, property_id, unit_kind, unit_number, area, floors_count,
                  construction_year, modification_year, fiscal_year,
                  use_coeff_item_id, depreciation_item_id, improvement_type_item_id,
                  typology_item_id, total_score, unit_value, observations, status,
                  created_at, updated_at
                ) VALUES (
                  :id, :property_id, :unit_kind, :unit_number, :area, :floors_count,
                  :construction_year, :modification_year, :fiscal_year,
                  :use_coeff_item_id, :depreciation_item_id, :improvement_type_item_id,
                  :typology_item_id, :total_score, :unit_value, :observations, :status,
                  :created_at, :updated_at
                )
                """
            ),
            {
                "id": new_unit_id,
                "property_id": new_property_id,
                "unit_kind": unit.unit_kind,
                "unit_number": unit.unit_number,
                "area": unit.area,
                "floors_count": unit.floors_count,
                "construction_year": unit.construction_year,
                "modification_year": unit.modification_year,
                "fiscal_year": unit.fiscal_year,
                "use_coeff_item_id": str(unit.use_coeff_item_id) if unit.use_coeff_item_id else None,
                "depreciation_item_id": str(unit.depreciation_item_id) if unit.depreciation_item_id else None,
                "improvement_type_item_id": str(unit.improvement_type_item_id) if unit.improvement_type_item_id else None,
                "typology_item_id": str(unit.typology_item_id) if unit.typology_item_id else None,
                "total_score": unit.total_score,
                "unit_value": unit.unit_value,
                "observations": unit.observations,
                "status": unit.status or "active",
                "created_at": now,
                "updated_at": now,
            },
        )
        for cv in unit.characteristic_values or []:
            conn.execute(
                text(
                    """
                    INSERT INTO catastro.unit_characteristic_values (
                      id, construction_unit_id, characteristic_group_id, characteristic_option_id,
                      percentage, score, sort_order
                    ) VALUES (
                      :id, :unit_id, :group_id, :option_id, :percentage, :score, :sort_order
                    )
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "unit_id": new_unit_id,
                    "group_id": str(cv.characteristic_group_id),
                    "option_id": str(cv.characteristic_option_id),
                    "percentage": cv.percentage,
                    "score": cv.score,
                    "sort_order": cv.sort_order or 0,
                },
            )

    return new_appraisal_id


def _record_batch(
    db: Session,
    appraisal_id: UUID,
    municipal_id: str,
    actor_id: UUID,
    deactivated: list[str],
    remigration: bool,
) -> None:
    db.execute(
        text(
            """
            INSERT INTO migration.batches (
              id, appraisal_id, status, initiated_by, reviewed_by,
              municipal_appraisal_id, started_at, completed_at, error_log
            ) VALUES (
              :id, :appraisal_id, 'completed', :actor, :actor,
              :mun_id, NOW(), NOW(), CAST(:err AS jsonb)
            )
            """
        ),
        {
            "id": str(uuid.uuid4()),
            "appraisal_id": str(appraisal_id),
            "actor": str(actor_id),
            "mun_id": municipal_id,
            "err": json.dumps({"deactivated": deactivated, "remigration": remigration}),
        },
    )


def migrate_appraisal(db: Session, appraisal: Appraisal, user: User) -> dict[str, Any]:
    _require_reviewer(db, user)
    code = appraisal.status.code if appraisal.status else ""
    if code == "migrated":
        raise HTTPException(409, "El formulario ya está migrado. Habilite corrección antes de remigrar.")
    if code not in MIGRATE_FROM:
        raise HTTPException(409, f"No se puede migrar desde el estado '{code}'")

    # refrescar valuación
    from app.services import valuation_service as val_svc

    try:
        val_svc.compute_appraisal_valuation(db, appraisal)
        db.flush()
    except Exception:
        # no bloquear migración si falla valuación parcial
        pass

    engine = get_municipal_engine()
    deactivated: list[str] = []
    remigration = False
    municipal_id: str

    try:
        with engine.begin() as conn:
            prev = count_municipal_versions(appraisal.id, appraisal.form_number)
            remigration = prev > 0
            deactivated = deactivate_previous_municipal(conn, appraisal.id, appraisal.form_number)
            municipal_id = _copy_appraisal_tree(conn, appraisal, user.id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Error al escribir en BD municipal: {exc}") from exc

    migrated = db.execute(
        text("SELECT id FROM config.workflow_statuses WHERE code = 'migrated'")
    ).scalar_one()
    appraisal.status_id = migrated
    db.execute(
        text(
            """
            UPDATE catastro.appraisals
            SET status_id = :sid,
                migrated_at = NOW(),
                approved_at = COALESCE(approved_at, NOW()),
                approved_by = COALESCE(approved_by, :uid),
                updated_at = NOW()
            WHERE id = :id
            """
        ),
        {"sid": str(migrated), "uid": str(user.id), "id": str(appraisal.id)},
    )
    _record_batch(db, appraisal.id, municipal_id, user.id, deactivated, remigration)
    db.commit()
    db.refresh(appraisal)

    return {
        "municipal_appraisal_id": municipal_id,
        "remigration": remigration,
        "deactivated_ids": deactivated,
    }


def enable_correction(db: Session, appraisal: Appraisal, user: User) -> None:
    _require_reviewer(db, user)
    code = appraisal.status.code if appraisal.status else ""
    if code != "migrated":
        raise HTTPException(409, "Solo se puede habilitar corrección en formularios migrados")

    needs = db.execute(
        text("SELECT id FROM config.workflow_statuses WHERE code = 'needs_correction'")
    ).scalar_one()
    appraisal.status_id = needs
    db.execute(
        text(
            """
            UPDATE catastro.appraisals
            SET status_id = :sid, updated_at = NOW()
            WHERE id = :id
            """
        ),
        {"sid": str(needs), "id": str(appraisal.id)},
    )
    db.commit()
    db.refresh(appraisal)
