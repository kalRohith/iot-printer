import pytest
import os
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from unittest.mock import MagicMock, patch

from db import (
    Task, 
    StorageType, 
    TaskStatus, 
    prepare_gdrive_download_task, 
    print_file_task,
    SessionLocal 
)
from tests.conftest import TEST_GDRIVE_DOWNLOAD_FULL_PATH, TEST_LOCAL_STORAGE_PATH

@pytest.fixture(autouse=True)
def clear_tasks_before_each_test(db_session: Session):
    # Clean up any files created by previous tests in this module
    for root, dirs, files in os.walk(TEST_GDRIVE_DOWNLOAD_FULL_PATH, topdown=False):
        for name in files:
            os.remove(os.path.join(root, name))
    for root, dirs, files in os.walk(TEST_LOCAL_STORAGE_PATH, topdown=False):
         for name in files:
            if name.startswith("task_") or name.startswith("local_") or name.startswith("temp_gdrive_"): # Be specific
                 try:
                    os.remove(os.path.join(root, name))
                 except OSError:
                    pass # File might have been removed by the test itself

    db_session.query(Task).delete()
    db_session.commit()


# The autouse mock_get_gdrive_service in conftest.py handles mocking helper.get_gdrive_service
def test_prepare_gdrive_download_task_success(db_session: Session, mock_helper_download, mock_scheduler): # Removed mock_gdrive_service_for_downloads
    # Setup task
    task_time = datetime.now(timezone.utc) + timedelta(minutes=30)
    task = Task(
        original_filename="gdrive_doc.pdf",
        uploader_email="downloader@test.com",
        storage_type=StorageType.GDRIVE,
        file_identifier="fake_gdrive_id_for_download",
        time_to_print=task_time,
        color_mode="color",
        page_size="A4",
        status=TaskStatus.SCHEDULED
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    # Mock scheduler object passed to the task
    mock_scheduler_obj = MagicMock()
    mock_scheduler_obj.remove_job = mock_scheduler["remove_job"] 

    prepare_gdrive_download_task(task.id, mock_scheduler_obj, TEST_GDRIVE_DOWNLOAD_FULL_PATH)

    db_session.refresh(task) 
    assert task.status == TaskStatus.SCHEDULED 
    assert task.gdrive_download_path is not None
    assert os.path.exists(task.gdrive_download_path)
    # Corrected assertion for filename
    expected_filename_part = f"task_{task.id}_{task.original_filename}"
    assert expected_filename_part in task.gdrive_download_path
    mock_helper_download.assert_called_once_with(task.file_identifier, task.gdrive_download_path)
    mock_scheduler_obj.remove_job.assert_not_called()

    if task.gdrive_download_path and os.path.exists(task.gdrive_download_path):
        os.remove(task.gdrive_download_path)

# The autouse mock_get_gdrive_service in conftest.py handles mocking helper.get_gdrive_service
def test_prepare_gdrive_download_task_failure_api_error(db_session: Session, mock_helper_download, mock_helper_send_email, mock_scheduler): # Removed mock_gdrive_service_for_downloads
    # Setup task
    task_time = datetime.now(timezone.utc) + timedelta(minutes=30)
    task = Task(
        original_filename="fail_gdrive_doc.pdf",
        uploader_email="fail_downloader@test.com",
        storage_type=StorageType.GDRIVE,
        file_identifier="fail_gdrive_id",
        time_to_print=task_time,
        color_mode="bw",
        page_size="Letter",
        status=TaskStatus.SCHEDULED
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    # This mock will cause the download_from_gdrive (as patched in db module) to raise an exception
    mock_helper_download.side_effect = Exception("Simulated GDrive API Error")
    
    mock_scheduler_obj = MagicMock()
    mock_scheduler_obj.remove_job = mock_scheduler["remove_job"]

    prepare_gdrive_download_task(task.id, mock_scheduler_obj, TEST_GDRIVE_DOWNLOAD_FULL_PATH)

    db_session.refresh(task)
    assert task.status == TaskStatus.FAILED
    assert "Simulated GDrive API Error" in task.error_message 
    mock_helper_send_email.assert_called_once() # This should now work as send_email is patched in db
    assert mock_helper_send_email.call_args[0][0] == task.uploader_email 
    assert "Print Task Failed" in mock_helper_send_email.call_args[0][1] 
    mock_scheduler_obj.remove_job.assert_called_once_with(f"print_task_{task.id}")

def test_prepare_gdrive_download_task_failure_no_service(db_session: Session, mock_helper_send_email, mock_scheduler, mocker):
    # Test scenario where get_gdrive_service itself returns None
    # This will be picked up by the original download_from_gdrive if it were called,
    # but our mock_helper_download in conftest.py (patching db.download_from_gdrive)
    # needs to be made to fail for this specific test.
    
    # Mock helper.get_gdrive_service to return None for this specific test
    # This ensures that when db.download_from_gdrive (the actual one, if our mock was too broad)
    # or any internal call within db.prepare_gdrive_download_task tries to use it, it gets None.
    mocker.patch('helper.get_gdrive_service', return_value=None)

    # We also need to make the mocked db.download_from_gdrive raise the ConnectionError
    # that the original helper.download_from_gdrive would raise.
    mock_db_download = mocker.patch('db.download_from_gdrive', side_effect=ConnectionError("Google Drive service not available for download."))


    task_time = datetime.now(timezone.utc) + timedelta(minutes=30)
    task = Task(
        original_filename="no_service_gdrive_doc.pdf",
        uploader_email="noservice_downloader@test.com",
        storage_type=StorageType.GDRIVE,
        file_identifier="noservice_gdrive_id",
        time_to_print=task_time,
        color_mode="bw",
        page_size="Letter",
        status=TaskStatus.SCHEDULED
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)
    
    mock_scheduler_obj = MagicMock()
    mock_scheduler_obj.remove_job = mock_scheduler["remove_job"]

    prepare_gdrive_download_task(task.id, mock_scheduler_obj, TEST_GDRIVE_DOWNLOAD_FULL_PATH)

    db_session.refresh(task)
    assert task.status == TaskStatus.FAILED
    assert "Google Drive service not available for download." in task.error_message
    mock_helper_send_email.assert_called_once() # Patched as db.send_email
    mock_scheduler_obj.remove_job.assert_called_once_with(f"print_task_{task.id}")


def test_print_file_task_local_success(db_session: Session, mock_subprocess_run):
    # Setup local task
    local_file_name = "local_to_print.txt"
    local_file_path = os.path.join(TEST_LOCAL_STORAGE_PATH, local_file_name)
    with open(local_file_path, "w") as f:
        f.write("content to print locally")

    task_time = datetime.now(timezone.utc) + timedelta(minutes=5)
    task = Task(
        original_filename=local_file_name,
        uploader_email="printer@test.com",
        storage_type=StorageType.LOCAL,
        file_identifier=local_file_path,
        time_to_print=task_time,
        color_mode="bw",
        page_size="A4",
        status=TaskStatus.SCHEDULED
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    printer_name_for_test = os.getenv("PRINTER_NAME", "TestPrinter")
    print_file_task(task.id, printer_name_for_test)

    db_session.refresh(task)
    assert task.status == TaskStatus.COMPLETED
    mock_subprocess_run.assert_called_once()
    assert mock_subprocess_run.call_args[0][0][-1] == local_file_path # Check file path in lp command

    # Local files are not removed by default in the current print_file_task logic
    assert os.path.exists(local_file_path) 
    # Clean up if desired for test hygiene, though the task doesn't remove it
    if os.path.exists(local_file_path):
        os.remove(local_file_path)


def test_print_file_task_gdrive_success(db_session: Session, mock_subprocess_run):
    # Setup GDrive task that has been "downloaded"
    gdrive_orig_filename = "gdrive_to_print.pdf"
    # Simulate that prepare_gdrive_download_task has run
    downloaded_gdrive_file_path = os.path.join(TEST_GDRIVE_DOWNLOAD_FULL_PATH, f"task_gdrive_{gdrive_orig_filename}")
    with open(downloaded_gdrive_file_path, "w") as f:
        f.write("mock downloaded gdrive content")

    task_time = datetime.now(timezone.utc) + timedelta(minutes=5)
    task = Task(
        original_filename=gdrive_orig_filename,
        uploader_email="gdrive_printer@test.com",
        storage_type=StorageType.GDRIVE,
        file_identifier="gdrive_id_printed", # Original GDrive ID
        gdrive_download_path=downloaded_gdrive_file_path, # Path after download
        time_to_print=task_time,
        color_mode="color",
        page_size="Letter",
        status=TaskStatus.SCHEDULED # Status after successful download
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)
    
    printer_name_for_test = os.getenv("PRINTER_NAME", "TestPrinter")
    print_file_task(task.id, printer_name_for_test)

    db_session.refresh(task)
    assert task.status == TaskStatus.COMPLETED
    mock_subprocess_run.assert_called_once()
    assert mock_subprocess_run.call_args[0][0][-1] == downloaded_gdrive_file_path
    assert not os.path.exists(downloaded_gdrive_file_path) # Check GDrive temp file was removed
    assert task.gdrive_download_path is None # Check DB path was cleared


def test_print_file_task_print_failure(db_session: Session, mock_subprocess_run):
    local_file_name = "fail_print.txt"
    local_file_path = os.path.join(TEST_LOCAL_STORAGE_PATH, local_file_name)
    with open(local_file_path, "w") as f:
        f.write("content for failed print")

    task_time = datetime.now(timezone.utc) + timedelta(minutes=5)
    task = Task(
        original_filename=local_file_name,
        uploader_email="failprinter@test.com",
        storage_type=StorageType.LOCAL,
        file_identifier=local_file_path,
        time_to_print=task_time,
        color_mode="bw",
        page_size="A4",
        status=TaskStatus.SCHEDULED
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    # Simulate print command failure
    mock_process_fail = MagicMock()
    mock_process_fail.returncode = 1
    mock_process_fail.stderr = "Printer error: out of paper"
    mock_subprocess_run.return_value = mock_process_fail
    
    printer_name_for_test = os.getenv("PRINTER_NAME", "TestPrinter")
    print_file_task(task.id, printer_name_for_test)

    db_session.refresh(task)
    assert task.status == TaskStatus.FAILED
    assert "Printer error: out of paper" in task.error_message

    if os.path.exists(local_file_path):
        os.remove(local_file_path)
