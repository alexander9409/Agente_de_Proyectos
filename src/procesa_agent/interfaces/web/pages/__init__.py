"""
Páginas y Vistas Principales de Streamlit (procesa_agent.interfaces.web.pages).
"""

from procesa_agent.interfaces.web.pages.auditoria_page import render_auditoria_page
from procesa_agent.interfaces.web.pages.chat_page import render_chat_page
from procesa_agent.interfaces.web.pages.proyectos_page import render_proyectos_page

__all__ = [
    "render_chat_page",
    "render_proyectos_page",
    "render_auditoria_page",
]
