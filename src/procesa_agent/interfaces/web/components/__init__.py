"""
Componentes UI Reutilizables de Streamlit (procesa_agent.interfaces.web.components).
"""

from procesa_agent.interfaces.web.components.chat import (
    renderizar_historial_chat,
    renderizar_trazabilidad,
)
from procesa_agent.interfaces.web.components.fuentes_viewer import resaltar_fuentes
from procesa_agent.interfaces.web.components.kpi_cards import renderizar_kpis_cards
from procesa_agent.interfaces.web.components.sidebar import renderizar_sidebar
from procesa_agent.interfaces.web.components.tabla_proyectos import renderizar_tabla_proyectos

__all__ = [
    "renderizar_sidebar",
    "renderizar_historial_chat",
    "renderizar_trazabilidad",
    "resaltar_fuentes",
    "renderizar_kpis_cards",
    "renderizar_tabla_proyectos",
]
