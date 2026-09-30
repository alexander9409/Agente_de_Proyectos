"""
Protocolo Base para Proveedores de Modelos de Lenguaje (LLMProvider).
Define interfaces para generación estructurada y sesiones de chat con herramientas.
"""

from typing import Any, Callable, Dict, List, Optional, Protocol, Type, TypeVar, runtime_checkable

from pydantic import BaseModel

from procesa_agent.tools.base import Tool, ToolResult

T = TypeVar("T", bound=BaseModel)


@runtime_checkable
class ChatSession(Protocol):
    """Protocolo para sesiones de conversación multi-turno con soporte de herramientas."""

    def send_message(self, message: str) -> str:
        """Envía un mensaje al modelo y retorna su respuesta final como texto."""
        ...


@runtime_checkable
class LLMProvider(Protocol):
    """Protocolo abstracto que desacopla la lógica del agente del SDK del proveedor (Gemini, etc.)."""

    def generar_estructurado(
        self,
        prompt: str,
        schema: Type[T],
        **cfg: Any,
    ) -> T:
        """Genera una respuesta garantizando adherencia estricta a un esquema Pydantic."""
        ...

    def crear_chat(
        self,
        system: str,
        tools: List[Tool],
        on_tool_executed: Optional[Callable[[str, Dict[str, Any], ToolResult], None]] = None,
        **cfg: Any,
    ) -> ChatSession:
        """Crea una nueva sesión de chat conversacional equipada con herramientas ejecutables."""
        ...
