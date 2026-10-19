import sys
from pathlib import Path
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings

def pytest_configure(config):
    config.addinivalue_line("markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')")

@pytest.fixture(scope="session")
def test_engine():
    test_db_url = settings.TEST_DATABASE_URL
    if not test_db_url:
        pytest.skip("TEST_DATABASE_URL is not set in backend/.env")

    # Run alembic migrations on test database
    alembic_cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", test_db_url)

    command.upgrade(alembic_cfg, "head")

    engine = create_engine(test_db_url, pool_pre_ping=True)
    yield engine
    engine.dispose()

@pytest.fixture
def db_session(test_engine):
    connection = test_engine.connect()
    transaction = connection.begin()
    TestSessionLocal = sessionmaker(bind=connection, expire_on_commit=False)
    session = TestSessionLocal()

    yield session

    session.close()
    if transaction.is_active:
        transaction.rollback()
    connection.close()

