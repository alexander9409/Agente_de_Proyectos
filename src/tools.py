"""
Módulo de Herramientas del Agente (src/tools.py)
Implementa consultar_sql (consultas SELECT con validación de seguridad)
y buscar_texto (búsqueda léxica y semántica sobre la tabla virtual FTS5).
"""

import re
import sqlite3
from typing import Optional

from src.db import get_default_db_path, obtener_conexion

PALABRAS_PROHIBIDAS_SQL = [
    r"\bINSERT\b",
    r"\bUPDATE\b",
    r"\bDELETE\b",
    r"\bDROP\b",
    r"\bALTER\b",
    r"\bCREATE\b",
    r"\bATTACH\b",
    r"\bDETACH\b",
    r"\bTRUNCATE\b",
    r"\bEXEC\b",
    r"\bPRAGMA\b",
    r"\bVACUUM\b",
]


def validar_seguridad_sql(query: str) -> None:
    """
    Verifica que el query sea exclusivamente de solo lectura (SELECT / WITH).
    Lanza PermissionError si se detecta cualquier instrucción DDL o DML peligrosa.
    """
    query_limpio = query.strip()
    if not (query_limpio.upper().startswith("SELECT") or query_limpio.upper().startswith("WITH")):
        raise PermissionError(
            "Seguridad violada: Solo se permiten consultas de solo lectura que inicien con SELECT o WITH."
        )

    for patron in PALABRAS_PROHIBIDAS_SQL:
        if re.search(patron, query_limpio, re.IGNORECASE):
            palabra = patron.replace(r"\b", "")
            raise PermissionError(
                f"Seguridad violada: La sentencia contiene la palabra clave no permitida '{palabra}'."
            )


def consultar_sql_detallado(query: str, db_path: Optional[str] = None) -> tuple[str, list[dict]]:
    """
    Ejecuta una consulta SQL de solo lectura (SELECT) sobre la base de datos SQLite.
    Retorna una tupla: (tabla_markdown, lista_de_diccionarios_con_las_filas).
    """
    try:
        validar_seguridad_sql(query)
    except PermissionError as pe:
        return f"Error de seguridad: {pe}", []

    conn = None
    try:
        conn = obtener_conexion(db_path)
        cursor = conn.cursor()
        cursor.execute(query)
        filas = cursor.fetchall()

        if not filas:
            return "La consulta SQL se ejecutó exitosamente pero no arrojó ninguna fila (0 resultados).", []

        # Convertir a lista de diccionarios
        datos_dict = [dict(fila) for fila in filas]

        # Obtener nombres de columnas
        columnas = [desc[0] for desc in cursor.description]

        # Construir tabla en Markdown
        header = "| " + " | ".join(columnas) + " |"
        separator = "| " + " | ".join(["---"] * len(columnas)) + " |"
        lineas = [header, separator]

        for fila in filas:
            valores = [str(fila[col]) if fila[col] is not None else "NULL" for col in columnas]
            valores = [v.replace("\n", " ").replace("\r", " ") for v in valores]
            lineas.append("| " + " | ".join(valores) + " |")

        resultado_md = "\n".join(lineas)
        total_filas = len(filas)
        res_final = f"{resultado_md}\n\n*Total: {total_filas} fila(s) obtenida(s).*"
        return res_final, datos_dict

    except sqlite3.Error as e:
        return f"Error de sintaxis o ejecución SQL: {e}", []
    except Exception as ex:
        return f"Error inesperado al ejecutar SQL: {ex}", []
    finally:
        if conn:
            conn.close()


def consultar_sql(query: str, db_path: Optional[str] = None) -> str:
    """
    Ejecuta una consulta SQL de solo lectura (SELECT) sobre la base de datos SQLite
    de proyectos, métricas (kpis) y lecciones aprendidas.
    Retorna el resultado formateado en una tabla Markdown legible.
    """
    resultado_md, _ = consultar_sql_detallado(query, db_path)
    return resultado_md


