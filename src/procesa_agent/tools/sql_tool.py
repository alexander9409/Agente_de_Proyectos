"""
Herramienta de Consulta SQL (tools/sql_tool.py).
Implementa el protocolo Tool para consultas estructuradas de solo lectura.
"""

from typing import Any, Dict, Optional

from procesa_agent.tools.base import ToolResult, default_registry
from procesa_agent.tools.tools import consultar_sql_detallado


class SQLTool:
    """Herramienta para ejecutar consultas SQL SELECT con validaciones de seguridad."""

    name: str = "consultar_sql"
    description: str = (
        "Ejecuta consultas SQL de solo lectura (SELECT) en la base de datos SQLite con las fichas de proyectos, "
        "métricas cuantitativas (kpis), lecciones aprendidas y reglas de negocio. "
        "Las tablas disponibles son: proyectos, kpis, lecciones, reglas_negocio. "
        "No está permitido acceder a la tabla sensible configuraciones ni realizar modificaciones."
    )
    parameters: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Consulta SQL SELECT estricta de solo lectura a ejecutar sobre la base de datos.",
            }
        },
        "required": ["query"],
    }

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = db_path

    def run(self, query: str = "", **kwargs: Any) -> ToolResult:
        """Ejecuta la consulta SQL y retorna el resultado formateado y estructurado."""
        target_db = kwargs.get("db_path") or self.db_path
        params = kwargs.get("params")
        texto_md, datos = consultar_sql_detallado(query, params=params, db_path=target_db)
        return ToolResult(texto=texto_md, datos=datos)


# Registro de la herramienta
sql_tool_instance = SQLTool()
default_registry.register(sql_tool_instance)
