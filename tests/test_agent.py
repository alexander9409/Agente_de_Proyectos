"""
Suite de Pruebas Automatizadas (tests/test_agent.py)
Valida exactitud de datos, integridad relacional, funcionamiento de herramientas,
respuestas del agente y protocolo estricto anti-alucinación.
"""

import pytest

from procesa_agent.agent.orchestrator import AgenteProyectos
from procesa_agent.core.config_manager import ConfigManager
from procesa_agent.infrastructure.db.connection import (
    obtener_conexion,
    obtener_resumen_bd,
)
from procesa_agent.tools.tools import consultar_sql


@pytest.fixture(autouse=True)
def aislar_tests_bd(bd_con_datos):
    """Garantiza que todos los tests de este módulo se ejecuten sobre la BD efímera aislada."""
    pass


def test_existencia_cuatro_proyectos():
    """Valida la existencia exacta de los 4 proyectos en SQLite tras la ingesta."""
    conn = obtener_conexion()
    cursor = conn.cursor()
    filas = cursor.execute(
        "SELECT codigo_proyecto, cliente FROM proyectos ORDER BY codigo_proyecto;"
    ).fetchall()
    conn.close()

    codigos = [f["codigo_proyecto"] for f in filas]
    assert len(codigos) == 4, f"Se esperaban exactamente 4 proyectos, se encontraron {len(codigos)}"
    assert set(codigos) == {"PC-2025-014", "PC-2025-027", "PC-2025-033", "PC-2026-006"}

    resumen = obtener_resumen_bd()
    assert resumen["proyectos"] == 4
    assert resumen["kpis"] >= 20
    assert resumen["lecciones"] >= 10
    assert resumen["fts"] >= 40


def test_exactitud_kpi_oee_plasticos():
    """Valida la exactitud del KPI de OEE de Plásticos del Pacífico (Línea base 58%, Resultado 71%)."""
    conn = obtener_conexion()
    cursor = conn.cursor()
    fila = cursor.execute(
        "SELECT indicador, linea_base, meta, resultado, cumplimiento "
        "FROM kpis WHERE codigo_proyecto = 'PC-2025-027' AND indicador LIKE '%OEE%';"
    ).fetchone()
    conn.close()

    assert fila is not None, "No se encontró el KPI de OEE para PC-2025-027"
    assert "58%" in fila["linea_base"], f"Línea base esperada 58%, obtenida: {fila['linea_base']}"
    assert "71%" in fila["resultado"], f"Resultado esperado 71%, obtenido: {fila['resultado']}"
    assert fila["cumplimiento"] == "Cumplido"

    # Validación a través del Agente
    agente = AgenteProyectos()
    respuesta = agente.responder(
        "¿Cuál fue la línea base y resultado final de OEE en Plásticos del Pacífico?"
    )
    texto = respuesta["respuesta"]
    assert "58%" in texto
    assert "71%" in texto
    assert "Informe_Cierre_PC-2025-027_Plasticos_del_Pacifico.pdf" in texto


def test_estado_no_cumplido_proveedores_la_canasta():
    """Valida el estado 'No cumplido' para la integración con proveedores en Supermercados La Canasta."""
    conn = obtener_conexion()
    cursor = conn.cursor()
    fila = cursor.execute(
        "SELECT indicador, resultado, meta, cumplimiento "
        "FROM kpis WHERE codigo_proyecto = 'PC-2026-006' AND indicador LIKE '%proveedor%';"
    ).fetchone()
    conn.close()

    assert fila is not None, "No se encontró el KPI de proveedores para PC-2026-006"
    assert fila["cumplimiento"] == "No cumplido"
    assert "0 de 3" in fila["resultado"]

    # Validación a través del Agente
    agente = AgenteProyectos()
    respuesta = agente.responder(
        "¿Se cumplió la integración con proveedores en Supermercados La Canasta?"
    )
    texto = respuesta["respuesta"]
    assert "No cumplido" in texto
    assert "Informe_Cierre_PC-2026-006_Supermercados_La_Canasta.pdf" in texto


def test_reduccion_tiempo_espera_clinica_santa_lucia():
    """Valida la reducción de tiempo de espera al 24% en Clínica Santa Lucía."""
    conn = obtener_conexion()
    cursor = conn.cursor()
    fila = cursor.execute(
        "SELECT indicador, linea_base, meta, resultado, variacion, cumplimiento "
        "FROM kpis WHERE codigo_proyecto = 'PC-2025-033' AND indicador LIKE '%espera%';"
    ).fetchone()
    conn.close()

    assert fila is not None, "No se encontró el KPI de tiempo de espera para PC-2025-033"
    assert "24%" in fila["variacion"]
    assert "39,5 min" in fila["resultado"]
    assert fila["cumplimiento"] == "Cumplido"

    # Validación a través del Agente
    agente = AgenteProyectos()
    respuesta = agente.responder("¿Cuánto se redujo el tiempo de espera en la Clínica Santa Lucía?")
    texto = respuesta["respuesta"]
    assert "24%" in texto
    assert "Informe_Cierre_PC-2025-033_Clinica_Santa_Lucia.docx" in texto


