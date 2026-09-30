"""
Componente de Visualización de KPIs y Métricas de Desempeño (interfaces/web/components/kpi_cards.py).
Presenta tarjetas con deltas de variación y badges de cumplimiento normativos.
"""

from typing import Any, Dict, List

import streamlit as st


def obtener_badge_cumplimiento(cumplimiento: str) -> str:
    """Genera la etiqueta HTML estilizada con delta de color según el estado del KPI."""
    c_lower = cumplimiento.strip().lower()
    if "cumplido" in c_lower and "no" not in c_lower and "parcial" not in c_lower:
        clase = "kpi-cumplido"
        icono = "✅"
    elif "parcial" in c_lower:
        clase = "kpi-parcial"
        icono = "⚠️"
    elif "no cumplido" in c_lower:
        clase = "kpi-nocumplido"
        icono = "❌"
    else:
        clase = "kpi-info"
        icono = "ℹ️"

    return f'<span class="kpi-badge {clase}">{icono} {cumplimiento}</span>'


def renderizar_kpis_cards(kpis: List[Dict[str, Any]]) -> None:
    """Renderiza una grilla o tarjetas ejecutivas de KPIs con soporte visual completo."""
    if not kpis:
        st.info("No hay métricas de KPIs para mostrar en este filtro.")
        return

    for kpi in kpis:
        indicador = kpi.get("indicador", "KPI")
        unidad = kpi.get("unidad", "")
        linea_base = kpi.get("linea_base", "N/A")
        meta = kpi.get("meta", "N/A")
        resultado = kpi.get("resultado", "N/A")
        variacion = kpi.get("variacion", "")
        cumplimiento = kpi.get("cumplimiento", "Informativo")
        observaciones = kpi.get("observaciones", "")
        codigo = kpi.get("codigo_proyecto", "")

        badge_html = obtener_badge_cumplimiento(cumplimiento)

        st.markdown(
            f"""
        <div class="saas-card">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
                <div>
                    <span style="font-size: 0.76rem; font-weight: 700; color: #1D4ED8; text-transform: uppercase;">
                        {codigo} · {unidad}
                    </span>
                    <h4 style="margin: 2px 0 0 0; font-size: 1.05rem; color: #0F172A;">{indicador}</h4>
                </div>
                <div>{badge_html}</div>
            </div>
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin: 10px 0; background: #F8FAFC; padding: 10px 14px; border-radius: 8px; border: 1px solid #E2E8F0;">
                <div>
                    <div style="font-size: 0.72rem; color: #64748B; font-weight: 600;">LÍNEA BASE</div>
                    <div style="font-size: 0.95rem; font-weight: 600; color: #334155;">{linea_base}</div>
                </div>
                <div>
                    <div style="font-size: 0.72rem; color: #64748B; font-weight: 600;">META</div>
                    <div style="font-size: 0.95rem; font-weight: 600; color: #334155;">{meta}</div>
                </div>
                <div>
                    <div style="font-size: 0.72rem; color: #64748B; font-weight: 600;">RESULTADO ({variacion})</div>
                    <div style="font-size: 1.0rem; font-weight: 700; color: #0F172A;">{resultado}</div>
                </div>
            </div>
            {"<div style='font-size: 0.82rem; color: #475569; margin-top: 6px;'><b>Detalle:</b> " + observaciones + "</div>" if observaciones else ""}
        </div>
        """,
            unsafe_allow_html=True,
        )
