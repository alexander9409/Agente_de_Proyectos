"""Módulo puente de compatibilidad hacia atrás para src.mcp_server."""

from procesa_agent.interfaces.mcp.server import *  # noqa: F401, F403
from procesa_agent.interfaces.mcp.server import main

if __name__ == "__main__":
    main()
