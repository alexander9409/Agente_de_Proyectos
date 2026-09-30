"""
Clase Base para Lectores de Documentos (ingestion/readers/base.py).
Define la interfaz abstracta que deben implementar los lectores de formatos específicos.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict


class DocumentReader(ABC):
    """Clase base abstracta para extracción de texto en documentos."""

    @abstractmethod
    def read(self, path: Path) -> Dict[str, Any]:
        """
        Lee el archivo documental y retorna un diccionario con metadatos y texto íntegro.
        Estructura retornada:
        - archivo_origen: str
        - tipo: str
        - texto_completo: str
        - metadatos: dict
        """
        ...
