"""
Repositorio de Proyectos, KPIs y Lecciones Aprendidas (proyectos_repo.py).
Gestiona la persistencia atómica relacional y la consulta de entidades de negocio.
Encapsula la serialización y deserialización de listas JSON (iniciativas_clave, proximos_pasos).
"""

import json
from typing import Any, Dict, List, Optional

from procesa_agent.domain.models import FichaProyecto, Iniciativa, LeccionAprendida, MetricaKPI
from procesa_agent.infrastructure.db.connection import conexion_solo_lectura, obtener_conexion


class ProyectosRepository:
    """Gestiona el acceso relacional a las tablas 'proyectos', 'kpis' y 'lecciones'."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def guardar_ficha(self, ficha: FichaProyecto) -> None:
        """
        Persiste una FichaProyecto completa en una sola transacción atómica:
        1. Tabla 'proyectos' con serialización JSON de iniciativas y próximos pasos.
        2. Tabla relacional 'kpis' (elimina anteriores del proyecto e inserta nuevas).
        3. Tabla relacional 'lecciones' (elimina anteriores del proyecto e inserta nuevas).
        """
        conn = obtener_conexion(self.db_path)
        try:
            cursor = conn.cursor()
            iniciativas_json = json.dumps(
                [i.model_dump() for i in ficha.iniciativas_clave], ensure_ascii=False
            )
            proximos_pasos_json = json.dumps(ficha.proximos_pasos, ensure_ascii=False)

            cursor.execute(
                """
                INSERT INTO proyectos (
                    codigo_proyecto, archivo_origen, cliente, cliente_descripcion,
                    sector, ubicacion, periodo, duracion_semanas, gerente_proyecto,
                    contraparte_cliente, estado, fecha_aceptacion, resumen_ejecutivo,
                    diagnostico_problema, alcance_incluido, alcance_excluido,
                    metodologia, iniciativas_clave, proximos_pasos
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(codigo_proyecto) DO UPDATE SET
                    archivo_origen = excluded.archivo_origen,
                    cliente = excluded.cliente,
                    cliente_descripcion = excluded.cliente_descripcion,
                    sector = excluded.sector,
                    ubicacion = excluded.ubicacion,
                    periodo = excluded.periodo,
                    duracion_semanas = excluded.duracion_semanas,
                    gerente_proyecto = excluded.gerente_proyecto,
                    contraparte_cliente = excluded.contraparte_cliente,
                    estado = excluded.estado,
                    fecha_aceptacion = excluded.fecha_aceptacion,
                    resumen_ejecutivo = excluded.resumen_ejecutivo,
                    diagnostico_problema = excluded.diagnostico_problema,
                    alcance_incluido = excluded.alcance_incluido,
                    alcance_excluido = excluded.alcance_excluido,
                    metodologia = excluded.metodologia,
                    iniciativas_clave = excluded.iniciativas_clave,
                    proximos_pasos = excluded.proximos_pasos;
                """,
                (
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
                ),
            )

            # Persistir KPIs
            cursor.execute("DELETE FROM kpis WHERE codigo_proyecto = ?;", (ficha.codigo_proyecto,))
            for k in ficha.kpis:
                cursor.execute(
                    """
                    INSERT INTO kpis (
                        codigo_proyecto, indicador, unidad, linea_base, meta, resultado,
                        variacion, cumplimiento, observaciones
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        ficha.codigo_proyecto,
                        k.indicador,
                        k.unidad,
                        k.linea_base,
                        k.meta,
                        k.resultado,
                        k.variacion,
                        k.cumplimiento,
                        k.observaciones,
                    ),
                )

            # Persistir Lecciones Aprendidas
            cursor.execute(
                "DELETE FROM lecciones WHERE codigo_proyecto = ?;", (ficha.codigo_proyecto,)
            )
            for lec in ficha.lecciones:
                cursor.execute(
                    """
                    INSERT INTO lecciones (codigo_proyecto, tema, titulo, descripcion)
                    VALUES (?, ?, ?, ?);
                    """,
                    (ficha.codigo_proyecto, lec.tema, lec.titulo, lec.descripcion),
                )

            conn.commit()
        finally:
            conn.close()

    def obtener_por_codigo(self, codigo_proyecto: str) -> Optional[FichaProyecto]:
        """Recupera la FichaProyecto completa reconstruyendo sus relaciones."""
        conn = conexion_solo_lectura(self.db_path)
        try:
            cursor = conn.cursor()
            r = cursor.execute(
                "SELECT * FROM proyectos WHERE codigo_proyecto = ?;", (codigo_proyecto,)
            ).fetchone()
            if not r:
                return None

            kpis_rows = cursor.execute(
                "SELECT * FROM kpis WHERE codigo_proyecto = ? ORDER BY id;", (codigo_proyecto,)
            ).fetchall()
            lecciones_rows = cursor.execute(
                "SELECT * FROM lecciones WHERE codigo_proyecto = ? ORDER BY id;", (codigo_proyecto,)
            ).fetchall()

            iniciativas_raw = json.loads(r["iniciativas_clave"]) if r["iniciativas_clave"] else []
            iniciativas = [Iniciativa(**item) for item in iniciativas_raw]
            proximos_pasos = json.loads(r["proximos_pasos"]) if r["proximos_pasos"] else []

            kpis = [
                MetricaKPI(
                    indicador=k["indicador"],
                    unidad=k["unidad"],
                    linea_base=k["linea_base"],
                    meta=k["meta"],
                    resultado=k["resultado"],
                    variacion=k["variacion"],
                    cumplimiento=k["cumplimiento"],
                    observaciones=k["observaciones"],
                )
                for k in kpis_rows
            ]

            lecciones = [
                LeccionAprendida(
                    tema=lec["tema"],
                    titulo=lec["titulo"],
                    descripcion=lec["descripcion"],
                )
                for lec in lecciones_rows
            ]

            return FichaProyecto(
                codigo_proyecto=r["codigo_proyecto"],
                archivo_origen=r["archivo_origen"],
                cliente=r["cliente"],
                cliente_descripcion=r["cliente_descripcion"],
                sector=r["sector"],
                ubicacion=r["ubicacion"],
                periodo=r["periodo"],
                duracion_semanas=r["duracion_semanas"],
                gerente_proyecto=r["gerente_proyecto"],
                contraparte_cliente=r["contraparte_cliente"],
                estado=r["estado"],
                fecha_aceptacion=r["fecha_aceptacion"],
                resumen_ejecutivo=r["resumen_ejecutivo"],
                diagnostico_problema=r["diagnostico_problema"],
                alcance_incluido=r["alcance_incluido"],
                alcance_excluido=r["alcance_excluido"],
                metodologia=r["metodologia"],
                iniciativas_clave=iniciativas,
                kpis=kpis,
                lecciones=lecciones,
                proximos_pasos=proximos_pasos,
            )
        finally:
            conn.close()

    def obtener_todos(self) -> List[Dict[str, Any]]:
        """Retorna todos los proyectos registrados como lista de diccionarios."""
        conn = conexion_solo_lectura(self.db_path)
        try:
            cursor = conn.cursor()
            rows = cursor.execute("SELECT * FROM proyectos ORDER BY codigo_proyecto;").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def obtener_kpis(self, codigo_proyecto: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retorna los KPIs registrados, opcionalmente filtrados por proyecto."""
        conn = conexion_solo_lectura(self.db_path)
        try:
            cursor = conn.cursor()
            if codigo_proyecto:
                rows = cursor.execute(
                    "SELECT * FROM kpis WHERE codigo_proyecto = ? ORDER BY id;", (codigo_proyecto,)
                ).fetchall()
            else:
                rows = cursor.execute("SELECT * FROM kpis ORDER BY codigo_proyecto, id;").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def obtener_lecciones(self, codigo_proyecto: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retorna las lecciones aprendidas registradas."""
        conn = conexion_solo_lectura(self.db_path)
        try:
            cursor = conn.cursor()
            if codigo_proyecto:
                rows = cursor.execute(
                    "SELECT * FROM lecciones WHERE codigo_proyecto = ? ORDER BY id;",
                    (codigo_proyecto,),
                ).fetchall()
            else:
                rows = cursor.execute(
                    "SELECT * FROM lecciones ORDER BY codigo_proyecto, id;"
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def obtener_resumen(self) -> Dict[str, int]:
        """Retorna el conteo global de entidades en la base de datos."""
        conn = conexion_solo_lectura(self.db_path)
        try:
            cursor = conn.cursor()
            n_proyectos = cursor.execute("SELECT count(*) FROM proyectos;").fetchone()[0]
            n_kpis = cursor.execute("SELECT count(*) FROM kpis;").fetchone()[0]
            n_lecciones = cursor.execute("SELECT count(*) FROM lecciones;").fetchone()[0]
            n_fts = cursor.execute("SELECT count(*) FROM informes_fts;").fetchone()[0]
            return {
                "proyectos": n_proyectos,
                "kpis": n_kpis,
                "lecciones": n_lecciones,
                "fts": n_fts,
            }
        finally:
            conn.close()
