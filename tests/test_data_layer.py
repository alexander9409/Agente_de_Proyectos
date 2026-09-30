"""
Tests unitarios para la capa de datos modular (Fase 3).
Verifica:
1. Versionado y migraciones de esquema (user_version v1 y v2).
2. Repositorio de reglas de negocio (idempotencia, filtrado, modelos).
3. Repositorio de proyectos, KPIs y lecciones (round-trip, JSON serialization).
4. Repositorio de configuraciones.
5. Repositorio FTS5.
6. Permisos de solo lectura para la nueva tabla reglas_negocio.
"""

import json
import sqlite3

import pytest

from procesa_agent.core.paths import FICHAS_DIR
from procesa_agent.domain.models import FichaProyecto, Iniciativa, LeccionAprendida, MetricaKPI
from procesa_agent.infrastructure.db.connection import (
    conexion_solo_lectura,
    obtener_conexion,
)
from procesa_agent.infrastructure.db.repositories.config_repo import ConfigRepository
from procesa_agent.infrastructure.db.repositories.fts_repo import FTSRepository
from procesa_agent.infrastructure.db.repositories.proyectos_repo import ProyectosRepository
from procesa_agent.infrastructure.db.repositories.reglas_repo import ReglasRepository
from procesa_agent.infrastructure.db.schema import (
    _migrar_v1,
    inicializar_o_migrar_bd,
)


def test_migracion_esquema_incremental(tmp_path):
    """Verifica que la migración incremental funcione paso a paso usando user_version."""
    db_file = str(tmp_path / "test_migration.sqlite")
    conn = sqlite3.connect(db_file)

    # Inicialmente la versión es 0
    v0 = conn.execute("PRAGMA user_version;").fetchone()[0]
    assert v0 == 0

    # Migrar a v1 manualmente
    _migrar_v1(conn)
    conn.execute("PRAGMA user_version = 1;")
    conn.commit()
    assert conn.execute("PRAGMA user_version;").fetchone()[0] == 1

    # Verificar que existen las tablas de v1 pero no reglas_negocio
    tablas_v1 = [
        r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
    ]
    assert "proyectos" in tablas_v1
    assert "kpis" in tablas_v1
    assert "lecciones" in tablas_v1
    assert "configuraciones" in tablas_v1
    assert "reglas_negocio" not in tablas_v1

    # Ejecutar inicializar_o_migrar_bd sobre la BD en v1
    v_final = inicializar_o_migrar_bd(conn)
    assert v_final == 2
    assert conn.execute("PRAGMA user_version;").fetchone()[0] == 2

    # Verificar que ahora existe reglas_negocio sin afectar los datos previos
    tablas_v2 = [
        r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
    ]
    assert "reglas_negocio" in tablas_v2
    conn.close()


def _cargar_fichas_en_bd(db_file: str) -> None:
    repo = ProyectosRepository(db_file)
    for p in FICHAS_DIR.glob("*.json"):
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
            ficha = FichaProyecto(**data)
            repo.guardar_ficha(ficha)


def test_reglas_repository_idempotencia_y_consulta(tmp_path):
    """Verifica la carga idempotente de reglas_negocio y el filtrado por proyecto."""
    db_file = str(tmp_path / "test_reglas.sqlite")
    conn = obtener_conexion(db_file)
    inicializar_o_migrar_bd(conn)
    conn.close()

    repo = ReglasRepository(db_file)

    # 1. En BD sin proyectos aún, solo se cargan las reglas globales (2 reglas)
    insertados_globales = repo.cargar_desde_json()
    assert insertados_globales == 2
    assert len(repo.obtener_todas()) == 2

    # 2. Poblamos los proyectos de fichas en la BD
    _cargar_fichas_en_bd(db_file)

    # 3. Segunda carga: ahora inserta las 5 reglas específicas de los proyectos existentes
    insertados_especificas = repo.cargar_desde_json()
    assert insertados_especificas == 5
    todas = repo.obtener_todas()
    assert len(todas) == 7

    # 4. Tercera carga (estrictamente idempotente: 0 nuevas)
    insertados_3 = repo.cargar_desde_json()
    assert insertados_3 == 0
    assert len(repo.obtener_todas()) == 7

    # 5. Filtrar reglas por proyecto específico
    reglas_santa_lucia = repo.obtener_por_proyecto("PC-2025-033")
    # Debe incluir reglas con codigo_proyecto == 'PC-2025-033' más las globales (NULL)
    codigos = {r.codigo_proyecto for r in reglas_santa_lucia}
    assert "PC-2025-033" in codigos
    assert None in codigos
    assert "PC-2025-014" not in codigos

    # 6. Reglas globales exclusivamente
    reglas_globales = repo.obtener_por_proyecto(None)
    assert all(r.codigo_proyecto is None for r in reglas_globales)
    assert len(reglas_globales) == 2


def test_config_repository(tmp_path):
    """Verifica el funcionamiento aislado de ConfigRepository."""
    db_file = str(tmp_path / "test_config.sqlite")
    conn = obtener_conexion(db_file)
    inicializar_o_migrar_bd(conn)
    conn.close()

    repo = ConfigRepository(db_file)

    # Get de clave inexistente retorna default
    assert repo.get("CLAVE_INEXISTENTE", "default_val") == "default_val"

    # Set e inserción
    repo.set("MODELO_LLM", "gemini-2.5-flash", "Modelo preferido de inferencia")
    assert repo.get("MODELO_LLM") == "gemini-2.5-flash"

    # Update sobre la misma clave
    repo.set("MODELO_LLM", "gemini-1.5-pro", "Modelo avanzado")
    assert repo.get("MODELO_LLM") == "gemini-1.5-pro"

    # get_all
    todas = repo.get_all()
    assert "MODELO_LLM" in todas
    assert todas["MODELO_LLM"]["valor"] == "gemini-1.5-pro"
    assert todas["MODELO_LLM"]["descripcion"] == "Modelo avanzado"


