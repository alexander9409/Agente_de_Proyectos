"""
Segmentador Lógico de Documentos (ingestion/segmenter.py).
Divide el texto íntegro de los informes en secciones y capítulos estructurados
para su posterior indexación contextual y búsqueda léxica en SQLite FTS5.
"""

import re
from typing import List, Tuple


class DocumentSegmenter:
    """Segmenta textos documentales continuos en fragmentos lógicos titulados."""

    # Patrón para identificar títulos de sección: números arábigos o anexos con letras
    PATRON_SECCION = re.compile(
        r"(?m)^(?:(?:\d+\.|\bAnexo\s+[A-Z]\.|\bANEXO\s+[A-Z]\.|\bSección\s+\d+\.)\s*[^\n]+)"
    )

    def segment(self, texto: str) -> List[Tuple[str, str]]:
        """
        Segmenta el texto continuo en una lista de tuplas (titulo_seccion, contenido_completo).
        Preserva el título dentro del contenido para contextualizar snippets en FTS5.
        """
        texto_limpio = texto.strip()
        if not texto_limpio:
            return []

        coincidencias = list(self.PATRON_SECCION.finditer(texto_limpio))

        if not coincidencias:
            return [("Documento Completo", texto_limpio)]

        secciones: List[Tuple[str, str]] = []

        # Capturar cabecera / metadatos antes de la primera sección formal
        primer_inicio = coincidencias[0].start()
        if primer_inicio > 0:
            cabecera = texto_limpio[:primer_inicio].strip()
            if cabecera:
                secciones.append(("Cabecera y Metadatos", cabecera))

        for idx, match in enumerate(coincidencias):
            titulo = match.group(0).strip()
            inicio = match.end()
            fin = (
                coincidencias[idx + 1].start()
                if idx + 1 < len(coincidencias)
                else len(texto_limpio)
            )
            cuerpo = texto_limpio[inicio:fin].strip()
            contenido = f"{titulo}\n\n{cuerpo}" if cuerpo else titulo
            secciones.append((titulo, contenido))

        return secciones


# Instancia singleton predeterminada
segmenter_default = DocumentSegmenter()


def segmentar_documento(texto: str) -> List[Tuple[str, str]]:
    """Función de conveniencia para segmentar texto en secciones."""
    return segmenter_default.segment(texto)
