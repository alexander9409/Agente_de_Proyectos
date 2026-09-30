"""
Orquestador Principal del Agente de Proyectos (agent/orchestrator.py).
Conecta el proveedor de LLM con Function Calling dinámico, ToolRegistry,
memoria conversacional multi-turno, PromptLoader y motor de Fallback analítico genérico.
"""

from typing import Any, Callable, Dict, List, Optional

from procesa_agent.agent.fallback import FallbackEngine
from procesa_agent.agent.memory import ConversationMemory
from procesa_agent.agent.prompt_loader import PromptLoader
from procesa_agent.core.logging import logger
from procesa_agent.core.settings import get_settings
from procesa_agent.infrastructure.llm.base import ChatSession, LLMProvider
from procesa_agent.infrastructure.llm.gemini import GeminiProvider
from procesa_agent.tools.base import ToolRegistry, ToolResult, get_default_registry


class AgenteProyectos:
    """
    Agente inteligente orquestador para consultar proyectos de Procesa Consultores.
    Coordina la interacción conversacional con el LLM, ejecución de herramientas y memoria.
    """

    def __init__(
        self,
        llm_provider: Optional[LLMProvider] = None,
        tool_registry: Optional[ToolRegistry] = None,
        memory: Optional[ConversationMemory] = None,
        prompt_loader: Optional[PromptLoader] = None,
        db_path: Optional[str] = None,
        config_mgr: Optional[Any] = None,
    ) -> None:
        settings = get_settings()
        self.db_path = db_path or getattr(config_mgr, "db_path", None) or settings.sqlite_db_path
        self.tool_registry = tool_registry or get_default_registry()
        self.prompt_loader = prompt_loader or PromptLoader(db_path=self.db_path)
        self.memory = memory or ConversationMemory(max_turns=10)
        self.fallback_engine = FallbackEngine(db_path=self.db_path)

        # Configurar proveedor de LLM
        if llm_provider is not None:
            self.llm_provider: Optional[LLMProvider] = llm_provider
        elif config_mgr is not None and getattr(config_mgr, "gemini_api_key", None):
            self.llm_provider = GeminiProvider(
                api_key=config_mgr.gemini_api_key,
                model_name=getattr(config_mgr, "model_name", settings.model_name),
                temperature=float(getattr(config_mgr, "temperature", settings.temperature)),
            )
        elif settings.gemini_api_key:
            self.llm_provider = GeminiProvider(
                api_key=settings.gemini_api_key,
                model_name=settings.model_name,
                temperature=settings.temperature,
            )
        else:
            self.llm_provider = None

        self._chat_session: Optional[ChatSession] = None
        self._current_on_tool: Optional[Callable[[str, Dict[str, Any], ToolResult], None]] = None

    @property
    def historial(self) -> List[Dict[str, Any]]:
        """Propiedad de compatibilidad que retorna el historial conversacional."""
        return self.memory.get_history()

    def nueva_conversacion(self) -> None:
        """Reinicia la memoria conversacional y descarta la sesión de chat activa."""
        self.memory.clear()
        self._chat_session = None

    def _obtener_o_crear_chat(
        self, on_tool_executed: Callable[[str, Dict[str, Any], ToolResult], None]
    ) -> ChatSession:
        """Crea o reutiliza la sesión de chat activa con el LLM Provider."""
        self._current_on_tool = on_tool_executed

        if self._chat_session is None:
            if not self.llm_provider:
                raise RuntimeError("No hay proveedor LLM configurado con credenciales válidas.")

            prompt_sistema = self.prompt_loader.cargar_prompt()

            # Callback wrapper que delega en el on_tool del turno actual
            def dispatch_tool_call(nombre: str, args: Dict[str, Any], res: ToolResult) -> None:
                if self._current_on_tool:
                    self._current_on_tool(nombre, args, res)

            self._chat_session = self.llm_provider.crear_chat(
                system=prompt_sistema,
                tools=self.tool_registry.all(),
                on_tool_executed=dispatch_tool_call,
            )

        return self._chat_session

    def responder(self, mensaje_usuario: str) -> Dict[str, Any]:
        """
        Procesa una consulta del usuario mediante Function Calling con el LLM.
        Si no hay credenciales o falla la conexión, activa el motor de Fallback analítico local.
        """
        trazabilidad: List[Dict[str, Any]] = []

        def capturar_trazabilidad(nombre: str, args: Dict[str, Any], res: ToolResult) -> None:
            trazabilidad.append(
                {
                    "herramienta": nombre,
                    "argumentos": args,
                    "resultado": res["texto"],
                    "datos": res["datos"],
                }
            )

        # Si no hay LLM Provider configurado, recurrir directamente a Fallback determinista
        if not self.llm_provider or not getattr(self.llm_provider, "api_key", True):
            resultado_fallback = self.fallback_engine.responder(mensaje_usuario, trazabilidad)
            self.memory.add_turn(mensaje_usuario, resultado_fallback["respuesta"], trazabilidad)
            return resultado_fallback

        try:
            chat = self._obtener_o_crear_chat(capturar_trazabilidad)
            respuesta_texto = chat.send_message(mensaje_usuario)

            self.memory.add_turn(mensaje_usuario, respuesta_texto, trazabilidad)
            modelo_usado = getattr(self.llm_provider, "model_name", "gemini")

            return {
                "respuesta": respuesta_texto,
                "trazabilidad": trazabilidad,
                "modelo": modelo_usado,
            }

        except Exception as e:
            logger.warning(f"Excepción en llamada LLM: {e}. Activando modo degradado determinista.")
            # Reiniciar chat en caso de error de sesión
            self._chat_session = None
            resultado_fallback = self.fallback_engine.responder(
                mensaje_usuario,
                trazabilidad,
                aviso_error=f"Aviso: Operando en modo analítico local debido a: {e}",
            )
            self.memory.add_turn(mensaje_usuario, resultado_fallback["respuesta"], trazabilidad)
            return resultado_fallback
