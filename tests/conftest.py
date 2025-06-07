import os
import pytest
import asyncio
from httpx import AsyncClient, ASGITransport 
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from typing import AsyncGenerator, Generator
import pytest_asyncio 
from unittest.mock import MagicMock 

from backend import app  
import db as app_db 
from db import Base, get_db, Task 
import helper as app_helper 

TEST_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    if os.path.exists("./test.db"):
        os.remove("./test.db")
    Base.metadata.create_all(bind=engine)
    yield
    if os.path.exists("./test.db"):
        os.remove("./test.db")

@pytest.fixture
def override_get_db() -> Generator:
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

@pytest.fixture(autouse=True)
def apply_db_override(override_get_db):
    app.dependency_overrides[get_db] = lambda: override_get_db

@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    # Use ASGITransport for httpx.AsyncClient with a FastAPI app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

@pytest.fixture
def db_session() -> Generator:
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture(autouse=True)
def patch_db_session_local(mocker):
    mocker.patch.object(app_db, 'SessionLocal', TestingSessionLocal)

@pytest.fixture(autouse=True)
def mock_scheduler(mocker):
    mock_add_job = mocker.patch('apscheduler.schedulers.background.BackgroundScheduler.add_job')
    mock_remove_job = mocker.patch('apscheduler.schedulers.background.BackgroundScheduler.remove_job')
    return {"add_job": mock_add_job, "remove_job": mock_remove_job}

@pytest.fixture(autouse=True)
def mock_helper_upload(mocker):
    # Patch where upload_to_gdrive is LOOKED UP and USED by the code under test (backend.py)
    return mocker.patch('backend.upload_to_gdrive', return_value="mock_gdrive_file_id_123")

@pytest.fixture(autouse=True) 
def mock_get_gdrive_service(mocker): 
    mock_service = MagicMock() 
    # This mock is primarily to ensure get_gdrive_service() in helper.py returns a mock object 
    # instead of None or erroring out due to missing credentials.json in tests. 
    # The actual download simulation is handled by mock_helper_download. 
    return mocker.patch.object(app_helper, 'get_gdrive_service', return_value=mock_service)

@pytest.fixture(autouse=True)
def mock_helper_download(mocker):
    def mock_download_behavior(file_id, destination_path):
        os.makedirs(os.path.dirname(destination_path), exist_ok=True)
        with open(destination_path, "w") as f:
            f.write(f"mock content for {file_id}")
        return destination_path
    
    # Patch where download_from_gdrive is LOOKED UP and USED, which is in the 'db' module.
    # db.py imports download_from_gdrive from helper.
    return mocker.patch('db.download_from_gdrive', side_effect=mock_download_behavior)

@pytest.fixture(autouse=True)
def mock_helper_send_email(mocker):
    # Patch where send_email is LOOKED UP and USED.
    # It's imported into db.py as `from helper import send_email`.
    return mocker.patch('db.send_email', return_value=True)

@pytest.fixture(autouse=True)
def mock_os_path_exists_for_credentials(mocker):
    # Mock os.path.exists specifically for "credentials.json"
    # to allow helper.get_gdrive_service to proceed further in some test setups
    # even if the service call itself is later mocked (e.g., for uploads).
    original_exists = os.path.exists
    def side_effect(path):
        if path == "credentials.json":
            return True  # Pretend credentials.json exists
        return original_exists(path)
    return mocker.patch('os.path.exists', side_effect=side_effect)

@pytest.fixture(autouse=True)
def mock_subprocess_run(mocker):
    # Mock subprocess.run to simulate successful print command
    mock_process = mocker.Mock()
    mock_process.returncode = 0
    mock_process.stdout = "Successfully printed."
    mock_process.stderr = ""
    return mocker.patch('subprocess.run', return_value=mock_process)

# Set necessary environment variables for tests if not already set
# These are used by the main application code during import or runtime
os.environ["PRINTER_NAME"] = "TestPrinter"
os.environ["GDRIVE_FOLDER_ID"] = "TestDriveFolderId"
os.environ["SMTP_SERVER"] = "smtp.test.com"
os.environ["SMTP_PORT"] = "587"
os.environ["SMTP_USERNAME"] = "user@test.com"
os.environ["SMTP_PASSWORD"] = "password"
os.environ["SENDER_EMAIL"] = "sender@test.com"

# Ensure test upload directories exist
TEST_LOCAL_STORAGE_PATH = "test_uploads"
TEST_GDRIVE_DOWNLOAD_FULL_PATH = os.path.join(TEST_LOCAL_STORAGE_PATH, "gdrive_downloads")

@pytest.fixture(scope="session", autouse=True)
def setup_test_upload_dirs():
    os.makedirs(TEST_LOCAL_STORAGE_PATH, exist_ok=True)
    os.makedirs(TEST_GDRIVE_DOWNLOAD_FULL_PATH, exist_ok=True)
    # Override paths in backend.py for testing if they are module-level constants
    # This is tricky; ideally, paths are configurable or passed around.
    # For now, we assume the test tasks will use paths passed to them or mocked.
    import backend
    backend.LOCAL_STORAGE_PATH = TEST_LOCAL_STORAGE_PATH
    backend.GDRIVE_DOWNLOAD_FULL_PATH = TEST_GDRIVE_DOWNLOAD_FULL_PATH
    yield
    # Clean up test upload directories
    # shutil.rmtree(TEST_LOCAL_STORAGE_PATH) # Be careful with rmtree

# Required for pytest-asyncio to work with async fixtures and tests
@pytest.fixture(scope="session")
def event_loop(request): # Changed to accept request for pytest-asyncio compatibility if needed
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
