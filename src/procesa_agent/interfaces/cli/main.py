"""
Interfaz CLI por Consola Interactiva (procesa_agent/interfaces/cli/main.py)
Bucle REPL con trazabilidad visual de herramientas, citación de fuentes
y comandos de gestión para el Agente de Proyectos de Procesa Consultores.
"""

import json
import sys

# Configurar salida UTF-8 en terminales de Windows
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from procesa_agent.agent.orchestrator import AgenteProyectos
from procesa_agent.core.config_manager import ConfigManager
from procesa_agent.infrastructure.db.connection import inicializar_bd, obtener_resumen_bd
from procesa_agent.ingestion.extractor import ejecutar_ingesta_completa


def imprimir_bienvenida(config_mgr: ConfigManager, resumen: dict):
    print("=" * 75)
    print("   PROCESA CONSULTORES · SISTEMA DE CONSULTA DE PROYECTOS")
    print("   Agente Inteligente con SQLite, Búsqueda FTS5 y Google Gemini")
    print("=" * 75)
    print(
        f"📊 Estado Base de Datos: {resumen['proyectos']} Proyectos | {resumen['kpis']} KPIs | {resumen['lecciones']} Lecciones"
    )

    api_key = config_mgr.gemini_api_key
    if api_key:
        mascarada = api_key[:6] + "..." + api_key[-4:] if len(api_key) > 10 else "***"
        print(f"🔑 Gemini API Key: ACTIVA ({mascarada}) | Modelo: {config_mgr.model_name}")
    else:
        print("⚠️ Gemini API Key: NO DETECTADA.")
        print("   (El agente operará en Modo Analítico Local con acceso directo a SQLite y FTS5)")
        print(
            "   Para activar Gemini, configura GEMINI_API_KEY en .env o en la UI con: streamlit run app.py"
        )

    print("-" * 75)
    print("Escribe tu consulta o usa uno de los comandos:")
    print("  'salir'   : Finalizar la sesión")
    print("  'ayuda'   : Ver ejemplos de consultas sugeridas")
    print("  'estado'  : Ver métricas actuales de la base de datos")
    print("=" * 75)


def mostrar_ayuda():
    print("\n💡 Ejemplos de consultas que puedes realizar:")
    print("  1. ¿Cuáles fueron los resultados de OEE en Plásticos del Pacífico?")
    print("  2. ¿Se logró la integración con proveedores en Supermercados La Canasta?")
    print("  3. ¿Cuánto se redujo el tiempo de espera en la Clínica Santa Lucía?")
    print("  4. ¿Qué lecciones aprendidas se registraron sobre gestión del cambio?")
    print("  5. ¿Qué proyectos lideró la Ing. Daniela Cevallos?")
    print("  6. ¿Qué proyectos se realizaron para Banco Pichincha? (Prueba anti-alucinación)\n")


def formatear_resultado_tool(resultado: str, nombre_tool: str) -> str:
    """Extrae un resumen conciso de los resultados para la traza del terminal."""
    if nombre_tool == "consultar_sql":
        lineas = resultado.strip().split("\n")
        filas_datos = [linea for linea in lineas if linea.startswith("|") and "---" not in linea]
        total_filas = max(0, len(filas_datos) - 1) if filas_datos else 0
        return f"{total_filas} fila(s) obtenida(s)."
    elif nombre_tool == "buscar_texto":
        num_coincidencias = resultado.count("#### Coincidencia")
        return f"{num_coincidencias} fragmento(s) documental(es) coincidente(s)."
    return "Resultado procesado."


def main():
    inicializar_bd()
    resumen = obtener_resumen_bd()
    if resumen["proyectos"] == 0:
        print("⏳ Ingestando informes iniciales...")
        ejecutar_ingesta_completa()
        resumen = obtener_resumen_bd()

    config_mgr = ConfigManager()
    agente = AgenteProyectos(config_mgr)

    imprimir_bienvenida(config_mgr, resumen)

    while True:
        try:
            entrada = input("\nConsultor > ").strip()
            if not entrada:
                continue

            comando = entrada.lower()
            if comando in ["salir", "exit", "quit", "q"]:
                print("\n👋 Sesión finalizada. ¡Hasta pronto!")
                break
            elif comando in ["ayuda", "help", "?"]:
                mostrar_ayuda()
                continue
            elif comando in ["estado", "status"]:
                stats = obtener_resumen_bd()
                print(f"\n📊 Estadísticas actuales: {stats}")
                continue

            # Procesar consulta con el agente
            respuesta_dict = agente.responder(entrada)

            # Imprimir trazabilidad de herramientas utilizadas
            trazabilidad = respuesta_dict.get("trazabilidad", [])
            if trazabilidad:
                print()
                for traza in trazabilidad:
                    t_name = traza.get("herramienta", "desconocida")
                    t_args = json.dumps(traza.get("argumentos", {}), ensure_ascii=False)
                    t_res_raw = traza.get("resultado", "")
                    resumen_res = formatear_resultado_tool(t_res_raw, t_name)

                    print(f"[TOOL CALL] -> Herramienta: {t_name} | Args: {t_args}")
                    print(f"[TOOL RESULT] -> {resumen_res}")
                print()

            # Imprimir respuesta final
            print("[RESPUESTA]:")
            print(respuesta_dict.get("respuesta", ""))
            print("-" * 75)

        except (KeyboardInterrupt, EOFError):
            print("\n\n👋 Operación cancelada. Sesión terminada.")
            break
        except Exception as e:
            print(f"\n❌ Error al procesar consulta: {e}")


if __name__ == "__main__":
    main()
