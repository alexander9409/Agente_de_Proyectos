"""
Repositorio de Reglas de Negocio (reglas_repo.py).
Gestiona la persistencia, carga inicial idempotente y consulta de reglas de fiabilidad documental.
"""

import json
from pathlib import Path
from typing import List, Optional

from procesa_agent.core.logging import logger
from procesa_agent.core.paths import REGLAS_NEGOCIO_PATH
from procesa_agent.domain.models import ReglaNegocio
from procesa_agent.infrastructure.db.connection import obtener_conexion


class ReglasRepository:
    """Gestiona el acceso a la tabla 'reglas_negocio'."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def cargar_desde_json(self, json_path: Optional[Path] = None) -> int:
        """
        Carga las reglas de fiabilidad desde el archivo JSON oficial en la tabla reglas_negocio.
        Operación estrictamente idempotente.
        """
        path = json_path or REGLAS_NEGOCIO_PATH
        if not path.exists():
            logger.warning(f"No se encontró el archivo de reglas de negocio en: {path}")
            return 0

        with open(path, "r", encoding="utf-8") as f:
            datos = json.load(f)

        conn = obtener_conexion(self.db_path)
        insertados = 0
        try:
            cursor = conn.cursor()
            for r in datos:
                cod = r.get("codigo_proyecto")
                cursor.execute(
                    """
                    INSERT INTO reglas_negocio (codigo_proyecto, tipo, titulo, descripcion, fuente)
                    SELECT ?, ?, ?, ?, ?
                    WHERE NOT EXISTS (
                        SELECT 1 FROM reglas_negocio
                        WHERE titulo = ? AND (codigo_proyecto = ? OR (codigo_proyecto IS NULL AND ? IS NULL))
                    )
                    AND (
                        ? IS NULL OR EXISTS (SELECT 1 FROM proyectos WHERE codigo_proyecto = ?)
                    );
                    """,
                    (
                        cod,
                        r["tipo"],
                        r["titulo"],
                        r["descripcion"],
                        r.get("fuente"),
                        r["titulo"],
                        cod,
                        cod,
                        cod,
                        cod,
                    ),
                )
                if cursor.rowcount > 0:
                    insertados += 1
            conn.commit()
            logger.info(f"Reglas de negocio sincronizadas: {insertados} nuevas cargadas.")
            return insertados
        finally:
            conn.close()

    def obtener_todas(self) -> List[ReglaNegocio]:
        """Obtiene todas las reglas de negocio registradas."""
        conn = obtener_conexion(self.db_path)
        try:
            cursor = conn.cursor()
            rows = cursor.execute(
                "SELECT id, codigo_proyecto, tipo, titulo, descripcion, fuente FROM reglas_negocio ORDER BY id;"
            ).fetchall()
            return [
                ReglaNegocio(
                    id=r["id"],
                    codigo_proyecto=r["codigo_proyecto"],
                    tipo=r["tipo"],
                    titulo=r["titulo"],
                    descripcion=r["descripcion"],
                    fuente=r["fuente"],
                )
                for r in rows
            ]
        finally:
            conn.close()

    def obtener_por_proyecto(self, codigo_proyecto: Optional[str]) -> List[ReglaNegocio]:
        """Obtiene las reglas específicas de un proyecto o globales."""
        conn = obtener_conexion(self.db_path)
        try:
            cursor = conn.cursor()
            if codigo_proyecto:
                rows = cursor.execute(
                    """
                    SELECT id, codigo_proyecto, tipo, titulo, descripcion, fuente
                    FROM reglas_negocio
                    WHERE codigo_proyecto = ? OR codigo_proyecto IS NULL
                    ORDER BY id;
                    """,
                    (codigo_proyecto,),
                ).fetchall()
            else:
                rows = cursor.execute(
                    """
                    SELECT id, codigo_proyecto, tipo, titulo, descripcion, fuente
                    FROM reglas_negocio
                    WHERE codigo_proyecto IS NULL
                    ORDER BY id;
                    """
                ).fetchall()
            return [
                ReglaNegocio(
                    id=r["id"],
                    codigo_proyecto=r["codigo_proyecto"],
                    tipo=r["tipo"],
                    titulo=r["titulo"],
                    descripcion=r["descripcion"],
                    fuente=r["fuente"],
                )
                for r in rows
            ]
        finally:
            conn.close()
