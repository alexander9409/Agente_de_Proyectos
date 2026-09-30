"""
Extractor Estructurado de Fichas de Proyecto (ingestion/extractor.py).
Utiliza el protocolo abstracto LLMProvider con Structured Outputs (FichaProyecto)
para extraer entidades técnicas desde el texto de los informes sin acoplarse al SDK de Gemini.
"""

from pathlib import Path
from typing import Optional

from procesa_agent.core.logging import logger
from procesa_agent.core.paths import FICHAS_DIR
from procesa_agent.domain.models import FichaProyecto
from procesa_agent.infrastructure.llm.base import LLMProvider
from procesa_agent.infrastructure.llm.gemini import GeminiProvider
from procesa_agent.ingestion.readers import get_reader

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


class DocumentExtractor:
    """Extrae fichas técnicas estructuradas desde texto documental mediante un LLMProvider."""

    def __init__(self, llm_provider: Optional[LLMProvider] = None) -> None:
        self.llm_provider = llm_provider or GeminiProvider()

    def extraer_ficha(self, texto_documento: str, nombre_archivo: str) -> FichaProyecto:
        """Invoca al LLMProvider para extraer una FichaProyecto tipada desde el texto."""
        prompt = (
            f"{PROMPT_SISTEMA_EXTRACCION}\n\n"
            f"INFORME DE CIERRE A PROCESAR:\n"
            f"Archivo de origen: {nombre_archivo}\n\n"
            f"--- CONTENIDO DEL INFORME ---\n"
            f"{texto_documento}\n"
            f"--- FIN DEL CONTENIDO ---\n\n"
            f"Extrae la ficha técnica completa del proyecto asegurando la máxima fidelidad y apego al esquema FichaProyecto."
        )

        logger.info(f"Extrayendo ficha estructurada con LLMProvider para: {nombre_archivo}")
        ficha = self.llm_provider.generar_estructurado(prompt=prompt, schema=FichaProyecto)

        if not ficha.archivo_origen:
            ficha.archivo_origen = nombre_archivo

        return ficha


def guardar_ficha_json(ficha: FichaProyecto, dir_fichas: Optional[Path] = None) -> Path:
    """Guarda la FichaProyecto en formato JSON en data/fichas/{codigo_proyecto}.json."""
    directorio = dir_fichas or FICHAS_DIR
    directorio.mkdir(parents=True, exist_ok=True)
    archivo_json = directorio / f"{ficha.codigo_proyecto.strip()}.json"
    with open(archivo_json, "w", encoding="utf-8") as f:
        f.write(ficha.model_dump_json(indent=2))
    return archivo_json


def extraer_ficha_con_gemini(
    ruta_archivo: str,
    api_key: Optional[str] = None,
    model_name: Optional[str] = None,
    temperature: float = 0.1,
) -> FichaProyecto:
    """Función de compatibilidad hacia atrás para extracción con Gemini."""
    path = Path(ruta_archivo)
    reader = get_reader(path)
    doc_info = reader.read(path)

    provider = GeminiProvider(api_key=api_key, model_name=model_name, temperature=temperature)
    extractor = DocumentExtractor(llm_provider=provider)
    return extractor.extraer_ficha(doc_info["texto_completo"], doc_info["archivo_origen"])


def ejecutar_ingesta_completa(*args, **kwargs):
    """Wrapper de conveniencia hacia procesa_agent.ingestion.pipeline.ejecutar_ingesta_completa."""
    from procesa_agent.ingestion.pipeline import ejecutar_ingesta_completa as _eic

    return _eic(*args, **kwargs)
