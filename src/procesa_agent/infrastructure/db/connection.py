"""
Módulo de Base de Datos SQLite (src/db.py)
Implementa la gestión de conexiones, DDL con claves foráneas activas,
persistencia de proyectos, KPIs, lecciones aprendidas y búsqueda FTS5.
"""

import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from procesa_agent.core.paths import DEFAULT_DB_PATH
from procesa_agent.domain.models import FichaProyecto


def get_default_db_path() -> str:
    """Retorna la ruta a database.sqlite, o la definida en PROCESA_DB_PATH para tests aislados."""
    if "PROCESA_DB_PATH" in os.environ and os.environ["PROCESA_DB_PATH"]:
        return os.environ["PROCESA_DB_PATH"]
    DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return str(DEFAULT_DB_PATH)


TABLAS_PERMITIDAS = {"proyectos", "kpis", "lecciones", "informes_fts", "reglas_negocio"}
FUNCIONES_PERMITIDAS = {
    "count",
    "sum",
    "avg",
    "min",
    "max",
    "lower",
    "upper",
    "substr",
    "length",
    "coalesce",
    "round",
    "like",
    "instr",
    "replace",
    "trim",
    "cast",
    "abs",
    "snippet",
    "rank",
    "bm25",
    "highlight",
    "match",
    "date",
    "strftime",
    "group_concat",
}


def _crear_handler_timeout(timeout_s: float):
    import time

    inicio = time.time()

    def handler():
        if time.time() - inicio > timeout_s:
            return 1  # Aborta la consulta con sqlite3.OperationalError: interrupted
        return 0

    return handler


def conexion_solo_lectura(
    db_path: Optional[str] = None, timeout_s: float = 3.0
) -> sqlite3.Connection:
    """
    Crea una conexión estrictamente de solo lectura a SQLite con:
    - Modo URI '?mode=ro' (bloquea escrituras a nivel de SO / motor SQLite).
    - sqlite3 authorizer con lista blanca estricta de tablas y funciones permitidas.
    - Bloqueo total de lectura a la tabla sensible 'configuraciones'.
    - Progress handler para cortar consultas que excedan el timeout configurado.
    """
    path_str = db_path or os.getenv("SQLITE_DB_PATH") or get_default_db_path()
    resolved_path = Path(path_str).resolve().as_posix()
    conn = sqlite3.connect(f"file:{resolved_path}?mode=ro", uri=True, timeout=timeout_s)
    conn.row_factory = sqlite3.Row

    def authorizer(action, arg1, arg2, db_name, trigger):
        # Permitir sentencias SELECT y recursión CTE
        if action in (sqlite3.SQLITE_SELECT, 33):  # 33 = SQLITE_RECURSIVE
            return sqlite3.SQLITE_OK

        # Filtrar lectura de tablas
        if action == sqlite3.SQLITE_READ:
            # Permitir lectura de expresiones temporales o CTEs en memoria (db_name es None)
            if db_name is None:
                return sqlite3.SQLITE_OK
            # Para tablas en base de datos, validar estrictamente contra la lista blanca permitida
            if arg1 in TABLAS_PERMITIDAS or (arg1 and arg1.startswith("informes_fts")):
                return sqlite3.SQLITE_OK
            return sqlite3.SQLITE_DENY

        # Filtrar funciones invocadas
        if action == sqlite3.SQLITE_FUNCTION:
            if arg2 and arg2.lower() in FUNCIONES_PERMITIDAS:
                return sqlite3.SQLITE_OK
            return sqlite3.SQLITE_DENY

        # Permitir lectura de data_version que SQLite invoca internamente
        if action == sqlite3.SQLITE_PRAGMA:
            if arg1 == "data_version":
                return sqlite3.SQLITE_OK
            return sqlite3.SQLITE_DENY

        # Todo lo demás (INSERT, UPDATE, DELETE, DROP, ATTACH, etc.) se deniega
        return sqlite3.SQLITE_DENY

    conn.set_authorizer(authorizer)
    conn.set_progress_handler(_crear_handler_timeout(timeout_s), 1_000)
    return conn


def obtener_conexion(db_path: Optional[str] = None) -> sqlite3.Connection:
    """
    Crea y retorna una conexión a SQLite con PRAGMA foreign_keys = ON
    y row_factory configurado para acceso por clave.
    """
    path = db_path or os.getenv("SQLITE_DB_PATH") or get_default_db_path()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn


def inicializar_bd(db_path: Optional[str] = None) -> None:
    """Inicializa la base de datos aplicando el esquema versionado (PRAGMA user_version)."""
    from procesa_agent.infrastructure.db.schema import inicializar_bd as _init_bd

    _init_bd(db_path)


def guardar_ficha_en_bd(ficha: FichaProyecto, db_path: Optional[str] = None) -> None:
    """Inserta o actualiza una ficha mediante ProyectosRepository."""
    from procesa_agent.infrastructure.db.repositories.proyectos_repo import ProyectosRepository

    ProyectosRepository(db_path).guardar_ficha(ficha)


def indexar_informe_fts(
    codigo_proyecto: str,
    archivo_origen: str,
    secciones: List[Tuple[str, str]],
    db_path: Optional[str] = None,
) -> None:
    """Indexa las secciones de un informe en la tabla virtual FTS5."""
    conn = obtener_conexion(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM informes_fts WHERE codigo_proyecto = ?;", (codigo_proyecto,))
        for seccion_nombre, contenido in secciones:
            if contenido and contenido.strip():
                cursor.execute(
                    "INSERT INTO informes_fts (codigo_proyecto, archivo_origen, seccion, contenido) VALUES (?, ?, ?, ?);",
                    (codigo_proyecto, archivo_origen, seccion_nombre, contenido.strip()),
                )
        conn.commit()
    finally:
        conn.close()


def obtener_resumen_bd(db_path: Optional[str] = None) -> Dict[str, int]:
    """Retorna el conteo global de entidades mediante ProyectosRepository."""
    from procesa_agent.infrastructure.db.repositories.proyectos_repo import ProyectosRepository

    return ProyectosRepository(db_path).obtener_resumen()


def obtener_todos_proyectos(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retorna todos los proyectos registrados mediante ProyectosRepository."""
    from procesa_agent.infrastructure.db.repositories.proyectos_repo import ProyectosRepository

    return ProyectosRepository(db_path).obtener_todos()


def obtener_todos_kpis(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retorna todos los KPIs registrados mediante ProyectosRepository."""
    from procesa_agent.infrastructure.db.repositories.proyectos_repo import ProyectosRepository

    return ProyectosRepository(db_path).obtener_kpis()


def obtener_todas_lecciones(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retorna todas las lecciones aprendidas registradas mediante ProyectosRepository."""
    from procesa_agent.infrastructure.db.repositories.proyectos_repo import ProyectosRepository

    return ProyectosRepository(db_path).obtener_lecciones()
