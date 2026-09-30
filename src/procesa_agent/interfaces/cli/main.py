"""
Interfaz de Línea de Comandos (CLI) de Procesa Consultores (interfaces/cli/main.py).
Ofrece subcomandos tipados con argparse: preguntar, ingestar, estado, mcp y modo interactivo.
Formateo rico con 'rich' si está disponible, o texto estructurado limpio por defecto.
"""

import argparse
import json
import sys
from typing import Any, List

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
from procesa_agent.agent.fallback import FallbackEngine
from procesa_agent.agent.orchestrator import AgenteProyectos
from procesa_agent.core.config_manager import ConfigManager
from procesa_agent.infrastructure.db.connection import (
    inicializar_bd,
    obtener_conexion,
    obtener_resumen_bd,
)
from procesa_agent.ingestion.pipeline import IngestionPipeline
from procesa_agent.tools.tools import consultar_sql

# Detección de biblioteca rich para presentación avanzada
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    TIENE_RICH = True
    console = Console()
except ImportError:
    TIENE_RICH = False
    console = None


def imprimir_panel(titulo: str, contenido: str, estilo: str = "blue") -> None:
    """Imprime un panel destacado usando rich o bordes ASCII como alternativa."""
    if TIENE_RICH and console:
        console.print(Panel(contenido, title=f"[bold]{titulo}[/bold]", border_style=estilo))
    else:
        linea = "=" * 70
        print(f"\n{linea}\n  {titulo.upper()}\n{linea}\n{contenido}\n{linea}")


def imprimir_tabla(titulo: str, columnas: List[str], filas: List[List[Any]]) -> None:
    """Imprime una tabla de datos usando rich.Table o formato tabular estándar."""
    if TIENE_RICH and console:
        table = Table(title=titulo)
        for col in columnas:
            table.add_column(col, style="cyan", no_wrap=False)
        for fila in filas:
            table.add_row(*[str(val) for val in fila])
        console.print(table)
    else:
        print(f"\n--- {titulo} ---")
        if not filas:
            print("  (Sin registros)")
            return
        header = " | ".join(columnas)
        sep = "-" * len(header)
        print(header)
        print(sep)
        for fila in filas:
            print(" | ".join(str(val) for val in fila))


def cmd_estado(args: argparse.Namespace) -> None:
    """Comando: muestra el estado integral de la base de datos y FTS5."""
    inicializar_bd()
    resumen = obtener_resumen_bd()

    conn = obtener_conexion()
    cursor = conn.cursor()
    proyectos = cursor.execute(
        "SELECT codigo_proyecto, cliente, sector, estado FROM proyectos ORDER BY codigo_proyecto;"
    ).fetchall()
    conn.close()

    contenido_resumen = (
        f"• Proyectos registrados : {resumen.get('proyectos', 0)}\n"
        f"• Métricas de KPIs      : {resumen.get('kpis', 0)}\n"
        f"• Lecciones aprendidas  : {resumen.get('lecciones', 0)}\n"
        f"• Secciones FTS5        : {resumen.get('fts', 0)}"
    )
    imprimir_panel("Estado del Repositorio de Proyectos", contenido_resumen, "green")

    cols = ["Código", "Cliente", "Sector", "Estado"]
    filas = [[p["codigo_proyecto"], p["cliente"], p["sector"], p["estado"]] for p in proyectos]
    imprimir_tabla("Portafolio Oficial de Proyectos", cols, filas)


def cmd_ingestar(args: argparse.Namespace) -> None:
    """Comando: ejecuta el pipeline de ingesta modular con detección SHA-256."""
    imprimir_panel(
        "Pipeline de Ingesta Documental",
        f"Iniciando ingesta... (Forzar: {args.force}, Archivo único: {args.solo or 'Todos'})",
        "cyan",
    )
    pipeline = IngestionPipeline()
    reporte = pipeline.ejecutar(force=args.force, solo_archivo=args.solo)

    filas = [
        ["Total detectados", str(reporte["total_archivos"])],
        [
            "Procesados con éxito",
            ", ".join(reporte["procesados"]) if reporte["procesados"] else "Ninguno",
        ],
        [
            "Omitidos (sin cambios SHA)",
            ", ".join(reporte["omitidos"]) if reporte["omitidos"] else "Ninguno",
        ],
        ["Fallidos", str(len(reporte["fallidos"]))],
    ]
    imprimir_tabla("Resultado del Lote de Ingesta", ["Métrica / Estado", "Detalle"], filas)

    if reporte["fallidos"]:
        print("\n❌ Errores detectados:")
        for f in reporte["fallidos"]:
            print(f"  • {f['archivo']}: {f['error']}")


