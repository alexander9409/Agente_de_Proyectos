# INSTRUCCIÓN DE INGENIERÍA: AGENTE DE CONSULTA DE PROYECTOS (GEMINI + SQLITE + STREAMLIT)

Actúa como un Tech Lead e Ingeniero de Inteligencia Artificial Senior. Tu tarea es inicializar, codificar y documentar una solución integral en Python dentro del repositorio Git actual llamado `Agente_de_Proyectos`.

---

## 1. CONTEXTO Y CASO DE NEGOCIO
"Procesa Consultores" es una firma de consultoría de optimización de procesos que ha cerrado cuatro proyectos documentados en informes heterogéneos (tres en PDF y uno en DOCX):
1. `Informe_Cierre_PC-2025-014_Cooperativa_Horizonte_Andino.pdf` (Servicios financieros)
2. `Informe_Cierre_PC-2025-027_Plasticos_del_Pacifico.pdf` (Manufactura)
3. `Informe_Cierre_PC-2025-033_Clinica_Santa_Lucia.docx` (Salud)
4. `Informe_Cierre_PC-2026-006_Supermercados_La_Canasta.pdf` (Retail)

El sistema debe:
1. Extraer fichas estructuradas de los informes usando la API de **Google Gemini** con tipado estricto (Pydantic).
2. Persistir las fichas en formato JSON individual y en una base de datos relacional local en **SQLite** (`data/database.sqlite`).
3. Permitir guardar y editar la API Key de Gemini y configuraciones del modelo directamente desde la interfaz en una tabla dedicada en SQLite (`configuraciones`).
4. Proveer un agente con dos herramientas mínimas:
   - `consultar_sql`: Generación y ejecución de queries `SELECT` sobre SQLite para métricas, conteos y filtros relacionales.
   - `buscar_texto`: Búsqueda léxica y semántica sobre el texto íntegro de los informes indexado en una tabla virtual SQLite FTS5.
5. Garantizar **trazabilidad explícita** de herramientas utilizadas, **citación estricta de la fuente** documental y **cero alucinaciones** (si algo no se encuentra documentado, debe declararlo expresamente).
6. Disponer de doble interfaz: **Interfaz Gráfica Web interactiva (Streamlit)** y **Consola interactiva CLI (main.py)**.

---

## 2. ESTRUCTURA MODULAR DEL REPOSITORIO

Genera exactamente el siguiente árbol de archivos dentro de `Agente_de_Proyectos/`:

```text
Agente_de_Proyectos/
├── data/
│   ├── raw/                  # Contiene los 4 archivos de entrada (3 PDF, 1 DOCX)
│   ├── fichas/               # Almacena los 4 archivos JSON extraídos ({codigo_proyecto}.json)
│   └── database.sqlite       # Base de datos SQLite creada automáticamente
├── src/
│   ├── __init__.py
│   ├── models.py             # Esquemas Pydantic para extracción y validación
│   ├── config_manager.py     # Gestor de configuración (CRUD sobre tabla SQLite 'configuraciones' y fallback a .env)
│   ├── db.py                 # DDL, conexión con foreign keys y funciones de consulta
│   ├── parser.py             # Lector universal para PDFs (pypdf) y DOCX (python-docx)
│   ├── extractor.py          # Pipeline de extracción con Gemini (response_schema=FichaProyecto)
│   ├── tools.py              # Definición e implementación de las herramientas (SQL y FTS5)
│   └── agent.py              # Orquestador del agente con Gemini (Tool Calling, trazabilidad y memoria)
├── tests/
│   ├── __init__.py
│   └── test_agent.py         # Suite de pruebas automatizadas con pytest (exactitud de datos y fallback)
├── app.py                    # Interfaz Gráfica interactiva en Streamlit (Chat + Explorador BD + Configuración)
├── main.py                   # Interfaz por Consola CLI (REPL interactivo con trazabilidad)
├── requirements.txt          # Dependencias del proyecto
├── .env.example              # Plantilla para variables de entorno locales
├── .gitignore                # Reglas de exclusión para Git (.env, database.sqlite, caches)
└── README.md                 # Documentación técnica, justificación de arquitectura y costeo para 50 usuarios
```
