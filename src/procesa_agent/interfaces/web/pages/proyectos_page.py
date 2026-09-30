"""
Página de Exploración de Proyectos y Fichas Técnicas (interfaces/web/pages/proyectos_page.py).
Permite navegar por proyectos, KPIs con deltas de color, lecciones aprendidas y fichas JSON.
"""

import json

import pandas as pd
import streamlit as st

from procesa_agent.core.paths import FICHAS_DIR
from procesa_agent.infrastructure.db.connection import (
    obtener_todas_lecciones,
    obtener_todos_kpis,
    obtener_todos_proyectos,
)
from procesa_agent.interfaces.web.components.kpi_cards import renderizar_kpis_cards
from procesa_agent.interfaces.web.components.tabla_proyectos import renderizar_tabla_proyectos


def render_proyectos_page() -> None:
    """Renderiza la vista analítica del repositorio documental y relacional."""
    st.subheader("Explorador de Fichas Técnicas y Base de Datos Relacional")

    tipo_vista = st.radio(
        "Seleccionar vista:",
        ["Proyectos", "KPIs y Métricas", "Lecciones Aprendidas", "Visor de Fichas JSON"],
        horizontal=True,
    )

    if tipo_vista == "Proyectos":
        proyectos = obtener_todos_proyectos()
        renderizar_tabla_proyectos(proyectos)

    elif tipo_vista == "KPIs y Métricas":
        kpis = obtener_todos_kpis()
        if kpis:
            proyectos_disponibles = sorted(
                list({k.get("codigo_proyecto", "") for k in kpis if k.get("codigo_proyecto")})
            )
            filtro_proy = st.selectbox("Filtrar por proyecto:", ["Todos"] + proyectos_disponibles)

            kpis_filtrados = (
                kpis
                if filtro_proy == "Todos"
                else [k for k in kpis if k.get("codigo_proyecto") == filtro_proy]
            )

            col_v1, col_v2 = st.tabs(["🗂️ Tarjetas Visuales", "📋 Vista Tabular"])
            with col_v1:
                renderizar_kpis_cards(kpis_filtrados)
            with col_v2:
                st.dataframe(
                    pd.DataFrame(kpis_filtrados), use_container_width=True, hide_index=True
                )
        else:
            st.info("No hay KPIs registrados en la base de datos.")

    elif tipo_vista == "Lecciones Aprendidas":
        lecciones = obtener_todas_lecciones()
        if lecciones:
            df_l = pd.DataFrame(lecciones)
            st.caption(f"Mostrando **{len(df_l)}** lecciones aprendidas documentadas.")
            st.dataframe(df_l, use_container_width=True, hide_index=True)
        else:
            st.info("No hay lecciones registradas en la base de datos.")

    elif tipo_vista == "Visor de Fichas JSON":
        archivos_json = sorted(list(FICHAS_DIR.glob("*.json")))
        if archivos_json:
            nombres = [f.name for f in archivos_json]
            seleccionado = st.selectbox("Seleccionar Ficha JSON:", nombres)
            ruta_seleccionada = FICHAS_DIR / seleccionado

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