def cmd_preguntar(args: argparse.Namespace) -> None:
    """Comando: ejecuta una consulta en modo agente, fallback o SQL directo."""
    inicializar_bd()
    consulta = args.consulta
    modo = args.modo

    if modo == "sql":
        imprimir_panel("Modo Consulta SQL Directa", f"Query: {consulta}", "yellow")
        res = consultar_sql(consulta)
        print(res)
        return

    if modo == "fallback":
        engine = FallbackEngine()
        res_dict = engine.responder(consulta)
    else:
        config_mgr = ConfigManager()
        agente = AgenteProyectos(config_mgr=config_mgr)
        res_dict = agente.responder(consulta)

    if args.verbose and res_dict.get("trazabilidad"):
        trazas = res_dict["trazabilidad"]
        filas_traza = []
        for t in trazas:
            h = t.get("herramienta", "")
            args_str = json.dumps(t.get("argumentos", {}), ensure_ascii=False)
            filas_traza.append([h, args_str])
        imprimir_tabla(
            "Trazabilidad de Herramientas Utilizadas", ["Herramienta", "Argumentos"], filas_traza
        )

    imprimir_panel("Respuesta Oficial", res_dict.get("respuesta", ""), "blue")


def cmd_mcp(args: argparse.Namespace) -> None:
    """Comando: inicia el servidor MCP estándar en transporte stdio."""
    imprimir_panel(
        "Servidor MCP (Model Context Protocol)",
        "Iniciando servidor MCP sobre stdio... Presiona Ctrl+C para detener.",
        "magenta",
    )
    from procesa_agent.interfaces.mcp.server import mcp

    mcp.run()


def bucle_interactivo() -> None:
    """Modo REPL interactivo cuando el comando se ejecuta sin argumentos."""
    inicializar_bd()
    config_mgr = ConfigManager()
    agente = AgenteProyectos(config_mgr=config_mgr)
    resumen = obtener_resumen_bd()

    imprimir_panel(
        "Procesa Consultores · CLI Interactivo",
        f"Proyectos: {resumen.get('proyectos', 0)} | KPIs: {resumen.get('kpis', 0)} | FTS5: {resumen.get('fts', 0)}\n"
        "Comandos disponibles: 'salir', 'estado', 'ayuda'",
        "blue",
    )

    while True:
        try:
            linea = input("\nConsultor > ").strip()
            if not linea:
                continue
            cmd = linea.lower()
            if cmd in ["salir", "exit", "quit", "q"]:
                print("\n👋 Sesión interactiva finalizada.")
                break
            elif cmd in ["estado", "status"]:
                cmd_estado(argparse.Namespace())
                continue
            elif cmd in ["ayuda", "help", "?"]:
                print("\n💡 Ejemplos de consulta:")
                print("  • ¿Cuáles fueron los resultados principales de KPIs?")
                print("  • ¿Qué proyectos se cerraron con pendientes y por qué?")
                print("  • ¿Qué lecciones aprendidas se registraron sobre gestión del cambio?\n")
                continue

            res = agente.responder(linea)
            trazabilidad = res.get("trazabilidad", [])
            if trazabilidad:
                for t in trazabilidad:
                    print(f"  [Tool] {t.get('herramienta')}: {t.get('argumentos')}")

            print("\n[RESPUESTA]:")
            print(res.get("respuesta", ""))
            print("-" * 65)

        except (KeyboardInterrupt, EOFError):
            print("\n👋 Sesión interrumpida.")
            break


def main() -> None:
    """Punto de entrada principal con parser de subcomandos."""
    parser = argparse.ArgumentParser(
        prog="procesa",
        description="CLI Oficial de Procesa Consultores · Inteligencia Operativa de Proyectos",
    )
    subparsers = parser.add_subparsers(dest="subcomando", help="Subcomandos disponibles")

    # Subcomando: preguntar
    p_preguntar = subparsers.add_parser("preguntar", help="Realiza una consulta al agente")
    p_preguntar.add_argument("consulta", type=str, help="Texto de la consulta")
    p_preguntar.add_argument(
        "--modo",
        choices=["agente", "fallback", "sql"],
        default="agente",
        help="Modo de ejecución de la consulta (default: agente)",
    )
    p_preguntar.add_argument(
        "--verbose", action="store_true", help="Muestra la trazabilidad de herramientas utilizadas"
    )

    # Subcomando: ingestar
    p_ingestar = subparsers.add_parser(
        "ingestar", help="Ejecuta el pipeline de ingesta de informes"
    )
    p_ingestar.add_argument(
        "--force", action="store_true", help="Fuerza el reprocesamiento ignorando hashes SHA-256"
    )
    p_ingestar.add_argument(
        "--solo", type=str, default=None, help="Nombre del archivo individual a procesar"
    )

    # Subcomando: estado
    subparsers.add_parser("estado", help="Muestra el resumen y estado del repositorio de proyectos")

    # Subcomando: mcp
    subparsers.add_parser("mcp", help="Inicia el servidor MCP (Model Context Protocol)")

    args = parser.parse_args()

    if args.subcomando == "preguntar":
        cmd_preguntar(args)
    elif args.subcomando == "ingestar":
        cmd_ingestar(args)
    elif args.subcomando == "estado":
        cmd_estado(args)
    elif args.subcomando == "mcp":
        cmd_mcp(args)
    else:
        bucle_interactivo()


if __name__ == "__main__":
    main()
