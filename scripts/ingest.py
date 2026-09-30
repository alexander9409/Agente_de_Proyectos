"""
Script de Ejecución del Pipeline de Ingesta Documental por CLI (scripts/ingest.py).
Permite ingestar informes (.pdf y .docx), calcular hashes SHA-256, extraer con LLMProvider
y persistir de forma atómica en SQLite y FTS5.
"""

import argparse
import sys
from pathlib import Path

from procesa_agent.ingestion.pipeline import IngestionPipeline


def main() -> None:
    """Punto de entrada para el comando procesa-ingest y ejecución directa del script."""
    parser = argparse.ArgumentParser(
        description="Pipeline de Ingesta Documental de Procesa Consultores."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Fuerza la re-extracción de fichas con el LLMProvider incluso si el hash SHA-256 no cambió.",
    )
    parser.add_argument(
        "--solo",
        type=str,
        default=None,
        help="Procesa exclusivamente un archivo específico por su nombre (ej. informe.pdf).",
    )
    parser.add_argument(
        "--raw-dir",
        type=str,
        default=None,
        help="Ruta al directorio de documentos crudos (data/raw por defecto).",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=None,
        help="Ruta a la base de datos SQLite de destino.",
    )

    args = parser.parse_args()

    raw_path = Path(args.raw_dir) if args.raw_dir else None

    print("=" * 70)
    print("   PROCESA CONSULTORES · PIPELINE ROBUSTO DE INGESTA DOCUMENTAL")
    print("=" * 70)
    print(f"Modo forzado (--force): {'SÍ' if args.force else 'NO'}")
    if args.solo:
        print(f"Filtro de archivo individual (--solo): {args.solo}")
    print("-" * 70)

    pipeline = IngestionPipeline(db_path=args.db_path, raw_dir=raw_path)
    reporte = pipeline.ejecutar(force=args.force, solo_archivo=args.solo)

    print("\n📊 REPORTE DE RESULTADOS DE INGESTA:")
    print(f"• Total archivos evaluados : {reporte['total_archivos']}")
    print(f"• Archivos procesados      : {len(reporte['procesados'])} {reporte['procesados']}")
    print(f"• Archivos omitidos (hash) : {len(reporte['omitidos'])} {reporte['omitidos']}")
    print(f"• Archivos con fallos      : {len(reporte['fallidos'])}")

    if reporte["fallidos"]:
        print("\n⚠️ DETALLE DE FALLOS:")
        for f in reporte["fallidos"]:
            print(f"  - [{f['archivo']}]: {f['error']}")
        sys.exit(1)
    else:
        print("\n✅ Proceso de ingesta completado con éxito total.")


if __name__ == "__main__":
    main()
