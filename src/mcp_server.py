"""
Servidor MCP (Model Context Protocol) para Procesa Consultores (src/mcp_server.py)
Expone las herramientas 'consultar_sql' y 'buscar_texto' mediante el protocolo estándar MCP
para su consumo por clientes compatibles: Google Gemini, Claude Desktop, Cursor, Windsurf, etc.
"""

import sys
from pathlib import Path

# Asegurar path para importaciones relativas
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

try:
    from mcp.server.mcpserver import MCPServer
    FastMCP = MCPServer
except (ImportError, ModuleNotFoundError):
    try:
        from mcp.server.fastmcp import FastMCP
    except Exception:
        from mcp.server import MCPServer as FastMCP

from src.tools import buscar_texto as tool_buscar_texto
from src.tools import consultar_sql as tool_consultar_sql

# Inicializar servidor MCP con el nombre del agente
mcp = FastMCP("AgenteConsultorIA")


@mcp.tool()
def consultar_sql(query: str) -> str:
    """
    Ejecuta consultas SQL de solo lectura (SELECT) en la base de datos relacional SQLite de Procesa Consultores.
    Tablas disponibles:
    - proyectos (codigo_proyecto, cliente, sector, duracion_semanas, gerente_proyecto, estado, alcance_incluido, alcance_excluido, ...)
    - kpis (codigo_proyecto, indicador, linea_base, meta, resultado, variacion, cumplimiento, ...)
    - lecciones (codigo_proyecto, tema, titulo, descripcion)
    """
    return tool_consultar_sql(query)


@mcp.tool()
def buscar_texto(terminos_busqueda: str) -> str:
    """
    Realiza búsquedas de texto completo (FTS5) en el contenido íntegro de los informes de consultoría.
    Permite encontrar descripciones cualitativas, detalles metodológicos, justificaciones de alcance y lecciones aprendidas.
    """
    return tool_buscar_texto(terminos_busqueda)


if __name__ == "__main__":
    # Ejecuta el servidor en modo estándar 'stdio'
    mcp.run(transport="stdio")
