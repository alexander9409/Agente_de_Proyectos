"""
Punto de Entrada de la Aplicación Web Streamlit (app.py).
Orquestador principal: configura la página, carga estilos, inicializa estado y despacha vistas.
"""

import sys
from pathlib import Path

# Asegurar resolucion de paquetes en src/ sin depender de instalacion previa
_SRC_DIR = str(Path(__file__).resolve().parent / "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

import streamlit as st

from procesa_agent.infrastructure.db.connection import obtener_resumen_bd
from procesa_agent.interfaces.web.components import renderizar_sidebar
from procesa_agent.interfaces.web.pages import (
    render_auditoria_page,
    render_chat_page,
    render_proyectos_page,
)
from procesa_agent.interfaces.web.state import cargar_estilos_css, inicializar_estado

st.set_page_config(
    page_title="Agente de Proyectos · Procesa Consultores",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded",
)


def main() -> None:
    """Orquestador de la interfaz web Streamlit."""
    cargar_estilos_css()
    inicializar_estado()

    config_mgr = st.session_state.config_mgr
    resumen = obtener_resumen_bd()
    renderizar_sidebar(config_mgr, resumen)

    st.markdown(
        """
        <div style="display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 8px;">
            <div class="app-header-title">💼 Consultor de Inteligencia Operativa y Proyectos</div>
            <div style="font-size: 0.82rem; color: #64748B;">Procesa Consultores · SQLite + FTS5 + Gemini</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab_chat, tab_explorador, tab_auditoria = st.tabs(
        [
            "💬 Chatbot Consultor",
            "📊 Explorador de Datos y Fichas",
            "⚙️ Auditoría y MCP",
        ]
    )

    with tab_chat:
        render_chat_page()

    with tab_explorador:
        render_proyectos_page()

    with tab_auditoria:
        render_auditoria_page()


if __name__ == "__main__":
    main()
