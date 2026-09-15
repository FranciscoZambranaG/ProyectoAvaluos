"""Corrige mojibake y deja textos de config/auth legibles."""
from __future__ import annotations

from sqlalchemy import create_engine, text

from app.config import get_settings

TARGETS = [
    ("config.catalog_items", "id", ["label", "description"]),
    ("config.catalog_types", "id", ["name", "description"]),
    ("config.characteristic_groups", "id", ["name"]),
    ("config.characteristic_options", "id", ["label", "description"]),
    ("config.media_types", "id", ["name"]),
    ("config.workflow_statuses", "id", ["name"]),
    ("config.form_sections", "id", ["name"]),
    ("config.form_fields", "id", ["label"]),
    ("config.formula_definitions", "id", ["name", "description"]),
    ("config.formula_versions", "id", ["expression", "notes"]),
    ("config.system_parameters", "id", ["description"]),
    ("auth.roles", "id", ["name", "description"]),
    ("auth.permissions", "id", ["name"]),
]


def fix_text(value: str | None) -> str | None:
    if not value or not isinstance(value, str):
        return value
    current = value
    for _ in range(3):
        if "Ã" not in current and "Â" not in current and "�" not in current:
            break
        try:
            nxt = current.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            break
        if nxt == current:
            break
        current = nxt
    return current


def main() -> None:
    engine = create_engine(get_settings().operativo_database_url)
    fixed = 0
    with engine.begin() as conn:
        for table, pk, cols in TARGETS:
            rows = conn.execute(text(f"SELECT {pk}, {', '.join(cols)} FROM {table}")).mappings().all()
            for row in rows:
                updates = {}
                for col in cols:
                    old = row[col]
                    new = fix_text(old)
                    if new is not None and new != old:
                        updates[col] = new
                if not updates:
                    continue
                sets = ", ".join(f"{c} = :{c}" for c in updates)
                conn.execute(
                    text(f"UPDATE {table} SET {sets} WHERE {pk} = :pk"),
                    {**updates, "pk": row[pk]},
                )
                fixed += 1
    print(f"OK rows_fixed={fixed}")


if __name__ == "__main__":
    main()
