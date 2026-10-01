"""
Punto de entrada de la interfaz CLI de Procesa Consultores.
"""

import sys
from pathlib import Path

_SRC_DIR = str(Path(__file__).resolve().parent / "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from procesa_agent.interfaces.cli.main import main

if __name__ == "__main__":
    main()
