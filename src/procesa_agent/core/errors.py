"""
Módulo de excepciones de dominio del sistema.
"""


class ProcesaAgentError(Exception):
    """Excepción base del sistema."""

    pass


ProcesaError = ProcesaAgentError


class SecurityError(ProcesaAgentError):
    """Excepción disparada por violación de seguridad SQL o acceso indebido a recursos."""

    pass


class LLMProviderError(ProcesaAgentError):
    """Error al comunicarse con el proveedor del modelo de lenguaje."""

    pass


class IngestionError(ProcesaAgentError):
    """Error durante el pipeline de ingesta o lectura de archivos."""

    pass
