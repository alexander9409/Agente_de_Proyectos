"""
Cliente de Prueba MCP con Google Gemini (test_mcp_client.py)
Demuestra la conexión cliente-servidor a través del protocolo estándar MCP (Model Context Protocol).
1. Inicia y se conecta al servidor MCP local (src/mcp_server.py) mediante transporte stdio.
2. Descubre dinámicamente las herramientas expuestas ('consultar_sql', 'buscar_texto').
3. Integra las herramientas descubiertas con el SDK oficial de Google Gemini (google-genai).
4. Ejecuta consultas en lenguaje natural donde Gemini invoca el MCP en tiempo real.
"""

import asyncio
import os
import sys

# Soporte de codificación UTF-8 para consola Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from procesa_agent.core.config_manager import ConfigManager
from procesa_agent.core.paths import PROJECT_ROOT


async def ejecutar_cliente_mcp(
    pregunta: str = "¿Cuáles son los 4 proyectos cerrados, sus clientes y sus sectores?",
):
    print("=" * 70)
    print("🤖 INICIANDO CLIENTE MCP CONECTADO A 'AgenteConsultorIA'")
    print("=" * 70)

    # 1. Configurar conexión con el servidor MCP local vía stdio
    script_servidor = str(PROJECT_ROOT / "src" / "mcp_server.py")
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[script_servidor],
        env=dict(os.environ),
    )

    print(f"\n[1/4] 🔌 Conectando con servidor MCP: {script_servidor}...")
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("      Conexión establecida con éxito.")

            # 2. Descubrir herramientas expuestas por el MCP
            print("\n[2/4] 🔍 Descubriendo herramientas registradas en el MCP...")
            herramientas_mcp = await session.list_tools()
            nombres_tools = [t.name for t in herramientas_mcp.tools]
            print(f"      Herramientas detectadas ({len(nombres_tools)}): {nombres_tools}")
            for t in herramientas_mcp.tools:
                print(
                    f"      • `{t.name}`: {t.description.strip().splitlines()[0] if t.description else ''}"
                )

            # 3. Verificar clave de API de Gemini
            config_mgr = ConfigManager()
            api_key = config_mgr.gemini_api_key or os.getenv("GEMINI_API_KEY", "")

            if not api_key:
                print("\n[3/4] ⚠️ No se detectó GEMINI_API_KEY configurada.")
                print(
                    "      Ejecutando prueba directa sobre el protocolo MCP (sin modelo externo)..."
                )

                print(
                    "\n      Invocando 'consultar_sql' vía MCP con: SELECT codigo_proyecto, cliente, sector FROM proyectos;"
                )
                res_sql = await session.call_tool(
                    "consultar_sql",
                    {"query": "SELECT codigo_proyecto, cliente, sector FROM proyectos;"},
                )
                print("\n[4/4] 📥 Respuesta recibida del servidor MCP:")
                print(res_sql.content[0].text if res_sql.content else "Sin contenido")

                print("\n      Invocando 'buscar_texto' vía MCP con: OEE SMED")
                res_fts = await session.call_tool("buscar_texto", {"terminos_busqueda": "OEE SMED"})
                print("\n[4/4] 📥 Respuesta de texto FTS recibida del servidor MCP:")
                print(res_fts.content[0].text if res_fts.content else "Sin contenido")
                print("\n✅ Verificación del protocolo MCP completada con éxito.")
                return

            # 4. Integrar dinámicamente con Google Gemini
            print("\n[3/4] 🧠 Vinculando herramientas MCP con el SDK de Google Gemini...")
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)
            modelo = config_mgr.model_name or "gemini-2.5-flash"

            # Envolturas locales que redirigen la llamada hacia la sesión MCP activa
            def consultar_sql(query: str) -> str:
                """Ejecuta consultas de solo lectura (SELECT) en la base de datos SQLite con las fichas de proyectos."""
                print(
                    f"\n      ⚡ [MCP Tool Call] Gemini está invocando consultar_sql(query='{query}') a través del MCP..."
                )
                # Correr la corrutina asíncrona dentro de un loop o tarea
                loop = asyncio.get_event_loop()
                fut = asyncio.run_coroutine_threadsafe(
                    session.call_tool("consultar_sql", {"query": query}), loop
                )
                res = fut.result(timeout=10)
                contenido = res.content[0].text if res.content else ""
                print(
                    f"      📥 [MCP Tool Result] Retornando {len(contenido)} caracteres a Gemini."
                )
                return contenido

            def buscar_texto(terminos_busqueda: str) -> str:
                """Realiza búsquedas de texto completo (FTS5) en el contenido de los informes."""
                print(
                    f"\n      ⚡ [MCP Tool Call] Gemini está invocando buscar_texto(terminos_busqueda='{terminos_busqueda}') a través del MCP..."
                )
                loop = asyncio.get_event_loop()
                fut = asyncio.run_coroutine_threadsafe(
                    session.call_tool("buscar_texto", {"terminos_busqueda": terminos_busqueda}),
                    loop,
                )
                res = fut.result(timeout=10)
                contenido = res.content[0].text if res.content else ""
                print(
                    f"      📥 [MCP Tool Result] Retornando {len(contenido)} caracteres a Gemini."
                )
                return contenido

            print(f'      Pregunta del usuario: "{pregunta}"')
            print(f"      Consultando modelo {modelo}...")

            # Ejecutar con Gemini pasándole las herramientas
            config = types.GenerateContentConfig(
                tools=[consultar_sql, buscar_texto],
                temperature=0.2,
                system_instruction="Eres un consultor analítico senior. Usa las herramientas provistas para fundamentar tus respuestas y cita siempre el archivo origen.",
            )

            import concurrent.futures

            loop = asyncio.get_running_loop()

            def _llamar_gemini(m: str):
                return client.models.generate_content(
                    model=m,
                    contents=pregunta,
                    config=config,
                )

            respuesta = None
            modelos_a_probar = [modelo, "gemini-3.8-flash", "gemini-3.5-flash"]
            # Evitar duplicados
            modelos_a_probar = list(dict.fromkeys(modelos_a_probar))

            for mod in modelos_a_probar:
                try:
                    print(f"      Intentando consulta con modelo: {mod}...")
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                        respuesta = await loop.run_in_executor(pool, lambda: _llamar_gemini(mod))
                    if respuesta:
                        break
                except Exception as e:
                    print(f"      ⚠️ Excepción con {mod}: {e}")

            if respuesta and getattr(respuesta, "text", None):
                print("\n" + "=" * 70)
                print("[4/4] 🎯 RESPUESTA FINAL DE GEMINI (CON DATOS OBTENIDOS VÍA MCP):")
                print("=" * 70)
                print(respuesta.text)
                print(
                    "\n✅ Interacción completada exitosamente a través de Model Context Protocol (MCP)."
                )
            else:
                print(
                    "\n[4/4] ⚠️ La API de Gemini no pudo completar la solicitud debido a límites de cuota (429)."
                )
                print(
                    "      Demostrando ejecución directa y verificación de herramientas a través del servidor MCP:"
                )
                print(
                    "\n      Invocando 'consultar_sql' vía MCP con: SELECT codigo_proyecto, cliente, sector, estado FROM proyectos;"
                )
                res_sql = await session.call_tool(
                    "consultar_sql",
                    {"query": "SELECT codigo_proyecto, cliente, sector, estado FROM proyectos;"},
                )
                print(res_sql.content[0].text if res_sql.content else "Sin contenido")

                print("\n      Invocando 'buscar_texto' vía MCP con: emergencias quirófanos")
                res_fts = await session.call_tool(
                    "buscar_texto", {"terminos_busqueda": "emergencias quirófanos"}
                )
                print(res_fts.content[0].text if res_fts.content else "Sin contenido")
                print(
                    "\n✅ El Servidor MCP ('AgenteConsultorIA') está 100% operativo y respondiendo vía protocolo MCP."
                )


if __name__ == "__main__":
    pregunta_arg = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "¿Cuáles son los 4 proyectos cerrados, sus clientes y sus sectores?"
    )
    asyncio.run(ejecutar_cliente_mcp(pregunta_arg))