def test_validacion_anti_alucinacion_cliente_inexistente():
    """Valida que una consulta sobre un cliente inexistente (ej. 'Banco Pichincha') retorne mensaje de información no documentada."""
    agente = AgenteProyectos()
    respuesta = agente.responder(
        "¿Qué proyectos o consultorías se ejecutaron para Banco Pichincha?"
    )
    texto_esperado = "La información consultada no se encuentra disponible en los informes de proyectos registrados."
    assert respuesta["respuesta"].strip() == texto_esperado


def test_seguridad_sql_rechaza_escritura():
    """Valida que consultar_sql rechace intentos de inyección o modificación DDL/DML, ATTACH y PRAGMA."""
    res_drop = consultar_sql("DROP TABLE proyectos;")
    assert "Error de seguridad" in res_drop

    res_delete = consultar_sql("DELETE FROM kpis WHERE id = 1;")
    assert "Error de seguridad" in res_delete

    res_insert = consultar_sql("INSERT INTO proyectos (codigo_proyecto) VALUES ('TEST');")
    assert "Error de seguridad" in res_insert

    res_update = consultar_sql("UPDATE proyectos SET cliente = 'Hacked';")
    assert "Error de seguridad" in res_update

    res_attach = consultar_sql("ATTACH DATABASE 'foo.db' AS foo;")
    assert "Error de seguridad" in res_attach

    res_pragma = consultar_sql("PRAGMA table_info(proyectos);")
    assert "Error de seguridad" in res_pragma


def test_seguridad_sql_bloquea_tabla_configuraciones():
    """Valida que la tabla 'configuraciones' (que almacena claves y secretos) nunca sea accesible desde consultar_sql."""
    res = consultar_sql("SELECT clave, valor FROM configuraciones;")
    assert "Error de seguridad" in res or "denegado" in res.lower()


def test_seguridad_sql_bloquea_multiples_sentencias():
    """Valida que no se permitan múltiples sentencias separadas por punto y coma."""
    res = consultar_sql("SELECT 1; SELECT 2;")
    assert "Error de seguridad" in res


def test_seguridad_sql_bloquea_funciones_no_permitidas():
    """Valida que funciones peligrosas como load_extension sean bloqueadas por el autorizador."""
    res = consultar_sql("SELECT load_extension('malicious.dll');")
    assert "Error de seguridad" in res or "denegado" in res.lower()


def test_seguridad_sql_timeout_cte_recursiva():
    """Valida que una consulta recursiva infinita/masiva se corte por el handler de timeout."""
    res = consultar_sql(
        "WITH RECURSIVE r(i) AS (VALUES(0) UNION ALL SELECT i+1 FROM r) SELECT count(*) FROM r;"
    )
    assert "timeout" in res.lower() or "interrumpida" in res.lower() or "cancelada" in res.lower()


def test_seguridad_sql_limite_max_filas_truncado():
    """Valida que si una consulta excede MAX_FILAS (200), el resultado se trunque a 200 y se agregue la advertencia."""
    res = consultar_sql(
        "WITH RECURSIVE r(i) AS (VALUES(1) UNION ALL SELECT i+1 FROM r WHERE i < 250) SELECT i FROM r;"
    )
    assert "truncado" in res.lower()
    assert "200" in res


def test_seguridad_sql_consultas_legitimas_y_fts():
    """Valida que consultas SELECT legítimas sobre proyectos y sobre informes_fts (MATCH) funcionen sin problema."""
    res_proj = consultar_sql(
        "SELECT codigo_proyecto, cliente FROM proyectos ORDER BY codigo_proyecto;"
    )
    assert "PC-2025-014" in res_proj
    assert "Total: 4 fila(s)" in res_proj

    res_fts = consultar_sql(
        "SELECT rowid, codigo_proyecto FROM informes_fts WHERE informes_fts MATCH 'calidad';"
    )
    assert "Total:" in res_fts


def test_seguridad_fallback_inyeccion_sql():
    """Valida que entradas maliciosas tipo SQLi en fallback no rompan la consulta ni expongan datos indebidos."""
    agente = AgenteProyectos()
    respuesta = agente.responder("Banco ' OR 1=1 --")
    assert "no se encuentra disponible" in respuesta["respuesta"].lower()


def test_persistencia_configuraciones():
    """Valida que ConfigManager guarde y recupere configuraciones en SQLite."""
    cfg = ConfigManager()
    cfg.set_config("test_key", "valor_123", "Configuración de prueba")
    valor = cfg.get_config("test_key")
    assert valor == "valor_123"


