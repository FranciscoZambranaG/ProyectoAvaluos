from uuid import UUID
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import DocumentFile, MediaType, User
from app.schemas.appraisal import (
    AppraisalCreateIn,
    AppraisalDetailOut,
    AppraisalListItem,
    CadastralCodeIn,
    CatalogOption,
    CharacteristicGroupOut,
    ConstructionUnitIn,
    MediaTypeOut,
    OwnerPutIn,
    PhotoTypeUpdateIn,
    PropertyDetailIn,
    UnitCharacteristicsSaveIn,
)
from app.services import appraisal_service as svc
from app.services import media_service as media_svc
from app.services import docx_service, pdf_service
from app.services import valuation_service as val_svc
from app.services.auth_service import get_current_user
from app.services.media_service import UPLOAD_ROOT
from sqlalchemy import select

router = APIRouter(prefix="/api/v1", tags=["appraisals"])


@router.get("/catalogs/{type_code}", response_model=list[CatalogOption])
def catalogs(type_code: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return svc.list_catalog(db, type_code)


@router.get("/characteristics/catalog", response_model=list[CharacteristicGroupOut])
def characteristics_catalog(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    construction_year: int | None = None,
):
    return media_svc.list_characteristic_catalog(db, construction_year)


@router.get("/media-types", response_model=list[MediaTypeOut])
def media_types(db: Session = Depends(get_db), _: User = Depends(get_current_user), category: str = "photo"):
    return media_svc.list_media_types(db, category)


@router.get("/media/{file_id}")
def get_media(file_id: UUID, db: Session = Depends(get_db)):
    row = media_svc.get_media_file(db, file_id)
    path = UPLOAD_ROOT / row.storage_key
    if not path.exists():
        from fastapi import HTTPException

        raise HTTPException(404, "Archivo físico no encontrado")
    headers = {"Cache-Control": "private, max-age=0, must-revalidate"}
    if row.checksum_sha256:
        headers["ETag"] = f'"{row.checksum_sha256}"'
    return FileResponse(
        path,
        media_type=row.mime_type or "image/webp",
        filename=row.original_name or path.name,
        content_disposition_type="inline",
        headers=headers,
    )


@router.get("/appraisals", response_model=list[AppraisalListItem])
def list_appraisals(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return svc.list_appraisals(db, user)


@router.get("/appraisals/search", response_model=list[AppraisalListItem])
def search_appraisals(
    q: str = Query(..., min_length=2),
    limit: int = Query(40, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return svc.search_appraisals(db, user, q, limit)


@router.post("/appraisals", response_model=AppraisalDetailOut, status_code=201)
def create_appraisal(payload: AppraisalCreateIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return svc.create_appraisal(db, user, payload)


@router.get("/appraisals/{appraisal_id}", response_model=AppraisalDetailOut)
def get_appraisal(appraisal_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return svc.get_appraisal(db, appraisal_id, user)


@router.put("/appraisals/{appraisal_id}/owner", response_model=AppraisalDetailOut)
def put_owner(
    appraisal_id: UUID,
    payload: OwnerPutIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return svc.update_owner(db, appraisal_id, user, payload)


@router.put("/appraisals/{appraisal_id}/detail", response_model=AppraisalDetailOut)
def put_detail(
    appraisal_id: UUID,
    payload: PropertyDetailIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return svc.update_detail(db, appraisal_id, user, payload)


@router.put("/appraisals/{appraisal_id}/cadastral", response_model=AppraisalDetailOut)
def put_cadastral(
    appraisal_id: UUID,
    payload: CadastralCodeIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return svc.update_cadastral(db, appraisal_id, user, payload)


@router.post("/appraisals/{appraisal_id}/blocks", response_model=AppraisalDetailOut, status_code=201)
def post_block(
    appraisal_id: UUID,
    payload: ConstructionUnitIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return svc.add_block(db, appraisal_id, user, payload)


@router.put("/appraisals/{appraisal_id}/blocks/{block_id}", response_model=AppraisalDetailOut)
def put_block(
    appraisal_id: UUID,
    block_id: UUID,
    payload: ConstructionUnitIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return svc.update_block(db, appraisal_id, user, block_id, payload)


@router.delete("/appraisals/{appraisal_id}/blocks/{block_id}", response_model=AppraisalDetailOut)
def delete_block(
    appraisal_id: UUID,
    block_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return svc.delete_block(db, appraisal_id, user, block_id)


@router.put("/appraisals/{appraisal_id}/blocks/{block_id}/characteristics", response_model=AppraisalDetailOut)
def put_block_characteristics(
    appraisal_id: UUID,
    block_id: UUID,
    payload: UnitCharacteristicsSaveIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return media_svc.save_unit_characteristics(db, appraisal_id, block_id, user, payload.items)


@router.post("/appraisals/{appraisal_id}/photos", response_model=AppraisalDetailOut, status_code=201)
async def post_photo(
    appraisal_id: UUID,
    media_type_code: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await media_svc.upload_photo(db, appraisal_id, user, media_type_code, file)


@router.patch("/appraisals/{appraisal_id}/photos/{photo_id}", response_model=AppraisalDetailOut)
def patch_photo_type(
    appraisal_id: UUID,
    photo_id: UUID,
    payload: PhotoTypeUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return media_svc.update_photo_type(db, appraisal_id, photo_id, user, payload.media_type_code)


@router.delete("/appraisals/{appraisal_id}/photos/{photo_id}", response_model=AppraisalDetailOut)
def delete_photo(
    appraisal_id: UUID,
    photo_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return media_svc.delete_photo(db, appraisal_id, photo_id, user)


@router.get("/appraisals/{appraisal_id}/valuation")
def get_appraisal_valuation(
    appraisal_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    svc.get_appraisal(db, appraisal_id, user)
    appraisal = val_svc.load_appraisal_for_pdf(db, appraisal_id)
    if not appraisal:
        from fastapi import HTTPException

        raise HTTPException(404, "Formulario no encontrado")
    data = val_svc.compute_appraisal_valuation(db, appraisal)
    try:
        db.commit()
    except Exception:
        db.rollback()
    return data


@router.post("/appraisals/{appraisal_id}/enable-correction", response_model=AppraisalDetailOut)
def enable_correction(
    appraisal_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Funcionario/admin: reabre un formulario migrado para corrección."""
    return svc.enable_appraisal_correction(db, appraisal_id, user)


@router.post("/appraisals/{appraisal_id}/migrate", response_model=AppraisalDetailOut)
def migrate_appraisal(
    appraisal_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Funcionario/admin: migra o remigra a municipal (inactiva la versión anterior)."""
    return svc.migrate_appraisal_to_municipal(db, appraisal_id, user)


@router.get("/appraisals/{appraisal_id}/pdf")
def download_appraisal_pdf(
    appraisal_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Genera PDF de declaración jurada (equivalente a reporte/datosTecnicos del sistema actual)."""
    from fastapi import HTTPException

    # control de acceso (dueño o revisor)
    svc.get_appraisal(db, appraisal_id, user)
    appraisal = val_svc.load_appraisal_for_pdf(db, appraisal_id)
    if not appraisal:
        raise HTTPException(404, "Formulario no encontrado")

    try:
        data = val_svc.compute_appraisal_valuation(db, appraisal)
        try:
            db.commit()
        except Exception:
            db.rollback()
    except Exception as exc:
        db.rollback()
        raise HTTPException(500, f"Error al calcular valuación: {exc}") from exc

    try:
        pdf_bytes = _appraisal_pdf_bytes(db, appraisal, appraisal_id, data)
    except Exception as exc:
        raise HTTPException(500, f"Error al generar el documento: {exc}") from exc

    filename = f"formulario_{(data.get('form_number') or appraisal_id)}.pdf".replace(" ", "_")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "no-cache",
        },
    )


def _filled_docx(db: Session, appraisal, appraisal_id: UUID, data: dict) -> bytes:
    from app.models import User as AuthUser

    prop = appraisal.property
    owner_user = db.get(AuthUser, appraisal.owner_user_id)
    professional_name = None
    professional_reg = None
    if owner_user:
        professional_name = f"{owner_user.first_name} {owner_user.last_name}".strip()
        professional_reg = owner_user.professional_reg
    return docx_service.generate_appraisal_docx(
        data,
        _photo_paths(db, appraisal_id),
        professional_name=professional_name,
        professional_reg=professional_reg,
        property_number=prop.property_number if prop else None,
        pmc=getattr(prop, "pmc", None) if prop else None,
        building_name=prop.building_name if prop else None,
        floor_label=prop.floor_label if prop else None,
        apartment_label=prop.apartment_label if prop else None,
    )


def _appraisal_pdf_bytes(db: Session, appraisal, appraisal_id: UUID, data: dict) -> bytes:
    """PDF = plantilla Word convertida (no editable). Si LibreOffice falla, ReportLab de respaldo."""
    import logging

    docx_bytes = _filled_docx(db, appraisal, appraisal_id, data)
    try:
        return docx_service.convert_docx_to_pdf(docx_bytes)
    except Exception as exc:
        logging.getLogger(__name__).warning("Conversión Word→PDF falló, se usa respaldo: %s", exc)
        return pdf_service.generate_appraisal_pdf(data, _photo_paths(db, appraisal_id))


def _photo_paths(db: Session, appraisal_id: UUID) -> list[tuple[str, Path]]:
    photo_paths: list[tuple[str, Path]] = []
    rows = db.execute(
        select(DocumentFile, MediaType)
        .join(MediaType, MediaType.id == DocumentFile.media_type_id, isouter=True)
        .where(DocumentFile.entity_type == "appraisal", DocumentFile.entity_id == appraisal_id)
        .order_by(DocumentFile.created_at.asc())
    ).all()
    for f, mt in rows:
        if mt and mt.category != "photo":
            continue
        path = UPLOAD_ROOT / f.storage_key
        if path.exists():
            photo_paths.append((mt.name if mt else "Foto", path))
    return photo_paths

