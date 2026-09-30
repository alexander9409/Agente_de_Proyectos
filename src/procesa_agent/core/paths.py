"""
Definición centralizada de todas las rutas del proyecto.
Garantiza portabilidad multiplataforma utilizando exclusivamente pathlib.Path.
"""

from pathlib import Path

# Raíz del proyecto (directorio Agente_de_Proyectos)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

# Directorios de datos y fichas
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
FICHAS_DIR = DATA_DIR / "fichas"
DEFAULT_DB_PATH = DATA_DIR / "database.sqlite"
REGLAS_NEGOCIO_PATH = DATA_DIR / "reglas_negocio.json"

# Directorio de prompts del sistema
PROMPTS_DIR = PROJECT_ROOT / "prompts"
SYSTEM_AGENTE_PROMPT_PATH = PROMPTS_DIR / "system_agente.md"
EXTRACCION_FICHA_PROMPT_PATH = PROMPTS_DIR / "extraccion_ficha.md"
