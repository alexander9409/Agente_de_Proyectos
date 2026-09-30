"""
Protocolo y Registro Centralizado de Herramientas (tools/base.py).
Define las abstracciones ToolResult, Tool y ToolRegistry para desacoplar
la ejecución de herramientas de los proveedores de LLM e interfaces (MCP, CLI, Web).
"""

from typing import Any, Dict, List, Optional, Protocol, TypedDict, runtime_checkable


class ToolResult(TypedDict):
    """Resultado estandarizado de la ejecución de una herramienta."""

    texto: str  # Markdown para el LLM y la interfaz de usuario
    datos: List[Dict[str, Any]]  # Registros estructurados para trazabilidad y tablas interactivas


@runtime_checkable
class Tool(Protocol):
    """Protocolo que debe implementar cualquier herramienta del sistema."""

    name: str
    description: str
    parameters: Dict[str, Any]  # JSON Schema para Function Declarations

    def run(self, **kwargs: Any) -> ToolResult:
        """Ejecuta la herramienta con los argumentos provistos."""
        ...


class ToolRegistry:
    """Registro desacoplado de herramientas ejecutables."""

    def __init__(self) -> None:
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Registra una nueva herramienta en el registro."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        """Recupera una herramienta por su identificador único."""
        return self._tools.get(name)

    def all(self) -> List[Tool]:
        """Retorna la lista de todas las herramientas registradas."""
        return list(self._tools.values())

    def unregister(self, name: str) -> Optional[Tool]:
        """Elimina una herramienta del registro (útil para pruebas)."""
        return self._tools.pop(name, None)


# Registro global por defecto
default_registry = ToolRegistry()


def get_default_registry() -> ToolRegistry:
    """Obtiene el registro global de herramientas por defecto."""
    return default_registry
