import pytest
import os
from httpx import AsyncClient
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from db import Task, TaskStatus, StorageType # Import your models
from tests.conftest import TEST_LOCAL_STORAGE_PATH, TEST_GDRIVE_DOWNLOAD_FULL_PATH # For path checks

# Mark all tests in this module as asyncio
pytestmark = pytest.mark.asyncio

@pytest.fixture(autouse=True)
def clear_tasks_before_each_test(db_session: Session):
    db_session.query(Task).delete()
    db_session.commit()

async def test_add_task_small_file(client: AsyncClient, mock_scheduler, db_session: Session):
    print_time = datetime.now(timezone.utc) + timedelta(minutes=15)
    print_time_ts = int(print_time.timestamp())

    # Create a dummy small file
    dummy_file_content = b"This is a small test file."
    dummy_file_name = "small_test.txt"
    
    files = {'file': (dummy_file_name, dummy_file_content, 'text/plain')}
    data = {
        "time_to_print_ts": print_time_ts,
        "color_mode": "bw",
        "page_size": "A4",
        "uploader_email": "test@example.com"
    }

    response = await client.post("/add-task/", files=files, data=data)
    
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["message"] == "Task added successfully"
    assert response_data["filename"] == dummy_file_name
    assert response_data["storage"] == StorageType.LOCAL.value
    task_id = response_data["task_id"]

    # Verify in DB
    task_in_db = db_session.query(Task).filter(Task.id == task_id).first()
    assert task_in_db is not None
    assert task_in_db.original_filename == dummy_file_name
    assert task_in_db.storage_type == StorageType.LOCAL
    assert task_in_db.uploader_email == "test@example.com"
    assert os.path.exists(task_in_db.file_identifier) # Check if local file was saved

    # Verify scheduler calls
    assert mock_scheduler["add_job"].call_count == 1 # Only print_file_task for local files
    call_args = mock_scheduler["add_job"].call_args_list[0]
    assert call_args[1]['args'][0] == task_id # task_id
    assert call_args[1]['run_date'].timestamp() == pytest.approx(print_time_ts)

    # Clean up the created file
    if task_in_db and task_in_db.file_identifier and os.path.exists(task_in_db.file_identifier):
        os.remove(task_in_db.file_identifier)


async def test_add_task_large_file(client: AsyncClient, mock_scheduler, mock_helper_upload, db_session: Session):
    from backend import MAX_FILE_SIZE_BYTES # Get this from backend config
    print_time = datetime.now(timezone.utc) + timedelta(minutes=20)
    print_time_ts = int(print_time.timestamp())

    # Create a dummy large file (content doesn't matter as much as size for the check)
    dummy_file_content = b"a" * (MAX_FILE_SIZE_BYTES + 100) 
    dummy_file_name = "large_test.txt"
    
    files = {'file': (dummy_file_name, dummy_file_content, 'text/plain')}
    data = {
        "time_to_print_ts": print_time_ts,
        "color_mode": "color",
        "page_size": "Letter",
        "uploader_email": "largeuploader@example.com"
    }

    response = await client.post("/add-task/", files=files, data=data)
    
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["storage"] == StorageType.GDRIVE.value
    mock_helper_upload.assert_called_once() # Check GDrive upload was called
    task_id = response_data["task_id"]

    # Verify in DB
    task_in_db = db_session.query(Task).filter(Task.id == task_id).first()
    assert task_in_db is not None
    assert task_in_db.storage_type == StorageType.GDRIVE
    assert task_in_db.file_identifier == "mock_gdrive_file_id_123" # From mock_helper_upload

    # Verify scheduler calls (download + print)
    assert mock_scheduler["add_job"].call_count == 2
    
    # Check download_task scheduling
    download_call_args = mock_scheduler["add_job"].call_args_list[0] # Assuming download is scheduled first
    assert download_call_args[1]['id'] == f"download_task_{task_id}"
    assert download_call_args[1]['args'][0] == task_id # task_id
    assert download_call_args[1]['args'][2] == TEST_GDRIVE_DOWNLOAD_FULL_PATH # Check path passed
    expected_download_time = print_time - timedelta(minutes=10)
    assert download_call_args[1]['run_date'].timestamp() == pytest.approx(expected_download_time.timestamp())

    # Check print_task scheduling
    print_call_args = mock_scheduler["add_job"].call_args_list[1]
    assert print_call_args[1]['id'] == f"print_task_{task_id}"
    assert print_call_args[1]['args'][0] == task_id # task_id
    assert print_call_args[1]['run_date'].timestamp() == pytest.approx(print_time_ts)


async def test_add_task_invalid_time(client: AsyncClient):
    past_time_ts = int((datetime.now(timezone.utc) - timedelta(minutes=5)).timestamp())
    files = {'file': ('test.txt', b"content", 'text/plain')}
    data = {
        "time_to_print_ts": past_time_ts,
        "color_mode": "bw",
        "page_size": "A4",
        "uploader_email": "timererror@example.com"
    }
    response = await client.post("/add-task/", files=files, data=data)
    assert response.status_code == 400
    assert "time_to_print must be in the future" in response.json()["detail"]


async def test_get_task_status(client: AsyncClient, db_session: Session):
    # First, add a task
    print_time = datetime.now(timezone.utc) + timedelta(hours=1)
    task = Task(
        original_filename="retrievable.txt",
        uploader_email="retriever@example.com",
        storage_type=StorageType.LOCAL,
        file_identifier=os.path.join(TEST_LOCAL_STORAGE_PATH, "retrievable.txt"),
        time_to_print=print_time,
        color_mode="bw",
        page_size="A4",
        status=TaskStatus.SCHEDULED
    )
    # Create a dummy file for the task
    os.makedirs(TEST_LOCAL_STORAGE_PATH, exist_ok=True)
    with open(task.file_identifier, "w") as f:
        f.write("dummy content for retrieval test")

    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)
    task_id = task.id

    response = await client.get(f"/tasks/{task_id}")
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["id"] == task_id
    assert response_data["original_filename"] == "retrievable.txt"

    # Clean up
    if os.path.exists(task.file_identifier):
        os.remove(task.file_identifier)

async def test_get_task_status_not_found(client: AsyncClient):
    response = await client.get("/tasks/99999") # Non-existent ID
    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"


async def test_list_tasks(client: AsyncClient, db_session: Session):
    # Add a couple of tasks
    task1_time = datetime.now(timezone.utc) + timedelta(hours=1)
    task1 = Task(original_filename="task1.txt", uploader_email="lister@example.com", storage_type=StorageType.LOCAL, file_identifier="localtask1", time_to_print=task1_time, color_mode="bw", page_size="A4", status=TaskStatus.SCHEDULED)
    task2_time = datetime.now(timezone.utc) + timedelta(hours=2)
    task2 = Task(original_filename="task2.txt", uploader_email="lister@example.com", storage_type=StorageType.LOCAL, file_identifier="localtask2", time_to_print=task2_time, color_mode="color", page_size="Letter", status=TaskStatus.SCHEDULED)
    
    db_session.add_all([task1, task2])
    db_session.commit()

    response = await client.get("/tasks/")
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) == 2
    # Tasks are ordered by created_at desc, so task2 might appear before task1 if created later
    filenames_in_response = {t["original_filename"] for t in response_data}
    assert "task1.txt" in filenames_in_response
    assert "task2.txt" in filenames_in_response
