"""
Componente de Chat y Trazabilidad de Herramientas (interfaces/web/components/chat.py).
Renderiza el historial de mensajes, avatares diferenciados y el inspector de ejecuciones de herramientas.
"""

from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from procesa_agent.interfaces.web.components.fuentes_viewer import resaltar_fuentes


def tabla_markdown_a_dataframe(texto_md: str) -> Optional[pd.DataFrame]:
    """Convierte una tabla en formato Markdown en un DataFrame de Pandas estructurado."""
    lineas = [
        linea.strip() for linea in texto_md.strip().split("\n") if linea.strip().startswith("|")
    ]
    if len(lineas) < 3:
        return None
    try:
        encabezados = [c.strip() for c in lineas[0].strip("|").split("|")]
        filas = []
        for linea in lineas[2:]:
            if not linea.startswith("|"):
                continue
            valores = [c.strip() for c in linea.strip("|").split("|")]
            if len(valores) == len(encabezados):
                filas.append(valores)
        if filas:
            return pd.DataFrame(filas, columns=encabezados)
    except Exception:
        pass
    return None


def renderizar_trazabilidad(
    trazabilidad: List[Dict[str, Any]], expandido: bool = False
) -> None:
    """Renderiza la trazabilidad de herramientas utilizadas por el agente sin textos truncados."""
    if not trazabilidad:
        return

    with st.expander(
        f"🛠️ Ver trazabilidad analítica ({len(trazabilidad)} herramienta(s) ejecutada(s))",
        expanded=expandido,
    ):
        for idx, t in enumerate(trazabilidad, start=1):
            herramienta = t.get("herramienta", "desconocida")
            argumentos = t.get("argumentos", {})
            datos_estructurados = t.get("datos", [])
            resultado_crudo = t.get("resultado", "")

            st.markdown(f"#### Invocación #{idx}: `{herramienta}`")

            if herramienta == "consultar_sql":
                query_sql = argumentos.get("query", "")
                st.caption("Sentencia SQL ejecutada contra SQLite:")
                st.code(query_sql, language="sql")

                df = None
                if datos_estructurados and isinstance(datos_estructurados, list):
                    df = pd.DataFrame(datos_estructurados)
                elif resultado_crudo:
                    df = tabla_markdown_a_dataframe(resultado_crudo)

                if df is not None and not df.empty:
                    st.caption(f"📊 **Resultados obtenidos:** {len(df)} fila(s) relacional(es)")
                    st.dataframe(df, use_container_width=True, hide_index=True)
                else:
                    st.info(resultado_crudo)

            elif herramienta == "buscar_texto":
                terminos = argumentos.get("terminos_busqueda", "")
                st.caption(f"Términos enviados al índice virtual FTS5: **`{terminos}`**")

                if datos_estructurados and isinstance(datos_estructurados, list):
                    st.caption(
                        f"🔍 **Fragmentos localizados:** {len(datos_estructurados)} coincidencia(s)"
                    )
                    for c in datos_estructurados:
                        st.markdown(
                            f"**Coincidencia #{c.get('coincidencia', '')}** · "
                            f"`{c.get('codigo_proyecto', '')}` · "
                            f"*{c.get('seccion', '')}* "
                            f"(`{c.get('archivo_origen', '')}`)"
                        )
                        st.info(c.get("extracto", ""))
                else:
                    st.markdown(resultado_crudo)

            st.divider()


def renderizar_historial_chat(mensajes: List[Dict[str, Any]]) -> None:
    """Renderiza la lista completa de mensajes con avatares corporativos y formato rico."""
    total = len(mensajes)
    for idx, mensaje in enumerate(mensajes):
        rol = mensaje.get("rol", "user")
        avatar = "👤" if rol == "user" else "💼"

        with st.chat_message(rol, avatar=avatar):
            if rol == "assistant":
                contenido = mensaje.get("contenido", "")
                st.markdown(resaltar_fuentes(contenido), unsafe_allow_html=True)
                trazabilidad = mensaje.get("trazabilidad", [])
                es_ultimo = idx == total - 1
                renderizar_trazabilidad(trazabilidad, expandido=es_ultimo)
            else:
                st.markdown(mensaje.get("contenido", ""))
