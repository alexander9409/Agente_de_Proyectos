"""
Script de ejecución de ingesta documental por CLI (scripts/ingest.py).
"""

import sys

from procesa_agent.ingestion.extractor import ejecutar_ingesta_completa


def main():
    force = "--force" in sys.argv
    print(f"Iniciando pipeline de ingesta (forzar_extraccion={force})...")
    ejecutar_ingesta_completa(forzar_gemini=force)
    print("Ingesta completada exitosamente.")


if __name__ == "__main__":
    main()
