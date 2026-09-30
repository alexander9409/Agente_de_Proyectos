"""
Módulo de Lectura Universal de Documentos (src/parser.py)
Soporta extracción y segmentación de archivos PDF (pypdf) y DOCX (python-docx).
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

import docx
import pypdf


def segmentar_texto_en_secciones(texto: str) -> List[Tuple[str, str]]:
    """
    Segmenta el texto continuo de un informe en secciones lógicas
    utilizando patrones de encabezados numerados o palabras clave estándar.
    """
    patron = r'(?m)^(?:(?:\d+\.|\bAnexo\s+[A-Z]\.)\s*[^\n]+)'
    coincidencias = list(re.finditer(patron, texto))

    if not coincidencias:
        return [("Documento Completo", texto.strip())]

    secciones: List[Tuple[str, str]] = []
    # Segmento inicial antes de la primera sección numerada (cabecera / metadatos)
    inicio_primera = coincidencias[0].start()
    if inicio_primera > 0:
        texto_cabecera = texto[:inicio_primera].strip()
        if texto_cabecera:
            secciones.append(("Cabecera y Metadatos", texto_cabecera))

    for idx, match in enumerate(coincidencias):
        titulo_seccion = match.group(0).strip()
        inicio = match.end()
        fin = coincidencias[idx + 1].start() if idx + 1 < len(coincidencias) else len(texto)
        cuerpo = texto[inicio:fin].strip()
        secciones.append((titulo_seccion, f"{titulo_seccion}\n{cuerpo}"))

    return secciones


def leer_pdf(ruta_archivo: str) -> Dict[str, Any]:
    """
    Extrae texto íntegro y segmentado de un archivo PDF utilizando pypdf.
    """
    path = Path(ruta_archivo)
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el archivo PDF: {ruta_archivo}")

    reader = pypdf.PdfReader(str(path))
    paginas_texto = []
    for pagina in reader.pages:
        texto_pag = pagina.extract_text() or ""
        paginas_texto.append(texto_pag)

    texto_completo = "\n\n".join(paginas_texto).strip()
    secciones = segmentar_texto_en_secciones(texto_completo)

    return {
        "archivo_origen": path.name,
        "tipo": "pdf",
        "texto_completo": texto_completo,
        "secciones": secciones,
        "num_paginas": len(reader.pages),
    }


def leer_docx(ruta_archivo: str) -> Dict[str, Any]:
    """
    Extrae texto íntegro y segmentado de un archivo DOCX utilizando python-docx,
    incluyendo párrafos y tablas.
    """
    path = Path(ruta_archivo)
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el archivo DOCX: {ruta_archivo}")

    doc = docx.Document(str(path))
    lineas: List[str] = []

    # Iterar por bloques preservando el orden de párrafos y tablas
    for elemento in doc.element.body:
        if elemento.tag.endswith('p'):
            p = docx.text.paragraph.Paragraph(elemento, doc)
            if p.text.strip():
                lineas.append(p.text.strip())
        elif elemento.tag.endswith('tbl'):
            t = docx.table.Table(elemento, doc)
            filas_texto = []
            for fila in t.rows:
                celdas = [c.text.strip() for c in fila.cells]
                filas_texto.append(" | ".join(celdas))
            if filas_texto:
                lineas.append("\n".join(filas_texto))

    texto_completo = "\n\n".join(lineas).strip()
    secciones = segmentar_texto_en_secciones(texto_completo)

    return {
        "archivo_origen": path.name,
        "tipo": "docx",
        "texto_completo": texto_completo,
        "secciones": secciones,
        "num_parrafos": len(doc.paragraphs),
    }


def leer_documento(ruta_archivo: str) -> Dict[str, Any]:
    """
    Lector universal que detecta la extensión (.pdf o .docx) y delega
    en la función extractora correspondiente.
    """
    ext = Path(ruta_archivo).suffix.lower()
    if ext == ".pdf":
        return leer_pdf(ruta_archivo)
    elif ext in [".docx", ".doc"]:
        return leer_docx(ruta_archivo)
    else:
        raise ValueError(f"Formato no soportado: {ext}. Solo se admiten archivos .pdf y .docx")
