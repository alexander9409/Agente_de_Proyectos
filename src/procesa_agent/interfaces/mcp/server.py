"""
Servidor MCP (Model Context Protocol) para Procesa Consultores.
Genera dinámicamente las herramientas expuestas iterando el ToolRegistry centralizado.
Permite el consumo por clientes compatibles: Google Gemini, Claude Desktop, Cursor, etc.
"""

import inspect
from typing import Any, Callable

from mcp.server.mcpserver import MCPServer as FastMCP

from procesa_agent.tools import Tool, ToolRegistry, get_default_registry

# Inicializar servidor MCP con el nombre del agente
mcp = FastMCP("AgenteConsultorIA")


def _crear_handler_mcp(tool: Tool) -> Callable[..., str]:
    """
    Construye una función ejecutable con la signatura e introspección de parámetros
    exacta requerida por FastMCP a partir de tool.parameters y tool.description.
    """
    props = tool.parameters.get("properties", {})
    params = []
    for param_name in props:
        params.append(
            inspect.Parameter(
                param_name,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=str,
            )
        )
    sig = inspect.Signature(parameters=params, return_annotation=str)

    def mcp_handler(*args: Any, **kwargs: Any) -> str:
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()
        resultado = tool.run(**bound.arguments)
        return resultado["texto"]

    mcp_handler.__name__ = tool.name
    mcp_handler.__doc__ = tool.description
    mcp_handler.__signature__ = sig  # type: ignore[attr-defined]
    return mcp_handler


def registrar_herramientas_en_mcp(server: FastMCP, registry: ToolRegistry) -> None:
    """Registra dinámicamente cada herramienta del registro en el servidor MCP."""
    for tool in registry.all():
        handler = _crear_handler_mcp(tool)
        server.add_tool(handler, name=tool.name, description=tool.description)


# Registrar herramientas del registro oficial por defecto
registrar_herramientas_en_mcp(mcp, get_default_registry())


def main() -> None:
    """Ejecuta el servidor en modo estándar stdio."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