def sanitizar_termino_fts(termino: str) -> str:
    """
    Limpia y estructura los términos de búsqueda para la sintaxis FTS5 de SQLite,
    utilizando AND entre palabras para asegurar alta precisión y evitar falsos positivos.
    """
    # Si viene entre comillas explícitas, respetar la búsqueda por frase
    termino_strip = termino.strip()
    if termino_strip.startswith('"') and termino_strip.endswith('"') and len(termino_strip) > 2:
        contenido = re.sub(r'[^\w\s\u00C0-\u017F]', ' ', termino_strip[1:-1]).strip()
        return f'"{contenido}"'

    # Eliminar caracteres especiales que rompen FTS5
    termino_limpio = re.sub(r'[^\w\s\u00C0-\u017F]', ' ', termino).strip()
    palabras = [p for p in termino_limpio.split() if len(p) >= 2]
    if not palabras:
        return f'"{termino.strip()}"'

    # Unir palabras con AND para que todas deban coocurrir en la sección
    return " AND ".join([f'"{p}"*' for p in palabras])


def buscar_texto_detallado(terminos_busqueda: str, db_path: Optional[str] = None) -> tuple[str, list[dict]]:
    """
    Realiza una búsqueda léxica y de texto completo sobre los informes de cierre.
    Retorna una tupla: (texto_markdown_formateado, lista_de_diccionarios_con_coincidencias).
    """
    if not terminos_busqueda or not terminos_busqueda.strip():
        return "Debe proporcionar al menos un término para buscar en los informes.", []

    conn = None
    try:
        conn = obtener_conexion(db_path)
        cursor = conn.cursor()

        consulta_fts = sanitizar_termino_fts(terminos_busqueda)

        # Intentar búsqueda MATCH en FTS5
        sql_match = """
        SELECT codigo_proyecto, archivo_origen, seccion,
               snippet(informes_fts, 3, '**', '**', '...', 35) AS fragmento,
               contenido
        FROM informes_fts
        WHERE informes_fts MATCH ?
        ORDER BY rank
        LIMIT 6;
        """

        try:
            cursor.execute(sql_match, (consulta_fts,))
            filas = cursor.fetchall()
        except sqlite3.OperationalError:
            # Fallback a búsqueda con comodín simple o LIKE
            sql_fallback = """
            SELECT codigo_proyecto, archivo_origen, seccion,
                   substr(contenido, 1, 300) AS fragmento,
                   contenido
            FROM informes_fts
            WHERE contenido LIKE ?
            LIMIT 6;
            """
            cursor.execute(sql_fallback, (f"%{terminos_busqueda.strip()}%",))
            filas = cursor.fetchall()

        if not filas:
            return (
                f"No se encontraron fragmentos relevantes para los términos de búsqueda: '{terminos_busqueda}' "
                f"en los textos completos de los informes.",
                []
            )

        bloques = []
        coincidencias_dict = []
        for idx, fila in enumerate(filas, start=1):
            codigo = fila["codigo_proyecto"]
            archivo = fila["archivo_origen"]
            seccion = fila["seccion"]
            frag = fila["fragmento"] or ""
            if len(frag.strip()) < 40 and fila["contenido"]:
                frag = fila["contenido"][:300] + "..."

            bloques.append(
                f"#### Coincidencia #{idx}\n"
                f"- **Proyecto:** `{codigo}`\n"
                f"- **Archivo fuente:** `{archivo}`\n"
                f"- **Sección:** *{seccion}*\n"
                f"- **Extracto relevante:**\n> {frag.strip()}\n"
            )
            coincidencias_dict.append({
                "coincidencia": idx,
                "codigo_proyecto": codigo,
                "archivo_origen": archivo,
                "seccion": seccion,
                "extracto": frag.strip(),
            })

        return "\n".join(bloques), coincidencias_dict

    except Exception as e:
        return f"Error al ejecutar la búsqueda de texto: {e}", []
    finally:
        if conn:
            conn.close()


def buscar_texto(terminos_busqueda: str, db_path: Optional[str] = None) -> str:
    """
    Realiza una búsqueda léxica y de texto completo sobre los informes de cierre
    indexados en la tabla virtual SQLite FTS5 (informes_fts).
    Devuelve los fragmentos más relevantes junto con el archivo de origen y la sección.
    """
    res_md, _ = buscar_texto_detallado(terminos_busqueda, db_path)
    return res_md
