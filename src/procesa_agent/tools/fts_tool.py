"""
Herramienta de Búsqueda de Texto Completo FTS5 (tools/fts_tool.py).
Implementa el protocolo Tool para búsquedas documentales cualitativas.
"""

from typing import Any, Dict, Optional

from procesa_agent.tools.base import ToolResult, default_registry
from procesa_agent.tools.tools import buscar_texto_detallado


class FTSTool:
    """Herramienta para ejecutar búsquedas de texto completo (FTS5) en informes de consultoría."""

    name: str = "buscar_texto"
    description: str = (
        "Realiza búsquedas de texto completo (FTS5) en el contenido íntegro de los informes de cierre de proyectos. "
        "Permite recuperar fragmentos textuales, diagnósticos cualitativos, justificaciones de alcance, "
        "metodología y citas literales con su archivo de origen."
    )
    parameters: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "terminos_busqueda": {
                "type": "string",
                "description": "Palabras o frases clave para buscar en el texto completo de los informes.",
            }
        },
        "required": ["terminos_busqueda"],
    }

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = db_path

    def run(self, terminos_busqueda: str = "", **kwargs: Any) -> ToolResult:
        """Ejecuta la búsqueda de texto FTS5 y retorna el resultado formateado y estructurado."""
        target_db = kwargs.get("db_path") or self.db_path
        # Respaldo en caso de que el llamador use 'query' en vez de 'terminos_busqueda'
        terminos = terminos_busqueda or kwargs.get("query") or ""
        texto_md, datos = buscar_texto_detallado(terminos, db_path=target_db)
        return ToolResult(texto=texto_md, datos=datos)


# Registro de la herramienta
fts_tool_instance = FTSTool()
default_registry.register(fts_tool_instance)
