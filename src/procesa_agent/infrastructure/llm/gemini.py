"""
Proveedor de Modelos de Lenguaje Google Gemini (infrastructure/llm/gemini.py).
Único punto del repositorio que importa y utiliza el SDK oficial google.genai.
Implementa el protocolo LLMProvider con soporte de reintentos exponenciales,
Function Calling dinámico a partir de ToolRegistry y extracción estructurada con Pydantic.
"""

import inspect
import os
import time
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar

from google import genai
from google.genai import errors, types
from pydantic import BaseModel

from procesa_agent.core.errors import ProcesaError
from procesa_agent.core.logging import logger
from procesa_agent.core.settings import get_settings
from procesa_agent.infrastructure.llm.base import ChatSession
from procesa_agent.tools.base import Tool, ToolResult

T = TypeVar("T", bound=BaseModel)


class GeminiChatSession:
    """Encapsula una sesión de chat multi-turno de Gemini."""

    def __init__(self, chat: genai.chats.Chat, retry_handler: Callable[..., Any]) -> None:
        self._chat = chat
        self._retry = retry_handler

    def send_message(self, message: str) -> str:
        """Envía un mensaje al chat y retorna el texto de respuesta ejecutando herramientas intermedias."""
        resp = self._retry(self._chat.send_message, message)
        if not resp or not resp.text:
            raise ProcesaError("No se obtuvo texto de respuesta válido del modelo Gemini.")
        return resp.text


class GeminiProvider:
    """Implementación de LLMProvider para los modelos Google Gemini (2.5 / 1.5)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        temperature: float = 0.1,
        max_retries: int = 3,
        base_delay: float = 1.0,
    ) -> None:
        settings = get_settings()
        self.api_key = api_key or settings.gemini_api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = model_name or settings.model_name
        self.temperature = temperature
        self.max_retries = max_retries
        self.base_delay = base_delay

        if self.api_key:
            self._client: Optional[genai.Client] = genai.Client(api_key=self.api_key)
        else:
            self._client = None

    @property
    def client(self) -> genai.Client:
        """Retorna el cliente de GenAI o lanza error si la clave no está configurada."""
        if not self._client:
            raise ProcesaError(
                "GEMINI_API_KEY no está configurada. Configure la clave en el panel o variable de entorno."
            )
        return self._client

    def _ejecutar_con_reintentos(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Ejecuta una llamada al API con reintentos y backoff exponencial ante errores 429/5xx."""
        ultimo_error: Optional[Exception] = None
        for intento in range(self.max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                ultimo_error = e
                # Reintentar en caso de cuota excedida (429) o fallos de servidor (5xx)
                es_429 = getattr(e, "code", None) == 429 or "429" in str(e)
                es_5xx = isinstance(e, errors.ServerError) or (
                    getattr(e, "code", 0) is not None and 500 <= getattr(e, "code", 0) < 600
                )
                if (es_429 or es_5xx) and intento < self.max_retries - 1:
                    demora = self.base_delay * (2**intento)
                    logger.warning(
                        f"Error transitorio en llamada Gemini ({e}). Reintentando en {demora:.1f}s (intento {intento + 1}/{self.max_retries})..."
                    )
                    time.sleep(demora)
                    continue
                # Errores no transitorios o intentos agotados se propagan
                raise e

        if ultimo_error:
            raise ultimo_error

    def generar_estructurado(
        self,
        prompt: str,
        schema: Type[T],
        **cfg: Any,
    ) -> T:
        """Genera una salida tipada con garantía de esquema JSON estructurado."""
        modelo = cfg.get("model") or self.model_name
        temp = cfg.get("temperature", self.temperature)

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=schema,
            temperature=temp,
        )

        resp = self._ejecutar_con_reintentos(
            self.client.models.generate_content,
            model=modelo,
            contents=prompt,
            config=config,
        )

        if hasattr(resp, "parsed") and resp.parsed is not None:
            return resp.parsed  # type: ignore[no-any-return]

        if not resp.text:
            raise ProcesaError("El modelo Gemini no retornó contenido para el esquema solicitado.")

        return schema.model_validate_json(resp.text)

    def crear_chat(
        self,
        system: str,
        tools: List[Tool],
        on_tool_executed: Optional[Callable[[str, Dict[str, Any], ToolResult], None]] = None,
        **cfg: Any,
    ) -> ChatSession:
        """Crea una sesión de chat multi-turno con Function Calling adaptado dinámicamente."""
        modelo = cfg.get("model") or self.model_name
        temp = cfg.get("temperature", self.temperature)

        funciones_gemini: List[Any] = []
        for t in tools:
            # Construir wrapper para capturar trazabilidad transparente
            props = t.parameters.get("properties", {})
            params = [
                inspect.Parameter(
                    param_name,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    annotation=str,
                )
                for param_name in props
            ]
            sig = inspect.Signature(parameters=params, return_annotation=str)

            def make_wrapper(tool_ref: Tool, signature: inspect.Signature) -> Callable[..., str]:
                def wrapper(*args: Any, **kwargs: Any) -> str:
                    bound = signature.bind(*args, **kwargs)
                    bound.apply_defaults()
                    res = tool_ref.run(**bound.arguments)
                    if on_tool_executed:
                        on_tool_executed(tool_ref.name, bound.arguments, res)
                    return res["texto"]

                wrapper.__name__ = tool_ref.name
                wrapper.__doc__ = tool_ref.description
                wrapper.__signature__ = signature  # type: ignore[attr-defined]
                return wrapper

            funciones_gemini.append(make_wrapper(t, sig))

        config = types.GenerateContentConfig(
            system_instruction=system,
            tools=funciones_gemini,
            temperature=temp,
        )

        chat_sdk = self.client.chats.create(model=modelo, config=config)
        return GeminiChatSession(chat_sdk, self._ejecutar_con_reintentos)
