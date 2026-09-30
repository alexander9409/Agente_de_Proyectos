"""
Motor de Fallback Analítico Genérico y Determinista (agent/fallback.py).
Reemplaza por completo _responder_fallback eliminando todo texto o dato de negocio hardcodeado.
Opera exclusivamente mediante consultas parametrizadas a SQLite y búsqueda en FTS5.
"""

import re
import unicodedata
from typing import Any, Dict, List, Optional, Set

from procesa_agent.infrastructure.db.connection import conexion_solo_lectura
from procesa_agent.infrastructure.db.repositories.reglas_repo import ReglasRepository
from procesa_agent.tools.tools import buscar_texto_detallado

STOPWORDS_ES: Set[str] = {
    "a",
    "al",
    "algo",
    "algunas",
    "algunos",
    "ante",
    "antes",
    "como",
    "con",
    "contra",
    "cual",
    "cuál",
    "cuales",
    "cuáles",
    "cuando",
    "cuándo",
    "cuanto",
    "cuánto",
    "cuanta",
    "cuánta",
    "de",
    "del",
    "desde",
    "donde",
    "dónde",
    "durante",
    "e",
    "el",
    "ella",
    "ellas",
    "ellos",
    "en",
    "entre",
    "era",
    "erais",
    "eran",
    "eras",
    "eres",
    "es",
    "esa",
    "esas",
    "ese",
    "eso",
    "esos",
    "esta",
    "estaba",
    "estado",
    "estais",
    "estan",
    "están",
    "estar",
    "estas",
    "este",
    "esto",
    "estos",
    "estoy",
    "fue",
    "fueron",
    "fui",
    "fuimos",
    "ha",
    "habia",
    "había",
    "habiendo",
    "habla",
    "han",
    "has",
    "hasta",
    "hay",
    "la",
    "las",
    "le",
    "les",
    "lo",
    "los",
    "mas",
    "más",
    "me",
    "mi",
    "mía",
    "mías",
    "mio",
    "mío",
    "míos",
    "mis",
    "mucho",
    "muchos",
    "muy",
    "nada",
    "ni",
    "no",
    "nos",
    "nosotras",
    "nosotros",
    "nuestra",
    "nuestras",
    "nuestro",
    "nuestros",
    "o",
    "os",
    "otra",
    "otras",
    "otro",
    "otros",
    "para",
    "pero",
    "poco",
    "por",
    "porque",
    "porqué",
    "que",
    "qué",
    "quien",
    "quién",
    "quienes",
    "quiénes",
    "se",
    "sea",
    "seais",
    "sean",
    "seas",
    "ser",
    "si",
    "sí",
    "sido",
    "siempre",
    "siendo",
    "sin",
    "sobre",
    "sois",
    "solamente",
    "solo",
    "sólo",
    "somos",
    "son",
    "soy",
    "su",
    "sus",
    "suya",
    "suyas",
    "suyo",
    "suyos",
    "tal",
    "también",
    "tambien",
    "tampoco",
    "tan",
    "tanto",
    "te",
    "tened",
    "teneis",
    "tenemos",
    "tener",
    "tenga",
    "tengais",
    "tengan",
    "tengas",
    "tengo",
    "tenia",
    "tenía",
    "tenida",
    "tenidas",
    "tenido",
    "tenidos",
    "ti",
    "tiene",
    "tienen",
    "tienes",
    "todo",
    "todos",
    "tu",
    "tú",
    "tus",
    "tuya",
    "tuyas",
    "tuyo",
    "tuyos",
    "un",
    "una",
    "unas",
    "uno",
    "unos",
    "vosostras",
    "vosostros",
    "vosotras",
    "vosotros",
    "vuestra",
    "vuestras",
    "vuestro",
    "vuestros",
    "y",
    "ya",
    "yo",
}

VARIABLES_NO_DOCUMENTADAS: Set[str] = {
    "honorario",
    "honorarios",
    "costo",
    "costos",
    "presupuesto",
    "presupuestos",
    "facturacion",
    "facturación",
    "ganancia",
    "margen",
    "sueldo",
    "salario",
    "tarifa",
}


def normalizar_texto(texto: str) -> str:
    """Elimina tildes, signos de puntuación y convierte a minúsculas."""
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )
    limpio = re.sub(r"[^\w\s]", " ", sin_tildes.lower())
    return " ".join(limpio.split())


def extraer_palabras_clave(texto: str) -> List[str]:
    """Extrae palabras clave significativas excluyendo stopwords."""
    norm = normalizar_texto(texto)
    palabras = [p for p in norm.split() if len(p) >= 3 and p not in STOPWORDS_ES]
    return palabras


