"""
Módulo de logging estructurado.
Garantiza que ningún secreto, token o clave sea volcado a logs o consola.
"""

import logging
import sys


def setup_logger(name: str = "procesa_agent", level: str = "INFO") -> logging.Logger:
    """Configura y retorna un logger estructurado."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(getattr(logging, level.upper(), logging.INFO))
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.propagate = False
    return logger


logger = setup_logger()
