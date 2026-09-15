from app.services.docx_service import convert_docx_to_pdf, generate_appraisal_docx
from app.services.pdf_service import generate_appraisal_pdf, image_bytes_to_png, _location_view_bbox
from io import BytesIO
from pathlib import Path

from PIL import Image


def test_generate_appraisal_docx_is_zip():
    raw = generate_appraisal_docx(
        {
            "form_number": "AV-TEST",
            "cadastral_code": "01-001-001-0-00-000-000",
            "address": "Calle Test",
            "front_length": 10,
            "depth_length": 20,
            "approved_area": 200,
            "services": ["Agua potable"],
            "blocks": [],
            "map_meta": {},
            "land_value": 1000,
            "blocks_value": 200,
            "improvements_value": 50,
            "total_value": 1250,
        },
        [],
        professional_name="Arquitecto",
        professional_reg="1",
    )
    assert raw[:2] == b"PK"
    assert len(raw) > 5000


def test_image_bytes_to_png_from_webp():
    buf = BytesIO()
    Image.new("RGB", (80, 60), (10, 20, 30)).save(buf, format="WEBP")
    png = image_bytes_to_png(buf.getvalue())
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    out = Image.open(BytesIO(png))
    assert out.size == (80, 60)


def test_reportlab_pdf_accepts_webp_photos(tmp_path: Path):
    webp = tmp_path / "foto.webp"
    Image.new("RGB", (2400, 1600), (80, 90, 100)).save(webp, format="WEBP")
    raw = generate_appraisal_pdf(
        {
            "form_number": "AV-TEST",
            "cadastral_code": "01-001-001",
            "address": "Calle Test",
            "blocks": [],
            "map_meta": {},
        },
        [("Foto frente", webp)],
    )
    assert raw[:4] == b"%PDF"


def test_convert_docx_to_pdf_if_libreoffice():
    import shutil

    if not (shutil.which("soffice") or shutil.which("libreoffice")):
        return
    raw = generate_appraisal_docx(
        {
            "form_number": "AV-TEST",
            "cadastral_code": "01-001-001",
            "address": "Calle Test",
            "front_length": 10,
            "depth_length": 20,
            "approved_area": 200,
            "blocks": [],
            "map_meta": {},
        },
        [],
    )
    pdf = convert_docx_to_pdf(raw)
    assert pdf[:4] == b"%PDF"


def test_header_qr_is_png():
    from app.services.docx_service import build_header_qr, _qr_payload

    png = build_header_qr("01-001-002-0-00-000-000", "12345", "PMC-9")
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    img = Image.open(BytesIO(png))
    assert img.size[0] >= 40
    assert img.size[0] == img.size[1]
    payload = _qr_payload("01-001-002-0-00-000-000", "12345", "PMC-9")
    assert "01-001-002-0-00-000-000" in payload
    assert "12345" in payload
    assert "PMC-9" in payload


def test_location_view_bbox_is_closer_than_city_block():
    import math

    ring = [
        [-66.1600, -17.4000],
        [-66.1597, -17.4000],
        [-66.1597, -17.3997],
        [-66.1600, -17.3997],
        [-66.1600, -17.4000],
    ]
    bbox = _location_view_bbox([ring], 840, 560)
    assert bbox is not None
    minx, miny, maxx, maxy = bbox
    clat = (miny + maxy) / 2
    m_per_lng = 111320.0 * math.cos(math.radians(clat))
    pw = (0.0003) * m_per_lng
    view_w = (maxx - minx) * m_per_lng
    # Predio ~20–30 % del ancho, o vista mínima ~90 m (calles de la manzana).
    assert view_w < 220
    assert pw / view_w >= 0.12
    assert view_w / pw >= 3.0
