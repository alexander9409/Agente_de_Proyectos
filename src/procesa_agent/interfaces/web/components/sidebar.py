"""
Componente Barra Lateral (Sidebar) de Streamlit (interfaces/web/components/sidebar.py).
Agrupa indicadores de estado del repositorio, configuración segura de LLM y disparadores de ingesta.
"""

from typing import Any, Dict

import streamlit as st

from procesa_agent.core.config_manager import ConfigManager
from procesa_agent.ingestion.pipeline import IngestionPipeline
from procesa_agent.interfaces.web.state import actualizar_configuracion, limpiar_chat


def renderizar_sidebar(config_mgr: ConfigManager, resumen: Dict[str, Any]) -> None:
    """Renderiza la barra lateral con controles operacionales y configuración segura."""
    with st.sidebar:
        st.title("💼 Procesa Consultores")
        st.caption("Sistema de Inteligencia de Proyectos y Optimización Operativa")

        st.markdown("---")
        st.subheader("📊 Estado del Repositorio")
        col_m1, col_m2 = st.columns(2)
        col_m1.metric("Proyectos", resumen.get("proyectos", 0))
        col_m2.metric("KPIs", resumen.get("kpis", 0))
        col_m3, col_m4 = st.columns(2)
        col_m3.metric("Lecciones", resumen.get("lecciones", 0))
        col_m4.metric("Docs FTS", resumen.get("fts", 0))

        st.markdown(
            """
        <div style="margin-top: 8px; margin-bottom: 6px;">
            <span class="deal-pill">Auditoría Operativa</span>
            <span class="deal-pill">Lean & TPM</span>
            <span class="deal-pill">Cero Alucinaciones</span>
            <span class="deal-pill">SQLite + FTS5</span>
        </div>
        <div style="font-size: 0.76rem; color: #64748B; background: #F8FAFC; padding: 6px 10px; border-radius: 6px; border: 1px solid #E2E8F0; margin-bottom: 4px;">
            <b>Pipeline:</b> Ingesta ➔ SQLite & FTS5 ➔ Agente IA
        </div>
        """,
            unsafe_allow_html=True,
        )

        st.markdown("---")
        st.subheader("⚙️ Configuración LLM")

        # Seguridad crítica: Campo password, jamás exponer texto plano
        key_actual = config_mgr.gemini_api_key or ""
        placeholder_key = (
            "•••••••• (Guardada en sistema)" if key_actual else "Pega tu GEMINI_API_KEY..."
        )

        input_api_key = st.text_input(
            "GEMINI_API_KEY",
            value="",
            placeholder=placeholder_key,
            type="password",
            help="Clave API de Gemini. Se guarda cifrada/persistida en SQLite. No se precarga en plano.",
        )

        modelos_disponibles = [
            "gemini-3.8-flash",
            "gemini-3.5-flash",
            "gemini-2.5-flash",
            "gemini-1.5-pro",
        ]
        modelo_actual = config_mgr.model_name
        idx_modelo = (
            modelos_disponibles.index(modelo_actual) if modelo_actual in modelos_disponibles else 0
        )
        select_model = st.selectbox("Modelo", modelos_disponibles, index=idx_modelo)

        temp_actual = config_mgr.temperature
        slider_temp = st.slider(
            "Temperatura", min_value=0.0, max_value=1.0, value=float(temp_actual), step=0.05
        )

        if st.button("💾 Guardar Configuración", type="primary", use_container_width=True):
            actualizar_configuracion(
                api_key=input_api_key if input_api_key.strip() else None,
                model_name=select_model,
                temperature=slider_temp,
            )
            st.success("Configuración actualizada con éxito.")
            st.rerun()

        st.markdown("---")
        st.subheader("📥 Ingesta de Informes")
        forzar_ingesta = st.checkbox(
            "Forzar re-extracción total",
            value=False,
            help="Ignora los hashes SHA-256 previos y vuelve a procesar todos los documentos.",
        )

        if st.button("🔄 Ejecutar Ingesta / Re-procesar", use_container_width=True):
            with st.spinner("Procesando pipeline de informes e indexando..."):
                try:
                    pipeline = IngestionPipeline()
                    reporte = pipeline.ejecutar(force=forzar_ingesta)
                    st.success(
                        f"Procesados: {len(reporte['procesados'])} · "
                        f"Omitidos: {len(reporte['omitidos'])} · "
                        f"Fallidos: {len(reporte['fallidos'])}"
                    )
                    st.rerun()
                except Exception as e:
                    st.error(f"Error durante la ingesta: {e}")

        st.markdown("---")
        if st.button("🗑️ Limpiar Historial de Chat", use_container_width=True):
            limpiar_chat()
            st.rerun()
