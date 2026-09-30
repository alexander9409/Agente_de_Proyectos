"""
Aplicación Web Interactiva en Streamlit (app.py)
Interfaz gráfica de alta fidelidad para el Agente de Proyectos de Procesa Consultores.
Diseñada para consultores y directores de negocio con visualización ejecutiva,
eliminación total de textos truncados y tablas interactivas en Pandas/Streamlit.
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from procesa_agent.agent.orchestrator import AgenteProyectos
from procesa_agent.core.config_manager import ConfigManager
from procesa_agent.infrastructure.db.connection import (
    inicializar_bd,
    obtener_resumen_bd,
    obtener_todas_lecciones,
    obtener_todos_kpis,
    obtener_todos_proyectos,
)
from procesa_agent.ingestion.extractor import ejecutar_ingesta_completa

BASE_DIR = Path(__file__).resolve().parent

# ==========================================
# CONFIGURACIÓN GENERAL Y ESTILOS CSS
# ==========================================
st.set_page_config(
    page_title="Agente de Proyectos · Procesa Consultores",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Estilos CSS personalizados para forzar interfaz blanca moderna estilo SaaS corporativo
st.markdown(
    """
<style>
    /* 1. Forzar tema blanco en todo el contenedor principal y sidebar */
    html, body, [data-testid="stAppViewContainer"], .stApp {
        background-color: #FFFFFF !important;
        color: #0F172A !important;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
    }

    [data-testid="stSidebar"] {
        background-color: #F8FAFC !important;
        border-right: 1px solid #E2E8F0 !important;
    }
    [data-testid="stSidebar"] * {
        color: #1E293B !important;
    }

    /* 2. Barra de proceso / Stepper horizontal superior */
    .stepper-container {
        display: flex;
        align-items: center;
        justify-content: flex-start;
        gap: 16px;
        padding: 12px 20px;
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        margin-bottom: 18px;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
    }
    .step-item {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 0.86rem;
        font-weight: 600;
        color: #64748B;
    }
    .step-item.active {
        color: #1D4ED8;
    }
    .step-badge {
        width: 24px;
        height: 24px;
        border-radius: 50%;
        background-color: #E2E8F0;
        color: #475569;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.76rem;
        font-weight: 700;
    }
    .step-badge.active {
        background-color: #2563EB;
        color: #FFFFFF;
    }
    .step-divider {
        flex: 1;
        height: 1px;
        background-color: #E2E8F0;
        max-width: 60px;
    }

    /* 3. Píldoras de Deals / Etiquetas contextuales */
    .deal-pill {
        display: inline-block;
        background-color: #EFF6FF;
        color: #1D4ED8;
        border: 1px solid #BFDBFE;
        border-radius: 9999px;
        font-size: 0.74rem;
        font-weight: 600;
        padding: 2px 10px;
        margin-right: 6px;
        margin-bottom: 6px;
    }

    /* 4. Encabezados corporativos */
    h1, h2, h3, h4 {
        color: #0F172A !important;
        font-weight: 700 !important;
        letter-spacing: -0.015em;
    }
    .app-header-title {
        font-size: 1.45rem;
        font-weight: 700;
        color: #0F172A;
        margin-bottom: 2px;
    }
    .app-header-subtitle {
        font-size: 0.84rem;
        color: #64748B;
        margin-bottom: 12px;
    }

    /* 5. Cajas y tarjetas blancas */
    .saas-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 16px 20px;
        margin-bottom: 16px;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
    }

    /* 6. Botones de acción rápida estilo SaaS */
    .stButton > button {
        background-color: #FFFFFF !important;
        color: #1E293B !important;
        border: 1px solid #CBD5E1 !important;
        border-radius: 8px !important;
        font-weight: 500 !important;
        font-size: 0.86rem !important;
        padding: 6px 14px !important;
        transition: all 0.15s ease-in-out !important;
        box-shadow: 0 1px 2px rgba(0,0,0,0.02) !important;
    }
    .stButton > button:hover {
        background-color: #F8FAFC !important;
        border-color: #93C5FD !important;
        color: #1D4ED8 !important;
        box-shadow: 0 2px 4px rgba(37,99,235,0.08) !important;
    }

    /* Botones primarios (Guardar configuración) */
    .stButton > button[kind="primary"],
    .stButton > button[data-testid="baseButton-primary"] {
        background-color: #2563EB !important;
        color: #FFFFFF !important;
        border: 1px solid #1D4ED8 !important;
        font-weight: 600 !important;
    }
    .stButton > button[kind="primary"]:hover,
    .stButton > button[data-testid="baseButton-primary"]:hover {
        background-color: #1D4ED8 !important;
        color: #FFFFFF !important;
    }

    /* 7. Mensajes de chat estilo Gemini / ChatGPT */
    [data-testid="stChatMessage"] {
        background-color: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 14px !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.02) !important;
        padding: 16px 22px !important;
        margin-bottom: 14px !important;
        color: #0F172A !important;
    }
    /* Burbuja de usuario estilo ChatGPT / Gemini */
    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
        background-color: #F8FAFC !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 18px !important;
        font-weight: 500 !important;
    }

    /* 7.1 Caja de entrada fija al fondo estilo Gemini / ChatGPT */
    [data-testid="stChatInput"] {
        background-color: #FFFFFF !important;
        border-radius: 28px !important;
        border: 1.5px solid #CBD5E1 !important;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06) !important;
        padding: 4px 12px !important;
        transition: border-color 0.2s, box-shadow 0.2s !important;
    }
    [data-testid="stChatInput"]:focus-within {
        border-color: #2563EB !important;
        box-shadow: 0 4px 20px rgba(37, 99, 235, 0.15) !important;
    }
    [data-testid="stChatInput"] textarea {
        font-size: 0.95rem !important;
        color: #0F172A !important;
    }
    [data-testid="stBottom"] {
        background-color: #FFFFFF !important;
        border-top: 1px solid #F1F5F9 !important;
        padding-bottom: 8px !important;
    }

    /* 8. Badge de fuentes documentales */
    .badge-fuente {
        display: inline-block;
        background-color: #EFF6FF;
        color: #1D4ED8;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.86em;
        margin: 4px 0;
        border: 1px solid #BFDBFE;
    }

    /* 9. Pestañas (Tabs) */
    .stTabs [data-baseweb="tab-list"] {
        border-bottom: 1px solid #E2E8F0;
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: transparent !important;
        color: #64748B !important;
        font-weight: 600;
        padding: 8px 16px;
        border-radius: 6px 6px 0 0;
    }
    .stTabs [aria-selected="true"] {
        color: #2563EB !important;
        border-bottom: 2px solid #2563EB !important;
    }

    /* 10. Tablas Markdown y DataFrames */
    table {
        width: 100%;
        border-collapse: collapse;
        margin: 12px 0;
        font-size: 0.92em;
        background-color: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        overflow: hidden;
    }
    th {
        background-color: #F8FAFC !important;
        color: #0F172A !important;
        font-weight: 600 !important;
        padding: 9px 12px !important;
        border: 1px solid #E2E8F0 !important;
    }
    td {
        padding: 9px 12px !important;
        border: 1px solid #E2E8F0 !important;
        color: #1E293B !important;
    }
    tr:nth-child(even) {
        background-color: #F8FAFC !important;
    }
