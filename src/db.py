"""
Módulo de Base de Datos SQLite (src/db.py)
Implementa la gestión de conexiones, DDL con claves foráneas activas,
persistencia de proyectos, KPIs, lecciones aprendidas y búsqueda FTS5.
"""

import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.models import FichaProyecto


def get_default_db_path() -> str:
    """Retorna la ruta absoluta por defecto a database.sqlite dentro de data/."""
    base_dir = Path(__file__).resolve().parent.parent
    data_dir = base_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return str(data_dir / "database.sqlite")


def obtener_conexion(db_path: Optional[str] = None) -> sqlite3.Connection:
    """
    Crea y retorna una conexión a SQLite con PRAGMA foreign_keys = ON
    y row_factory configurado para acceso por clave.
    """
    path = db_path or os.getenv("SQLITE_DB_PATH") or get_default_db_path()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn


def inicializar_bd(db_path: Optional[str] = None) -> None:
    """
    Ejecuta el esquema DDL oficial en la base de datos SQLite.
    Crea las tablas maestras, relacionales y la tabla virtual FTS5.
    """
    conn = obtener_conexion(db_path)
    cursor = conn.cursor()

    # 1. Tabla de Configuraciones del Sistema (Para gestionar API Key y Modelos desde la UI)
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
        alcance_excluido TEXT,     -- Campo crítico anti-alucinación
        metodologia TEXT,
        iniciativas_clave TEXT,    -- JSON Array serializado
        proximos_pasos TEXT        -- JSON Array serializado
    );
    """)

    # 3. Tabla de KPIs (1:N) para consultas numéricas y agregaciones
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS kpis (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        codigo_proyecto TEXT NOT NULL,
        indicador TEXT NOT NULL,
        unidad TEXT,
        linea_base TEXT,
        meta TEXT,
        resultado TEXT NOT NULL,
        variacion TEXT,
        cumplimiento TEXT NOT NULL, -- 'Cumplido', 'Parcialmente cumplido', 'No cumplido', 'Informativo'
        observaciones TEXT,
        FOREIGN KEY (codigo_proyecto) REFERENCES proyectos(codigo_proyecto) ON DELETE CASCADE
    );
    """)

    # 4. Tabla de Lecciones Aprendidas (1:N) para retrospectivas
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS lecciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        codigo_proyecto TEXT NOT NULL,
        tema TEXT NOT NULL,         -- 'Gestión del cambio', 'Calidad de datos', 'Terceros', 'Metodología'
        titulo TEXT NOT NULL,
        descripcion TEXT NOT NULL,
        FOREIGN KEY (codigo_proyecto) REFERENCES proyectos(codigo_proyecto) ON DELETE CASCADE
    );
    """)

    # 5. Tabla Virtual FTS5 para Búsqueda en Texto Completo de los Informes
    cursor.execute("""
    CREATE VIRTUAL TABLE IF NOT EXISTS informes_fts USING fts5(
        codigo_proyecto,
        archivo_origen,
        seccion,
        contenido
    );
    """)

    conn.commit()
    conn.close()


def guardar_ficha_en_bd(ficha: FichaProyecto, db_path: Optional[str] = None) -> None:
    """
    Inserta o reemplaza una FichaProyecto en las tablas proyectos, kpis y lecciones.
    """
    conn = obtener_conexion(db_path)
    cursor = conn.cursor()

    try:
        # Serialización de listas complejas
        iniciativas_json = json.dumps([i.model_dump() for i in ficha.iniciativas_clave], ensure_ascii=False)
        proximos_pasos_json = json.dumps(ficha.proximos_pasos, ensure_ascii=False)

        cursor.execute("""
        INSERT INTO proyectos (
            codigo_proyecto, archivo_origen, cliente, cliente_descripcion, sector,
            ubicacion, periodo, duracion_semanas, gerente_proyecto, contraparte_cliente,
            estado, fecha_aceptacion, resumen_ejecutivo, diagnostico_problema,
            alcance_incluido, alcance_excluido, metodologia, iniciativas_clave, proximos_pasos
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(codigo_proyecto) DO UPDATE SET
            archivo_origen=excluded.archivo_origen,
            cliente=excluded.cliente,
            cliente_descripcion=excluded.cliente_descripcion,
            sector=excluded.sector,
            ubicacion=excluded.ubicacion,
            periodo=excluded.periodo,
            duracion_semanas=excluded.duracion_semanas,
            gerente_proyecto=excluded.gerente_proyecto,
            contraparte_cliente=excluded.contraparte_cliente,
            estado=excluded.estado,
            fecha_aceptacion=excluded.fecha_aceptacion,
            resumen_ejecutivo=excluded.resumen_ejecutivo,
            diagnostico_problema=excluded.diagnostico_problema,
            alcance_incluido=excluded.alcance_incluido,
            alcance_excluido=excluded.alcance_excluido,
            metodologia=excluded.metodologia,
            iniciativas_clave=excluded.iniciativas_clave,
            proximos_pasos=excluded.proximos_pasos;
        """, (
            ficha.codigo_proyecto,
            ficha.archivo_origen,
            ficha.cliente,
            ficha.cliente_descripcion,
            ficha.sector,
            ficha.ubicacion,
            ficha.periodo,
            ficha.duracion_semanas,
            ficha.gerente_proyecto,
            ficha.contraparte_cliente,
            ficha.estado,
            ficha.fecha_aceptacion,
            ficha.resumen_ejecutivo,
            ficha.diagnostico_problema,
            ficha.alcance_incluido,
            ficha.alcance_excluido,
            ficha.metodologia,
            iniciativas_json,
            proximos_pasos_json,
        ))

        # Reemplazar KPIs
        cursor.execute("DELETE FROM kpis WHERE codigo_proyecto = ?;", (ficha.codigo_proyecto,))
        for k in ficha.kpis:
            cursor.execute("""
            INSERT INTO kpis (
                codigo_proyecto, indicador, unidad, linea_base, meta,
                resultado, variacion, cumplimiento, observaciones
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                ficha.codigo_proyecto,
                k.indicador,
                k.unidad,
                k.linea_base,
                k.meta,
                k.resultado,
                k.variacion,
                k.cumplimiento,
                k.observaciones,
            ))

        # Reemplazar Lecciones
        cursor.execute("DELETE FROM lecciones WHERE codigo_proyecto = ?;", (ficha.codigo_proyecto,))
        for lec in ficha.lecciones:
            cursor.execute("""
            INSERT INTO lecciones (
                codigo_proyecto, tema, titulo, descripcion
            ) VALUES (?, ?, ?, ?);
            """, (
                ficha.codigo_proyecto,
                lec.tema,
                lec.titulo,
                lec.descripcion,
            ))

        conn.commit()
    finally:
        conn.close()


