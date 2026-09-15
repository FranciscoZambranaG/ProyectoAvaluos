"""Genera la plantilla Word de referencia (layout del PDF legacy)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.docx_service import TEMPLATE_PATH, write_blank_template

if __name__ == "__main__":
    path = write_blank_template(TEMPLATE_PATH)
    print(f"Plantilla escrita en {path}")
