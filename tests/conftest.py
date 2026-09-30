"""
Configuración Global y Fixtures de Pruebas Aisladas (tests/conftest.py).
Garantiza 0 dependencias de red por defecto y aislamiento en bases de datos efímeras (tmp_path).
Ningún test interactúa con data/database.sqlite.
"""

from pathlib import Path

import pytest

from procesa_agent.agent.orchestrator import AgenteProyectos
from procesa_agent.core.paths import FICHAS_DIR, RAW_DATA_DIR
from procesa_agent.infrastructure.db.schema import inicializar_bd
from procesa_agent.infrastructure.llm.fake import FakeLLM
from procesa_agent.ingestion.pipeline import IngestionPipeline


@pytest.fixture
def bd_vacia(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    """Fixture que crea e inicializa un esquema SQLite limpio en un directorio efímero."""
    db_file = str(tmp_path / "test_vacia.sqlite")
    monkeypatch.setenv("PROCESA_DB_PATH", db_file)
    inicializar_bd(db_file)
    return db_file


@pytest.fixture
def bd_con_datos(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    """
    Fixture que crea una base de datos efímera y carga las fichas oficiales y FTS5
    desde data/fichas/ y data/raw/ sin requerir llamadas externas ni LLM.
    """
    db_file = str(tmp_path / "test_con_datos.sqlite")
    monkeypatch.setenv("PROCESA_DB_PATH", db_file)
    inicializar_bd(db_file)

    pipeline = IngestionPipeline(
        db_path=db_file,
        raw_dir=RAW_DATA_DIR,
        fichas_dir=FICHAS_DIR,
    )
    pipeline.ejecutar()
    return db_file


@pytest.fixture
def fake_llm() -> FakeLLM:
    """Fixture de proveedor simulado FakeLLM para pruebas sin conexión."""
    return FakeLLM(text_response="Respuesta generada por el agente de pruebas simulado.")


@pytest.fixture
def agente_test(bd_con_datos: str, fake_llm: FakeLLM) -> AgenteProyectos:
    """Fixture de AgenteProyectos configurado sobre base de datos efímera y FakeLLM."""
    return AgenteProyectos(db_path=bd_con_datos, llm_provider=fake_llm)
