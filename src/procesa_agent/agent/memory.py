"""
Memoria Conversacional y Gestión de Historial (agent/memory.py).
Mantiene el historial de la sesión con ventana deslizante configurable (últimos N turnos)
para evitar desbordamiento de contexto y permitir diálogos multi-turno coherentes.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TurnoConversacion(BaseModel):
    """Representa un turno individual de interacción usuario-asistente."""

    usuario: str = Field(description="Mensaje del usuario")
    asistente: str = Field(description="Respuesta generada por el agente")
    trazabilidad: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Eventos de invocación de herramientas ejecutadas durante el turno",
    )


class ConversationMemory:
    """Gestiona la memoria y el historial conversacional con ventana delimitada."""

    def __init__(self, max_turns: int = 10) -> None:
        self.max_turns = max_turns
        self._turnos: List[TurnoConversacion] = []

    def add_turn(
        self,
        usuario: str,
        asistente: str,
        trazabilidad: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Agrega un nuevo turno de conversación respetando el límite máximo de turnos."""
        turno = TurnoConversacion(
            usuario=usuario,
            asistente=asistente,
            trazabilidad=trazabilidad or [],
        )
        self._turnos.append(turno)
        if len(self._turnos) > self.max_turns:
            self._turnos = self._turnos[-self.max_turns :]

    def get_history(self) -> List[Dict[str, Any]]:
        """Retorna el historial completo de turnos en formato de lista de diccionarios."""
        return [t.model_dump() for t in self._turnos]

    def clear(self) -> None:
        """Reinicia la memoria y elimina todo el historial conversacional."""
        self._turnos.clear()

    def __len__(self) -> int:
        return len(self._turnos)