def indexar_informe_fts(
    codigo_proyecto: str,
    archivo_origen: str,
    secciones: List[Tuple[str, str]],
    db_path: Optional[str] = None
) -> None:
    """
    Inserta las secciones de un informe en la tabla virtual informes_fts.
    Limpia los fragmentos previos de ese proyecto para evitar duplicación.
    """
    conn = obtener_conexion(db_path)
    cursor = conn.cursor()

    try:
        # Limpiar registros previos del proyecto en FTS5
        cursor.execute("DELETE FROM informes_fts WHERE codigo_proyecto = ?;", (codigo_proyecto,))

        for seccion_nombre, contenido in secciones:
            if contenido and contenido.strip():
                cursor.execute("""
                INSERT INTO informes_fts (codigo_proyecto, archivo_origen, seccion, contenido)
                VALUES (?, ?, ?, ?);
                """, (codigo_proyecto, archivo_origen, seccion_nombre, contenido.strip()))

        conn.commit()
    finally:
        conn.close()


def obtener_resumen_bd(db_path: Optional[str] = None) -> Dict[str, int]:
    """Retorna un diccionario con el conteo de proyectos, kpis, lecciones y fragmentos FTS."""
    conn = obtener_conexion(db_path)
    cursor = conn.cursor()
    try:
        num_proyectos = cursor.execute("SELECT COUNT(*) FROM proyectos;").fetchone()[0]
        num_kpis = cursor.execute("SELECT COUNT(*) FROM kpis;").fetchone()[0]
        num_lecciones = cursor.execute("SELECT COUNT(*) FROM lecciones;").fetchone()[0]
        num_fts = cursor.execute("SELECT COUNT(*) FROM informes_fts;").fetchone()[0]
        return {
            "proyectos": num_proyectos,
            "kpis": num_kpis,
            "lecciones": num_lecciones,
            "fts": num_fts,
        }
    finally:
        conn.close()


def obtener_todos_proyectos(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retorna todos los registros de proyectos como lista de diccionarios."""
    conn = obtener_conexion(db_path)
    cursor = conn.cursor()
    try:
        rows = cursor.execute("SELECT * FROM proyectos ORDER BY codigo_proyecto;").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def obtener_todos_kpis(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retorna todos los registros de KPIs como lista de diccionarios."""
    conn = obtener_conexion(db_path)
    cursor = conn.cursor()
    try:
        rows = cursor.execute("SELECT * FROM kpis ORDER BY codigo_proyecto, id;").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def obtener_todas_lecciones(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retorna todas las lecciones aprendidas como lista de diccionarios."""
    conn = obtener_conexion(db_path)
    cursor = conn.cursor()
    try:
        rows = cursor.execute("SELECT * FROM lecciones ORDER BY codigo_proyecto, id;").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
