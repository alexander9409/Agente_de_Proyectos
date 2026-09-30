"""
Módulo de Proveedores de Modelos de Lenguaje (procesa_agent.infrastructure.llm).
Expone interfaces abstractas (LLMProvider, ChatSession), la implementación oficial (GeminiProvider)
y el proveedor simulado para pruebas unitarias (FakeLLM).
"""

from procesa_agent.infrastructure.llm.base import ChatSession, LLMProvider
from procesa_agent.infrastructure.llm.fake import FakeChatSession, FakeLLM
from procesa_agent.infrastructure.llm.gemini import GeminiChatSession, GeminiProvider

__all__ = [
    "ChatSession",
    "LLMProvider",
    "GeminiProvider",
    "GeminiChatSession",
    "FakeLLM",
    "FakeChatSession",
]
