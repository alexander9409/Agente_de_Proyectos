"""
Configuración centralizada del sistema utilizando pydantic-settings.
Única fuente de verdad para parámetros, modelos predeterminados y seguridad.
"""

from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

from procesa_agent.core.paths import DEFAULT_DB_PATH, PROJECT_ROOT


class Settings(BaseSettings):
    """
    Configuración global con prioridad jerárquica:
    1. Base de datos SQLite (si está disponible vía repositorio)
    2. Variables de entorno / archivo .env
    3. Valores predeterminados del sistema
    """

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    gemini_api_key: Optional[str] = None
    model_name: str = "gemini-2.5-flash"
    temperature: float = 0.1
    sqlite_db_path: str = str(DEFAULT_DB_PATH)
    max_filas_sql: int = 200
    timeout_sql_s: float = 3.0
    log_level: str = "INFO"


# Instancia singleton predeterminada
settings = Settings()
