"""
Visor y Resaltador de Citas Documentales (interfaces/web/components/fuentes_viewer.py).
Identifica referencias documentales en respuestas y genera distintivos visuales SaaS.
"""

import re


def resaltar_fuentes(texto: str) -> str:
    """
    Resalta visualmente las citas de fuentes documentales con distintivos nativos de Streamlit.
    Evita etiquetas HTML <span class="..."> que el renderizador de Markdown de Streamlit
    escapa como texto plano o bloques de código al estar dentro de listas.
    """
    # 1. Limpiar spans residuales si ya existían en el texto
    texto = re.sub(
        r'<span\s+class=["\']badge-fuente["\']>(?:📄\s*)?(\[Fuente:\s*[^\]]+\])<\/span>',
        r"\1",
        texto,
    )
    # 2. Reemplazar citas oficiales por distintivo visual nativo compatible con Streamlit
    patron = r"\[Fuente:\s*([^\]]+)\]"
    reemplazo = r":blue-background[📄 **Fuente:** \1]"
    return re.sub(patron, reemplazo, texto)
