"""
Módulo de Definición y Migración de Esquema SQLite (schema.py).
Gestiona el DDL oficial y el versionado del esquema mediante PRAGMA user_version.
Garantiza migraciones idempotentes sin pérdida de datos.
"""

import sqlite3
from typing import Optional

from procesa_agent.core.logging import logger
from procesa_agent.infrastructure.db.connection import obtener_conexion

VERSION_OBJETIVO = 2


def _migrar_v1(conn: sqlite3.Connection) -> None:
    """Migración V1: Esquema base de proyectos, KPIs, lecciones, configuraciones y FTS5."""
    cursor = conn.cursor()

    # 1. Tabla de Configuraciones del Sistema
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS configuraciones (
        clave TEXT PRIMARY KEY,
        valor TEXT NOT NULL,
        descripcion TEXT,
        fecha_actualizacion DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 2. Tabla Maestra de Proyectos
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS proyectos (
        codigo_proyecto TEXT PRIMARY KEY,
        archivo_origen TEXT NOT NULL,
        cliente TEXT NOT NULL,
        cliente_descripcion TEXT,
        sector TEXT NOT NULL,
        ubicacion TEXT,
        periodo TEXT,
        duracion_semanas INTEGER,
        gerente_proyecto TEXT NOT NULL,
        contraparte_cliente TEXT,
        estado TEXT NOT NULL,
        fecha_aceptacion TEXT,
        resumen_ejecutivo TEXT NOT NULL,
        diagnostico_problema TEXT,
        alcance_incluido TEXT,
        alcance_excluido TEXT,
        metodologia TEXT,
        iniciativas_clave TEXT,
        proximos_pasos TEXT,
        fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 3. Tabla Relacional de Métricas y KPIs
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS kpis (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        codigo_proyecto TEXT NOT NULL,
        indicador TEXT NOT NULL,
        unidad TEXT,
        linea_base TEXT NOT NULL,
        meta TEXT,
        resultado TEXT NOT NULL,
        variacion TEXT,
        cumplimiento TEXT NOT NULL,
        observaciones TEXT,
        FOREIGN KEY (codigo_proyecto) REFERENCES proyectos(codigo_proyecto) ON DELETE CASCADE
    );
    """)

    # 4. Tabla Relacional de Lecciones Aprendidas
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS lecciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        codigo_proyecto TEXT NOT NULL,
        tema TEXT NOT NULL,
        titulo TEXT NOT NULL,
        descripcion TEXT NOT NULL,
        FOREIGN KEY (codigo_proyecto) REFERENCES proyectos(codigo_proyecto) ON DELETE CASCADE
    );
    """)

    # 5. Tabla Virtual FTS5 para Búsqueda Full-Text
    cursor.execute("""
    CREATE VIRTUAL TABLE IF NOT EXISTS informes_fts USING fts5(
        codigo_proyecto UNINDEXED,
        archivo_origen UNINDEXED,
        seccion,
        contenido,
        tokenize = 'unicode61 remove_diacritics 2'
    );
    """)
    conn.commit()


def _migrar_v2(conn: sqlite3.Connection) -> None:
    """Migración V2: Incorporación de la tabla reglas_negocio para fiabilidad documental."""
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reglas_negocio (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        codigo_proyecto TEXT,
        tipo TEXT NOT NULL,
        titulo TEXT NOT NULL,
        descripcion TEXT NOT NULL,
        fuente TEXT,
        FOREIGN KEY (codigo_proyecto) REFERENCES proyectos(codigo_proyecto) ON DELETE CASCADE
    );
    """)
    conn.commit()


def inicializar_o_migrar_bd(conn: sqlite3.Connection) -> int:
    """
    Aplica las migraciones pendientes según el PRAGMA user_version actual.
    Retorna la versión final alcanzada.
    """
    cursor = conn.cursor()
    version_actual = cursor.execute("PRAGMA user_version;").fetchone()[0]

    if version_actual < 1:
        logger.info("Aplicando migración V1 (esquema base)...")
        _migrar_v1(conn)
        cursor.execute("PRAGMA user_version = 1;")
        conn.commit()
        version_actual = 1

    if version_actual < 2:
        logger.info("Aplicando migración V2 (reglas de negocio)...")
        _migrar_v2(conn)
        cursor.execute("PRAGMA user_version = 2;")
        conn.commit()
        version_actual = 2

    return version_actual


def inicializar_bd(db_path: Optional[str] = None) -> None:
    """
    Inicializa o migra la base de datos SQLite a la versión de esquema más reciente.
    Habilita claves foráneas y modo WAL.
    """
    conn = obtener_conexion(db_path)
    try:
        inicializar_o_migrar_bd(conn)
    finally:
        conn.close()
