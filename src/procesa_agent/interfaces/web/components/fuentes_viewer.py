"""
Visor y Resaltador de Citas Documentales (interfaces/web/components/fuentes_viewer.py).
Identifica referencias documentales en respuestas y genera distintivos visuales SaaS.
"""

import re


def resaltar_fuentes(texto: str) -> str:
    """Resalta visualmente las citas de fuentes documentales con un badge SaaS."""
    patron = r"(\[Fuente:\s*([^\]]+)\])"
    reemplazo = r'<span class="badge-fuente">📄 \1</span>'
    return re.sub(patron, reemplazo, texto)
