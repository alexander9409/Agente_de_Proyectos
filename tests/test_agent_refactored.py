"""
Tests unitarios para el Agente Refactorizado, PromptLoader, Memoria y Fallback (Fase 5).
Verifica:
1. Inyección dinámica del prompt del sistema (PromptLoader).
2. Memoria conversacional con ventana delimitada (ConversationMemory).
3. Motor de Fallback determinista, genérico y libre de hardcoding (FallbackEngine).
4. AgenteProyectos integrado con FakeLLM y trazabilidad unificada.
"""

from procesa_agent.agent.fallback import FallbackEngine, extraer_palabras_clave
from procesa_agent.agent.memory import ConversationMemory
from procesa_agent.agent.orchestrator import AgenteProyectos
from procesa_agent.agent.prompt_loader import PromptLoader
from procesa_agent.infrastructure.llm.fake import FakeLLM


def test_normalizacion_y_extraccion_palabras_clave():
    """Verifica limpieza de tildes, mayúsculas y eliminación de stopwords."""
    frase = "¿Cuál fue la línea base y resultado de OEE en Plásticos del Pacífico?"
    palabras = extraer_palabras_clave(frase)
    assert "linea" in palabras
    assert "base" in palabras
    assert "resultado" in palabras
    assert "oee" in palabras
    assert "plasticos" in palabras
    assert "pacifico" in palabras
    # Stopwords no deben estar presentes
    assert "cual" not in palabras
    assert "fue" not in palabras
    assert "la" not in palabras
    assert "de" not in palabras
    assert "del" not in palabras


def test_prompt_loader_inyeccion_dinamica():
    """Verifica que PromptLoader inyecte tablas, proyectos y reglas sin placeholders residuales."""
    loader = PromptLoader()
    prompt = loader.cargar_prompt()

    assert "{{TABLAS_ESQUEMA}}" not in prompt
    assert "{{PROYECTOS_REGISTRADOS}}" not in prompt
    assert "{{REGLAS_NEGOCIO}}" not in prompt

    assert "Tabla `proyectos`:" in prompt
    assert "Tabla `kpis`:" in prompt
    assert "Tabla `reglas_negocio`:" in prompt

    # Verificar que contiene los proyectos de la base de datos
    assert "PC-2025-014" in prompt
    assert "PC-2025-027" in prompt
    assert "PC-2025-033" in prompt
    assert "PC-2026-006" in prompt


def test_conversation_memory_ventana_deslizante():
    """Verifica que ConversationMemory acote el historial a max_turns y permita reinicio."""
    memoria = ConversationMemory(max_turns=3)
    assert len(memoria) == 0

    memoria.add_turn("pregunta 1", "respuesta 1")
    memoria.add_turn("pregunta 2", "respuesta 2")
    memoria.add_turn("pregunta 3", "respuesta 3")
    assert len(memoria) == 3

    # Añadir cuarto turno debe descartar el primero
    memoria.add_turn("pregunta 4", "respuesta 4")
    assert len(memoria) == 3
    historial = memoria.get_history()
    assert historial[0]["usuario"] == "pregunta 2"
    assert historial[-1]["usuario"] == "pregunta 4"

    # Limpiar memoria
    memoria.clear()
    assert len(memoria) == 0
    assert memoria.get_history() == []


def test_fallback_engine_anti_alucinacion_cliente_desconocido():
    """Verifica que FallbackEngine responda el texto canónico ante entidades no registradas."""
    fallback = FallbackEngine()
    res = fallback.responder("¿Qué proyectos se hicieron para Banco Pichincha?")
    assert res["respuesta"].strip() == (
        "La información consultada no se encuentra disponible en los informes de proyectos registrados."
    )


def test_fallback_engine_anti_alucinacion_variables_no_documentadas():
    """Verifica respuesta adecuada ante honorarios o presupuestos de consultoría."""
    fallback = FallbackEngine()
    res = fallback.responder("¿Cuáles fueron los honorarios pagados a la consultora?")
    assert "no se encuentra documentado" in res["respuesta"].lower()


def test_fallback_engine_recuperacion_kpis_y_reglas():
    """Verifica que FallbackEngine recupere KPIs y reglas aplicables desde SQLite."""
    fallback = FallbackEngine()
    res = fallback.responder("¿Cuál fue el resultado de OEE en Plásticos?")
    texto = res["respuesta"]

    assert "OEE" in texto or "Matriz" in texto
    assert "[Fuente: Informe_Cierre_PC-2025-027_Plasticos_del_Pacifico.pdf]" in texto
    assert res["modelo"] == "fallback-local"


def test_agente_con_fake_llm_multi_turno_y_reinicio():
    """Verifica que AgenteProyectos preserve la sesión en múltiples turnos y permita reiniciarla."""
    fake_llm = FakeLLM(
        responses=[
            "Respuesta turno 1: proyectos liderados.",
            "Respuesta turno 2: proyectos con pendientes.",
        ],
        tool_calls_to_simulate=[
            ("consultar_sql", {"query": "SELECT codigo_proyecto FROM proyectos;"})
        ],
    )

    agente = AgenteProyectos(llm_provider=fake_llm)

    # Turno 1
    resp1 = agente.responder("¿Qué proyectos lideró Daniela?")
    assert "turno 1" in resp1["respuesta"]
    assert len(resp1["trazabilidad"]) == 1
    assert len(agente.historial) == 1

    # Turno 2 (misma conversación)
    resp2 = agente.responder("¿Y cuál tuvo pendientes?")
    assert "turno 2" in resp2["respuesta"]
    assert len(agente.historial) == 2

    # Reiniciar conversación
    agente.nueva_conversacion()
    assert len(agente.historial) == 0
    assert agente._chat_session is None
