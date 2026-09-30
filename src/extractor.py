"""
Módulo de Extracción y Pipeline Estructurado (src/extractor.py)
Utiliza Google GenAI SDK con Structured Outputs (response_schema=FichaProyecto)
para procesar informes PDF/DOCX, guardar fichas JSON e indexar en SQLite y FTS5.
"""

import json
import os
from pathlib import Path
from typing import List, Optional

from src.db import (
    get_default_db_path,
    guardar_ficha_en_bd,
    indexar_informe_fts,
    inicializar_bd,
)
from src.models import FichaProyecto
from src.parser import leer_documento

PROMPT_SISTEMA_EXTRACCION = """
Eres un Asistente Senior de Inteligencia Artificial y Consultoría Operativa para Procesa Consultores.
Tu labor es extraer una ficha estructurada de alta fidelidad a partir del informe de cierre de proyecto proporcionado.

REGLAS CRÍTICAS:
1. Extrae únicamente información explícitamente documentada en el informe. No infieras datos ausentes.
2. Identifica con rigor el campo 'alcance_excluido', ya que es un filtro crítico anti-alucinaciones.
3. Para cada KPI evaluado, clasifica el cumplimiento exactamente en: 'Cumplido', 'Parcialmente cumplido', 'No cumplido' o 'Informativo'.
4. Cada lección aprendida debe clasificarse en uno de los temas: 'Gestión del cambio', 'Calidad de datos', 'Terceros' o 'Metodología'.
5. Cumple estrictamente con el esquema JSON de FichaProyecto.
"""


def get_default_fichas_dir() -> Path:
    """Retorna la ruta del directorio data/fichas/."""
    base_dir = Path(__file__).resolve().parent.parent
    fichas_dir = base_dir / "data" / "fichas"
    fichas_dir.mkdir(parents=True, exist_ok=True)
    return fichas_dir


def extraer_ficha_con_gemini(
    ruta_archivo: str,
    api_key: str,
    model_name: str = "gemini-2.5-flash",
    temperature: float = 0.1
) -> FichaProyecto:
    """
    Llama a la API oficial de Google GenAI enviando el texto del documento
    y forzando la salida tipada según FichaProyecto.
    """
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        raise ImportError("El paquete google-genai no está instalado. Ejecuta: pip install google-genai")

    # Lectura del archivo (PDF o DOCX)
    doc_info = leer_documento(ruta_archivo)
    texto_documento = doc_info["texto_completo"]
    nombre_archivo = doc_info["archivo_origen"]

    client = genai.Client(api_key=api_key)

    contenido_usuario = f"""
INFORME DE CIERRE A PROCESAR:
Archivo de origen: {nombre_archivo}

--- CONTENIDO DEL INFORME ---
{texto_documento}
--- FIN DEL CONTENIDO ---

Extrae la ficha técnica completa del proyecto asegurando la máxima fidelidad y apego al esquema FichaProyecto.
"""

    response = client.models.generate_content(
        model=model_name,
        contents=[
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=PROMPT_SISTEMA_EXTRACCION + "\n\n" + contenido_usuario)
                ]
            )
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=FichaProyecto,
            temperature=temperature,
        ),
    )

    if not response.text:
        raise ValueError(f"Respuesta vacía recibida de Gemini para el archivo {nombre_archivo}")

    ficha = FichaProyecto.model_validate_json(response.text)
    # Asegurar nombre de archivo de origen
    if not ficha.archivo_origen:
        ficha.archivo_origen = nombre_archivo

    return ficha


def guardar_ficha_json(ficha: FichaProyecto, dir_fichas: Optional[str] = None) -> str:
    """Guarda la ficha en formato JSON en data/fichas/{codigo_proyecto}.json."""
    directorio = Path(dir_fichas) if dir_fichas else get_default_fichas_dir()
    directorio.mkdir(parents=True, exist_ok=True)
    nombre_archivo = f"{ficha.codigo_proyecto.strip()}.json"
    ruta_salida = directorio / nombre_archivo

    with open(ruta_salida, "w", encoding="utf-8") as f:
        json_str = ficha.model_dump_json(indent=2)
        f.write(json_str)

    return str(ruta_salida)


