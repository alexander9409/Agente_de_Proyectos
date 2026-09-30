"""
Pipeline de Ingesta y Procesamiento de Informes (ingestion/pipeline.py).
Gestiona el flujo integral:
1. Inspección de archivos en data/raw/ y cálculo de hash SHA-256 para detección de cambios.
2. Extracción de texto con readers modulares (.pdf y .docx).
3. Segmentación en secciones lógicas para FTS5.
4. Extracción estructurada con LLMProvider (FichaProyecto).
5. Persistencia atómica por archivo (ficha + kpis + lecciones + FTS5 en una transacción).
6. Aislamiento de fallos por documento con reporte detallado de ejecución.
"""

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from procesa_agent.core.logging import logger
from procesa_agent.core.paths import FICHAS_DIR, RAW_DATA_DIR
from procesa_agent.domain.models import FichaProyecto
from procesa_agent.infrastructure.db.connection import get_default_db_path, obtener_conexion
from procesa_agent.infrastructure.db.repositories.reglas_repo import ReglasRepository
from procesa_agent.infrastructure.db.schema import inicializar_bd
from procesa_agent.infrastructure.llm.base import LLMProvider
from procesa_agent.ingestion.extractor import DocumentExtractor, guardar_ficha_json
from procesa_agent.ingestion.readers import get_reader
from procesa_agent.ingestion.segmenter import DocumentSegmenter


def calcular_sha256(archivo_path: Path) -> str:
    """Calcula el hash SHA-256 de un archivo en disco."""
    sha = hashlib.sha256()
    with open(archivo_path, "rb") as f:
        while chunk := f.read(65536):
            sha.update(chunk)
    return sha.hexdigest()


