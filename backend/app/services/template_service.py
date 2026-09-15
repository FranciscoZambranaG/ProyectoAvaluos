"""Gestión parametrizable de plantillas Word (.docx) del formulario técnico."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, UploadFile
from pydantic import BaseModel, Field

BUILTIN_DIR = Path(__file__).resolve().parent.parent / "templates"
CUSTOM_DIR = Path(__file__).resolve().parents[2] / "uploads" / "templates"
REPO_TEMPLATES_DIR = Path(__file__).resolve().parents[3] / "templates"

TEMPLATE_CODE = "formulario_datos_tecnicos"
TEMPLATE_FILENAME = "formulario_datos_tecnicos.docx"

PLACEHOLDERS = [
    "cadastral_code",
    "property_number",
    "pmc",
    "owner_name",
    "owner_document",
    "owner_city",
    "registry_matricula",
    "registry_asiento",
    "registry_ddr_date",
    "form_number",
    "form_date",
    "form_code",
    "address",
    "door_number",
    "building_name",
    "floor_label",
    "apartment_label",
    "latitude",
    "longitude",
    "front_length",
    "depth_length",
    "approved_area",
    "location_label",
    "zone_label",
    "zone_m2",
    "road_label",
    "topo_label",
    "shape_label",
    "services",
    "observations",
    "professional_name",
    "professional_reg",
    "land_value",
    "blocks_value",
    "improvements_value",
    "total_value",
    "blocks (lista: unit_number, construction_year, kind, area, floors_count, typology, total_score, modification_year)",
    "all_chars (lista: block, n, group, option, base, pct, score)",
    "croquis_predio / croquis_ubicacion / foto_fachada1 / foto_fachada2 / foto_interior (imágenes)",
]


class TemplateInfo(BaseModel):
    code: str
    name: str
    filename: str
    description: str
    source: str = Field(description="builtin | custom")
    size_bytes: int
    updated_at: datetime | None = None
    has_custom: bool = False
    placeholders: list[str] = Field(default_factory=list)


def _builtin_path() -> Path:
    path = BUILTIN_DIR / TEMPLATE_FILENAME
    if path.exists():
        return path
    mirror = REPO_TEMPLATES_DIR / TEMPLATE_FILENAME
    if mirror.exists():
        return mirror
    return path


def _custom_path() -> Path:
    return CUSTOM_DIR / TEMPLATE_FILENAME


def ensure_builtin_template() -> Path:
    """Garantiza que exista la plantilla vacía de referencia."""
    path = _builtin_path()
    if path.exists() and path.stat().st_size > 0:
        return path
    from app.services.docx_service import write_blank_template

    path.parent.mkdir(parents=True, exist_ok=True)
    return write_blank_template(path)


def get_active_template_path() -> Path:
    custom = _custom_path()
    if custom.exists() and custom.stat().st_size > 0:
        return custom
    return ensure_builtin_template()


def _file_info(path: Path) -> tuple[int, datetime | None]:
    if not path.exists():
        return 0, None
    st = path.stat()
    return int(st.st_size), datetime.fromtimestamp(st.st_mtime, tz=timezone.utc)


def list_templates() -> list[TemplateInfo]:
    ensure_builtin_template()
    custom = _custom_path()
    active = get_active_template_path()
    size, updated = _file_info(active)
    return [
        TemplateInfo(
            code=TEMPLATE_CODE,
            name="Formulario de datos técnicos",
            filename=TEMPLATE_FILENAME,
            description=(
                "Plantilla Word del formulario de actualización de datos técnicos "
                "(declaración jurada / impresión PDF)."
            ),
            source="custom" if active == custom else "builtin",
            size_bytes=size,
            updated_at=updated,
            has_custom=custom.exists() and custom.stat().st_size > 0,
            placeholders=PLACEHOLDERS,
        )
    ]


def get_template(code: str) -> TemplateInfo:
    if code != TEMPLATE_CODE:
        raise HTTPException(404, "Plantilla no encontrada")
    return list_templates()[0]


def read_active_bytes(code: str) -> tuple[bytes, str]:
    info = get_template(code)
    path = get_active_template_path()
    return path.read_bytes(), info.filename


def read_blank_bytes(code: str) -> tuple[bytes, str]:
    if code != TEMPLATE_CODE:
        raise HTTPException(404, "Plantilla no encontrada")
    from app.services.docx_service import write_blank_template

    with_tmp = CUSTOM_DIR / "_blank_preview.docx"
    CUSTOM_DIR.mkdir(parents=True, exist_ok=True)
    write_blank_template(with_tmp)
    data = with_tmp.read_bytes()
    with_tmp.unlink(missing_ok=True)
    return data, f"plantilla_vacia_{TEMPLATE_FILENAME}"


async def upload_template(code: str, upload: UploadFile) -> TemplateInfo:
    if code != TEMPLATE_CODE:
        raise HTTPException(404, "Plantilla no encontrada")
    name = (upload.filename or "").lower()
    if not name.endswith(".docx"):
        raise HTTPException(400, "Solo se admiten archivos .docx (Word)")
    raw = await upload.read()
    if not raw or len(raw) < 100:
        raise HTTPException(400, "Archivo vacío o inválido")
    # Firma ZIP/Office Open XML
    if raw[:2] != b"PK":
        raise HTTPException(400, "El archivo no parece un .docx válido")
    CUSTOM_DIR.mkdir(parents=True, exist_ok=True)
    dest = _custom_path()
    # Respaldo de la custom anterior
    if dest.exists():
        bak = CUSTOM_DIR / f"{TEMPLATE_FILENAME}.bak"
        shutil.copy2(dest, bak)
    dest.write_bytes(raw)
    # Espejo en carpeta del repo templates/ (referencia)
    try:
        REPO_TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(dest, REPO_TEMPLATES_DIR / TEMPLATE_FILENAME)
    except OSError:
        pass
    return get_template(code)


def restore_builtin(code: str) -> TemplateInfo:
    if code != TEMPLATE_CODE:
        raise HTTPException(404, "Plantilla no encontrada")
    custom = _custom_path()
    if custom.exists():
        custom.unlink()
    ensure_builtin_template()
    return get_template(code)
