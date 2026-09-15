"""Regenera placeholders centrados y descarga 2 imágenes reales de prueba."""
from __future__ import annotations

import hashlib
import uuid
from io import BytesIO
from pathlib import Path

import httpx
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import create_engine, text

from app.config import get_settings

ROOT = Path(__file__).resolve().parents[1]
W, H = 800, 600

REAL_SAMPLES = {
    "CIM-HA": "https://images.unsplash.com/photo-1503387762-592deb58ef4e?auto=format&fit=crop&w=1200&q=70",
    "EST-HA0": "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?auto=format&fit=crop&w=1200&q=70",
}


def _font(size: int):
    for name in ("segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_w: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        trial = f"{cur} {w}".strip()
        bbox = draw.textbbox((0, 0), trial, font=font)
        if bbox[2] - bbox[0] <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines[:4]


def make_placeholder(label: str, group: str) -> bytes:
    img = Image.new("RGB", (W, H), (236, 244, 252))
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, W, 72), fill=(11, 58, 110))
    title_font = _font(26)
    body_font = _font(36)
    foot_font = _font(18)

    # group centered in header
    gb = draw.textbbox((0, 0), group.upper(), font=title_font)
    gx = (W - (gb[2] - gb[0])) // 2
    draw.text((gx, 22), group.upper(), fill=(255, 255, 255), font=title_font)

    lines = _wrap(draw, label, body_font, W - 80)
    total_h = len(lines) * 44
    y = (H - total_h) // 2 - 10
    for line in lines:
        lb = draw.textbbox((0, 0), line, font=body_font)
        lx = (W - (lb[2] - lb[0])) // 2
        draw.text((lx, y), line, fill=(11, 58, 110), font=body_font)
        y += 44

    foot = "Catálogo municipal · material constructivo"
    fb = draw.textbbox((0, 0), foot, font=foot_font)
    fx = (W - (fb[2] - fb[0])) // 2
    draw.text((fx, H - 48), foot, fill=(91, 107, 124), font=foot_font)

    buf = BytesIO()
    img.save(buf, format="WEBP", quality=84, method=4)
    return buf.getvalue()


def make_from_url(url: str, label: str) -> bytes:
    with httpx.Client(timeout=40.0, follow_redirects=True) as client:
        resp = client.get(url)
        resp.raise_for_status()
        src = Image.open(BytesIO(resp.content)).convert("RGB")
    src = src.resize((W, H), Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(src)
    # subtle bottom gradient band
    draw.rectangle((0, H - 70, W, H), fill=(11, 58, 110))
    font = _font(28)
    lines = _wrap(draw, label, font, W - 60)
    y = H - 58
    for line in lines[:1]:
        lb = draw.textbbox((0, 0), line, font=font)
        lx = (W - (lb[2] - lb[0])) // 2
        draw.text((lx, y), line, fill=(255, 255, 255), font=font)
    buf = BytesIO()
    src.save(buf, format="WEBP", quality=82, method=4)
    return buf.getvalue()


def upsert_file(conn, option_id, code: str, label: str, group_name: str, mt, existing_file_id) -> None:
    if code in REAL_SAMPLES:
        try:
            data = make_from_url(REAL_SAMPLES[code], label)
        except Exception:
            data = make_placeholder(label, group_name)
    else:
        data = make_placeholder(label, group_name)

    checksum = hashlib.sha256(data).hexdigest()
    file_id = existing_file_id or uuid.uuid4()
    rel = f"catalog/materials/{code}.webp"
    path = ROOT / "uploads" / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)

    if existing_file_id:
        conn.execute(
            text(
                """
                UPDATE documents.files
                SET storage_key=:key, mime_type='image/webp', size_bytes=:size,
                    checksum_sha256=:chk, width_px=:w, height_px=:h,
                    original_name=:name, media_type_id=:mt
                WHERE id=:id
                """
            ),
            {"key": rel, "size": len(data), "chk": checksum, "w": W, "h": H, "name": f"{code}.webp", "mt": mt, "id": file_id},
        )
    else:
        conn.execute(
            text(
                """
                INSERT INTO documents.files
                  (id, entity_type, entity_id, media_type_id, storage_backend, storage_key,
                   original_name, mime_type, size_bytes, checksum_sha256, width_px, height_px)
                VALUES
                  (:id, 'characteristic_option', :entity, :mt, 'local', :key,
                   :name, 'image/webp', :size, :chk, :w, :h)
                """
            ),
            {
                "id": file_id,
                "entity": option_id,
                "mt": mt,
                "key": rel,
                "name": f"{code}.webp",
                "size": len(data),
                "chk": checksum,
                "w": W,
                "h": H,
            },
        )
        conn.execute(
            text("UPDATE config.characteristic_options SET image_file_id=:fid WHERE id=:oid"),
            {"fid": file_id, "oid": option_id},
        )


def main() -> None:
    engine = create_engine(get_settings().operativo_database_url)
    with engine.begin() as conn:
        mt = conn.execute(text("SELECT id FROM config.media_types WHERE code='catalog_material' LIMIT 1")).scalar()
        if not mt:
            raise SystemExit("media_type catalog_material no existe")
        rows = conn.execute(
            text(
                """
                SELECT o.id, o.code, o.label, g.name AS group_name, o.image_file_id
                FROM config.characteristic_options o
                JOIN config.characteristic_groups g ON g.id=o.group_id
                WHERE o.is_active
                ORDER BY g.sort_order, o.sort_order
                """
            )
        ).mappings().all()
        for row in rows:
            upsert_file(conn, row["id"], row["code"], row["label"], row["group_name"], mt, row["image_file_id"])
        print(f"OK materials={len(rows)} real={list(REAL_SAMPLES)}")


if __name__ == "__main__":
    main()
