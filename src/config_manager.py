"""
Módulo de Gestión de Configuración (src/config_manager.py)
Implementa la clase ConfigManager con persistencia en SQLite (tabla 'configuraciones')
y fallback dinámico a variables de entorno (.env / os.environ).
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv

from src.db import get_default_db_path, inicializar_bd, obtener_conexion

# Cargar variables de entorno desde el archivo .env si existe
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()


class ConfigManager:
    """
    Gestor central de configuraciones con prioridad:
    1. Base de datos SQLite (tabla 'configuraciones')
    2. Variables de entorno (os.environ / .env)
    3. Valores predeterminados del sistema
    """

    DEFAULTS = {
        "gemini_api_key": None,
        "model_name": "gemini-3.8-flash",
        "temperature": "0.1",
    }

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.getenv("SQLITE_DB_PATH") or get_default_db_path()
        # Asegurar inicialización de la tabla configuraciones
        inicializar_bd(self.db_path)

    def get_config(self, clave: str, default: Optional[str] = None) -> Optional[str]:
        """
        Obtiene el valor de una clave de configuración.
        Prioriza la tabla SQLite 'configuraciones', luego variables de entorno, luego defaults.
        """
        conn = obtener_conexion(self.db_path)
        cursor = conn.cursor()
        val_db = None
        try:
            row = cursor.execute(
                "SELECT valor FROM configuraciones WHERE clave = ?;", (clave,)
            ).fetchone()
            if row and row["valor"]:
                val_db = row["valor"]
        except Exception:
            val_db = None
        finally:
            conn.close()

        if val_db is not None and str(val_db).strip() != "":
            return str(val_db).strip()

        # Fallback a variables de entorno (mayúsculas o exactas)
        val_env = os.getenv(clave.upper()) or os.getenv(clave)
        if val_env is not None and str(val_env).strip() != "":
            return str(val_env).strip()

        # Fallback a default proporcionado o predeterminado
        if default is not None:
            return default

        return self.DEFAULTS.get(clave.lower())

    def set_config(self, clave: str, valor: str, descripcion: Optional[str] = None) -> None:
        """
        Guarda o actualiza una clave en la tabla 'configuraciones'.
        """
        conn = obtener_conexion(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("""
            INSERT INTO configuraciones (clave, valor, descripcion, fecha_actualizacion)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(clave) DO UPDATE SET
                valor=excluded.valor,
                descripcion=COALESCE(excluded.descripcion, configuraciones.descripcion),
                fecha_actualizacion=CURRENT_TIMESTAMP;
            """, (clave, valor, descripcion))
            conn.commit()
        finally:
            conn.close()

    def get_all_configs(self) -> Dict[str, Dict[str, Any]]:
        """Retorna todas las configuraciones almacenadas en SQLite."""
        conn = obtener_conexion(self.db_path)
        cursor = conn.cursor()
        try:
            rows = cursor.execute(
                "SELECT clave, valor, descripcion, fecha_actualizacion FROM configuraciones ORDER BY clave;"
            ).fetchall()
            return {
                r["clave"]: {
                    "valor": r["valor"],
                    "descripcion": r["descripcion"],
                    "fecha_actualizacion": r["fecha_actualizacion"],
                }
                for r in rows
            }
        finally:
            conn.close()

    @property
    def gemini_api_key(self) -> Optional[str]:
        return self.get_config("gemini_api_key")

    @property
    def model_name(self) -> str:
        return self.get_config("model_name", default="gemini-2.5-flash") or "gemini-2.5-flash"

    @property
    def temperature(self) -> float:
        val = self.get_config("temperature", default="0.1")
        try:
            return float(val) if val else 0.1
        except ValueError:
            return 0.1
