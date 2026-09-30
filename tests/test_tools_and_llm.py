"""
Tests unitarios para Herramientas, ToolRegistry y Proveedores LLM (Fase 4).
Verifica:
1. ToolRegistry y ciclo de vida de herramientas.
2. Cumplimiento de protocolo Tool por SQLTool y FTSTool.
3. FakeLLM para pruebas deterministas y ejecución simulada de herramientas con trazabilidad.
4. GeminiProvider (protocolo LLMProvider y mecanismo de reintentos).
5. Servidor MCP generado dinámicamente desde ToolRegistry.
"""

from typing import Any, Dict

from mcp.server.mcpserver import MCPServer as FastMCP
from pydantic import BaseModel, Field

from procesa_agent.infrastructure.llm.base import ChatSession, LLMProvider
from procesa_agent.infrastructure.llm.fake import FakeLLM
from procesa_agent.infrastructure.llm.gemini import GeminiProvider
from procesa_agent.interfaces.mcp.server import _crear_handler_mcp, registrar_herramientas_en_mcp
from procesa_agent.tools.base import Tool, ToolRegistry, ToolResult, get_default_registry
from procesa_agent.tools.fts_tool import FTSTool
from procesa_agent.tools.sql_tool import SQLTool


class DummyModel(BaseModel):
    nombre: str = Field(default="test")
    valor: int = Field(default=42)


class CustomTool:
    name: str = "herramienta_custom"
    description: str = "Herramienta personalizada de prueba"
    parameters: Dict[str, Any] = {
        "type": "object",
        "properties": {"parametro_1": {"type": "string", "description": "Parámetro de prueba"}},
        "required": ["parametro_1"],
    }

    def run(self, **kwargs: Any) -> ToolResult:
        p1 = kwargs.get("parametro_1", "")
        return ToolResult(
            texto=f"Ejecutado con {p1}",
            datos=[{"param": p1}],
        )


def test_tool_registry_operaciones():
    """Verifica registro, consulta y eliminación en ToolRegistry."""
    registry = ToolRegistry()
    assert len(registry.all()) == 0

    custom = CustomTool()
    registry.register(custom)

    assert len(registry.all()) == 1
    assert registry.get("herramienta_custom") is custom
    assert registry.get("inexistente") is None

    eliminado = registry.unregister("herramienta_custom")
    assert eliminado is custom
    assert len(registry.all()) == 0


def test_default_registry_contiene_herramientas_oficiales():
    """Verifica que el registro global contenga las herramientas oficiales."""
    registry = get_default_registry()
    nombres = {t.name for t in registry.all()}
    assert "consultar_sql" in nombres
    assert "buscar_texto" in nombres


def test_sql_tool_protocolo_y_ejecucion():
    """Verifica que SQLTool cumpla el protocolo Tool y ejecute consultas de forma segura."""
    tool = SQLTool()
    assert isinstance(tool, Tool)
    assert tool.name == "consultar_sql"
    assert "query" in tool.parameters["properties"]

    # Consulta SELECT legítima sobre proyectos
    res = tool.run(query="SELECT count(*) as total FROM proyectos;")
    assert "total" in res["texto"] or "Total: 1 fila" in res["texto"]
    assert isinstance(res["datos"], list)

    # Intento de DDL debe ser bloqueado por seguridad
    res_bloqueado = tool.run(query="DROP TABLE proyectos;")
    assert "Error de seguridad" in res_bloqueado["texto"]
    assert res_bloqueado["datos"] == []


def test_fts_tool_protocolo_y_ejecucion():
    """Verifica que FTSTool cumpla el protocolo Tool y acepte tanto terminos_busqueda como query."""
    tool = FTSTool()
    assert isinstance(tool, Tool)
    assert tool.name == "buscar_texto"
    assert "terminos_busqueda" in tool.parameters["properties"]

    # Con terminos_busqueda
    res1 = tool.run(terminos_busqueda="paciente")
    assert isinstance(res1["texto"], str)
    assert isinstance(res1["datos"], list)

    # Respaldo si el llamador envía 'query'
    res2 = tool.run(query="paciente")
    assert isinstance(res2["texto"], str)
    assert isinstance(res2["datos"], list)


def test_fake_llm_generar_estructurado():
    """Verifica que FakeLLM cumpla LLMProvider y genere datos estructurados."""
    modelo_esperado = DummyModel(nombre="gemini_fake", valor=99)
    fake = FakeLLM(structured_response=modelo_esperado)
    assert isinstance(fake, LLMProvider)

    res = fake.generar_estructurado("dummy prompt", schema=DummyModel)
    assert res.nombre == "gemini_fake"
    assert res.valor == 99
    assert len(fake.prompts_recibidos) == 1


def test_fake_llm_chat_con_trazabilidad_de_herramientas():
    """Verifica que FakeChatSession ejecute herramientas y notifique trazabilidad."""
    eventos_trazabilidad = []

    def callback_trazabilidad(tool_name: str, args: Dict[str, Any], res: ToolResult):
        eventos_trazabilidad.append((tool_name, args, res))

    fake = FakeLLM(
        responses=["Respuesta final del agente consultor."],
        tool_calls_to_simulate=[("consultar_sql", {"query": "SELECT count(*) FROM proyectos;"})],
    )

    registry = get_default_registry()
    session = fake.crear_chat(
        system="Eres un asistente",
        tools=registry.all(),
        on_tool_executed=callback_trazabilidad,
    )
    assert isinstance(session, ChatSession)

    respuesta = session.send_message("¿Cuántos proyectos hay?")
    assert respuesta == "Respuesta final del agente consultor."
    assert len(eventos_trazabilidad) == 1
    tool_name, args, res = eventos_trazabilidad[0]
    assert tool_name == "consultar_sql"
    assert "query" in args
    assert isinstance(res["datos"], list)


def test_mcp_generacion_dinamica_con_custom_tool():
    """Verifica que registrar_herramientas_en_mcp exponga dinámicamente nuevas herramientas."""
    registry = ToolRegistry()
    registry.register(CustomTool())

    server = FastMCP("ServidorPrueba")
    registrar_herramientas_en_mcp(server, registry)

    handler = _crear_handler_mcp(CustomTool())
    assert handler.__name__ == "herramienta_custom"
    resultado_texto = handler(parametro_1="valor_prueba")
    assert "Ejecutado con valor_prueba" in resultado_texto


def test_gemini_provider_reintentos_exponenciales():
    """Verifica el mecanismo de reintentos exponenciales ante errores simulados en GeminiProvider."""
    provider = GeminiProvider(api_key="fake-test-key", max_retries=3, base_delay=0.01)
    assert isinstance(provider, LLMProvider)

    intentos = 0

    def funcion_con_fallos_transitorios():
        nonlocal intentos
        intentos += 1
        if intentos < 3:
            # Simular error 429
            err = Exception("429 Resource exhausted: quota exceeded")
            err.code = 429  # type: ignore[attr-defined]
            raise err
        return "exito_en_intento_3"

    resultado = provider._ejecutar_con_reintentos(funcion_con_fallos_transitorios)
    assert resultado == "exito_en_intento_3"
    assert intentos == 3
