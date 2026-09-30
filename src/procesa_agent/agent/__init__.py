"""
Módulo del Agente de Consulta (procesa_agent.agent).
Expone el orquestador principal, la memoria conversacional, el cargador dinámico de prompts
y el motor de fallback analítico.
"""

from procesa_agent.agent.fallback import FallbackEngine
from procesa_agent.agent.memory import ConversationMemory, TurnoConversacion
from procesa_agent.agent.orchestrator import AgenteProyectos
from procesa_agent.agent.prompt_loader import PromptLoader

__all__ = [
    "AgenteProyectos",
    "ConversationMemory",
    "TurnoConversacion",
    "PromptLoader",
    "FallbackEngine",
]