def test_linea_base_paradas_64h_prevalece_sobre_anexo():
    """Valida que la línea base de paradas no programadas sea 64 h/mes y prevalezca sobre el anexo."""
    conn = obtener_conexion()
    cursor = conn.cursor()
    fila = cursor.execute(
        "SELECT indicador, linea_base, meta, resultado, variacion, cumplimiento "
        "FROM kpis WHERE codigo_proyecto = 'PC-2025-027' AND indicador LIKE '%paradas%';"
    ).fetchone()
    conn.close()

    assert fila is not None, "No se encontró el KPI de paradas no programadas para PC-2025-027"
    assert "64 h/mes" in fila["linea_base"], (
        f"Línea base esperada 64 h/mes, obtenida: {fila['linea_base']}"
    )
    assert "31 h/mes" in fila["resultado"]
    assert "-52%" in fila["variacion"]
    assert fila["cumplimiento"] == "Cumplido"

    # Validación a través del Agente
    agente = AgenteProyectos()
    respuesta = agente.responder(
        "¿Qué línea base se tomó para las paradas no programadas en Plásticos del Pacífico y por qué?"
    )
    texto = respuesta["respuesta"]
    assert "64 h/mes" in texto
    assert "31 h/mes" in texto
    assert "prevalece" in texto.lower()


def test_no_atribuibilidad_colocacion_horizonte_andino():
    """Valida que el +9% de colocación no conste como resultado de consultoría y sea no atribuible."""
    conn = obtener_conexion()
    cursor = conn.cursor()
    filas = cursor.execute(
        "SELECT indicador, resultado FROM kpis WHERE codigo_proyecto = 'PC-2025-014';"
    ).fetchall()
    conn.close()

    # Comprobar que en la tabla relacional de KPIs del proyecto NO existe colocación como KPI evaluado
    indicadores = [f["indicador"].lower() for f in filas]
    assert not any("colocación" in ind or "colocado" in ind for ind in indicadores), (
        "El +9% de colocación no debe registrarse como indicador/KPI del proyecto"
    )

    # Validación a través del Agente
    agente = AgenteProyectos()
    respuesta = agente.responder(
        "¿Se debe registrar el +9% de colocación de Cooperativa Horizonte Andino como resultado del proyecto?"
    )
    texto = respuesta["respuesta"]
    assert "no atribuible" in texto.lower() or "campaña comercial" in texto.lower()
    assert (
        "no se registra" in texto.lower()
        or "no debe" in texto.lower()
        or "no constituye" in texto.lower()
    )


def test_distincion_cerrado_con_pendientes_vs_cerrados():
    """Valida que todos los proyectos terminaron ejecución pero únicamente La Canasta tiene estado con pendientes."""
    agente = AgenteProyectos()
    respuesta = agente.responder(
        "¿Cuáles de los proyectos se consideran cerrados y cuál cerró con pendientes?"
    )
    texto = respuesta["respuesta"]
    assert "PC-2026-006" in texto or "Supermercados La Canasta" in texto
    assert "Cerrado con pendientes" in texto
    assert "Informe_Cierre_PC-2026-006_Supermercados_La_Canasta.pdf" in texto


def test_alcance_excluido_emergencia_santa_lucia():
    """Valida que ante consultas de Emergencia y Quirófanos en Santa Lucía, se declare formalmente su exclusión."""
    agente = AgenteProyectos()
    pregunta = "¿Cómo variaron los tiempos de atención en la atención de Emergencia y Quirófanos de la Clínica Santa Lucía?"
    respuesta = agente.responder(pregunta)
    texto = respuesta["respuesta"]

    # Debe indicar claramente la exclusión del alcance
    assert "excluido" in texto.lower() or "excluidos" in texto.lower()
    assert "emergencia" in texto.lower()
    assert (
        "quirófano" in texto.lower()
        or "quirofano" in texto.lower()
        or "hospitalización" in texto.lower()
    )
    assert "consulta externa" in texto.lower()
    assert "no existen variaciones" in texto.lower() or "sin mediciones" in texto.lower()
    assert "Informe_Cierre_PC-2025-033_Clinica_Santa_Lucia.docx" in texto


def test_anti_alucinacion_honorarios_no_documentados():
    """Valida que ante preguntas por variables no documentadas (honorarios/presupuestos de consultoría), se active anti-alucinación."""
    agente = AgenteProyectos()
    pregunta = "¿Cuáles fueron los honorarios o presupuesto pagado a la consultora por el proyecto de Clínica Santa Lucía?"
    respuesta = agente.responder(pregunta)
    texto = respuesta["respuesta"]

    assert "no se encuentra documentado" in texto.lower() or "no disponible" in texto.lower()
