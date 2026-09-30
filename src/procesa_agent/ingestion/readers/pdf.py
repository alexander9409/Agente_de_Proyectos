"""
Lector de Archivos PDF (ingestion/readers/pdf.py).
Extrae texto continuo utilizando pypdf y detecta PDFs sin capa de texto (escaneados).
"""

from pathlib import Path
from typing import Any, Dict

import pypdf

from procesa_agent.core.errors import IngestionError
from procesa_agent.ingestion.readers.base import DocumentReader


class PDFReader(DocumentReader):
    """Lector especializado para archivos PDF con validación de capa de texto."""

    def read(self, path: Path) -> Dict[str, Any]:
        """Lee un archivo PDF y extrae su contenido textual."""
        if not path.exists():
            raise FileNotFoundError(f"No se encontró el archivo PDF: {path}")

        try:
            reader = pypdf.PdfReader(str(path))
            paginas_texto = []
            for pagina in reader.pages:
                texto_pag = pagina.extract_text() or ""
                paginas_texto.append(texto_pag)

            texto_completo = "\n\n".join(paginas_texto).strip()

            # Validación de capa de texto
            if not texto_completo:
                raise IngestionError(
                    f"El archivo PDF '{path.name}' no tiene capa de texto (sin capa de texto detectable, posible documento escaneado o imagen pura)."
                )

            return {
                "archivo_origen": path.name,
                "tipo": "pdf",
                "texto_completo": texto_completo,
                "num_paginas": len(reader.pages),
            }
        except IngestionError:
            raise
        except Exception as e:
            raise IngestionError(f"Error al procesar el archivo PDF '{path.name}': {e}") from e
