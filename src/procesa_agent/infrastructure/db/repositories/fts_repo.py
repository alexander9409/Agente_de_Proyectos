"""
Repositorio de Búsqueda Full-Text FTS5 (fts_repo.py).
Gestiona la indexación y recuperación léxica en la tabla virtual SQLite 'informes_fts'.
"""

from typing import Any, Dict, List, Optional

from procesa_agent.infrastructure.db.connection import conexion_solo_lectura, obtener_conexion


class FTSRepository:
    """Gestiona las operaciones sobre la tabla virtual SQLite FTS5 'informes_fts'."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def indexar_seccion(
        self,
        codigo_proyecto: str,
        archivo_origen: str,
        seccion: str,
        contenido: str,
    ) -> None:
        """Inserta un fragmento documental en la tabla virtual FTS5."""
        conn = obtener_conexion(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO informes_fts (codigo_proyecto, archivo_origen, seccion, contenido)
                VALUES (?, ?, ?, ?);
                """,
                (codigo_proyecto, archivo_origen, seccion, contenido),
            )
            conn.commit()
        finally:
            conn.close()

    def buscar(self, consulta_fts: str, limite: int = 5) -> List[Dict[str, Any]]:
        """
        Ejecuta una búsqueda de texto completo con ranking BM25 y snippets contextuales.
        Utiliza una conexión de solo lectura segura.
        """
        conn = conexion_solo_lectura(self.db_path)
        try:
            cursor = conn.cursor()
            query = """
            SELECT
                rowid,
                codigo_proyecto,
                archivo_origen,
                seccion,
                snippet(informes_fts, 3, '<b>', '</b>', '...', 12) AS fragmento,
                rank
            FROM informes_fts
            WHERE informes_fts MATCH ?
            ORDER BY rank
            LIMIT ?;
            """
            filas = cursor.execute(query, (consulta_fts, limite)).fetchall()
            return [dict(f) for f in filas]
        finally:
            conn.close()

    def contar(self) -> int:
        """Retorna el número total de fragmentos indexados en FTS5."""
        conn = conexion_solo_lectura(self.db_path)
        try:
            cursor = conn.cursor()
            res = cursor.execute("SELECT count(*) FROM informes_fts;").fetchone()
            return res[0] if res else 0
        finally:
            conn.close()
