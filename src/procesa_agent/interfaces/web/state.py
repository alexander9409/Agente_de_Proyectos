"""
Manejo Centralizado del Estado de Sesión en Streamlit (interfaces/web/state.py).
Gestiona el ciclo de vida del ConfigManager, AgenteProyectos y el historial conversacional.
"""

from pathlib import Path
from typing import Any, Dict, Optional

import streamlit as st

from procesa_agent.agent.orchestrator import AgenteProyectos
from procesa_agent.core.config_manager import ConfigManager
from procesa_agent.infrastructure.db.connection import (
    get_default_db_path,
    inicializar_bd,
    obtener_resumen_bd,
)
from procesa_agent.ingestion.pipeline import ejecutar_ingesta_completa

CSS_PATH = Path(__file__).resolve().parent / "styles.css"


def cargar_estilos_css() -> None:
    """Carga y aplica la hoja de estilos desacoplada styles.css en Streamlit."""
    if CSS_PATH.exists():
        with open(CSS_PATH, "r", encoding="utf-8") as f:
            css = f.read()
        st.markdown(f"<style>\n{css}\n</style>", unsafe_allow_html=True)


def inicializar_estado(db_path: Optional[str] = None) -> None:
    """Inicializa la base de datos, repositorios, agente y memoria de sesión en Streamlit."""
    ruta_bd = db_path or get_default_db_path()
    inicializar_bd(ruta_bd)

    if "config_mgr" not in st.session_state:
        st.session_state.config_mgr = ConfigManager(db_path=ruta_bd)

    if "agente" not in st.session_state:
        st.session_state.agente = AgenteProyectos(config_mgr=st.session_state.config_mgr)

    if "mensajes" not in st.session_state:
        st.session_state.mensajes = []

    # Ingesta inicial automática si el repositorio está vacío
    resumen = obtener_resumen_bd(ruta_bd)
    if resumen.get("proyectos", 0) == 0:
        with st.spinner("Inicializando base de datos e ingesta de informes..."):
            ejecutar_ingesta_completa(db_path=ruta_bd)


def limpiar_chat() -> None:
    """Restablece el historial de mensajes de la interfaz y la memoria conversacional del agente."""
    st.session_state.mensajes = []
    if "agente" in st.session_state and hasattr(st.session_state.agente, "reiniciar_conversacion"):
        st.session_state.agente.reiniciar_conversacion()


def actualizar_configuracion(
    api_key: Optional[str] = None,
    model_name: Optional[str] = None,
    temperature: Optional[float] = None,
) -> None:
    """Persiste los cambios en la configuración y recarga la instancia del agente."""
    config_mgr: ConfigManager = st.session_state.config_mgr
    if api_key and api_key.strip():
        config_mgr.set_config("gemini_api_key", api_key.strip(), "Clave API de Gemini")
    if model_name:
        config_mgr.set_config("model_name", model_name, "Modelo LLM seleccionado")
    if temperature is not None:
        config_mgr.set_config("temperature", str(temperature), "Temperatura del modelo")

    # Reinstanciar el agente con los nuevos parámetros
    st.session_state.agente = AgenteProyectos(config_mgr=config_mgr)


def obtener_estado() -> Dict[str, Any]:
    """Retorna un diccionario seguro con los objetos de estado actuales."""
    return {
        "config_mgr": st.session_state.get("config_mgr"),
        "agente": st.session_state.get("agente"),
        "mensajes": st.session_state.get("mensajes", []),
    }
