"""
Cargador Dinámico de Prompts del Sistema (agent/prompt_loader.py).
Lee prompts/system_agente.md e inyecta dinámicamente en tiempo de ejecución:
1. Esquema de tablas introspectado de sqlite_master (restringido a tablas permitidas).
2. Lista de proyectos registrados en la base de datos.
3. Reglas de negocio y criterios de prevalencia desde la tabla reglas_negocio.
Garantiza cero hardcoding de datos de negocio en el código Python y en las plantillas.
"""

from pathlib import Path
from typing import Optional

from procesa_agent.core.paths import PROMPTS_DIR
from procesa_agent.infrastructure.db.connection import TABLAS_PERMITIDAS, obtener_conexion
from procesa_agent.infrastructure.db.repositories.reglas_repo import ReglasRepository

PROMPT_SISTEMA_DEFAULT = PROMPTS_DIR / "system_agente.md"


class PromptLoader:
    """Gestiona la lectura, introspección e inyección dinámica del prompt del sistema."""

    def __init__(
        self,
        db_path: Optional[str] = None,
        template_path: Optional[Path] = None,
    ) -> None:
        self.db_path = db_path
        self.template_path = template_path or PROMPT_SISTEMA_DEFAULT

    def _introspectar_esquema(self, conn) -> str:
        """Introspecta las columnas y tipos de las tablas permitidas desde SQLite."""
        cursor = conn.cursor()
        bloques = []

        for tabla in sorted(TABLAS_PERMITIDAS):
            # Obtener columnas vía PRAGMA table_info
            try:
                cols = cursor.execute(f"PRAGMA table_info({tabla});").fetchall()
                if cols:
                    lineas_col = [f"   - {c['name']} ({c['type']})" for c in cols]
                    bloques.append(f"• Tabla `{tabla}`:\n" + "\n".join(lineas_col))
                elif tabla == "informes_fts":
                    bloques.append(
                        "• Tabla virtual `informes_fts` (FTS5):\n"
                        "   - codigo_proyecto (UNINDEXED)\n"
                        "   - archivo_origen (UNINDEXED)\n"
                        "   - seccion\n"
                        "   - contenido"
                    )
            except Exception:
                continue

        return "\n\n".join(bloques)

    def _consultar_proyectos(self, conn) -> str:
        """Consulta la lista de proyectos registrados dinámicamente en la base de datos."""
        cursor = conn.cursor()
        try:
            filas = cursor.execute(
                "SELECT codigo_proyecto, cliente, sector, gerente_proyecto, estado FROM proyectos ORDER BY codigo_proyecto;"
            ).fetchall()
            if not filas:
                return "*(Actualmente no hay proyectos registrados en la base de datos)*"

            lineas = []
            for r in filas:
                lineas.append(
                    f"- **{r['codigo_proyecto']}**: Cliente: *{r['cliente']}* | Sector: {r['sector']} | "
                    f"Gerente de Proyecto: {r['gerente_proyecto']} | Estado: `{r['estado']}`"
                )
            return "\n".join(lineas)
        except Exception:
            return "*(No fue posible consultar los proyectos registrados)*"

    def _consultar_reglas(self) -> str:
        """Recupera las reglas de negocio registradas en la tabla reglas_negocio."""
        repo = ReglasRepository(self.db_path)
        reglas = repo.obtener_todas()
        if not reglas:
            return "*(No hay reglas de negocio o discrepancias registradas en la base de datos)*"

        lineas = []
        for r in reglas:
            alcance = f"Proyecto {r.codigo_proyecto}" if r.codigo_proyecto else "Regla Global"
            fuente_str = f" [Sustento: {r.fuente}]" if r.fuente else ""
            lineas.append(
                f"- **[{alcance} - {r.tipo.upper()}] {r.titulo}:**\n  {r.descripcion}{fuente_str}"
            )
        return "\n\n".join(lineas)

    def cargar_prompt(self) -> str:
        """Lee la plantilla Markdown e inyecta dinámicamente el contexto de la base de datos."""
        if not self.template_path.exists():
            raise FileNotFoundError(f"Plantilla de prompt no encontrada en: {self.template_path}")

        with open(self.template_path, "r", encoding="utf-8") as f:
            template = f.read()

        conn = obtener_conexion(self.db_path)
        try:
            esquema_str = self._introspectar_esquema(conn)
            proyectos_str = self._consultar_proyectos(conn)
        finally:
            conn.close()

        reglas_str = self._consultar_reglas()

        # Inyección dinámica en los placeholders
        prompt_final = template.replace("{{TABLAS_ESQUEMA}}", esquema_str)
        prompt_final = prompt_final.replace("{{PROYECTOS_REGISTRADOS}}", proyectos_str)
        prompt_final = prompt_final.replace("{{REGLAS_NEGOCIO}}", reglas_str)

        return prompt_final