class IngestionPipeline:
    """Pipeline de ingesta robusto con hash SHA-256, transacciones atómicas y reporte de lote."""

    def __init__(
        self,
        db_path: Optional[str] = None,
        raw_dir: Optional[Path] = None,
        fichas_dir: Optional[Path] = None,
        llm_provider: Optional[LLMProvider] = None,
    ) -> None:
        self.db_path = db_path or get_default_db_path()
        self.raw_dir = raw_dir or RAW_DATA_DIR
        self.fichas_dir = fichas_dir or FICHAS_DIR
        self.extractor = DocumentExtractor(llm_provider=llm_provider)
        self.segmenter = DocumentSegmenter()

        self.fichas_dir.mkdir(parents=True, exist_ok=True)
        self.raw_dir.mkdir(parents=True, exist_ok=True)

        # Inicializar o migrar BD
        inicializar_bd(self.db_path)

    def _mapear_fichas_existentes(self) -> Dict[str, Tuple[Path, FichaProyecto]]:
        """Mapea una sola vez las fichas JSON existentes por nombre de archivo origen."""
        mapa: Dict[str, Tuple[Path, FichaProyecto]] = {}
        for p in self.fichas_dir.glob("*.json"):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    ficha = FichaProyecto(**data)
                    if ficha.archivo_origen:
                        mapa[ficha.archivo_origen] = (p, ficha)
            except Exception as e:
                logger.warning(f"No se pudo cargar ficha existente {p.name}: {e}")
        return mapa

    def _persistir_transaccion_archivo(
        self,
        ficha: FichaProyecto,
        secciones: List[Tuple[str, str]],
        conn,
    ) -> None:
        """Persiste ficha, KPIs, lecciones y fragmentos FTS5 en una única transacción atómica."""
        # 1. Tabla proyectos
        iniciativas_json = json.dumps(
            [i.model_dump() for i in ficha.iniciativas_clave], ensure_ascii=False
        )
        proximos_pasos_json = json.dumps(ficha.proximos_pasos, ensure_ascii=False)

        cursor = conn.cursor()
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

        # 2. KPIs
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

        # 3. Lecciones
        cursor.execute("DELETE FROM lecciones WHERE codigo_proyecto = ?;", (ficha.codigo_proyecto,))
        for lec in ficha.lecciones:
            cursor.execute(
                """
                INSERT INTO lecciones (codigo_proyecto, tema, titulo, descripcion)
                VALUES (?, ?, ?, ?);
                """,
                (ficha.codigo_proyecto, lec.tema, lec.titulo, lec.descripcion),
            )

        # 4. Tabla virtual FTS5
        cursor.execute(
            "DELETE FROM informes_fts WHERE codigo_proyecto = ?;", (ficha.codigo_proyecto,)
        )
        for seccion_nombre, contenido in secciones:
            if contenido and contenido.strip():
                cursor.execute(
                    """
                    INSERT INTO informes_fts (codigo_proyecto, archivo_origen, seccion, contenido)
                    VALUES (?, ?, ?, ?);
                    """,
                    (
                        ficha.codigo_proyecto,
                        ficha.archivo_origen,
                        seccion_nombre,
                        contenido.strip(),
                    ),
                )

    def procesar_archivo(
        self,
        archivo_path: Path,
        fichas_existentes: Dict[str, Tuple[Path, FichaProyecto]],
        force: bool = False,
    ) -> Tuple[str, FichaProyecto]:
        """
        Procesa un único archivo fuente aplicando hash y persistencia atómica.
        Retorna ('procesado' | 'omitido', ficha).
        """
        reader = get_reader(archivo_path)
        doc_info = reader.read(archivo_path)
        texto_completo = doc_info["texto_completo"]
        nombre_archivo = archivo_path.name
        secciones = self.segmenter.segment(texto_completo)

        # Comprobar si ya existe ficha previa
        ficha_existente_entry = fichas_existentes.get(nombre_archivo)
        sha_actual = calcular_sha256(archivo_path)

        # Metadato de hash guardado en archivo sidecar .sha256
        sha_file = self.fichas_dir / f"{nombre_archivo}.sha256"
        sha_previo = sha_file.read_text(encoding="utf-8").strip() if sha_file.exists() else None

        if ficha_existente_entry and sha_previo == sha_actual and not force:
            # Archivo idéntico sin cambios: omitir re-extracción LLM
            logger.info(f"Omitiendo re-extracción para {nombre_archivo} (SHA-256 sin cambios).")
            _, ficha = ficha_existente_entry
            estado = "omitido"
        elif ficha_existente_entry and not force:
            # Existe ficha y no hay --force: reutilizar la ficha existente
            logger.info(f"Reutilizando ficha existente para {nombre_archivo}.")
            _, ficha = ficha_existente_entry
            estado = "omitido"
        else:
            # Requiere extracción con LLMProvider
            ficha = self.extractor.extraer_ficha(texto_completo, nombre_archivo)
            guardar_ficha_json(ficha, self.fichas_dir)
            sha_file.write_text(sha_actual, encoding="utf-8")
            estado = "procesado"

        # Persistencia en base de datos en una sola transacción
        conn = obtener_conexion(self.db_path)
        try:
            self._persistir_transaccion_archivo(ficha, secciones, conn)
            conn.commit()
        finally:
            conn.close()

        # Sincronizar reglas de negocio que correspondan a este proyecto
        reglas_repo = ReglasRepository(self.db_path)
        reglas_repo.cargar_desde_json()

        return estado, ficha

    def ejecutar(
        self,
        force: bool = False,
        solo_archivo: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Ejecuta el lote de ingesta sobre data/raw/ con aislamiento de fallos por archivo.
        Retorna reporte con listas de procesados, omitidos y fallidos con su motivo.
        """
        archivos = sorted(
            [
                p
                for p in self.raw_dir.iterdir()
                if p.is_file() and p.suffix.lower() in [".pdf", ".docx", ".doc"]
            ]
        )

        if solo_archivo:
            archivos = [p for p in archivos if p.name == solo_archivo or p.stem == solo_archivo]

        logger.info(
            f"Iniciando pipeline de ingesta para {len(archivos)} archivo(s) en: {self.raw_dir}"
        )

        fichas_existentes = self._mapear_fichas_existentes()

        procesados: List[str] = []
        omitidos: List[str] = []
        fallidos: List[Dict[str, str]] = []

        for p in archivos:
            try:
                estado, ficha = self.procesar_archivo(p, fichas_existentes, force=force)
                if estado == "procesado":
                    procesados.append(p.name)
                else:
                    omitidos.append(p.name)
            except Exception as e:
                logger.error(f"Fallo en procesamiento de {p.name}: {e}")
                fallidos.append({"archivo": p.name, "error": str(e)})

        reporte = {
            "total_archivos": len(archivos),
            "procesados": procesados,
            "omitidos": omitidos,
            "fallidos": fallidos,
            "exitoso": len(fallidos) == 0,
        }

        logger.info(
            f"Ingesta finalizada: {len(procesados)} procesados, {len(omitidos)} omitidos, {len(fallidos)} fallidos."
        )
        return reporte


def ejecutar_ingesta_completa(
    raw_dir: Optional[str] = None,
    fichas_dir: Optional[str] = None,
    db_path: Optional[str] = None,
    api_key: Optional[str] = None,
    model_name: str = "gemini-2.5-flash",
    temperature: float = 0.1,
    forzar_extraccion_gemini: bool = False,
    force: bool = False,
) -> Dict[str, Any]:
    """
    Función de compatibilidad retrocompatible.
    Envuelve IngestionPipeline().ejecutar() para conservar la API previa sin romper código existente.
    """
    p_raw = Path(raw_dir) if raw_dir else None
    p_fichas = Path(fichas_dir) if fichas_dir else None
    llm_prov = None
    if api_key:
        from procesa_agent.infrastructure.llm.gemini import GeminiProvider

        llm_prov = GeminiProvider(api_key=api_key, model_name=model_name, temperature=temperature)

    pipeline = IngestionPipeline(
        db_path=db_path,
        raw_dir=p_raw,
        fichas_dir=p_fichas,
        llm_provider=llm_prov,
    )
    return pipeline.ejecutar(force=(force or forzar_extraccion_gemini))