def cargar_ficha_json(ruta_json: str) -> FichaProyecto:
    """Carga y valida una ficha desde un archivo JSON."""
    with open(ruta_json, "r", encoding="utf-8") as f:
        data = json.load(f)
    return FichaProyecto.model_validate(data)


def procesar_e_indexar_informe(
    ruta_archivo: str,
    ficha: FichaProyecto,
    db_path: Optional[str] = None
) -> None:
    """
    Persiste la ficha en SQLite (tablas proyectos, kpis, lecciones)
    y parsea el archivo original para indexar sus secciones en informes_fts.
    """
    db = db_path or get_default_db_path()
    inicializar_bd(db)

    # 1. Guardar en tablas relacionales
    guardar_ficha_en_bd(ficha, db)

    # 2. Segmentar e indexar en FTS5
    doc_info = leer_documento(ruta_archivo)
    indexar_informe_fts(
        codigo_proyecto=ficha.codigo_proyecto,
        archivo_origen=doc_info["archivo_origen"],
        secciones=doc_info["secciones"],
        db_path=db,
    )


def ejecutar_ingesta_completa(
    raw_dir: Optional[str] = None,
    fichas_dir: Optional[str] = None,
    db_path: Optional[str] = None,
    api_key: Optional[str] = None,
    model_name: str = "gemini-2.5-flash",
    temperature: float = 0.1,
    forzar_extraccion_gemini: bool = False,
) -> List[FichaProyecto]:
    """
    Pipeline maestro de ingesta:
    1. Si forzar_extraccion_gemini es True y hay api_key, llama a Gemini para cada informe en data/raw/.
    2. Si existen fichas JSON previas en data/fichas/ y no se fuerza extracción con Gemini,
       las reutiliza para carga rápida y resiliente.
    3. Si no hay JSONs y hay API key, invoca Gemini.
    4. Indexa los textos íntegros en SQLite FTS5 y persiste las entidades relacionales.
    """
    base_dir = Path(__file__).resolve().parent.parent
    dir_raw = Path(raw_dir) if raw_dir else (base_dir / "data" / "raw")
    dir_fichas = Path(fichas_dir) if fichas_dir else (base_dir / "data" / "fichas")
    db = db_path or get_default_db_path()

    inicializar_bd(db)
    archivos_procesados: List[FichaProyecto] = []

    archivos_raw = [
        f for f in sorted(dir_raw.iterdir())
        if f.is_file() and f.suffix.lower() in [".pdf", ".docx"]
    ]

    for archivo in archivos_raw:
        ficha: Optional[FichaProyecto] = None

        # Verificar si ya existe JSON correspondiente en data/fichas/
        archivos_json = list(dir_fichas.glob("*.json"))
        json_candidato = None
        for j in archivos_json:
            try:
                with open(j, "r", encoding="utf-8") as f_json:
                    contenido_json = json.load(f_json)
                    if contenido_json.get("archivo_origen") == archivo.name:
                        json_candidato = j
                        break
            except Exception:
                continue

        # Si se fuerza Gemini y hay API key, o si no hay JSON candidato
        if (forzar_extraccion_gemini and api_key) or (json_candidato is None and api_key):
            ficha = extraer_ficha_con_gemini(
                ruta_archivo=str(archivo),
                api_key=api_key,
                model_name=model_name,
                temperature=temperature,
            )
            guardar_ficha_json(ficha, str(dir_fichas))
        elif json_candidato is not None:
            ficha = cargar_ficha_json(str(json_candidato))

        if ficha is not None:
            procesar_e_indexar_informe(
                ruta_archivo=str(archivo),
                ficha=ficha,
                db_path=db,
            )
            archivos_procesados.append(ficha)

    return archivos_procesados
