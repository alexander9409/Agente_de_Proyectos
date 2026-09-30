"""
Aplicación Web Interactiva en Streamlit (app.py)
Interfaz gráfica de alta fidelidad para el Agente de Proyectos de Procesa Consultores.
Diseñada para consultores y directores de negocio con visualización ejecutiva,
eliminación total de textos truncados y tablas interactivas en Pandas/Streamlit.
"""

import io
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import streamlit as st

# Configurar path base para importar módulos de src
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.agent import AgenteProyectos
from src.config_manager import ConfigManager
from src.db import (
    get_default_db_path,
    inicializar_bd,
    obtener_resumen_bd,
    obtener_todas_lecciones,
    obtener_todos_kpis,
    obtener_todos_proyectos,
)
from src.extractor import ejecutar_ingesta_completa

# ==========================================
# CONFIGURACIÓN GENERAL Y ESTILOS CSS
# ==========================================
st.set_page_config(
    page_title="Agente de Proyectos · Procesa Consultores",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Estilos CSS personalizados para mejorar legibilidad de tablas, fuentes y mensajes
st.markdown("""
<style>
    /* Estilo para las fuentes documentales */
    .badge-fuente {
        display: inline-block;
        background-color: #e8f0fe;
        color: #1a73e8;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.88em;
        margin: 3px 0;
        border: 1px solid #c2e7ff;
    }
    /* Estilo para títulos de secciones del bot */
    h3 {
        color: #1f2937;
        margin-top: 1.2rem !important;
        margin-bottom: 0.6rem !important;
        font-weight: 700;
    }
    /* Mejora en la visualización de tablas Markdown estándar */
    table {
        width: 100%;
        border-collapse: collapse;
        margin: 12px 0;
        font-size: 0.95em;
    }
    th {
        background-color: #f3f4f6;
        color: #111827;
        font-weight: 600;
        padding: 8px 12px;
        border: 1px solid #e5e7eb;
        text-align: left;
    }
    td {
        padding: 8px 12px;
        border: 1px solid #e5e7eb;
    }
    tr:nth-child(even) {
        background-color: #f9fafb;
    }
</style>
""", unsafe_allow_html=True)


def resaltar_fuentes(texto: str) -> str:
    """Resalta visualmente las citas de fuentes documentales con un badge estilizado."""
    patron = r'(\[Fuente:\s*([^\]]+)\])'
    reemplazo = r'<span class="badge-fuente">📄 \1</span>'
    return re.sub(patron, reemplazo, texto)


def tabla_markdown_a_dataframe(texto_md: str) -> Optional[pd.DataFrame]:
    """Convierte una tabla en formato Markdown en un DataFrame de Pandas limpio."""
    lineas = [l.strip() for l in texto_md.strip().split("\n") if l.strip().startswith("|")]
    if len(lineas) < 3:
        return None
    try:
        # Tomar encabezados
        encabezados = [c.strip() for c in lineas[0].strip("|").split("|")]
        filas = []
        for l in lineas[2:]:  # Omitir separador |---|---|
            if not l.startswith("|"):
                continue
            valores = [c.strip() for c in l.strip("|").split("|")]
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
                    st.caption(f"🔍 **Fragmentos localizados:** {len(datos_estructurados)} coincidencia(s)")
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

        st.markdown("---")
        st.subheader("⚙️ Configuración Gemini")

        key_actual = config_mgr.gemini_api_key or ""
        input_api_key = st.text_input(
            "GEMINI_API_KEY",
            value=key_actual,
            type="password",
            help="Clave API de Google AI Studio / Gemini. Se prioriza la almacenada en SQLite.",
        )

        modelos_disponibles = ["gemini-3.8-flash", "gemini-3.5-flash", "gemini-2.5-flash", "gemini-1.5-pro"]
        modelo_actual = config_mgr.model_name
        idx_modelo = modelos_disponibles.index(modelo_actual) if modelo_actual in modelos_disponibles else 0
        select_model = st.selectbox("Modelo", modelos_disponibles, index=idx_modelo)

        temp_actual = config_mgr.temperature
        slider_temp = st.slider("Temperatura", min_value=0.0, max_value=1.0, value=float(temp_actual), step=0.05)

        if st.button("💾 Guardar Configuración", use_container_width=True):
            if input_api_key.strip():
                config_mgr.set_config("gemini_api_key", input_api_key.strip(), "Clave API de Gemini")
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
            help="Re-extrae directamente mediante llamada a Gemini (requiere API Key)."
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
    # PESTAÑAS PRINCIPALES DE LA APLICACIÓN
    # ==========================================
    tab_chat, tab_explorador, tab_config = st.tabs([
        "💬 Chatbot Consultor",
        "📊 Explorador de Datos y Fichas",
        "⚙️ Tabla SQLite 'Configuraciones'"
    ])

    # ------------------------------------------
    # PESTAÑA 1: CHATBOT CONSULTOR
    # ------------------------------------------
    with tab_chat:
        st.subheader("Asistente Virtual de Inteligencia de Proyectos")
        st.markdown(
            "Bienvenido al consultor inteligente de **Procesa Consultores**. "
            "Realice preguntas sobre métricas, duraciones, causas de desvío, lecciones aprendidas o metodologías. "
            "Todas las respuestas combinan un **resumen ejecutivo de negocio**, **matrices comparativas**, **insights operativos** y **citación formal**."
        )

        # Atajos rápidos de preguntas
        st.markdown("**Consultas sugeridas para el caso de negocio:**")
        cols_btn = st.columns(3)
        if cols_btn[0].button("⏱️ Proyectos ≥ 20 semanas", use_container_width=True):
            st.session_state.prompt_prellenado = "¿Qué proyectos tuvieron una duración igual o superior a 20 semanas?"
        if cols_btn[1].button("📈 OEE Plásticos del Pacífico", use_container_width=True):
            st.session_state.prompt_prellenado = "¿Cuál fue el OEE de Plásticos del Pacífico, su línea base y resultado final?"
        if cols_btn[2].button("❌ Proveedores La Canasta", use_container_width=True):
            st.session_state.prompt_prellenado = "¿Se cumplió la integración con proveedores en Supermercados La Canasta y cuál fue la causa?"

        cols_btn2 = st.columns(3)
        if cols_btn2[0].button("🏥 Espera Clínica Santa Lucía", use_container_width=True):
            st.session_state.prompt_prellenado = "¿Cuánto se redujo el tiempo total de espera del paciente en Clínica Santa Lucía?"
        if cols_btn2[1].button("👥 Gerentes de Proyecto", use_container_width=True):
            st.session_state.prompt_prellenado = "¿Quiénes fueron los gerentes de proyecto y qué proyectos lideraron?"
        if cols_btn2[2].button("🛡️ Prueba Anti-Alucinación", use_container_width=True):
            st.session_state.prompt_prellenado = "¿Qué proyectos se realizaron para Banco Pichincha?"

        cols_btn3 = st.columns(3)
        if cols_btn3[0].button("🏭 Paradas 64 h/mes (Línea Base)", use_container_width=True):
            st.session_state.prompt_prellenado = "¿Qué línea base se tomó para las paradas no programadas en Plásticos del Pacífico y por qué prevalece sobre el anexo?"
        if cols_btn3[1].button("🏦 +9% Colocación (No Atribuible)", use_container_width=True):
            st.session_state.prompt_prellenado = "¿Se debe registrar el +9% de colocación de Cooperativa Horizonte Andino como resultado del proyecto?"
        if cols_btn3[2].button("📋 Proyectos Cerrados vs Pendientes", use_container_width=True):
            st.session_state.prompt_prellenado = "¿Cuáles de los proyectos se consideran cerrados y cuál cerró con pendientes?"

        st.markdown("---")

        # Mostrar historial de conversación
        for mensaje in st.session_state.mensajes:
            with st.chat_message(mensaje["rol"], avatar="👤" if mensaje["rol"] == "user" else "🤖"):
                if mensaje["rol"] == "assistant":
                    st.markdown(resaltar_fuentes(mensaje["contenido"]), unsafe_allow_html=True)
                    # Mostrar trazabilidad limpia y sin truncamientos
                    trazabilidad = mensaje.get("trazabilidad", [])
                    renderizar_trazabilidad(trazabilidad)
                else:
                    st.markdown(mensaje["contenido"])

        # Entrada del usuario (o atajo sugerido)
        prompt_inicial = st.session_state.pop("prompt_prellenado", None)
        prompt_chat = st.chat_input("Escribe tu consulta sobre los proyectos...")

        pregunta = prompt_inicial or prompt_chat

        if pregunta:
            # Mostrar pregunta del usuario
            st.session_state.mensajes.append({"rol": "user", "contenido": pregunta})
            with st.chat_message("user", avatar="👤"):
                st.markdown(pregunta)

            # Generar respuesta con el agente
            with st.chat_message("assistant", avatar="🤖"):
                with st.spinner("Analizando base de datos relacional y textos completos..."):
                    respuesta_dict = st.session_state.agente.responder(pregunta)
                    texto_resp = respuesta_dict.get("respuesta", "")
                    traza = respuesta_dict.get("trazabilidad", [])

                    # Renderizar respuesta formateada
                    st.markdown(resaltar_fuentes(texto_resp), unsafe_allow_html=True)

                    # Renderizar trazabilidad interactiva completa
                    renderizar_trazabilidad(traza)

            # Persistir respuesta del asistente
            st.session_state.mensajes.append({
                "rol": "assistant",
                "contenido": texto_resp,
                "trazabilidad": traza
            })

    # ------------------------------------------
    # PESTAÑA 2: EXPLORADOR DE BASE DE DATOS Y FICHAS
    # ------------------------------------------
    with tab_explorador:
        st.subheader("Explorador de Fichas Técnicas y Base de Datos Relacional")
        tipo_vista = st.radio(
            "Seleccionar vista:",
            ["Proyectos", "KPIs y Métricas", "Lecciones Aprendidas", "Visor de Fichas JSON"],
            horizontal=True
        )

        if tipo_vista == "Proyectos":
            proyectos = obtener_todos_proyectos()
            if proyectos:
                df_p = pd.DataFrame(proyectos)
                columnas_ver = [
                    "codigo_proyecto", "cliente", "sector", "duracion_semanas",
                    "gerente_proyecto", "estado", "fecha_aceptacion", "archivo_origen"
                ]
                st.dataframe(df_p[columnas_ver], use_container_width=True, hide_index=True)
                with st.expander("🔍 Ver detalles completos de proyectos (Alcance, Diagnóstico, Metodología)"):
                    st.dataframe(df_p, use_container_width=True, hide_index=True)
            else:
                st.info("No hay proyectos registrados en la base de datos.")

        elif tipo_vista == "KPIs y Métricas":
            kpis = obtener_todos_kpis()
            if kpis:
                df_k = pd.DataFrame(kpis)
                proy_filtro = st.selectbox(
                    "Filtrar por proyecto:",
                    ["Todos"] + list(df_k["codigo_proyecto"].unique())
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
        st.caption("Esta tabla almacena parámetros persistentes para evitar depender de archivos de entorno locales.")

        configs = config_mgr.get_all_configs()
        if configs:
            df_cfg = pd.DataFrame([
                {
                    "Clave": k,
                    "Valor": "***" if "key" in k.lower() else v["valor"],
                    "Descripción": v["descripcion"],
                    "Última actualización": v["fecha_actualizacion"]
                }
                for k, v in configs.items()
            ])
            st.dataframe(df_cfg, use_container_width=True, hide_index=True)
        else:
            st.info("No hay registros en la tabla configuraciones.")


if __name__ == "__main__":
    main()
