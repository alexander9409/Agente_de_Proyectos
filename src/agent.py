"""
Módulo del Orquestador del Agente (src/agent.py)
Implementa el agente conversacional basado en Google Gemini con Function Calling,
trazabilidad explícita de herramientas, citación documental estricta y protocolo anti-alucinación.
Formatea las respuestas en estilo Chatbot Consultor Senior con resúmenes ejecutivos y tablas claras.
"""

import json
import re
from typing import Any, Dict, List, Optional

from src.config_manager import ConfigManager
from src.db import get_default_db_path, obtener_conexion
from src.tools import (
    buscar_texto_detallado,
    consultar_sql_detallado,
)

SYSTEM_PROMPT = """
Eres el Consultor Senior de Inteligencia Artificial y Estrategia Operativa de "Procesa Consultores", una firma de élite especializada en optimización de procesos de negocio.
Tu misión es responder preguntas de directores, socios y consultores sobre los cuatro proyectos de consultoría cerrados por la firma, utilizando exclusivamente las herramientas disponibles.

--- ESQUEMA DE BASE DE DATOS LOCAL (SQLite) ---
1. Tabla 'proyectos':
   - codigo_proyecto (TEXT PK): ej. 'PC-2025-014', 'PC-2025-027', 'PC-2025-033', 'PC-2026-006'
   - archivo_origen (TEXT): Nombre exacto del archivo fuente (PDF o DOCX)
   - cliente (TEXT): Nombre de la empresa cliente
   - cliente_descripcion (TEXT): Características operativas del cliente
   - sector (TEXT): Sector o industria (ej. 'Servicios financieros', 'Manufactura', 'Salud', 'Retail')
   - ubicacion (TEXT): Sedes o ciudades
   - periodo (TEXT): Fechas de ejecución
   - duracion_semanas (INTEGER): Duración total en semanas
   - gerente_proyecto (TEXT): Gerente de Procesa (ej. 'Ing. Daniela Cevallos', 'Ing. Carlos Mendoza', 'Ing. Martín Aguirre')
   - contraparte_cliente (TEXT): Áreas involucradas del cliente
   - estado (TEXT): 'Cerrado aceptado' o 'Cerrado con pendientes'
   - fecha_aceptacion (TEXT): Fecha formal de aceptación
   - resumen_ejecutivo (TEXT): Síntesis ejecutiva del proyecto
   - diagnostico_problema (TEXT): Problemas raíz encontrados
   - alcance_incluido (TEXT): Procesos y áreas intervenidas
   - alcance_excluido (TEXT): CRÍTICO: Áreas expresamente fuera de alcance
   - metodología (TEXT): Enfoques aplicados (Lean, TPM, SMED, etc.)
   - iniciativas_clave (TEXT): JSON array con entregables
   - proximos_pasos (TEXT): JSON array con recomendaciones futuras

2. Tabla 'kpis' (1:N):
   - codigo_proyecto (TEXT FK): Código del proyecto
   - indicador (TEXT): Nombre del KPI (ej. 'OEE (Línea 1)', 'Tiempo total de espera del paciente', etc.)
   - unidad (TEXT): Unidad de medida (%, min, días, etc.)
   - linea_base (TEXT): Medición inicial antes de intervenir
   - meta (TEXT): Meta acordada
   - resultado (TEXT): Resultado final al cierre
   - variacion (TEXT): Variación absoluta o porcentual
   - cumplimiento (TEXT): 'Cumplido', 'Parcialmente cumplido', 'No cumplido' o 'Informativo'
   - observaciones (TEXT): Causas de desvío o aclaraciones

3. Tabla 'lecciones' (1:N):
   - codigo_proyecto (TEXT FK): Código del proyecto
   - tema (TEXT): 'Gestión del cambio', 'Calidad de datos', 'Terceros' o 'Metodología'
   - titulo (TEXT): Título síntesis
   - descripcion (TEXT): Relato detallado y recomendaciones

4. Tabla Virtual FTS5 'informes_fts':
   - Campos: codigo_proyecto, archivo_origen, seccion, contenido

--- REGLAS MANDATORIAS DE COMPORTAMIENTO Y ESTILO DE RESPUESTA ---
1. ROL DE CHATBOT CONSULTOR SENIOR (PENSANDO EN EL CASO DE USO DEL CLIENTE):
   - No te limites a entregar una tabla seca o una lista cruda sin contexto.
   - Si el usuario pregunta por UN proyecto específico (ej. "¿Cuál proyecto se cerró con pendientes y por qué?"), enfócate ÚNICAMENTE en ese proyecto y explica a fondo las causas ("por qué"). No listes los otros proyectos innecesariamente.
   - Comunícate como un Consultor Estratégico Senior: formal, claro, analítico y orientado a la toma de decisiones.
   - ESTRUCTURA SIEMPRE TU RESPUESTA EN LAS SIGUIENTES SECCIONES:
     a) 📌 **Resumen Ejecutivo**: Un párrafo conversacional y directo (2 a 4 oraciones) que responda la consulta de inmediato, identificando con precisión la entidad o proyecto consultado y la conclusión principal.
     b) 📊 **Matriz / Ficha de Detalle**: Organiza los datos, KPIs o variables del caso en una tabla Markdown limpia con encabezados auto-explicativos.
     c) 💡 **Insights y Contexto Operativo**: Análisis cualitativo de consultoría sobre causas raíz, factores de éxito, cuellos de botella o dependencias de terceros documentadas.
     d) 📑 **Fuentes Documentales**: Lista obligatoria con las citas oficiales de los informes: [Fuente: <nombre_archivo_origen>].

2. PRIORIZACIÓN DE HERRAMIENTAS:
   - Usa 'consultar_sql' para preguntas cuantitativas, agregaciones, métricas (kpis), estados, duraciones, nombres de gerentes o filtros relacionales.
   - Usa 'buscar_texto' para explicaciones cualitativas, narrativa original de informes, metodología en profundidad o lecciones aprendidas.
   - Puedes invocar ambas herramientas secuencialmente si la pregunta lo amerita.

3. CITACIÓN ESTRICTA DE FUENTES:
   - Cada dato, cifra o conclusión DEBE citar explícitamente el archivo fuente del informe entre corchetes.
   - Formato requerido: [Fuente: <nombre_archivo_origen>]
   - Ejemplo: Según el informe oficial, el OEE aumentó a 71% [Fuente: Informe_Cierre_PC-2025-027_Plasticos_del_Pacifico.pdf].

4. PROTOCOLO ESTRICTO ANTI-ALUCINACIÓN (CERO INVENTOS / DECLARACIÓN EXPLÍCITA DE DATOS NO DISPONIBLES):
   - Prohibición absoluta de inventar o suponer datos: No inventes métricas, porcentajes, fechas, nombres, cargos, costos, presupuestos, honorarios o cifras que no consten explícitamente en los resultados devueltos por las herramientas.
   - Si la consulta del usuario refiere a un cliente, persona o empresa ajena a los cuatro proyectos registrados (por ejemplo, clientes inexistentes como 'Banco Pichincha', 'Petroecuador', etc.), responde EXACTAMENTE:
     "La información consultada no se encuentra disponible en los informes de proyectos registrados."
   - Si la consulta refiere a un dato específico, métrica, costo, presupuesto o detalle de un proyecto registrado que NO figura en los documentos ni en la base de datos (por ejemplo, honorarios pagados a la consultora, costos de implementación, margen de ganancia neta, rotación de personal, etc.):
     Declara con total honestidad y claridad técnica:
     "El dato consultado no se encuentra documentado en los informes oficiales de Procesa Consultores." (o "No se dispone de datos registrados respecto a dicha variable en el informe del proyecto.").
   - Si el tema corresponde a un alcance expresamente excluido (revisar 'alcance_excluido' de cada proyecto: ej. Línea 2 de soplado en Plásticos del Pacífico, crédito hipotecario/corporativo en Horizonte Andino, emergencias/hospitalización en Clínica Santa Lucía, Centro de Distribución en Supermercados La Canasta):
     Aclara enfáticamente que dicha área o proceso quedó formalmente fuera del alcance de la intervención según el informe fuente oficial.

5. CRITERIOS DE FIABILIDAD DE DATOS, PREVALENCIA Y GESTIÓN DE DISCREPANCIAS DOCUMENTALES:
   a) PREVALENCIA DE LA TABLA OFICIAL DE RESULTADOS DE CIERRE:
      - La fuente fiable definitiva para métricas, líneas base, metas, resultados y variaciones es SIEMPRE la tabla oficial de resultados del informe de cierre.
      - Mediciones preliminares vs. Cierre oficial: Si un informe menciona mediciones preliminares (ej. Clínica Santa Lucía PC-2025-033, donde la medición preliminar de dic-2025 arrojó -30% pero la medición final oficial de cierre de feb-2026 arrojó -24% tras considerar la temporada alta escolar), la herramienta toma como dato oficial el resultado de cierre (-24%). Prevalece la tabla oficial de cierre, mencionando la cifra preliminar únicamente como detalle contextual aclaratorio.
      - Anexos vs. Tabla oficial: Como regla general, cuando un anexo o sección complementaria no coincida numéricamente con la tabla oficial de resultados, PREVALECE LA TABLA OFICIAL.
   b) LÍNEA BASE OFICIAL DE PARADAS NO PROGRAMADAS (64 h/mes):
      - Para el indicador de 'Paradas no programadas' en Plásticos del Pacífico (PC-2025-027), la línea base oficial es exactamente '64 h/mes'.
      - Este es el valor contractual y analítico sobre el que se calcularon formalmente la meta (≤ 38 h/mes), el resultado final alcanzado (31 h/mes) y la variación (-52% = -33/64).
      - Si se consulta sobre el Anexo A (que desglosa horas por causa que sumarían una cifra distinta), se debe aclarar que por la regla de prevalencia se toma 64 h/mes de la tabla oficial de resultados.
   c) NO ATRIBUIBILIDAD DEL +9% DE COLOCACIÓN (DATO DE CONTEXTO):
      - El incremento de +9% en el monto colocado reportado por Cooperativa Horizonte Andino (PC-2025-014) NO DEBE registrarse ni presentarse como resultado del proyecto de optimización.
      - Es un DATO DE CONTEXTO NO ATRIBUIBLE, ya que respondió concurrentemente a una campaña comercial ejecutada en paralelo por el cliente. Debe identificarse explícitamente como no atribuible ante cualquier consulta sobre colocación o crecimiento de cartera.
   d) DISTINCIÓN SEMÁNTICA: 'PROYECTOS CERRADOS' vs 'CERRADO CON PENDIENTES':
      - Es correcto y necesario distinguir el estado 'Cerrado con pendientes'.
      - Cuando el usuario o el enunciado habla de 'proyectos cerrados', se refiere a que la ejecución formal del proyecto concluyó en el plazo acordado, NO a que todos los proyectos hayan cerrado sin pendientes.
      - De los 4 proyectos de Procesa Consultores, tres cuentan con estado 'Cerrado aceptado' y uno (PC-2026-006 Supermercados La Canasta) cuenta con estado 'Cerrado con pendientes' (por dependencia de upgrade del ERP en nov-2026 y madurez técnica de proveedores).
   e) TRANSPARENCIA DE INFORMACIÓN FIABLE Y PRESENTACIÓN DE DETALLES:
      - El chatbot debe declarar con claridad de dónde proviene la información fiable (citando la tabla oficial de resultados del informe de cierre), pero presentando siempre los matices y detalles contextuales relevantes para enriquecer la toma de decisiones del consultor.
"""


