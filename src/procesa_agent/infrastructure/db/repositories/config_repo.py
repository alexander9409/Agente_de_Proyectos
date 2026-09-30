"""
Repositorio de Configuraciones (config_repo.py).
Acceso tipado y seguro a la tabla 'configuraciones' sin exposición de secrets.
"""

from typing import Any, Dict, Optional

from procesa_agent.infrastructure.db.connection import obtener_conexion


class ConfigRepository:
    """Gestiona la persistencia y lectura de configuraciones en la tabla 'configuraciones'."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def get(self, clave: str, default: Optional[str] = None) -> Optional[str]:
        """Obtiene el valor de una clave de configuración."""
        conn = obtener_conexion(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT valor FROM configuraciones WHERE clave = ?;", (clave,))
            row = cursor.fetchone()
            return row["valor"] if row else default
        finally:
            conn.close()

    def set(self, clave: str, valor: str, descripcion: Optional[str] = None) -> None:
        """Inserta o actualiza una clave de configuración en SQLite de forma atómica."""
        conn = obtener_conexion(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
            INSERT INTO configuraciones (clave, valor, descripcion, fecha_actualizacion)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(clave) DO UPDATE SET
                valor = excluded.valor,
                descripcion = COALESCE(excluded.descripcion, configuraciones.descripcion),
                fecha_actualizacion = CURRENT_TIMESTAMP;
            """,
                (clave, valor, descripcion),
            )
            conn.commit()
        finally:
            conn.close()

    def get_all(self) -> Dict[str, Dict[str, Any]]:
        """Recupera todas las configuraciones almacenadas."""
        conn = obtener_conexion(self.db_path)
        try:
            cursor = conn.cursor()
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