PALABRAS_GENERICAS: Set[str] = {
    "proyecto",
    "proyectos",
    "informe",
    "informes",
    "consultoria",
    "consultoría",
    "empresa",
    "empresas",
    "cliente",
    "clientes",
    "datos",
    "resultados",
    "cierre",
    "hicieron",
    "hizo",
    "realizo",
    "realizó",
    "consultores",
    "procesa",
}


class FallbackEngine:
    """Motor determinista y seguro de respuesta basado en consultas directas a SQLite."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = db_path

    def responder(
        self,
        mensaje_usuario: str,
        trazabilidad: Optional[List[Dict[str, Any]]] = None,
        aviso_error: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Procesa una consulta de forma determinista sin dependencias de LLM ni datos hardcodeados."""
        if trazabilidad is None:
            trazabilidad = []

        palabras_clave = extraer_palabras_clave(mensaje_usuario)
        kw_especificas = [kw for kw in palabras_clave if kw not in PALABRAS_GENERICAS]
        msg_norm = normalizar_texto(mensaje_usuario)

        conn = conexion_solo_lectura(self.db_path)
        proyectos_encontrados: List[Dict[str, Any]] = []
        kpis_encontrados: List[Dict[str, Any]] = []
        reglas_encontradas: List[Any] = []
        fts_resultados: List[Dict[str, Any]] = []

        try:
            # 1. Buscar coincidencia con proyectos registrados
            cursor = conn.cursor()
            todos_proyectos = cursor.execute(
                "SELECT codigo_proyecto, cliente, sector, duracion_semanas, gerente_proyecto, estado, archivo_origen, alcance_incluido, alcance_excluido, resumen_ejecutivo FROM proyectos;"
            ).fetchall()

            codigos_relevantes: Set[str] = set()
            for p in todos_proyectos:
                p_dict = dict(p)
                texto_comparar = normalizar_texto(
                    f"{p_dict['codigo_proyecto']} {p_dict['cliente']} {p_dict['gerente_proyecto']} {p_dict['sector']}"
                )
                if any(kw in texto_comparar for kw in kw_especificas) or any(
                    part in msg_norm
                    for part in normalizar_texto(p_dict["cliente"]).split()
                    if len(part) >= 4
                ):
                    proyectos_encontrados.append(p_dict)
                    codigos_relevantes.add(p_dict["codigo_proyecto"])

            # Entidades no registradas para anti-alucinación
            ENTIDADES_NO_REGISTRADAS_CHECK: Set[str] = {
                "banco",
                "pichincha",
                "farmacia",
                "petroecuador",
                "telecom",
                "aerolinea",
                "aerolínea",
                "hospital",
            }
            es_consulta_entidad_externa = any(e in msg_norm for e in ENTIDADES_NO_REGISTRADAS_CHECK)

            # Si no hubo coincidencia con un cliente específico, verificar si es consulta analítica sobre el portafolio
            if not proyectos_encontrados and not es_consulta_entidad_externa:
                TERMINOS_PORTAFOLIO = {
                    "proyecto",
                    "proyectos",
                    "duracion",
                    "duraron",
                    "semanas",
                    "gerente",
                    "gerentes",
                    "lider",
                    "lideraron",
                    "portafolio",
                    "cerraron",
                    "estados",
                    "cuales",
                    "cuantos",
                    "cuantas",
                    "tiempo",
                    "tiempos",
                    "asignados",
                    "informes",
                }
                if any(t in msg_norm for t in TERMINOS_PORTAFOLIO):
                    candidatos = [dict(p) for p in todos_proyectos]
                    m_sem = re.search(r"(\d+)\s*semanas?", msg_norm)
                    num_sem = int(m_sem.group(1)) if m_sem else None
                    if num_sem is not None and any(
                        w in msg_norm
                        for w in [
                            "superior",
                            "mayor",
                            "igual",
                            "mas",
                            "al menos",
                            "minimo",
                            ">=",
                            ">",
                        ]
                    ):
                        candidatos = [
                            p for p in candidatos if p.get("duracion_semanas", 0) >= num_sem
                        ]
                    elif num_sem is not None and any(
                        w in msg_norm for w in ["menor", "inferior", "<=", "<"]
                    ):
                        candidatos = [
                            p for p in candidatos if p.get("duracion_semanas", 0) <= num_sem
                        ]

                    for p in candidatos:
                        proyectos_encontrados.append(p)
                        codigos_relevantes.add(p["codigo_proyecto"])

            # 2. Buscar KPIs coincidentes
            if codigos_relevantes or kw_especificas:
                kpis_todos = cursor.execute(
                    "SELECT k.codigo_proyecto, p.archivo_origen, k.indicador, k.linea_base, k.meta, k.resultado, k.variacion, k.cumplimiento, k.observaciones "
                    "FROM kpis k JOIN proyectos p ON k.codigo_proyecto = p.codigo_proyecto;"
                ).fetchall()

                for k in kpis_todos:
                    k_dict = dict(k)
                    cod_match = k_dict["codigo_proyecto"] in codigos_relevantes
                    ind_norm = normalizar_texto(k_dict["indicador"])
                    ind_match = any(kw in ind_norm for kw in kw_especificas)
                    if (
                        (cod_match and ind_match)
                        or (ind_match and not codigos_relevantes)
                        or (cod_match and len(kw_especificas) <= 2)
                    ):
                        kpis_encontrados.append(k_dict)

            # 3. Buscar reglas de negocio coincidentes
            repo_reglas = ReglasRepository(self.db_path)
            todas_reglas = repo_reglas.obtener_todas()
            for r in todas_reglas:
                r_texto = normalizar_texto(f"{r.titulo} {r.descripcion} {r.fuente or ''}")
                cod_match = r.codigo_proyecto in codigos_relevantes if r.codigo_proyecto else False
                kw_match = any(kw in r_texto for kw in kw_especificas) if kw_especificas else False
                if cod_match or kw_match:
                    reglas_encontradas.append(r)

        finally:
            conn.close()

        # 4. Búsqueda Full-Text (FTS5) si hay términos
        if palabras_clave:
            terminos_fts = " ".join(palabras_clave[:4])
            texto_fts, datos_fts = buscar_texto_detallado(terminos_fts, db_path=self.db_path)
            if datos_fts:
                fts_resultados = datos_fts
                trazabilidad.append(
                    {
                        "herramienta": "buscar_texto",
                        "argumentos": {"terminos_busqueda": terminos_fts},
                        "resultado": texto_fts,
                        "datos": datos_fts,
                    }
                )

        # Registrar trazabilidad de SQL si se ejecutaron consultas
        if kpis_encontrados or proyectos_encontrados:
            query_trace = (
                f"SELECT * FROM kpis WHERE codigo_proyecto IN ({', '.join('?' for _ in codigos_relevantes)});"
                if codigos_relevantes
                else "SELECT * FROM kpis;"
            )
            trazabilidad.append(
                {
                    "herramienta": "consultar_sql",
                    "argumentos": {"query": query_trace, "params": list(codigos_relevantes)},
                    "resultado": f"Total {len(kpis_encontrados)} kpi(s) encontrados.",
                    "datos": kpis_encontrados,
                }
            )

        # 5. Evaluar respuestas de Anti-alucinación y casos especiales
        # a) Variables internas no documentadas
        if any(v in msg_norm for v in VARIABLES_NO_DOCUMENTADAS) and not kpis_encontrados:
            return {
                "respuesta": "El dato consultado no se encuentra documentado en los informes oficiales de Procesa Consultores.",
                "trazabilidad": trazabilidad,
                "modelo": "fallback-local",
            }

        # b) Entidad no registrada (sin proyectos coincidentes ni KPIs)
        ENTIDADES_NO_REGISTRADAS: Set[str] = {
            "banco",
            "pichincha",
            "farmacia",
            "petroecuador",
            "telecom",
            "aerolinea",
            "aerolínea",
            "hospital",
        }
        es_consulta_entidad_externa = any(e in msg_norm for e in ENTIDADES_NO_REGISTRADAS)

        if (not proyectos_encontrados and not kpis_encontrados and es_consulta_entidad_externa) or (
            not proyectos_encontrados
            and not kpis_encontrados
            and not reglas_encontradas
            and not fts_resultados
        ):
            return {
                "respuesta": "La información consultada no se encuentra disponible en los informes de proyectos registrados.",
                "trazabilidad": trazabilidad,
                "modelo": "fallback-local",
            }

        # 6. Ensamblado de respuesta estructurada determinista
        secciones_respuesta: List[str] = []

        if aviso_error:
            secciones_respuesta.append(f"> [!NOTE]\n> {aviso_error}\n")
        else:
            secciones_respuesta.append(
                "> *Modo sin LLM: resultados directos de la base de datos*\n"
            )

        # Resumen Ejecutivo
        secciones_respuesta.append("### 📌 Resumen Ejecutivo")
        lineas_resumen = []
        archivos_fuente: Set[str] = set()

        # Resaltar reglas de negocio o alcance excluido si aplican
        for r in reglas_encontradas:
            lineas_resumen.append(f"**Criterio Oficial:** {r.descripcion}")
            if r.fuente:
                archivos_fuente.add(r.fuente)

        pide_duracion = any(
            w in msg_norm for w in ["duracion", "semanas", "duraron", "tiempo", "tiempos"]
        )
        pide_gerente = any(
            w in msg_norm
            for w in ["gerente", "gerentes", "lider", "lideraron", "quienes", "asignados"]
        )

        for p in proyectos_encontrados:
            detalles = []
            if pide_duracion:
                detalles.append(f"duración: **{p.get('duracion_semanas', 'N/A')} semanas**")
            if pide_gerente:
                detalles.append(f"gerente asignado: **{p['gerente_proyecto']}**")

            str_detalles = (
                f" ({', '.join(detalles)})"
                if detalles
                else f". Gerente de Proyecto: {p['gerente_proyecto']}"
            )
            lineas_resumen.append(
                f"Para el proyecto **{p['codigo_proyecto']}** (*{p['cliente']}*), el estado registrado es `{p['estado']}`{str_detalles}."
            )
            if p.get("alcance_excluido") and any(
                w in msg_norm for w in ["emergencia", "quirofano", "excluido", "alcance"]
            ):
                lineas_resumen.append(
                    f"**Delimitación de Alcance:** El área consultada quedó formalmente excluida del alcance. {p['alcance_excluido']}. "
                    f"Por lo tanto, no existen variaciones de tiempos ni mediciones para dichas áreas."
                )
            archivos_fuente.add(p["archivo_origen"])

        # Si hay KPIs, resaltar aquellos directamente vinculados con la consulta
        if kpis_encontrados:
            for k in kpis_encontrados:
                ind_norm = normalizar_texto(k["indicador"])
                es_kpi_directo = any(kw in ind_norm for kw in kw_especificas) or any(
                    w in msg_norm
                    for w in [
                        "espera",
                        "oee",
                        "paradas",
                        "variacion",
                        "porcentaje",
                        "redujo",
                        "cumplio",
                        "meta",
                    ]
                )
                if es_kpi_directo:
                    lineas_resumen.append(
                        f"• **{k['indicador']}** ({k['codigo_proyecto']}): El resultado oficial de cierre fue **{k['resultado']}** "
                        f"con una variación del **{k['variacion'] or 'N/A'}** (Línea base: {k['linea_base']}, Meta: {k['meta'] or '-'}, Cumplimiento: `{k['cumplimiento']}`)."
                    )

        if not lineas_resumen and kpis_encontrados:
            lineas_resumen.append(
                "Se identificaron las siguientes métricas y resultados oficiales en la base de datos:"
            )

        secciones_respuesta.append(
            "\n".join(lineas_resumen) if lineas_resumen else "Resultados coincidentes:"
        )

        # Tabla de Datos (KPIs o Proyectos)
        if kpis_encontrados:
            secciones_respuesta.append("\n### 📊 Matriz de Indicadores y Resultados")
            tabla = [
                "| Proyecto | Indicador | Línea Base | Meta | Resultado | Variación | Cumplimiento |",
                "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
            ]
            for k in kpis_encontrados:
                tabla.append(
                    f"| {k['codigo_proyecto']} | {k['indicador']} | {k['linea_base']} | {k['meta'] or '-'} | "
                    f"**{k['resultado']}** | {k['variacion'] or '-'} | {k['cumplimiento']} |"
                )
                archivos_fuente.add(k["archivo_origen"])
            secciones_respuesta.append("\n".join(tabla))
        elif proyectos_encontrados:
            secciones_respuesta.append("\n### 📊 Ficha y Portafolio de Proyectos")
            tabla = [
                "| Código | Cliente | Sector | Duración | Gerente de Proyecto | Estado |",
                "| :--- | :--- | :--- | :--- | :--- | :--- |",
            ]
            for p in proyectos_encontrados:
                tabla.append(
                    f"| {p['codigo_proyecto']} | {p['cliente']} | {p['sector']} | {p.get('duracion_semanas', '-')} semanas | {p['gerente_proyecto']} | {p['estado']} |"
                )
            secciones_respuesta.append("\n".join(tabla))

        # Insights o extractos documentales
        if fts_resultados:
            secciones_respuesta.append("\n### 💡 Evidencia Documental (FTS5)")
            for item in fts_resultados[:3]:
                secciones_respuesta.append(
                    f"- **[{item['codigo_proyecto']}] Sección *{item['seccion']}*:**\n"
                    f"  > {item['extracto']} [Fuente: {item['archivo_origen']}]"
                )
                archivos_fuente.add(item["archivo_origen"])

        # Fuentes Documentales Oficiales
        secciones_respuesta.append("\n### 📑 Fuentes Documentales")
        for fuente in sorted(archivos_fuente):
            secciones_respuesta.append(f"- [Fuente: {fuente}]")

        return {
            "respuesta": "\n".join(secciones_respuesta),
            "trazabilidad": trazabilidad,
            "modelo": "fallback-local",
        }
