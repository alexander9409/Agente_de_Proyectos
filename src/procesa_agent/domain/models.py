from typing import List, Optional

from pydantic import BaseModel, Field


class MetricaKPI(BaseModel):
    indicador: str = Field(description="Nombre del KPI o indicador evaluado")
    unidad: Optional[str] = Field(None, description="Unidad de medida (%, min, días, etc.)")
    linea_base: str = Field(description="Valor inicial medido antes de la intervención")
    meta: Optional[str] = Field(None, description="Meta acordada o 'Sin meta'")
    resultado: str = Field(description="Resultado final cuantitativo al cierre")
    variacion: Optional[str] = Field(None, description="Variación porcentual o absoluta")
    cumplimiento: str = Field(
        description="Cumplido | Parcialmente cumplido | No cumplido | Informativo"
    )
    observaciones: Optional[str] = Field(
        None, description="Causas de desvío, factores externos o estacionalidad"
    )


class LeccionAprendida(BaseModel):
    tema: str = Field(
        description="Categoría: Gestión del cambio | Calidad de datos | Terceros | Metodología"
    )
    titulo: str = Field(description="Frase síntesis de la lección aprendida")
    descripcion: str = Field(description="Detalle de lo ocurrido y cómo abordarlo")


class Iniciativa(BaseModel):
    nombre: str = Field(description="Nombre de la iniciativa o entregable")
    descripcion: str = Field(description="Detalle técnico de qué se implementó")


class FichaProyecto(BaseModel):
    codigo_proyecto: str = Field(description="Código único del proyecto (ej. PC-2025-027)")
    archivo_origen: str = Field(description="Nombre del archivo original de informe")
    cliente: str = Field(description="Nombre oficial de la empresa cliente")
    cliente_descripcion: Optional[str] = Field(
        None, description="Tamaño, capacidad o contexto operativo"
    )
    sector: str = Field(description="Sector o industria")
    ubicacion: Optional[str] = Field(None, description="Ciudad o sedes intervenidas")
    periodo: str = Field(description="Rango de fechas formal de ejecución")
    duracion_semanas: int = Field(description="Duración total en semanas (número entero)")
    gerente_proyecto: str = Field(description="Nombre del Gerente de Proyecto de Procesa")
    contraparte_cliente: Optional[str] = Field(
        None, description="Gerencias o áreas de contacto del cliente"
    )
    estado: str = Field(description="Estado de cierre (Cerrado aceptado | Cerrado con pendientes)")
    fecha_aceptacion: Optional[str] = Field(None, description="Fecha de firma de aceptación")
    resumen_ejecutivo: str = Field(
        description="Síntesis del problema, abordaje y resultados principales"
    )
    diagnostico_problema: Optional[str] = Field(
        None, description="Causas raíz, cuellos de botella y situación inicial"
    )
    alcance_incluido: Optional[str] = Field(
        None, description="Procesos, líneas y locales efectivamente intervenidos"
    )
    alcance_excluido: Optional[str] = Field(
        None, description="Áreas o líneas expresamente fuera de alcance"
    )
    metodologia: Optional[str] = Field(
        None, description="Marcos de trabajo aplicados (Lean, TPM, SMED, etc.)"
    )
    iniciativas_clave: List[Iniciativa] = Field(
        default_factory=list, description="Iniciativas clave implementadas"
    )
    kpis: List[MetricaKPI] = Field(
        default_factory=list, description="Listado completo de métricas evaluadas"
    )
    lecciones: List[LeccionAprendida] = Field(
        default_factory=list, description="Lecciones aprendidas documentadas"
    )
    proximos_pasos: List[str] = Field(
        default_factory=list, description="Recomendaciones post-cierre y fases futuras"
    )


class ReglaNegocio(BaseModel):
    id: Optional[int] = Field(None, description="Identificador único autoincremental")
    codigo_proyecto: Optional[str] = Field(
        None, description="Código de proyecto o None si es global"
    )
    tipo: str = Field(
        description="Tipo de regla: prevalencia | no_atribuible | discrepancia | estado"
    )
    titulo: str = Field(description="Título descriptivo de la regla")
    descripcion: str = Field(description="Contenido exacto de la regla de fiabilidad")
    fuente: Optional[str] = Field(None, description="Archivo origen que sustenta la regla")
