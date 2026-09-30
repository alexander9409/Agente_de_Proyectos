"""
Componente de Tabla Interactiva de Proyectos (interfaces/web/components/tabla_proyectos.py).
Permite filtrado facetado por sector, estado y cliente sin truncar texto.
"""

from typing import Any, Dict, List

import pandas as pd
import streamlit as st


def renderizar_tabla_proyectos(proyectos: List[Dict[str, Any]]) -> None:
    """Renderiza la tabla interactiva de proyectos con filtros dinámicos."""
    if not proyectos:
        st.info("No hay proyectos registrados en la base de datos.")
        return

    df = pd.DataFrame(proyectos)

    # Controles de filtrado en columnas
    col_f1, col_f2, col_f3 = st.columns(3)

    sectores = ["Todos"] + sorted(list(df["sector"].dropna().unique()))
    with col_f1:
        sector_sel = st.selectbox("Filtrar por Sector:", sectores)

    estados = ["Todos"] + sorted(list(df["estado"].dropna().unique()))
    with col_f2:
        estado_sel = st.selectbox("Filtrar por Estado:", estados)

    with col_f3:
        filtro_texto = st.text_input(
            "Buscar por cliente o código:", placeholder="Escribe para filtrar..."
        )

    df_filtrado = df.copy()
    if sector_sel != "Todos":
        df_filtrado = df_filtrado[df_filtrado["sector"] == sector_sel]
    if estado_sel != "Todos":
        df_filtrado = df_filtrado[df_filtrado["estado"] == estado_sel]
    if filtro_texto.strip():
        term = filtro_texto.strip().lower()
        mask = (
            df_filtrado["cliente"].str.lower().str.contains(term, na=False)
            | df_filtrado["codigo_proyecto"].str.lower().str.contains(term, na=False)
            | df_filtrado["gerente_proyecto"].str.lower().str.contains(term, na=False)
        )
        df_filtrado = df_filtrado[mask]

    columnas_resumen = [
        "codigo_proyecto",
        "cliente",
        "sector",
        "duracion_semanas",
        "gerente_proyecto",
        "estado",
        "fecha_aceptacion",
        "archivo_origen",
    ]
    cols_existentes = [c for c in columnas_resumen if c in df_filtrado.columns]

    st.caption(f"Mostrando **{len(df_filtrado)}** de **{len(df)}** proyectos registrados.")
    st.dataframe(df_filtrado[cols_existentes], use_container_width=True, hide_index=True)

    with st.expander("🔍 Ver ficha analítica detallada (Alcances, Metodologías y Resúmenes)"):
        st.dataframe(df_filtrado, use_container_width=True, hide_index=True)
