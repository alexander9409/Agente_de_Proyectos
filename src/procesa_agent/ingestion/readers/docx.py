"""
Lector de Archivos DOCX (ingestion/readers/docx.py).
Extrae texto íntegro y estructurado preservando el orden de párrafos y tablas mediante python-docx.
"""

from pathlib import Path
from typing import Any, Dict, List

import docx
from docx.table import Table
from docx.text.paragraph import Paragraph

from procesa_agent.core.errors import IngestionError
from procesa_agent.ingestion.readers.base import DocumentReader


class DocxReader(DocumentReader):
    """Lector especializado para archivos DOCX."""

    def read(self, path: Path) -> Dict[str, Any]:
        """Lee un archivo DOCX extrayendo párrafos y tablas tabulares."""
        if not path.exists():
            raise FileNotFoundError(f"No se encontró el archivo DOCX: {path}")

        try:
            doc = docx.Document(str(path))
            lineas: List[str] = []

            for elemento in doc.element.body:
                if elemento.tag.endswith("p"):
                    p = Paragraph(elemento, doc)
                    if p.text.strip():
                        lineas.append(p.text.strip())
                elif elemento.tag.endswith("tbl"):
                    t = Table(elemento, doc)
                    filas_texto = []
                    for fila in t.rows:
                        celdas = [c.text.strip() for c in fila.cells]
                        filas_texto.append(" | ".join(celdas))
                    if filas_texto:
                        lineas.append("\n".join(filas_texto))

            texto_completo = "\n\n".join(lineas).strip()

            if not texto_completo:
                raise IngestionError(
                    f"El archivo DOCX '{path.name}' se encuentra vacío o sin contenido legible."
                )

            return {
                "archivo_origen": path.name,
                "tipo": "docx",
                "texto_completo": texto_completo,
                "num_bloques": len(lineas),
            }
        except IngestionError:
            raise
        except Exception as e:
            raise IngestionError(f"Error al procesar el archivo DOCX '{path.name}': {e}") from e
