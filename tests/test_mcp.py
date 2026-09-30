"""
Pruebas Automatizadas para el Servidor MCP (tests/test_mcp.py)
Valida la inicialización del servidor MCP, el registro de herramientas
y la ejecución de consultas mediante el protocolo estándar MCP (Model Context Protocol).
"""

import asyncio
import os
import sys
from pathlib import Path

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

BASE_DIR = Path(__file__).resolve().parent.parent


def test_mcp_server_tools_registration():
    """Valida que el servidor MCP inicie y exponga las herramientas 'consultar_sql' y 'buscar_texto'."""

    async def _test():
        script_mcp = str(BASE_DIR / "src" / "mcp_server.py")
        params = StdioServerParameters(
            command=sys.executable,
            args=[script_mcp],
            env=dict(os.environ),
        )

        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools_resp = await session.list_tools()
                nombres = [t.name for t in tools_resp.tools]

                assert "consultar_sql" in nombres, (
                    "La herramienta 'consultar_sql' debe estar registrada en el MCP"
                )
                assert "buscar_texto" in nombres, (
                    "La herramienta 'buscar_texto' debe estar registrada en el MCP"
                )

    asyncio.run(_test())


def test_mcp_server_tool_execution():
    """Valida la ejecución de una consulta SQL mediante el protocolo MCP."""

    async def _test():
        script_mcp = str(BASE_DIR / "src" / "mcp_server.py")
        params = StdioServerParameters(
            command=sys.executable,
            args=[script_mcp],
            env=dict(os.environ),
        )

        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # Probar consultar_sql
                res_sql = await session.call_tool(
                    "consultar_sql", {"query": "SELECT COUNT(*) as total FROM proyectos;"}
                )
                assert res_sql.content, "La respuesta de consultar_sql no debe ser vacía"
                texto_sql = res_sql.content[0].text
                assert "4" in texto_sql, "Debe retornar los 4 proyectos registrados"

                # Probar buscar_texto
                res_fts = await session.call_tool("buscar_texto", {"terminos_busqueda": "OEE"})
                assert res_fts.content, "La respuesta de buscar_texto no debe ser vacía"
                texto_fts = res_fts.content[0].text
                assert "PC-2025-027" in texto_fts or "Plásticos" in texto_fts

    asyncio.run(_test())