</style>
""",
    unsafe_allow_html=True,
)


def resaltar_fuentes(texto: str) -> str:
    """Resalta visualmente las citas de fuentes documentales con un badge estilizado."""
    patron = r"(\[Fuente:\s*([^\]]+)\])"
    reemplazo = r'<span class="badge-fuente">📄 \1</span>'
    return re.sub(patron, reemplazo, texto)


def tabla_markdown_a_dataframe(texto_md: str) -> Optional[pd.DataFrame]:
    """Convierte una tabla en formato Markdown en un DataFrame de Pandas limpio."""
    lineas = [
        linea.strip() for linea in texto_md.strip().split("\n") if linea.strip().startswith("|")
    ]
    if len(lineas) < 3:
        return None
    try:
        # Tomar encabezados
        encabezados = [c.strip() for c in lineas[0].strip("|").split("|")]
        filas = []
        for linea in lineas[2:]:  # Omitir separador |---|---|
            if not linea.startswith("|"):
                continue
            valores = [c.strip() for c in linea.strip("|").split("|")]
            if len(valores) == len(encabezados):
                filas.append(valores)
        if filas:
            return pd.DataFrame(filas, columns=encabezados)
    except Exception:
        pass
    return None


def renderizar_trazabilidad(trazabilidad: List[Dict[str, Any]]) -> None:
    """
    Renderiza de forma elegante, completa y sin truncamientos arbitrarios
    la trazabilidad de herramientas utilizadas por el agente.
    """
    if not trazabilidad:
        return

    with st.expander("🛠️ Ver trazabilidad y datos de herramientas utilizadas", expanded=False):
        for idx, t in enumerate(trazabilidad, start=1):
            herramienta = t.get("herramienta", "desconocida")
            argumentos = t.get("argumentos", {})
            datos_estructurados = t.get("datos", [])
            resultado_crudo = t.get("resultado", "")

            st.markdown(f"#### Invocación #{idx}: `{herramienta}`")

            if herramienta == "consultar_sql":
                query_sql = argumentos.get("query", "")
                st.caption("Sentencia SQL ejecutada contra SQLite:")
                st.code(query_sql, language="sql")

                # Visualización rica en DataFrame si hay datos
                df = None
                if datos_estructurados and isinstance(datos_estructurados, list):
                    df = pd.DataFrame(datos_estructurados)
                elif resultado_crudo:
                    df = tabla_markdown_a_dataframe(resultado_crudo)

                if df is not None and not df.empty:
                    st.caption(f"📊 **Resultados obtenidos:** {len(df)} fila(s) relacional(es)")
                    st.dataframe(df, use_container_width=True, hide_index=True)
                else:
                    st.info(resultado_crudo)

            elif herramienta == "buscar_texto":
                terminos = argumentos.get("terminos_busqueda", "")
                st.caption(f"Términos enviados al índice virtual FTS5: **`{terminos}`**")

                if datos_estructurados and isinstance(datos_estructurados, list):
                    st.caption(
                        f"🔍 **Fragmentos localizados:** {len(datos_estructurados)} coincidencia(s)"
                    )
                    for c in datos_estructurados:
                        st.markdown(
                            f"**Coincidencia #{c.get('coincidencia', '')}** · "
                            f"`{c.get('codigo_proyecto', '')}` · "
                            f"*{c.get('seccion', '')}* "
                            f"(`{c.get('archivo_origen', '')}`)"
                        )
                        st.info(c.get("extracto", ""))
                else:
                    st.markdown(resultado_crudo)

            st.divider()


def main():
    inicializar_bd()

    # Inicializar estado de sesión
    if "config_mgr" not in st.session_state:
        st.session_state.config_mgr = ConfigManager()
    if "agente" not in st.session_state:
        st.session_state.agente = AgenteProyectos(st.session_state.config_mgr)
    if "mensajes" not in st.session_state:
        st.session_state.mensajes = []

    config_mgr: ConfigManager = st.session_state.config_mgr

    # Ingesta inicial automática si la base de datos está vacía
    resumen = obtener_resumen_bd()
    if resumen["proyectos"] == 0:
        with st.spinner("Inicializando base de datos e ingesta de informes..."):
            ejecutar_ingesta_completa()
            resumen = obtener_resumen_bd()

    # ==========================================
    # BARRA LATERAL (SIDEBAR): CONFIGURACIÓN & STATUS
    # ==========================================
    with st.sidebar:
        st.title("💼 Procesa Consultores")
        st.caption("Sistema de Inteligencia de Proyectos y Optimización Operativa")

        st.markdown("---")
        st.subheader("📊 Estado del Repositorio")
        col_m1, col_m2 = st.columns(2)
        col_m1.metric("Proyectos", resumen["proyectos"])
        col_m2.metric("KPIs", resumen["kpis"])
        col_m3, col_m4 = st.columns(2)
        col_m3.metric("Lecciones", resumen["lecciones"])
        col_m4.metric("Docs FTS", resumen["fts"])

        # Píldoras de gobernanza y estado del pipeline (movidos a la izquierda para despejar el chat)
        st.markdown(
            """
        <div style="margin-top: 8px; margin-bottom: 6px;">
            <span class="deal-pill">Auditoría Operativa</span>
            <span class="deal-pill">Lean & TPM</span>
            <span class="deal-pill">Cero Alucinaciones</span>
            <span class="deal-pill">SQLite + FTS5</span>
        </div>
        <div style="font-size: 0.76rem; color: #64748B; background: #F8FAFC; padding: 6px 10px; border-radius: 6px; border: 1px solid #E2E8F0; margin-bottom: 4px;">
            <b>Pipeline:</b> Ingesta (4) ➔ SQLite & FTS5 ➔ Agente IA
        </div>
        """,
            unsafe_allow_html=True,
        )
        st.markdown("---")
        st.subheader("⚙️ Configuración Gemini")

        key_actual = config_mgr.gemini_api_key or ""
        placeholder_key = (
            "•••••••• (Guardada en sistema)" if key_actual else "Pega tu GEMINI_API_KEY..."
        )
        input_api_key = st.text_input(
            "GEMINI_API_KEY",
            value="",
            placeholder=placeholder_key,
            type="password",
            help="Clave API de Google AI Studio / Gemini. Se prioriza la almacenada en SQLite.",
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
            if input_api_key.strip():
                config_mgr.set_config(
                    "gemini_api_key", input_api_key.strip(), "Clave API de Gemini"
                )
            config_mgr.set_config("model_name", select_model, "Modelo seleccionado")
            config_mgr.set_config("temperature", str(slider_temp), "Temperatura del modelo")

            # Actualizar agente en memoria
            st.session_state.agente = AgenteProyectos(config_mgr)
            st.success("Configuración persistida en SQLite con éxito.")
            st.rerun()

        st.markdown("---")
        st.subheader("📥 Ingesta de Informes")
        forzar_gemini = st.checkbox(
            "Forzar extracción con Gemini",
            value=False,
            help="Re-extrae directamente mediante llamada a Gemini (requiere API Key).",
        )
        if st.button("🔄 Ejecutar Ingesta / Re-procesar", use_container_width=True):
            with st.spinner("Procesando informes PDF/DOCX e indexando..."):
                try:
                    fichas = ejecutar_ingesta_completa(
                        api_key=config_mgr.gemini_api_key,
                        model_name=select_model,
                        temperature=slider_temp,
                        forzar_extraccion_gemini=forzar_gemini,
                    )
                    st.success(f"Se procesaron {len(fichas)} proyectos correctamente.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error durante la ingesta: {e}")

        st.markdown("---")
        if st.button("🗑️ Limpiar Historial de Chat", use_container_width=True):
            st.session_state.mensajes = []
            st.rerun()

    # ==========================================
    # ENCABEZADO MINIMALISTA ESTILO SAAS / GEMINI
    # ==========================================
    st.markdown(
        """
    <div style="display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 8px;">
        <div class="app-header-title">💼 Consultor de Inteligencia Operativa y Proyectos</div>
        <div style="font-size: 0.82rem; color: #64748B;">Procesa Consultores &nbsp;·&nbsp; 4 Proyectos &nbsp;·&nbsp; SQLite + FTS5 + Gemini</div>
    </div>
    """,
        unsafe_allow_html=True,
    )

    # ==========================================
    # PESTAÑAS PRINCIPALES DE LA APLICACIÓN
    # ==========================================
    tab_chat, tab_explorador, tab_config, tab_mcp = st.tabs(
        [
            "💬 Chatbot Consultor",
            "📊 Explorador de Datos y Fichas",
            "⚙️ Tabla SQLite 'Configuraciones'",
            "🔌 Servidor MCP",
        ]
    )

    # ------------------------------------------
    # PESTAÑA 1: CHATBOT CONSULTOR (ESTILO GEMINI / CHATGPT)
    # ------------------------------------------
    with tab_chat:
        chat_container = st.container()

        # Si no hay mensajes, mostrar bienvenida minimalista y espaciosa tipo Gemini
        if not st.session_state.mensajes:
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
                for mensaje in st.session_state.mensajes:
                    with st.chat_message(
                        mensaje["rol"], avatar="👤" if mensaje["rol"] == "user" else "🤖"
                    ):
                        if mensaje["rol"] == "assistant":
                            st.markdown(
                                resaltar_fuentes(mensaje["contenido"]), unsafe_allow_html=True
                            )
                            trazabilidad = mensaje.get("trazabilidad", [])
                            renderizar_trazabilidad(trazabilidad)
                        else:
                            st.markdown(mensaje["contenido"])

        # Entrada del usuario: SIEMPRE ABAJO, después del contenedor de mensajes
        pregunta = st.chat_input("Escribe tu consulta sobre los proyectos...")

        if pregunta:
            # Mostrar la pregunta de inmediato en el contenedor
            st.session_state.mensajes.append({"rol": "user", "contenido": pregunta})
            with chat_container:
                with st.chat_message("user", avatar="👤"):
                    st.markdown(pregunta)

                # Generar respuesta con el agente
                with st.chat_message("assistant", avatar="🤖"):
                    with st.spinner("Analizando base de datos relacional y textos completos..."):
                        respuesta_dict = st.session_state.agente.responder(pregunta)
                        texto_resp = respuesta_dict.get("respuesta", "")
                        traza = respuesta_dict.get("trazabilidad", [])
                        st.markdown(resaltar_fuentes(texto_resp), unsafe_allow_html=True)
                        renderizar_trazabilidad(traza)

            # Persistir respuesta del asistente en el historial
            st.session_state.mensajes.append(
                {"rol": "assistant", "contenido": texto_resp, "trazabilidad": traza}
            )

            # CRÍTICO: Rerun para que toda la conversación se pinte arriba en orden cronológico
            # y la caja st.chat_input quede SIEMPRE ABAJO del último mensaje y respuesta
            st.rerun()

    # ------------------------------------------
    # PESTAÑA 2: EXPLORADOR DE BASE DE DATOS Y FICHAS
    # ------------------------------------------
    with tab_explorador:
        st.subheader("Explorador de Fichas Técnicas y Base de Datos Relacional")
        tipo_vista = st.radio(
            "Seleccionar vista:",
            ["Proyectos", "KPIs y Métricas", "Lecciones Aprendidas", "Visor de Fichas JSON"],
            horizontal=True,
        )

        if tipo_vista == "Proyectos":
            proyectos = obtener_todos_proyectos()
            if proyectos:
                df_p = pd.DataFrame(proyectos)
                columnas_ver = [
                    "codigo_proyecto",
                    "cliente",
                    "sector",
                    "duracion_semanas",
                    "gerente_proyecto",
                    "estado",
                    "fecha_aceptacion",
                    "archivo_origen",
                ]
                st.dataframe(df_p[columnas_ver], use_container_width=True, hide_index=True)
                with st.expander(
                    "🔍 Ver detalles completos de proyectos (Alcance, Diagnóstico, Metodología)"
                ):
                    st.dataframe(df_p, use_container_width=True, hide_index=True)
            else:
                st.info("No hay proyectos registrados en la base de datos.")

        elif tipo_vista == "KPIs y Métricas":
            kpis = obtener_todos_kpis()
            if kpis:
                df_k = pd.DataFrame(kpis)
                proy_filtro = st.selectbox(
                    "Filtrar por proyecto:", ["Todos"] + list(df_k["codigo_proyecto"].unique())
                )
                if proy_filtro != "Todos":
                    df_k = df_k[df_k["codigo_proyecto"] == proy_filtro]
                st.dataframe(df_k, use_container_width=True, hide_index=True)
            else:
                st.info("No hay KPIs registrados en la base de datos.")

        elif tipo_vista == "Lecciones Aprendidas":
            lecciones = obtener_todas_lecciones()
            if lecciones:
                df_l = pd.DataFrame(lecciones)
                st.dataframe(df_l, use_container_width=True, hide_index=True)
            else:
                st.info("No hay lecciones registradas en la base de datos.")

        elif tipo_vista == "Visor de Fichas JSON":
            fichas_dir = BASE_DIR / "data" / "fichas"
            archivos_json = list(fichas_dir.glob("*.json"))
            if archivos_json:
                nombres = [f.name for f in archivos_json]
                seleccionado = st.selectbox("Seleccionar Ficha JSON:", nombres)
                ruta_seleccionada = fichas_dir / seleccionado

                with open(ruta_seleccionada, "r", encoding="utf-8") as f:
                    contenido_json = json.load(f)

                col_dl, _ = st.columns([1, 4])
                col_dl.download_button(
                    label=f"⬇️ Descargar {seleccionado}",
                    data=json.dumps(contenido_json, indent=2, ensure_ascii=False),
                    file_name=seleccionado,
                    mime="application/json",
                    use_container_width=True,
                )

                st.json(contenido_json)
            else:
                st.info("No se encontraron fichas JSON en data/fichas/.")

    # ------------------------------------------
    # PESTAÑA 3: CONFIGURACIÓN SQLITE
    # ------------------------------------------
    with tab_config:
        st.subheader("Gestión de la Tabla SQLite 'configuraciones'")
        st.caption(
            "Esta tabla almacena parámetros persistentes para evitar depender de archivos de entorno locales."
        )

        configs = config_mgr.get_all_configs()
        if configs:
            df_cfg = pd.DataFrame(
                [
                    {
                        "Clave": k,
                        "Valor": "••••••••" if "key" in k.lower() else v["valor"],
                        "Descripción": v["descripcion"],
                        "Última actualización": v["fecha_actualizacion"],
                    }
                    for k, v in configs.items()
                ]
            )
            st.dataframe(df_cfg, use_container_width=True, hide_index=True)
        else:
            st.info("No hay registros en la tabla configuraciones.")

    # ------------------------------------------
    # PESTAÑA 4: SERVIDOR MCP (MODEL CONTEXT PROTOCOL)
    # ------------------------------------------
    with tab_mcp:
        st.subheader("🔌 Servidor MCP (Model Context Protocol)")
        st.markdown(
            "El servidor MCP expone las herramientas `consultar_sql` y `buscar_texto` mediante el estándar "
            "de la industria **Model Context Protocol (MCP)** para conectar bases de datos con clientes de Inteligencia Artificial: "
            "**Google Gemini**, **Claude Desktop**, **Cursor IDE** y **Windsurf**."
        )

        col_st1, col_st2 = st.columns([1, 1])
        with col_st1:
            st.markdown(
                """
            <div style="background: #F0FDF4; border: 1px solid #BBF7D0; border-radius: 10px; padding: 16px; margin-bottom: 16px;">
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">
                    <span style="font-size: 1.2rem;">🟢</span>
                    <strong style="color: #166534; font-size: 1rem;">Servidor MCP Listo y Disponible</strong>
                </div>
                <div style="font-size: 0.85rem; color: #15803D; line-height: 1.5;">
                    Módulo: <code>src/mcp_server.py</code> · Transporte: <b>stdio</b> estándar.<br>
                    <b>Auto-levantamiento:</b> Los clientes MCP (Cursor, Claude Desktop, o scripts) levantan e interactúan automáticamente con el servidor como proceso hijo sin necesidad de abrir terminales adicionales.
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
                    <li><code>consultar_sql(query: str)</code>: Consultas SELECT analíticas sobre SQLite.</li>
                    <li><code>buscar_texto(terminos_busqueda: str)</code>: Búsqueda léxica y semántica en índice virtual FTS5.</li>
                </ul>
            </div>
            """,
                unsafe_allow_html=True,
            )

        ruta_mcp_abs = str((BASE_DIR / "src" / "mcp_server.py").resolve()).replace("\\", "\\\\")
        python_exe = sys.executable.replace("\\", "\\\\")

        config_mcp_dict = {
            "mcpServers": {"procesa-consultores": {"command": python_exe, "args": [ruta_mcp_abs]}}
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
        st.caption(
            "Ejecuta una verificación de extremo a extremo a través del protocolo MCP para confirmar la comunicación:"
        )

        if st.button("🚀 Ejecutar Diagnóstico MCP en Vivo"):
            with st.spinner("Conectando con el servidor MCP y ejecutando llamadas de prueba..."):
                try:
                    import asyncio

                    from mcp.client.session import ClientSession
                    from mcp.client.stdio import StdioServerParameters, stdio_client

                    async def _diagnostico():
                        env_mcp = dict(os.environ)
                        # Pasar rutas activas de sys.path en PYTHONPATH para compatibilidad con venv y user-site
                        rutas = [str(BASE_DIR)] + [p for p in sys.path if p and Path(p).exists()]
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
                                return [t.name for t in tools_resp.tools], res_sql.content[
                                    0
                                ].text if res_sql.content else ""

                    herramientas, resultado_sql = asyncio.run(_diagnostico())
                    st.success(
                        f"✅ Protocolo MCP 100% operativo. Herramientas detectadas: `{herramientas}`"
                    )
                    st.markdown("**Resultado obtenido vía MCP:**")
                    st.markdown(resultado_sql)
                except Exception as e:
                    st.error(f"Error al verificar servidor MCP: {e}")
                    if "No module named 'mcp'" in str(e):
                        st.info(
                            "💡 **Solución rápida:** Tu entorno virtual (`venv`) no tiene instalado el paquete `mcp`. "
                            "Ejecuta en tu terminal de PowerShell:\n\n"
                            "```powershell\n"
                            ".\\venv\\Scripts\\pip install mcp\n"
                            "```\n"
                            "o con el entorno activado: `pip install mcp`"
                        )


if __name__ == "__main__":
    main()
