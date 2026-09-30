"""
Módulo de Herramientas del Agente (procesa_agent.tools).
Expone protocolos, registro de herramientas y las herramientas oficiales de consulta.
"""

from procesa_agent.tools.base import (
    Tool,
    ToolRegistry,
    ToolResult,
    default_registry,
    get_default_registry,
)
from procesa_agent.tools.fts_tool import FTSTool, fts_tool_instance
from procesa_agent.tools.sql_tool import SQLTool, sql_tool_instance

__all__ = [
    "Tool",
    "ToolResult",
    "ToolRegistry",
    "default_registry",
    "get_default_registry",
    "SQLTool",
    "FTSTool",
    "sql_tool_instance",
    "fts_tool_instance",
]