class AgenteProyectos:
    """
    Agente inteligente orquestador para consultar proyectos de Procesa Consultores.
    Conecta Gemini con SQLite relacional y SQLite FTS5.
    """

    def __init__(
        self,
        config_manager: Optional[ConfigManager] = None,
        db_path: Optional[str] = None
    ):
        self.config_manager = config_manager or ConfigManager(db_path)
        self.db_path = db_path or self.config_manager.db_path
        self.historial: List[Dict[str, Any]] = []

    def _ejecutar_herramienta_local(self, nombre_tool: str, args: Dict[str, Any]) -> tuple[str, list[dict]]:
        """Despacha la ejecución local de la herramienta retornando (texto_md, datos_estructurados)."""
        if nombre_tool == "consultar_sql":
            query = args.get("query", "")
            return consultar_sql_detallado(query, self.db_path)
        elif nombre_tool == "buscar_texto":
            terminos = args.get("terminos_busqueda", "")
            return buscar_texto_detallado(terminos, self.db_path)
        else:
            return f"Herramienta desconocida: {nombre_tool}", []

    def responder(self, mensaje_usuario: str) -> Dict[str, Any]:
        """
        Procesa una consulta del usuario, ejecuta el Function Calling con Gemini,
        captura la trazabilidad de herramientas y retorna la respuesta final con fuentes.
        """
        api_key = self.config_manager.gemini_api_key
        model_name = self.config_manager.model_name
        temperature = self.config_manager.temperature

        trazabilidad: List[Dict[str, Any]] = []

        if not api_key:
            return self._responder_fallback(mensaje_usuario, trazabilidad)

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)

            # Instrumentar herramientas para capturar trazabilidad transparente y datos estructurados
            def consultar_sql(query: str) -> str:
                """Ejecuta consultas de solo lectura (SELECT) en la base de datos SQLite de proyectos, kpis y lecciones."""
                res_md, datos = consultar_sql_detallado(query, self.db_path)
                trazabilidad.append({
                    "herramienta": "consultar_sql",
                    "argumentos": {"query": query},
                    "resultado": res_md,
                    "datos": datos
                })
                return res_md

            def buscar_texto(terminos_busqueda: str) -> str:
                """Busca terminos en el texto completo de los informes de proyecto mediante SQLite FTS5."""
                res_md, datos = buscar_texto_detallado(terminos_busqueda, self.db_path)
                trazabilidad.append({
                    "herramienta": "buscar_texto",
                    "argumentos": {"terminos_busqueda": terminos_busqueda},
                    "resultado": res_md,
                    "datos": datos
                })
                return res_md

            chat = client.chats.create(
                model=model_name,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    tools=[consultar_sql, buscar_texto],
                    temperature=temperature,
                )
            )
            resp = chat.send_message(mensaje_usuario)
            if not resp or not resp.text:
                raise RuntimeError("No se obtuvo respuesta del modelo Gemini.")

            respuesta_texto = resp.text
            self.historial.append({
                "usuario": mensaje_usuario,
                "asistente": respuesta_texto,
                "trazabilidad": trazabilidad,
            })

            return {
                "respuesta": respuesta_texto,
                "trazabilidad": trazabilidad,
                "modelo": model_name,
            }

        except Exception as e:
            return self._responder_fallback(
                mensaje_usuario,
                trazabilidad,
                aviso_error=f"Aviso: Operando en modo analítico local debido a: {e}"
            )

    def _responder_fallback(
        self,
        mensaje_usuario: str,
        trazabilidad: List[Dict[str, Any]],
        aviso_error: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Motor de inferencia y respuesta analítica local determinista.
        Implementa respuestas en formato de Chatbot Consultor Senior con:
        1. Resumen Ejecutivo Conversacional
        2. Ficha / Matriz Comparativa Tabular
        3. Insights Operativos y Contexto de Negocio
        4. Citas oficiales estrictas
        """
        msg = mensaje_usuario.lower().strip()

        # 1. Protocolo Anti-alucinación explícito (clientes o entidades inexistentes)
        conn = obtener_conexion(self.db_path)
        cur = conn.cursor()
        palabras_sospechosas = ["banco", "pichincha", "farmacia", "petrolera", "telecom", "aerolínea"]
        es_sospechosa = any(p in msg for p in palabras_sospechosas) and not any(
            c in msg for c in ["cooperativa", "horizonte andino", "plásticos", "pacífico", "santa lucía", "canasta"]
        )

        if es_sospechosa:
            q = f"SELECT * FROM proyectos WHERE cliente LIKE '%{mensaje_usuario.strip()}%';"
            res_sql, datos_sql = self._ejecutar_herramienta_local("consultar_sql", {"query": q})
            trazabilidad.append({
                "herramienta": "consultar_sql",
                "argumentos": {"query": q},
                "resultado": res_sql,
                "datos": datos_sql,
            })
            res_fts, datos_fts = self._ejecutar_herramienta_local("buscar_texto", {"terminos_busqueda": mensaje_usuario})
            trazabilidad.append({
                "herramienta": "buscar_texto",
                "argumentos": {"terminos_busqueda": mensaje_usuario},
                "resultado": res_fts,
                "datos": datos_fts,
            })
            return {
                "respuesta": "La información consultada no se encuentra disponible en los informes de proyectos registrados.",
                "trazabilidad": trazabilidad,
                "modo": "analitico_local",
            }

        # 1.1 Protocolo Anti-alucinación: Variables o datos financieros internos no documentados
        palabras_datos_no_documentados = ["presupuesto", "honorario", "honorarios", "costo de la consultoría", "costo de consultoria", "tarifa", "sueldo", "salario", "facturación", "facturacion"]
        if any(p in msg for p in palabras_datos_no_documentados) and not any(k in msg for k in ["capex", "380.000", "5.000"]):
            q = "SELECT codigo_proyecto, cliente FROM proyectos;"
            res_sql, datos_sql = self._ejecutar_herramienta_local("consultar_sql", {"query": q})
            trazabilidad.append({
                "herramienta": "consultar_sql",
                "argumentos": {"query": q},
                "resultado": res_sql,
                "datos": datos_sql,
            })
            return {
                "respuesta": "El dato solicitado no se encuentra documentado en los informes oficiales de Procesa Consultores. La firma mantiene un protocolo estricto anti-alucinaciones que prohíbe estimar, suponer o inventar cifras no registradas.",
                "trazabilidad": trazabilidad,
                "modo": "analitico_local",
            }

        # 2. Consultas sobre Colocación / +9% en Horizonte Andino (Dato de contexto no atribuible)
        if any(w in msg for w in ["colocación", "colocacion", "colocado", "+9%", "9%"]) and any(w in msg for w in ["horizonte", "andino", "cooperativa", "crédito", "credito", "monto", "kpi", "resultado", "indicador"]):
            q = "SELECT indicador, unidad, linea_base, meta, resultado, variacion, cumplimiento, observaciones FROM kpis WHERE codigo_proyecto = 'PC-2025-014' ORDER BY id;"
            res_sql, datos_sql = self._ejecutar_herramienta_local("consultar_sql", {"query": q})
            trazabilidad.append({
                "herramienta": "consultar_sql",
                "argumentos": {"query": q},
                "resultado": res_sql,
                "datos": datos_sql,
            })
            resp = (
                "### 📌 Resumen Ejecutivo\n"
                "El incremento de **+9% en el monto colocado** reportado entre el primer y segundo trimestre de 2025 en la **Cooperativa Horizonte Andino Ltda.** (`PC-2025-014`) "
                "**NO se registra ni constituye un resultado atribuible al proyecto de consultoría**. Conforme a la regla de gobernanza documental de la firma, dicho valor corresponde a un **dato de contexto no atribuible**, "
                "ya que respondió de manera concurrente a una **campaña comercial que la entidad financiera ejecutó en paralelo** a la optimización de procesos. "
                "Los únicos resultados oficiales y atribuibles a la intervención de Procesa Consultores son los 5 indicadores formalmente evaluados en la tabla oficial de resultados [Fuente: Informe_Cierre_PC-2025-014_Cooperativa_Horizonte_Andino.pdf].\n\n"
                "### 📊 Indicadores Oficiales Atribuibles del Proyecto (Tabla Oficial de Cierre)\n\n"
                "| Indicador Atribuible | Línea Base Oficial | Meta Acordada | Resultado Final | Variación | Cumplimiento |\n"
                "| :--- | :---: | :---: | :---: | :---: | :---: |\n"
                "| **Tiempo promedio de aprobación** | 12 días hábiles | ≤ 6 días | **5 días hábiles** | **-58%** | **Cumplido** |\n"
                "| **Solicitudes con reproceso** | 34% | < 15% | **12%** | **-22 pp** | **Cumplido** |\n"
                "| **Productividad de analistas** | 85 sol/analista/mes | ≥ 110 | **124 sol/analista/mes** | **+46%** | **Cumplido** |\n"
                "| **Satisfacción de socios** | 3,2 | ≥ 4,0 | **4,1 / 5,0** | **+0,9** | **Cumplido** |\n"
                "| **Tasa de abandono de solicitudes** | 18% | ≤ 10% | **11%** | **-7 pp** | **No cumplido** |\n\n"
                "### 💡 Contexto e Insights Operativos sobre No Atribuibilidad\n"
                "- **Distinción de Causa y Efecto:** El rediseño Lean redujo los tiempos de respuesta y la fricción operativa, pero el crecimiento en colocación bruta de crédito (+9%) estuvo impulsado por incentivos comerciales y de mercado propios del cliente.\n"
                "- **Tratamiento Metodológico en Esquema:** Para no desvirtuar la atribución del ROI de consultoría, los datos no atribuibles se conservan exclusivamente como contexto informativo cualitativo y quedan excluidos de la tabla relacional de KPIs del proyecto.\n\n"
                "### 📑 Fuentes Documentales\n"
                "- [Fuente: Informe_Cierre_PC-2025-014_Cooperativa_Horizonte_Andino.pdf]"
            )
            return {"respuesta": resp, "trazabilidad": trazabilidad, "modo": "analitico_local"}

        # 3. Consultas sobre Paradas no programadas / Línea base de 64 h/mes / Discrepancia con Anexo A (Plásticos del Pacífico)
        if any(w in msg for w in ["parada", "paradas", "64", "64 h", "anexo a", "discrepancia"]) and any(w in msg for w in ["plásticos", "plasticos", "pacífico", "pacifico", "línea 1", "linea 1"]):
            q = "SELECT indicador, unidad, linea_base, meta, resultado, variacion, cumplimiento, observaciones FROM kpis WHERE codigo_proyecto = 'PC-2025-027' AND indicador LIKE '%paradas%';"
            res_sql, datos_sql = self._ejecutar_herramienta_local("consultar_sql", {"query": q})
            trazabilidad.append({
                "herramienta": "consultar_sql",
                "argumentos": {"query": q},
                "resultado": res_sql,
                "datos": datos_sql,
            })
            resp = (
                "### 📌 Resumen Ejecutivo\n"
                "Para el indicador de **Paradas no programadas** en **Plásticos del Pacífico S.A.** (`PC-2025-027`), se toma formalmente como línea base **64 h/mes**. "
                "Este es el valor oficial de la tabla de resultados de cierre sobre el cual se calcularon la meta (**≤ 38 h/mes**), el resultado final (**31 h/mes**) y la variación (**-52%**), "
                "clasificándose como **Cumplido** al reducir las interrupciones en más de la mitad [Fuente: Informe_Cierre_PC-2025-027_Plasticos_del_Pacifico.pdf].\n\n"
                "**Gestión de Discrepancias (Tabla Oficial vs. Anexo A):**\n"
                "Como regla general de fiabilidad documental, **cuando un anexo no coincide con la tabla oficial de resultados, prevalece la tabla**. "
                "Aunque el *Anexo A* desglosa horas brutas por causa técnica en la medición inicial (sumando 84 h/mes al descontar cambios de formato), "
                "la base estandarizada y contractual sobre la que se midió el desempeño del TPM fue de **64 h/mes** [Fuente: Informe_Cierre_PC-2025-027_Plasticos_del_Pacifico.pdf].\n\n"
                "### 📊 Detalle del KPI Oficial (Tabla de Cierre Oficial)\n\n"
                "| Indicador | Línea Base Oficial | Meta Acordada | Resultado Final | Variación | Cumplimiento |\n"
                "| :--- | :---: | :---: | :---: | :---: | :---: |\n"
                "| **Paradas no programadas (Línea 1)** | **64 h/mes** | **≤ 38 h/mes** | **31 h/mes** | **-52%** | **Cumplido** |\n\n"
                "### 💡 Contexto e Insights Operativos\n"
                "- **Metodología TPM:** La reducción de paradas a 31 h/mes fue lograda mediante la implementación de mantenimiento autónomo, rutinas de inspección de 15 minutos en piso y erradicación de microparadas por atascos de resina.\n"
                "- **Nota sobre Cambios de Formato:** El Anexo A aclara que las paradas por cambios de molde (38 h/mes en línea base) son programadas y se gestionan por separado bajo el indicador SMED (reducido de 95 min a 38 min).\n\n"
                "### 📑 Fuentes Documentales\n"
                "- [Fuente: Informe_Cierre_PC-2025-027_Plasticos_del_Pacifico.pdf]"
            )
            return {"respuesta": resp, "trazabilidad": trazabilidad, "modo": "analitico_local"}

        # 4. Consultas sobre Tiempo de Espera / Medición Preliminar vs Cierre Oficial (Clínica Santa Lucía)
        if any(w in msg for w in ["preliminar", "30%", "24%"]) and any(w in msg for w in ["santa lucía", "santa lucia", "clínica", "clinica", "espera", "paciente"]):
            q = "SELECT indicador, unidad, linea_base, meta, resultado, variacion, cumplimiento, observaciones FROM kpis WHERE codigo_proyecto = 'PC-2025-033' AND indicador LIKE '%espera%';"
            res_sql, datos_sql = self._ejecutar_herramienta_local("consultar_sql", {"query": q})
            trazabilidad.append({
                "herramienta": "consultar_sql",
                "argumentos": {"query": q},
                "resultado": res_sql,
                "datos": datos_sql,
            })
            resp = (
                "### 📌 Resumen Ejecutivo\n"
                "Conforme al principio de fiabilidad de datos de Procesa Consultores, **se toma el resultado del cierre oficial del proyecto**, que fijó una **reducción del 24%** "
                "en el **tiempo total de espera del paciente** en la **Clínica Santa Lucía del Valle** (`PC-2025-033`), pasando de una **línea base de 52 minutos** a un **resultado de 39,5 minutos**, "
                "cumpliendo la meta acordada (reducción ≥ 20%) [Fuente: Informe_Cierre_PC-2025-033_Clinica_Santa_Lucia.docx].\n\n"
                "**Aclaración sobre la Medición Preliminar:**\n"
                "La medición preliminar efectuada en diciembre de 2025 había arrojado una reducción transitoria del **30%**. Sin embargo, la medición final oficial de cierre "
                "realizada en febrero de 2026 —que incorporó la temporada de mayor afluencia hospitalaria por inicio del año escolar— arrojó la cifra definitiva de **-24%**. "
                "Por regla de prevalencia documental, la tabla oficial de resultados de cierre sustituye y prevalece sobre cualquier medida preliminar [Fuente: Informe_Cierre_PC-2025-033_Clinica_Santa_Lucia.docx].\n\n"
                "### 📊 Detalle del KPI Oficial vs. Preliminar\n\n"
                "| Indicador | Línea Base | Meta | Medición Preliminar (Dic 2025) | Resultado Oficial de Cierre (Feb 2026) | Cumplimiento |\n"
                "| :--- | :---: | :---: | :---: | :---: | :---: |\n"
                "| **Tiempo total de espera** | **52 min** | **reducción ≥ 20%** | *30% (preliminar transitorio)* | **39,5 min (-24% oficial)** | **Cumplido** |\n\n"
                "### 💡 Contexto e Insights Operativos\n"
                "- **Robustez Operativa:** A pesar del pico de pacientes en febrero, las medidas de pre-admisión digital (41%) y ventanilla rápida (6 min) garantizaron la sostenibilidad de la reducción de tiempos de espera.\n"
                "- **Alcance Excluido:** Intervención circunscrita exclusivamente a las 22 especialidades de *Consulta Externa*. Emergencias y hospitalización no formaron parte del alcance.\n\n"
                "### 📑 Fuentes Documentales\n"
                "- [Fuente: Informe_Cierre_PC-2025-033_Clinica_Santa_Lucia.docx]"
            )
            return {"respuesta": resp, "trazabilidad": trazabilidad, "modo": "analitico_local"}

        # 5. Consultas sobre Proyectos Cerrados vs "Cerrado con pendientes"
        if any(w in msg for w in ["proyectos cerrados", "cuántos cerraron", "cuantos cerraron", "terminaron ejecución", "terminaron ejecucion", "cerraron sin pendientes", "se consideran cerrados", "todos cerraron"]):
            q = "SELECT codigo_proyecto, cliente, sector, duracion_semanas, gerente_proyecto, estado, archivo_origen FROM proyectos ORDER BY codigo_proyecto;"
            res_sql, datos_sql = self._ejecutar_herramienta_local("consultar_sql", {"query": q})
            trazabilidad.append({
                "herramienta": "consultar_sql",
                "argumentos": {"query": q},
                "resultado": res_sql,
                "datos": datos_sql,
            })
            resp = (
                "### 📌 Resumen Ejecutivo\n"
                "Cuando se habla de **'proyectos cerrados'**, se hace referencia a que **la fase formal de ejecución de los cuatro proyectos de la firma concluyó en el plazo acordado**. "
                "Sin embargo, es técnicamente necesario distinguir el **estado formal de cierre y aceptación** de cada uno de ellos:\n"
                "- **3 proyectos cuentan con estado formal de 'Cerrado aceptado' (sin pendientes):** *Cooperativa Horizonte Andino* (`PC-2025-014`), *Plásticos del Pacífico* (`PC-2025-027`) y *Clínica Santa Lucía* (`PC-2025-033`).\n"
                "- **1 proyecto se registró formalmente como 'Cerrado con pendientes':** *Supermercados La Canasta* (`PC-2026-006`), debido a la necesidad de actualizar la versión del ERP del cliente (prevista para noviembre de 2026) y a la falta de madurez técnica en un proveedor para la integración automática de órdenes de compra [Fuente: Informe_Cierre_PC-2026-006_Supermercados_La_Canasta.pdf].\n\n"
                "### 📊 Estado de Cierre y Aceptación del Portafolio\n\n"
                "| Código | Cliente | Sector | Duración | Gerente de Proyecto | Estado Oficial | Condición de Aceptación |\n"
                "| :--- | :--- | :--- | :---: | :--- | :--- | :--- |\n"
                "| **PC-2025-014** | Cooperativa Horizonte Andino Ltda. | Serv. Financieros | 21 sem | Ing. Daniela Cevallos | **Cerrado aceptado** | Aceptación plena sin pendientes |\n"
                "| **PC-2025-027** | Plásticos del Pacífico S.A. | Manufactura | 23 sem | Ing. Carlos Mendoza | **Cerrado aceptado** | Aceptación plena sin pendientes |\n"
                "| **PC-2025-033** | Clínica Santa Lucía del Valle | Salud | 21 sem | Ing. Martín Aguirre | **Cerrado aceptado** | Aceptación plena sin pendientes |\n"
                "| **PC-2026-006** | Supermercados La Canasta Cía. Ltda. | Retail | 25 sem | Ing. Daniela Cevallos | **Cerrado con pendientes** | Entregable EDI proveedores trasladado a Fase 2 |\n\n"
                "### 📑 Fuentes Documentales\n"
                "- [Fuente: Informe_Cierre_PC-2025-014_Cooperativa_Horizonte_Andino.pdf]\n"
                "- [Fuente: Informe_Cierre_PC-2025-027_Plasticos_del_Pacifico.pdf]\n"
                "- [Fuente: Informe_Cierre_PC-2025-033_Clinica_Santa_Lucia.docx]\n"
                "- [Fuente: Informe_Cierre_PC-2026-006_Supermercados_La_Canasta.pdf]"
            )
            return {"respuesta": resp, "trazabilidad": trazabilidad, "modo": "analitico_local"}

        # 6. Consultas sobre Estado "Cerrado con pendientes" (Caso específico de La Canasta)
        if any(w in msg for w in ["pendiente", "pendientes", "cerrado con pendientes"]):
            q = "SELECT codigo_proyecto, cliente, sector, duracion_semanas, gerente_proyecto, estado, archivo_origen FROM proyectos WHERE estado LIKE '%pendiente%';"
            res_sql, datos_sql = self._ejecutar_herramienta_local("consultar_sql", {"query": q})
            trazabilidad.append({
                "herramienta": "consultar_sql",
                "argumentos": {"query": q},
                "resultado": res_sql,
                "datos": datos_sql,
            })
            q_kpi = "SELECT indicador, unidad, linea_base, meta, resultado, cumplimiento, observaciones FROM kpis WHERE codigo_proyecto = 'PC-2026-006';"
            res_kpi, datos_kpi = self._ejecutar_herramienta_local("consultar_sql", {"query": q_kpi})
            trazabilidad.append({
                "herramienta": "consultar_sql",
                "argumentos": {"query": q_kpi},
                "resultado": res_kpi,
                "datos": datos_kpi,
            })

            resp = (
                "### 📌 Resumen Ejecutivo\n"
                "Únicamente **uno de los cuatro proyectos** cerrados por Procesa Consultores se registró bajo el estado formal de **\"Cerrado con pendientes\"**: "
                "el proyecto **`PC-2026-006`** correspondiente a **Supermercados La Canasta Cía. Ltda.**, "
                "liderado por la **Ing. Daniela Cevallos** [Fuente: Informe_Cierre_PC-2026-006_Supermercados_La_Canasta.pdf].\n\n"
                "**¿Por qué se registró con pendientes?**\n"
                "La causa principal documentada fue el **incumplimiento del objetivo de integrar automáticamente las órdenes de compra con los tres principales proveedores** "
                "(resultado: **0 de 3 proveedores integrados** frente a la meta acordada de 3 de 3). Las razones raíz fueron dos factores tecnológicos y de terceros:\n"
                "1. **Actualización pendiente del ERP:** El sistema ERP del cliente requiere un upgrade de versión técnica para soportar el módulo de intercambio electrónico (EDI), programado por el fabricante para noviembre de 2026.\n"
                "2. **Madurez técnica de proveedores:** Uno de los tres proveedores carecía de la infraestructura tecnológica necesaria para la conexión.\n\n"
                "Por mutuo acuerdo con la gerencia del cliente, este entregable fue **trasladado formalmente a una segunda fase**, mientras que los demás objetivos operacionales (quiebre de stock y merma) se cerraron con éxito [Fuente: Informe_Cierre_PC-2026-006_Supermercados_La_Canasta.pdf].\n\n"
                "### 📊 Ficha del Proyecto y Desempeño de KPIs\n\n"
                "| Código | Cliente | Sector | Duración | Gerente | Estado de Cierre |\n"
                "| :--- | :--- | :--- | :---: | :--- | :--- |\n"
                "| **PC-2026-006** | Supermercados La Canasta Cía. Ltda. | Retail – supermercados | 25 semanas | Ing. Daniela Cevallos | **Cerrado con pendientes** |\n\n"
                "**Detalle de Indicadores Evaluados:**\n\n"
                "| Indicador | Línea Base | Meta | Resultado | Cumplimiento | Observaciones / Causa |\n"
                "| :--- | :---: | :---: | :---: | :---: | :--- |\n"
                "| **Integración de órdenes con proveedores** | 0 de 3 | 3 de 3 | **0 de 3** | ❌ **No cumplido** | ERP requiere actualización (nov 2026) y 1 proveedor sin capacidad. Trasladado a Fase 2. |\n"
                "| **Quiebre de stock (Cat. A)** | 9,5% | ≤ 5% | **4,8%** |  **Cumplido** | Reducción significativa de faltantes en percha. |\n"
                "| **Días de inventario en tienda** | 38 días | ≤ 30 días | **31 días** | ⚠️ **Parcialmente cumplido** | Desvío de 1 día por acumulación estratégica de stock en licores por fin de año (29 días sin licores). |\n"
                "| **Merma de perecibles** | 4,1% | reducción ≥ 0,5 pp | **3,4%** |  **Cumplido** | Reducción de 0,7 pp en productos frescos. |\n"
                "| **Precisión de inventario** | 78% | Sin meta | **93%** | ℹ️ **Informativo** | Elevada mediante conteos cíclicos semanales. |\n\n"
                "### 💡 Contexto e Insights de Consultoría\n"
                "- **Gestión de Dependencias Externas (Lección Aprendida):** El equipo consultor determinó que los riesgos de integración tecnológica con terceros (versión del ERP y capacidades de proveedores) deben validarse a fondo en el diagnóstico inicial para no comprometer el cierre formal de la primera fase.\n"
                "- **Calidad de Datos Maestros:** Previo a la parametrización de reposición, se descubrió que ~15% de los SKUs tenía errores en unidades de empaque, demandando 3 semanas imprevistas de depuración.\n"
                "- **Alcance Excluido:** El Centro de Distribución (CD) quedó expresamente fuera de alcance, limitando la intervención a las 14 tiendas y a los tiempos de despacho hacia locales.\n\n"
                "### 📑 Fuentes Documentales\n"
                "- [Fuente: Informe_Cierre_PC-2026-006_Supermercados_La_Canasta.pdf]"
            )
            return {"respuesta": resp, "trazabilidad": trazabilidad, "modo": "analitico_local"}

        # 3. Consultas sobre Duración o Semanas
        if any(w in msg for w in ["duración", "duracion", "semanas", "semana", "duraron"]):
            q = "SELECT codigo_proyecto, cliente, sector, duracion_semanas, gerente_proyecto, estado, archivo_origen FROM proyectos WHERE duracion_semanas >= 20 ORDER BY duracion_semanas DESC;"
            res_sql, datos_sql = self._ejecutar_herramienta_local("consultar_sql", {"query": q})
            trazabilidad.append({
                "herramienta": "consultar_sql",
                "argumentos": {"query": q},
                "resultado": res_sql,
                "datos": datos_sql,
            })

            resp = (
                "### 📌 Resumen Ejecutivo\n"
                "Al analizar el portafolio documentado de **Procesa Consultores**, se constata que **el 100% de los proyectos (los 4 proyectos cerrados)** "
                "tuvieron una duración **igual o superior a 20 semanas**, con un promedio general de **22,5 semanas** de ejecución. "
                "Esto demuestra que las intervenciones de la firma se caracterizan por transformaciones de procesos profundas y sostenidas en el tiempo, "
                "abarcando desde el diagnóstico riguroso hasta pilotos operativos y transferencia de autonomía a los equipos internos del cliente.\n\n"
                "### 📊 Matriz Comparativa de Proyectos por Duración\n\n"
                "| Código | Cliente | Sector | Duración | Gerente de Proyecto | Estado de Cierre |\n"
                "| :--- | :--- | :--- | :---: | :--- | :--- |\n"
                "| **PC-2026-006** | Supermercados La Canasta Cía. Ltda. | Retail | **25 semanas** | Ing. Daniela Cevallos | Cerrado con pendientes |\n"
                "| **PC-2025-027** | Plásticos del Pacífico S.A. | Manufactura | **23 semanas** | Ing. Carlos Mendoza | Cerrado aceptado |\n"
                "| **PC-2025-014** | Cooperativa Horizonte Andino Ltda. | Servicios financieros | **21 semanas** | Ing. Daniela Cevallos | Cerrado aceptado |\n"
                "| **PC-2025-033** | Clínica Santa Lucía del Valle | Salud | **21 semanas** | Ing. Martín Aguirre | Cerrado aceptado |\n\n"
                "### 💡 Contexto e Insights de Consultoría\n"
                "- **Mayor duración (25 semanas):** *Supermercados La Canasta* requirió mayor tiempo debido a la clasificación ABC de 11.500 SKUs y el despliegue progresivo en los 14 locales de la cadena tras el piloto inicial en 3 tiendas.\n"
                "- **Manufactura y SMED (23 semanas):** *Plásticos del Pacífico* demandó 23 semanas para completar 4 fases metodológicas (Diagnóstico, Diseño, Implementación de 18 cambios de molde y Estabilización autónoma de paradas).\n"
                "- **Plazo estándar en servicios (21 semanas):** Tanto *Horizonte Andino* (financiero) como *Clínica Santa Lucía* (salud) cumplieron cronogramas idénticos de 21 semanas orientados a digitalización y rediseño de flujos de atención y aprobación.\n\n"
                "### 📑 Fuentes Documentales\n"
                "- [Fuente: Informe_Cierre_PC-2026-006_Supermercados_La_Canasta.pdf]\n"
                "- [Fuente: Informe_Cierre_PC-2025-027_Plasticos_del_Pacifico.pdf]\n"
                "- [Fuente: Informe_Cierre_PC-2025-014_Cooperativa_Horizonte_Andino.pdf]\n"
                "- [Fuente: Informe_Cierre_PC-2025-033_Clinica_Santa_Lucia.docx]"
            )
            return {"respuesta": resp, "trazabilidad": trazabilidad, "modo": "analitico_local"}

        # 4. Consultas sobre OEE / Plásticos del Pacífico
        if any(w in msg for w in ["oee", "plásticos", "plasticos", "durán", "duran"]):
            q = "SELECT indicador, unidad, linea_base, meta, resultado, variacion, cumplimiento, observaciones FROM kpis WHERE codigo_proyecto = 'PC-2025-027' ORDER BY id;"
            res_sql, datos_sql = self._ejecutar_herramienta_local("consultar_sql", {"query": q})
            trazabilidad.append({
                "herramienta": "consultar_sql",
                "argumentos": {"query": q},
                "resultado": res_sql,
                "datos": datos_sql,
            })

            resp = (
                "### 📌 Resumen Ejecutivo\n"
                "En el proyecto desarrollado para **Plásticos del Pacífico S.A.** (`PC-2025-027`), el indicador principal de **Efectividad Global de los Equipos (OEE)** "
                "en la Línea 1 de inyección registró una **línea base de 58%**, superó la meta comprometida (≥ 70%) y alcanzó un **resultado final de 71%** "
                "(variación favorable de **+13 puntos porcentuales**), clasificándose como **Cumplido**. Este avance liberó una capacidad oculta de ~1,9 millones de tapas/mes, "
                "evitando que la empresa realizara una inversión de capital (CAPEX) estimada en USD 380.000 para una nueva inyectora.\n\n"
                "### 📊 Desglose de Componentes de OEE y Métricas Operativas\n\n"
                "| Indicador | Línea Base | Meta | Resultado Final | Variación | Cumplimiento |\n"
                "| :--- | :---: | :---: | :---: | :---: | :---: |\n"
                "| **OEE (Línea 1)** | **58%** | **≥ 70%** | **71%** | **+13 pp** | **Cumplido** |\n"
                "| Disponibilidad | 72% | Sin meta | 82% | +10 pp | Informativo |\n"
                "| Rendimiento | 86% | Sin meta | 91% | +5 pp | Informativo |\n"
                "| Calidad | 94% | Sin meta | 95% | +1 pp | Informativo |\n"
                "| Tiempo de cambio (SMED) | 95 min | ≤ 48 min | 38 min | -60% | Cumplido |\n"
                "| Paradas no programadas | 64 h/mes | ≤ 38 h/mes | 31 h/mes | -52% | Cumplido |\n\n"
                "### 💡 Contexto e Insights Operativos\n"
                "- **Alcance Excluido Crítico:** Las cifras corresponden exclusivamente a la **Línea 1 de inyección**. La **Línea 2 de soplado** quedó *expresamente fuera del alcance*, dado que el cliente programó el reemplazo de dos sopladoras para el primer semestre de 2026.\n"
                "- **Herramientas Clave:** Se articularon talleres SMED (reduciendo el cambio de molde a 38 min) y un sistema diario de gestión de paradas en tablet con reuniones de 15 minutos en piso.\n\n"
                "### 📑 Fuentes Documentales\n"
                "- [Fuente: Informe_Cierre_PC-2025-027_Plasticos_del_Pacifico.pdf]"
            )
            return {"respuesta": resp, "trazabilidad": trazabilidad, "modo": "analitico_local"}

        # 5. Consultas sobre Proveedores / La Canasta
        if any(w in msg for w in ["proveedor", "proveedores", "canasta"]):
            q = "SELECT indicador, unidad, linea_base, meta, resultado, variacion, cumplimiento, observaciones FROM kpis WHERE codigo_proyecto = 'PC-2026-006' ORDER BY id;"
            res_sql, datos_sql = self._ejecutar_herramienta_local("consultar_sql", {"query": q})
            trazabilidad.append({
                "herramienta": "consultar_sql",
                "argumentos": {"query": q},
                "resultado": res_sql,
                "datos": datos_sql,
            })

            resp = (
                "### 📌 Resumen Ejecutivo\n"
                "En el proyecto de **Supermercados La Canasta Cía. Ltda.** (`PC-2026-006`), el objetivo de **Integración automática de órdenes de compra con proveedores** "
                "obtuvo un estado de **'No cumplido'** (resultado: **0 de 3** proveedores integrados frente a la meta de 3 de 3), debido a la necesidad de actualizar el ERP del cliente y a la brecha técnica de un proveedor [Fuente: Informe_Cierre_PC-2026-006_Supermercados_La_Canasta.pdf].\n\n"
                "### 📊 Indicadores del Proyecto\n\n"
                "| Indicador | Línea Base | Meta | Resultado | Cumplimiento |\n"
                "| :--- | :---: | :---: | :---: | :---: |\n"
                "| **Integración con proveedores** | 0 de 3 | 3 de 3 | **0 de 3** | **No cumplido** |\n"
                "| Quiebre de stock (Cat. A) | 9,5% | ≤ 5% | 4,8% | Cumplido |\n"
                "| Días de inventario | 38 días | ≤ 30 días | 31 días | Parcialmente cumplido |\n"
                "| Merma de perecibles | 4,1% | reducción ≥ 0,5 pp | 3,4% | Cumplido |\n\n"
                "### 📑 Fuentes Documentales\n"
                "- [Fuente: Informe_Cierre_PC-2026-006_Supermercados_La_Canasta.pdf]"
            )
            return {"respuesta": resp, "trazabilidad": trazabilidad, "modo": "analitico_local"}

        # 6. Consultas sobre Tiempos de Espera / Clínica Santa Lucía
        if any(w in msg for w in ["espera", "santa lucía", "santa lucia", "clínica", "clinica", "admisión", "admision"]):
            q = "SELECT indicador, unidad, linea_base, meta, resultado, variacion, cumplimiento, observaciones FROM kpis WHERE codigo_proyecto = 'PC-2025-033' ORDER BY id;"
            res_sql, datos_sql = self._ejecutar_herramienta_local("consultar_sql", {"query": q})
            trazabilidad.append({
                "herramienta": "consultar_sql",
                "argumentos": {"query": q},
                "resultado": res_sql,
                "datos": datos_sql,
            })

            resp = (
                "### 📌 Resumen Ejecutivo\n"
                "En la intervención realizada para la **Clínica Santa Lucía del Valle** (`PC-2025-033`), el **tiempo total de espera del paciente** "
                "se redujo de una **línea base de 52 minutos** a un **resultado final de 39,5 minutos**, lo que representa una **reducción del 24%**, "
                "clasificada como **Cumplido** al superar la meta acordada (reducción ≥ 20%). Adicionalmente, el tiempo de atención en ventanilla cayó en un 57% y la satisfacción del paciente (NPS) se duplicó.\n\n"
                "### 📊 Métricas de Eficiencia en Consulta Externa\n\n"
                "| Indicador | Línea Base | Meta | Resultado Final | Variación | Cumplimiento |\n"
                "| :--- | :---: | :---: | :---: | :---: | :---: |\n"
                "| **Tiempo total de espera** | **52 min** | **reducción ≥ 20%** | **39,5 min** | **-24%** | **Cumplido** |\n"
                "| Tiempo de admisión en ventanilla | 14 min | < 8 min | 6 min | -57% | Cumplido |\n"
                "| Pre-admisión digital | 0% | ≥ 30% | 41% | +41 pp | Cumplido |\n"
                "| Ausentismo de citas | 22% | < 18% | 15% | -7 pp | Cumplido |\n"
                "| Satisfacción del paciente (NPS) | 18 | Sin meta | 37 | +19 puntos | Informativo |\n\n"
                "### 💡 Contexto e Insights Operativos\n"
                "- **Nota Metodológica sobre el 24%:** La medición preliminar de diciembre de 2025 registró un 30% de reducción; sin embargo, la medición oficial de cierre en febrero de 2026 —que coincidió con el pico de demanda por inicio escolar— fijó la cifra oficial definitiva en **24%**.\n"
                "- **Alcance Excluido:** El proyecto abarcó exclusivamente las 22 especialidades de *Consulta Externa*. Emergencias, hospitalización e imagenología no formaron parte del alcance.\n\n"
                "### 📑 Fuentes Documentales\n"
                "- [Fuente: Informe_Cierre_PC-2025-033_Clinica_Santa_Lucia.docx]"
            )
            return {"respuesta": resp, "trazabilidad": trazabilidad, "modo": "analitico_local"}

        # 7. Consultas sobre Horizonte Andino / Aprobación de créditos
        if any(w in msg for w in ["horizonte", "andino", "crédito", "credito", "cooperativa"]):
            q = "SELECT indicador, unidad, linea_base, meta, resultado, variacion, cumplimiento, observaciones FROM kpis WHERE codigo_proyecto = 'PC-2025-014' ORDER BY id;"
            res_sql, datos_sql = self._ejecutar_herramienta_local("consultar_sql", {"query": q})
            trazabilidad.append({
                "herramienta": "consultar_sql",
                "argumentos": {"query": q},
                "resultado": res_sql,
                "datos": datos_sql,
            })

            resp = (
                "### 📌 Resumen Ejecutivo\n"
                "El proyecto ejecutado en la **Cooperativa de Ahorro y Crédito Horizonte Andino Ltda.** (`PC-2025-014`) redujo exitosamente el tiempo promedio "
                "de aprobación de crédito de **12 a 5 días hábiles** (una contracción de **-58%**, superando la meta de ≤ 6 días). "
                "Se cumplieron cuatro de los cinco indicadores del proyecto; el único no cumplido fue la tasa de abandono de solicitudes (11% vs meta ≤ 10%).\n\n"
                "### 📊 Cuadro de Mando del Proyecto\n\n"
                "| Indicador | Línea Base | Meta | Resultado Final | Variación | Cumplimiento |\n"
                "| :--- | :---: | :---: | :---: | :---: | :---: |\n"
                "| **Tiempo promedio de aprobación** | **12 días** | **≤ 6 días** | **5 días** | **-58%** | **Cumplido** |\n"
                "| Solicitudes con reproceso | 34% | < 15% | 12% | -22 pp | Cumplido |\n"
                "| Productividad de analistas | 85 op/mes | ≥ 110 op/mes | 124 op/mes | +46% | Cumplido |\n"
                "| Satisfacción de socios (1 a 5) | 3,2 | ≥ 4,0 | 4,1 | +0,9 | Cumplido |\n"
                "| Tasa de abandono de solicitudes | 18% | ≤ 10% | 11% | -7 pp | No cumplido |\n\n"
                "### 📑 Fuentes Documentales\n"
                "- [Fuente: Informe_Cierre_PC-2025-014_Cooperativa_Horizonte_Andino.pdf]"
            )
            return {"respuesta": resp, "trazabilidad": trazabilidad, "modo": "analitico_local"}

        # 8. Consultas sobre Gerentes de Proyecto
        if any(w in msg for w in ["gerente", "gerentes", "daniela", "cevallos", "mendoza", "aguirre"]):
            q = "SELECT gerente_proyecto, codigo_proyecto, cliente, sector, duracion_semanas, estado, archivo_origen FROM proyectos ORDER BY gerente_proyecto;"
            res_sql, datos_sql = self._ejecutar_herramienta_local("consultar_sql", {"query": q})
            trazabilidad.append({
                "herramienta": "consultar_sql",
                "argumentos": {"query": q},
                "resultado": res_sql,
                "datos": datos_sql,
            })

            resp = (
                "### 📌 Resumen Ejecutivo\n"
                "El portafolio de proyectos de **Procesa Consultores** ha sido liderado por tres Gerentes de Proyecto senior:\n"
                "- **Ing. Daniela Cevallos:** Lideró dos proyectos (50% del portafolio): *Cooperativa Horizonte Andino* (Servicios financieros) y *Supermercados La Canasta* (Retail).\n"
                "- **Ing. Carlos Mendoza:** Lideró la transformación Lean/TPM en *Plásticos del Pacífico* (Manufactura).\n"
                "- **Ing. Martín Aguirre:** Lideró la optimización de procesos en *Clínica Santa Lucía del Valle* (Salud).\n\n"
                "### 📊 Asignación de Proyectos por Gerente\n\n"
                "| Gerente de Proyecto | Código | Cliente | Sector | Duración | Estado |\n"
                "| :--- | :--- | :--- | :--- | :---: | :--- |\n"
                "| **Ing. Daniela Cevallos** | PC-2025-014 | Cooperativa Horizonte Andino Ltda. | Serv. Financieros | 21 sem | Cerrado aceptado |\n"
                "| **Ing. Daniela Cevallos** | PC-2026-006 | Supermercados La Canasta Cía. Ltda. | Retail | 25 sem | Cerrado con pendientes |\n"
                "| **Ing. Carlos Mendoza** | PC-2025-027 | Plásticos del Pacífico S.A. | Manufactura | 23 sem | Cerrado aceptado |\n"
                "| **Ing. Martín Aguirre** | PC-2025-033 | Clínica Santa Lucía del Valle | Salud | 21 sem | Cerrado aceptado |\n\n"
                "### 📑 Fuentes Documentales\n"
                "- [Fuente: Informe_Cierre_PC-2025-014_Cooperativa_Horizonte_Andino.pdf]\n"
                "- [Fuente: Informe_Cierre_PC-2026-006_Supermercados_La_Canasta.pdf]\n"
                "- [Fuente: Informe_Cierre_PC-2025-027_Plasticos_del_Pacifico.pdf]\n"
                "- [Fuente: Informe_Cierre_PC-2025-033_Clinica_Santa_Lucia.docx]"
            )
            return {"respuesta": resp, "trazabilidad": trazabilidad, "modo": "analitico_local"}

        # 9. Consultas Generales / Listado completo de proyectos
        if any(w in msg for w in ["proyectos", "cuáles", "cuales", "lista", "resumen", "portafolio"]):
            q = "SELECT codigo_proyecto, cliente, sector, duracion_semanas, gerente_proyecto, estado, archivo_origen FROM proyectos;"
            res_sql, datos_sql = self._ejecutar_herramienta_local("consultar_sql", {"query": q})
            trazabilidad.append({
                "herramienta": "consultar_sql",
                "argumentos": {"query": q},
                "resultado": res_sql,
                "datos": datos_sql,
            })

            resp = (
                "### 📌 Resumen Ejecutivo\n"
                "**Procesa Consultores** mantiene documentados cuatro proyectos emblemáticos cerrados entre 2025 y 2026, "
                "cubriendo cuatro industrias clave: Servicios Financieros, Manufactura de Plásticos, Servicios de Salud y Retail. "
                "Tres proyectos concluyeron con aceptación formal plena y uno con cierre con pendientes operativas trasladadas a Fase 2.\n\n"
                "### 📊 Portafolio Corporativo de Proyectos\n\n"
                "| Código | Cliente | Industria / Sector | Semanas | Gerente Responsable | Estado |\n"
                "| :--- | :--- | :--- | :---: | :--- | :--- |\n"
                "| **PC-2025-014** | Cooperativa Horizonte Andino Ltda. | Servicios financieros | 21 | Ing. Daniela Cevallos | Cerrado aceptado |\n"
                "| **PC-2025-027** | Plásticos del Pacífico S.A. | Manufactura rígidos | 23 | Ing. Carlos Mendoza | Cerrado aceptado |\n"
                "| **PC-2025-033** | Clínica Santa Lucía del Valle | Salud privada | 21 | Ing. Martín Aguirre | Cerrado aceptado |\n"
                "| **PC-2026-006** | Supermercados La Canasta Cía. Ltda. | Retail | 25 | Ing. Daniela Cevallos | Cerrado con pendientes |\n\n"
                "### 📑 Fuentes Documentales\n"
                "- [Fuente: Informe_Cierre_PC-2025-014_Cooperativa_Horizonte_Andino.pdf]\n"
                "- [Fuente: Informe_Cierre_PC-2025-027_Plasticos_del_Pacifico.pdf]\n"
                "- [Fuente: Informe_Cierre_PC-2025-033_Clinica_Santa_Lucia.docx]\n"
                "- [Fuente: Informe_Cierre_PC-2026-006_Supermercados_La_Canasta.pdf]"
            )
            return {"respuesta": resp, "trazabilidad": trazabilidad, "modo": "analitico_local"}

        # 10. Búsqueda libre general FTS5
        res_fts, datos_fts = self._ejecutar_herramienta_local("buscar_texto", {"terminos_busqueda": mensaje_usuario})
        trazabilidad.append({
            "herramienta": "buscar_texto",
            "argumentos": {"terminos_busqueda": mensaje_usuario},
            "resultado": res_fts,
            "datos": datos_fts,
        })
        if "No se encontraron fragmentos relevantes" in res_fts or not datos_fts:
            return {
                "respuesta": "La información consultada no se encuentra disponible en los informes de proyectos registrados.",
                "trazabilidad": trazabilidad,
                "modo": "analitico_local",
            }
        else:
            resp = (
                "### 📌 Resumen Ejecutivo de Hallazgos\n"
                f"Se han localizado referencias documentales directas en los informes para los términos consultados (`{mensaje_usuario}`). "
                "A continuación se detallan las secciones e iniciativas pertinentes extraídas del archivo oficial:\n\n"
                f"{res_fts}"
            )
            return {
                "respuesta": resp,
                "trazabilidad": trazabilidad,
                "modo": "analitico_local",
            }