def test_proyectos_repository_roundtrip(tmp_path):
    """Verifica guardar y recuperar una FichaProyecto con serialización JSON de listas."""
    db_file = str(tmp_path / "test_proyectos.sqlite")
    conn = obtener_conexion(db_file)
    inicializar_o_migrar_bd(conn)
    conn.close()

    repo = ProyectosRepository(db_file)

    ficha_mock = FichaProyecto(
        codigo_proyecto="TEST-001",
        archivo_origen="test_document.pdf",
        cliente="Empresa de Prueba S.A.",
        cliente_descripcion="Empresa del sector tecnológico",
        sector="Tecnología",
        ubicacion="Lima, Perú",
        periodo="2025",
        duracion_semanas=12,
        gerente_proyecto="Ana Gómez",
        contraparte_cliente="Carlos Ruiz",
        estado="Cerrado aceptado",
        fecha_aceptacion="2025-12-15",
        resumen_ejecutivo="Resumen ejecutivo del proyecto de prueba.",
        diagnostico_problema="Problema de latencia operativa.",
        alcance_incluido="Módulos A, B y C.",
        alcance_excluido="Módulo D.",
        metodologia="Lean Six Sigma",
        iniciativas_clave=[
            Iniciativa(
                nombre="Automatización CI/CD",
                descripcion="Implementación de pipelines automáticos",
                impacto_esperado="Reducción de despliegue",
            )
        ],
        kpis=[
            MetricaKPI(
                indicador="Tiempo de Despliegue",
                unidad="min",
                linea_base="45 min",
                meta="< 15 min",
                resultado="10 min",
                variacion="-78%",
                cumplimiento="Cumplido",
                observaciones="Superó la meta",
            )
        ],
        lecciones=[
            LeccionAprendida(
                tema="Cultura DevOps",
                titulo="Capacitación temprana",
                descripcion="La adopción rápida requirió talleres presenciales",
            )
        ],
        proximos_pasos=["Monitoreo mensual", "Escalamiento a sedes"],
    )

    repo.guardar_ficha(ficha_mock)

    # Recuperar por código
    recuperada = repo.obtener_por_codigo("TEST-001")
    assert recuperada is not None
    assert recuperada.codigo_proyecto == "TEST-001"
    assert recuperada.cliente == "Empresa de Prueba S.A."
    assert len(recuperada.iniciativas_clave) == 1
    assert recuperada.iniciativas_clave[0].nombre == "Automatización CI/CD"
    assert len(recuperada.kpis) == 1
    assert recuperada.kpis[0].resultado == "10 min"
    assert len(recuperada.lecciones) == 1
    assert recuperada.lecciones[0].tema == "Cultura DevOps"
    assert recuperada.proximos_pasos == ["Monitoreo mensual", "Escalamiento a sedes"]

    # Resumen
    resumen = repo.obtener_resumen()
    assert resumen["proyectos"] == 1
    assert resumen["kpis"] == 1
    assert resumen["lecciones"] == 1


def test_fts_repository(tmp_path):
    """Verifica indexación y búsqueda en FTSRepository."""
    db_file = str(tmp_path / "test_fts.sqlite")
    conn = obtener_conexion(db_file)
    inicializar_o_migrar_bd(conn)
    conn.close()

    fts_repo = FTSRepository(db_file)
    fts_repo.indexar_seccion(
        codigo_proyecto="TEST-001",
        archivo_origen="informe_test.pdf",
        seccion="Diagnóstico Operativo",
        contenido="El cuello de botella principal fue identificado en la etapa de empaque manual.",
    )

    assert fts_repo.contar() == 1

    resultados = fts_repo.buscar("botella", limite=5)
    assert len(resultados) == 1
    assert resultados[0]["codigo_proyecto"] == "TEST-001"
    assert "empaque" in resultados[0]["fragmento"].lower()


def test_authorizer_permite_reglas_negocio_y_bloquea_escritura(tmp_path):
    """Verifica que conexion_solo_lectura permita leer reglas_negocio pero bloquee escrituras."""
    db_file = str(tmp_path / "test_auth.sqlite")
    conn = obtener_conexion(db_file)
    inicializar_o_migrar_bd(conn)
    conn.close()

    # Cargar proyectos y reglas
    _cargar_fichas_en_bd(db_file)
    repo = ReglasRepository(db_file)
    repo.cargar_desde_json()

    # Conexión solo lectura
    conn_ro = conexion_solo_lectura(db_file)
    cursor = conn_ro.cursor()

    # Lectura de reglas_negocio permitida
    filas = cursor.execute("SELECT count(*) FROM reglas_negocio;").fetchone()
    assert filas[0] == 7

    # Escritura sobre reglas_negocio denegada
    with pytest.raises(sqlite3.DatabaseError):
        cursor.execute(
            "INSERT INTO reglas_negocio (tipo, titulo, descripcion) VALUES ('t', 't', 'd');"
        )

    # Lectura de configuraciones denegada
    with pytest.raises(sqlite3.DatabaseError):
        cursor.execute("SELECT * FROM configuraciones;")

    conn_ro.close()
