"""
Página Principal del Chatbot Consultor (interfaces/web/pages/chat_page.py).
Gestiona el flujo interactivo de diálogo, presentación de fuentes y trazabilidad en Streamlit.
"""

import streamlit as st

from procesa_agent.interfaces.web.components.chat import (
    renderizar_historial_chat,
    renderizar_trazabilidad,
)
from procesa_agent.interfaces.web.components.fuentes_viewer import resaltar_fuentes


def render_chat_page() -> None:
    """Renderiza la vista principal de conversación con el agente."""
    mensajes = st.session_state.get("mensajes", [])

    chat_container = st.container()

    if not mensajes:
        with chat_container:
            st.markdown(
                """
            <div style="background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 14px; padding: 36px 24px; margin: 30px auto; text-align: center; max-width: 650px;">
                <div style="font-size: 2.4rem; margin-bottom: 10px;">💼</div>
                <h3 style="margin: 0 0 10px 0; color: #0F172A; font-weight: 700; font-size: 1.3rem;">
                    ¿En qué puedo ayudarte hoy sobre los proyectos?
                </h3>
                <p style="color: #64748B; font-size: 0.92rem; margin-bottom: 18px; line-height: 1.55;">
                    Consulta métricas oficiales de cierre, duraciones, causas de desvío, lecciones aprendidas o metodologías de <b>Procesa Consultores</b> con rigor analítico y cero alucinaciones.
                </p>
                <div style="display: inline-block; background: #EFF6FF; border: 1px solid #BFDBFE; border-radius: 20px; padding: 7px 18px; font-size: 0.84rem; color: #1D4ED8; font-weight: 500;">
                    💬 <i>Escribe tu consulta en la barra inferior para consultar el portafolio de proyectos.</i>
                </div>
            </div>
            """,
                unsafe_allow_html=True,
            )
    else:
        with chat_container:
            renderizar_historial_chat(mensajes)

    # Barra fija de chat input
    pregunta = st.chat_input("Escribe tu consulta sobre los proyectos...")

    if pregunta:
        # Registrar mensaje del usuario
        st.session_state.mensajes.append({"rol": "user", "contenido": pregunta})
        with chat_container:
            with st.chat_message("user", avatar="👤"):
                st.markdown(pregunta)

            with st.chat_message("assistant", avatar="💼"):
                with st.spinner("Analizando base de datos relacional y textos completos..."):
                    agente = st.session_state.agente
                    respuesta_dict = agente.responder(pregunta)
                    texto_resp = respuesta_dict.get("respuesta", "")
                    traza = respuesta_dict.get("trazabilidad", [])

                    st.markdown(resaltar_fuentes(texto_resp), unsafe_allow_html=True)
                    renderizar_trazabilidad(traza)

        # Persistir respuesta del asistente en el historial
        st.session_state.mensajes.append(
            {"rol": "assistant", "contenido": texto_resp, "trazabilidad": traza}
        )
        st.rerun()
