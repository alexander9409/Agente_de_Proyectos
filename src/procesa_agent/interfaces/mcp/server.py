"""
Servidor MCP (Model Context Protocol) para Procesa Consultores (src/mcp_server.py)
Expone las herramientas 'consultar_sql' y 'buscar_texto' mediante el protocolo estándar MCP
para su consumo por clientes compatibles: Google Gemini, Claude Desktop, Cursor, Windsurf, etc.
"""

from mcp.server.mcpserver import MCPServer as FastMCP

from procesa_agent.tools.tools import buscar_texto as tool_buscar_texto
from procesa_agent.tools.tools import consultar_sql as tool_consultar_sql

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


def main():
    """Ejecuta el servidor en modo estándar stdio."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
