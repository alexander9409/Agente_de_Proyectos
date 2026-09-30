"""
Página de Auditoría, Configuraciones y Diagnóstico MCP (interfaces/web/pages/auditoria_page.py).
Permite auditar parámetros del sistema, claves enmascaradas y diagnosticar el servidor MCP.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

from procesa_agent.core.config_manager import ConfigManager
from procesa_agent.core.paths import BASE_DIR


def render_auditoria_page() -> None:
    """Renderiza la vista de auditoría técnica, configuraciones persistidas y estado del MCP."""
    st.subheader("Auditoría Técnica, Parámetros y Diagnóstico")

    subtab_config, subtab_mcp = st.tabs(
        ["⚙️ Tabla 'configuraciones' SQLite", "🔌 Servidor MCP (Model Context Protocol)"]
    )

    with subtab_config:
        st.markdown(
            "Esta tabla almacena parámetros persistentes del sistema en SQLite. "
            "Por políticas estrictas de seguridad (S1/S4), las claves de API están permanentemente enmascaradas."
        )

        config_mgr: ConfigManager = st.session_state.config_mgr
        configs = config_mgr.get_all_configs()

        if configs:
            filas = [
                {
                    "Clave": k,
                    "Valor": "•••••••• (Protegido)" if "key" in k.lower() else v.get("valor", ""),
                    "Descripción": v.get("descripcion", ""),
                    "Última Actualización": v.get("fecha_actualizacion", ""),
                }
                for k, v in configs.items()
            ]
            st.dataframe(pd.DataFrame(filas), use_container_width=True, hide_index=True)
        else:
            st.info("No hay registros en la tabla configuraciones.")

    with subtab_mcp:
        st.markdown(
            "El servidor MCP expone las herramientas `consultar_sql` y `buscar_texto` mediante el estándar "
            "de la industria **Model Context Protocol (MCP)** para conectar con clientes de IA: "
            "**Claude Desktop**, **Cursor**, **Windsurf** y agentes autónomos."
        )

        col_st1, col_st2 = st.columns([1, 1])
        with col_st1:
            st.markdown(
                """
            <div style="background: #F0FDF4; border: 1px solid #BBF7D0; border-radius: 10px; padding: 16px; margin-bottom: 16px;">
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">
                    <span style="font-size: 1.2rem;">🟢</span>
                    <strong style="color: #166534; font-size: 1rem;">Servidor MCP Disponible</strong>
                </div>
                <div style="font-size: 0.85rem; color: #15803D; line-height: 1.5;">
                    Módulo: <code>src/procesa_agent/interfaces/mcp/server.py</code> · Transporte: <b>stdio</b> estándar.<br>
                    <b>Auto-levantamiento:</b> Los clientes MCP levantan e interactúan automáticamente con el servidor como proceso hijo.
                </div>
            </div>
            """,
                unsafe_allow_html=True,
            )

        with col_st2:
            st.markdown(
                """
            <div style="background: #EFF6FF; border: 1px solid #BFDBFE; border-radius: 10px; padding: 16px; margin-bottom: 16px;">
                <strong style="color: #1D4ED8; font-size: 0.95rem;">🛠️ Herramientas Registradas en el MCP:</strong>
                <ul style="font-size: 0.85rem; color: #1E40AF; margin: 6px 0 0 0; padding-left: 20px;">
                    <li><code>consultar_sql(query: str)</code>: Consultas analíticas de solo lectura contra SQLite.</li>
                    <li><code>buscar_texto(terminos_busqueda: str)</code>: Búsqueda léxica y semántica en índice virtual FTS5.</li>
                </ul>
            </div>
            """,
                unsafe_allow_html=True,
            )

        ruta_mcp_abs = str((BASE_DIR / "src" / "mcp_server.py").resolve()).replace("\\", "\\\\")
        python_exe = sys.executable.replace("\\", "\\\\")

        config_mcp_dict = {
            "mcpServers": {
                "procesa-consultores": {
                    "command": python_exe,
                    "args": [ruta_mcp_abs],
                }
            }
        }
        config_mcp_str = json.dumps(config_mcp_dict, indent=2)

        st.markdown("#### 📋 Configuración para Claude Desktop, Cursor y Windsurf")
        st.caption("Copia y pega este bloque JSON en tu archivo de configuración del cliente MCP:")
        st.code(config_mcp_str, language="json")

        st.caption(
            "📁 **Ruta en Windows para Claude Desktop:** `%APPDATA%\\Claude\\claude_desktop_config.json`"
        )
        st.caption(
            "📁 **Ruta en Cursor / Windsurf:** `.cursor/mcp.json` o en Configuración > Features > MCP."
        )

        st.markdown("---")
        st.markdown("#### 🧪 Prueba de Diagnóstico MCP en Vivo")

        if st.button("🚀 Ejecutar Diagnóstico MCP en Vivo"):
            with st.spinner("Conectando con el servidor MCP y ejecutando verificación..."):
                try:
                    from mcp.client.session import ClientSession
                    from mcp.client.stdio import StdioServerParameters, stdio_client

                    async def _diagnostico():
                        env_mcp = dict(os.environ)
                        rutas = [str(BASE_DIR), str(BASE_DIR / "src")] + [
                            p for p in sys.path if p and Path(p).exists()
                        ]
                        env_mcp["PYTHONPATH"] = os.pathsep.join(rutas)

                        params = StdioServerParameters(
                            command=sys.executable,
                            args=[str(BASE_DIR / "src" / "mcp_server.py")],
                            env=env_mcp,
                        )
                        async with stdio_client(params) as (read, write):
                            async with ClientSession(read, write) as session:
                                await session.initialize()
                                tools_resp = await session.list_tools()
                                res_sql = await session.call_tool(
                                    "consultar_sql",
                                    {
                                        "query": "SELECT codigo_proyecto, cliente, estado FROM proyectos ORDER BY codigo_proyecto;"
                                    },
                                )
                                return [t.name for t in tools_resp.tools], (
                                    res_sql.content[0].text if res_sql.content else ""
                                )

                    herramientas, resultado_sql = asyncio.run(_diagnostico())
                    st.success(
                        f"✅ Protocolo MCP 100% operativo. Herramientas registradas: `{herramientas}`"
                    )
                    st.markdown("**Resultado de consulta SQL vía MCP:**")
                    st.markdown(resultado_sql)
                except Exception as e:
                    st.error(f"Error al verificar servidor MCP: {e}")
                    if "No module named 'mcp'" in str(e):
                        st.info("💡 Instala mcp en tu entorno: `pip install mcp`")
