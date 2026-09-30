"""
Proveedor Falso de LLM para Pruebas Deterministas (infrastructure/llm/fake.py).
Permite probar agentes, extracción y ejecución de herramientas sin red ni consumo de tokens.
"""

from typing import Any, Callable, Dict, List, Optional, Tuple, Type, TypeVar

from pydantic import BaseModel

from procesa_agent.infrastructure.llm.base import ChatSession
from procesa_agent.tools.base import Tool, ToolResult

T = TypeVar("T", bound=BaseModel)


class FakeChatSession:
    """Sesión de chat simulada para pruebas deterministas."""

    def __init__(
        self,
        responses: List[str],
        tools: List[Tool],
        on_tool_executed: Optional[Callable[[str, Dict[str, Any], ToolResult], None]] = None,
        tool_calls_to_simulate: Optional[List[Tuple[str, Dict[str, Any]]]] = None,
    ) -> None:
        self.responses = list(responses)
        self.tools = {t.name: t for t in tools}
        self.on_tool_executed = on_tool_executed
        self.tool_calls_to_simulate = tool_calls_to_simulate or []
        self.mensajes_recibidos: List[str] = []

    def send_message(self, message: str) -> str:
        """Registra el mensaje recibido, ejecuta herramientas simuladas si corresponde y retorna respuesta."""
        self.mensajes_recibidos.append(message)

        # Simular llamadas a herramientas si fueron programadas
        for tool_name, args in self.tool_calls_to_simulate:
            if tool_name in self.tools:
                tool = self.tools[tool_name]
                resultado = tool.run(**args)
                if self.on_tool_executed:
                    self.on_tool_executed(tool_name, args, resultado)

        if self.responses:
            return self.responses.pop(0)
        return "Respuesta simulada por FakeLLM."


class FakeLLM:
    """Implementación simulada de LLMProvider para pruebas automatizadas."""

    def __init__(
        self,
        responses: Optional[List[str]] = None,
        structured_response: Optional[BaseModel] = None,
        tool_calls_to_simulate: Optional[List[Tuple[str, Dict[str, Any]]]] = None,
    ) -> None:
        self.responses = responses or ["Respuesta simulada estándar de FakeLLM."]
        self.structured_response = structured_response
        self.tool_calls_to_simulate = tool_calls_to_simulate or []
        self.prompts_recibidos: List[str] = []
        self.last_chat_session: Optional[FakeChatSession] = None

    def generar_estructurado(
        self,
        prompt: str,
        schema: Type[T],
        **cfg: Any,
    ) -> T:
        """Retorna una respuesta estructurada preconfigurada o vacía del tipo schema."""
        self.prompts_recibidos.append(prompt)
        if self.structured_response and isinstance(self.structured_response, schema):
            return self.structured_response  # type: ignore[return-value]
        # Crear instancia mock con campos por defecto
        return schema.model_validate({})

    def crear_chat(
        self,
        system: str,
        tools: List[Tool],
        on_tool_executed: Optional[Callable[[str, Dict[str, Any], ToolResult], None]] = None,
        **cfg: Any,
    ) -> ChatSession:
        """Crea una sesión de chat falsa que simula el flujo de interacción."""
        session = FakeChatSession(
            responses=list(self.responses),
            tools=tools,
            on_tool_executed=on_tool_executed,
            tool_calls_to_simulate=self.tool_calls_to_simulate,
        )
        self.last_chat_session = session
        return session
