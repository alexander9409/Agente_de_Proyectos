"""
Módulo de Lectores de Documentos (procesa_agent.ingestion.readers).
Provee la fábrica get_reader para instanciar el lector adecuado según la extensión (.pdf o .docx)
y rechazar formatos no soportados con mensajes de error explícitos.
"""

from pathlib import Path

from procesa_agent.core.errors import IngestionError
from procesa_agent.ingestion.readers.base import DocumentReader
from procesa_agent.ingestion.readers.docx import DocxReader
from procesa_agent.ingestion.readers.pdf import PDFReader


def get_reader(file_path: Path) -> DocumentReader:
    """Retorna la instancia del lector apropiado según la extensión del archivo."""
    extension = file_path.suffix.lower()

    if extension == ".pdf":
        return PDFReader()
    elif extension == ".docx":
        return DocxReader()
    elif extension == ".doc":
        raise IngestionError(
            f"Formato heredado '.doc' no soportado en '{file_path.name}'. "
            "Por favor guarde o convierta el archivo al formato moderno '.docx' o '.pdf'."
        )
    else:
        raise IngestionError(
            f"Formato no soportado '{extension}' en '{file_path.name}'. "
            "El sistema de ingesta solo admite documentos en formato .pdf o .docx."
        )


__all__ = [
    "DocumentReader",
    "PDFReader",
    "DocxReader",
    "get_reader",
]
