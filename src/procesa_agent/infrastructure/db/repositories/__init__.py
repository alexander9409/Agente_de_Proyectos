"""Módulo de repositorios de acceso a datos."""

from procesa_agent.infrastructure.db.repositories.config_repo import ConfigRepository
from procesa_agent.infrastructure.db.repositories.fts_repo import FTSRepository
from procesa_agent.infrastructure.db.repositories.proyectos_repo import ProyectosRepository
from procesa_agent.infrastructure.db.repositories.reglas_repo import ReglasRepository

__all__ = [
    "ConfigRepository",
    "FTSRepository",
    "ProyectosRepository",
    "ReglasRepository",
]
