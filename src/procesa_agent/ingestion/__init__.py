"""
Módulo del Pipeline de Ingesta (procesa_agent.ingestion).
Exporta el pipeline robusto, extractor estructurado, segmentador y fábrica de lectores.
"""

from pathlib import Path
from typing import Any, Dict, Optional

from procesa_agent.ingestion.extractor import DocumentExtractor, guardar_ficha_json
from procesa_agent.ingestion.pipeline import IngestionPipeline, calcular_sha256
from procesa_agent.ingestion.readers import DocumentReader, DocxReader, PDFReader, get_reader
from procesa_agent.ingestion.segmenter import DocumentSegmenter, segmentar_documento


def ejecutar_ingesta_completa(
    db_path: Optional[str] = None,
    raw_dir: Optional[Path] = None,
    fichas_dir: Optional[Path] = None,
    force: bool = False,
) -> Dict[str, Any]:
    """Función de compatibilidad para ejecutar el lote completo de ingesta."""
    pipeline = IngestionPipeline(db_path=db_path, raw_dir=raw_dir, fichas_dir=fichas_dir)
    return pipeline.ejecutar(force=force)


__all__ = [
    "IngestionPipeline",
    "DocumentExtractor",
    "guardar_ficha_json",
    "DocumentSegmenter",
    "segmentar_documento",
    "DocumentReader",
    "PDFReader",
    "DocxReader",
    "get_reader",
    "calcular_sha256",
    "ejecutar_ingesta_completa",
]
