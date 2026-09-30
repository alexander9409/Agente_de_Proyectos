"""
Suite de Pruebas Automatizadas (tests/test_agent.py)
Valida exactitud de datos, integridad relacional, funcionamiento de herramientas,
respuestas del agente y protocolo estricto anti-alucinación.
"""

import pytest

from src.agent import AgenteProyectos
from src.config_manager import ConfigManager
from src.db import inicializar_bd, obtener_conexion, obtener_resumen_bd
from src.extractor import ejecutar_ingesta_completa
from src.tools import buscar_texto, consultar_sql


@pytest.fixture(scope="session", autouse=True)
def preparar_base_datos():
    """Asegura que la base de datos esté inicializada e ingerida antes de los tests."""
    inicializar_bd()
    ejecutar_ingesta_completa()


def test_existencia_cuatro_proyectos():
    """Valida la existencia exacta de los 4 proyectos en SQLite tras la ingesta."""
    conn = obtener_conexion()
    cursor = conn.cursor()
    filas = cursor.execute("SELECT codigo_proyecto, cliente FROM proyectos ORDER BY codigo_proyecto;").fetchall()
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
    respuesta = agente.responder("¿Cuál fue la línea base y resultado final de OEE en Plásticos del Pacífico?")
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
    respuesta = agente.responder("¿Se cumplió la integración con proveedores en Supermercados La Canasta?")
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
    respuesta = agente.responder("¿Qué proyectos o consultorías se ejecutaron para Banco Pichincha?")
    texto_esperado = "La información consultada no se encuentra disponible en los informes de proyectos registrados."
    assert respuesta["respuesta"].strip() == texto_esperado


def test_seguridad_sql_rechaza_escritura():
    """Valida que consultar_sql rechace intentos de inyección o modificación DDL/DML."""
    res_drop = consultar_sql("DROP TABLE proyectos;")
    assert "Error de seguridad" in res_drop

    res_delete = consultar_sql("DELETE FROM kpis WHERE id = 1;")
    assert "Error de seguridad" in res_delete

    res_insert = consultar_sql("INSERT INTO proyectos (codigo_proyecto) VALUES ('TEST');")
    assert "Error de seguridad" in res_insert


def test_persistencia_configuraciones():
    """Valida que ConfigManager guarde y recupere configuraciones en SQLite."""
    cfg = ConfigManager()
    cfg.set_config("test_key", "valor_123", "Configuración de prueba")
    valor = cfg.get_config("test_key")
    assert valor == "valor_123"
