import os
import logging
import subprocess
from datetime import datetime, timezone
import enum 
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Enum as SAEnum
from sqlalchemy.orm import sessionmaker, declarative_base # Updated import
from sqlalchemy.exc import SQLAlchemyError
from apscheduler.jobstores.base import JobLookupError

# Import from helper, but ensure no circular dependencies if helper also imports from db
from helper import send_email, download_from_gdrive # download_from_gdrive is used here

# Configuration
DATABASE_URL = "sqlite:///./tasks.db" # Relative to where backend.py runs

# Logging setup
logger = logging.getLogger(__name__)

# Database Setup (SQLAlchemy)
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base() # This line remains the same, uses the updated import

class StorageType(str, enum.Enum): # Changed to use enum.Enum
    LOCAL = "local"
    GDRIVE = "gdrive"

class TaskStatus(str, enum.Enum): # Changed to use enum.Enum
    PENDING = "pending"
    SCHEDULED = "scheduled"
    DOWNLOADING = "downloading"
    PRINTING = "printing"
    COMPLETED = "completed"
    FAILED = "failed"

class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True)
    original_filename = Column(String, index=True)
    uploader_email = Column(String, nullable=False)
    storage_type = Column(SAEnum(StorageType, values_callable=lambda obj: [e.value for e in obj])) # Pass the enum class directly
    file_identifier = Column(String) # local path or GDrive file ID
    gdrive_download_path = Column(String, nullable=True) # Path to locally downloaded GDrive file
    time_to_print = Column(DateTime)
    color_mode = Column(String)
    page_size = Column(String)
    status = Column(SAEnum(TaskStatus, values_callable=lambda obj: [e.value for e in obj])) # Pass the enum class directly
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    error_message = Column(String, nullable=True)

Base.metadata.create_all(bind=engine)

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Task Functions
def prepare_gdrive_download_task(task_id: int, scheduler_obj, gdrive_download_full_path_val: str):
    db = SessionLocal()
    task = db.query(Task).filter(Task.id == task_id).first()

    if not task:
        logger.error(f"PrepareGdriveDownload: Task ID {task_id} not found.")
        db.close()
        return

    if task.status == TaskStatus.FAILED:
        logger.info(f"PrepareGdriveDownload: Task {task_id} is already marked as FAILED. Skipping download.")
        db.close()
        return

    if task.storage_type != StorageType.GDRIVE:
        logger.info(f"PrepareGdriveDownload: Task {task_id} is not a GDrive task. Skipping.")
        db.close()
        return

    logger.info(f"PrepareGdriveDownload: Starting download for task {task_id}, file ID {task.file_identifier}")
    task.status = TaskStatus.DOWNLOADING
    db.commit()

    download_destination = os.path.join(gdrive_download_full_path_val, f"task_{task.id}_{task.original_filename}")

    try:
        download_from_gdrive(task.file_identifier, download_destination)
        task.gdrive_download_path = download_destination
        task.status = TaskStatus.SCHEDULED # Ready for the print_file_task
        logger.info(f"PrepareGdriveDownload: File for task {task_id} downloaded to {download_destination}")
    except Exception as e:
        error_msg = f"PrepareGdriveDownload: Failed to download file for task {task_id} (ID: {task.file_identifier}): {e}"
        logger.error(error_msg)
        task.status = TaskStatus.FAILED
        task.error_message = str(e)
        
        email_subject = f"Print Task Failed: {task.original_filename}"
        email_body = (
            f"Hello,\n\nThe file '{task.original_filename}' scheduled for printing could not be downloaded from Google Drive.\n"
            f"Error: {str(e)}\n\nYou may need to print this file manually.\n"
            f"Task ID: {task.id}"
        )
        send_email(task.uploader_email, email_subject, email_body)

        try:
            scheduler_obj.remove_job(f"print_task_{task.id}")
            logger.info(f"PrepareGdriveDownload: Removed scheduled print_task_{task.id} due to download failure.")
        except JobLookupError:
            logger.warning(f"PrepareGdriveDownload: Could not find print_task_{task.id} to remove.")
    finally:
        db.commit()
        db.close()

def print_file_task(task_id: int, printer_name_val: str):
    db = SessionLocal()
    task = db.query(Task).filter(Task.id == task_id).first()

    if not task:
        logger.error(f"PrintTask: Task ID {task_id} not found for printing.")
        db.close()
        return

    if task.status == TaskStatus.FAILED:
        logger.info(f"PrintTask: Task {task_id} ({task.original_filename}) is marked FAILED. Skipping print.")
        db.close()
        return
    
    if task.status == TaskStatus.DOWNLOADING:
        logger.warning(f"PrintTask: Task {task_id} ({task.original_filename}) is still DOWNLOADING. This implies an issue. Marking as FAILED.")
        task.status = TaskStatus.FAILED
        task.error_message = "Print task ran while file was still in downloading state or download failed to update status."
        db.commit()
        db.close()
        return

    if not printer_name_val:
        logger.error("PRINTER_NAME is not configured (passed as empty). Cannot print.")
        task.status = TaskStatus.FAILED
        task.error_message = "Printer name not configured (passed as empty)."
        db.commit()
        db.close()
        return

    logger.info(f"PrintTask: Processing print task ID: {task_id}, File: {task.original_filename}")
    
    file_to_print_path = ""
    is_gdrive_downloaded_file = False

    if task.storage_type == StorageType.GDRIVE:
        if task.gdrive_download_path and os.path.exists(task.gdrive_download_path):
            file_to_print_path = task.gdrive_download_path
            is_gdrive_downloaded_file = True
        else:
            error_msg = f"GDrive file {task.original_filename} (ID: {task.file_identifier}) not found locally at expected path {task.gdrive_download_path}. Download may have failed or path is incorrect."
            logger.error(f"PrintTask: {error_msg}")
            task.status = TaskStatus.FAILED
            task.error_message = error_msg
            db.commit()
            db.close()
            return
    elif task.storage_type == StorageType.LOCAL:
        file_to_print_path = task.file_identifier
    else:
        logger.error(f"PrintTask: Unknown storage type for task {task_id}.")
        task.status = TaskStatus.FAILED
        task.error_message = "Unknown storage type."
        db.commit()
        db.close()
        return

    if not os.path.exists(file_to_print_path):
        error_msg = f"File not found at {file_to_print_path} for task {task_id}."
        logger.error(f"PrintTask: {error_msg}")
        task.status = TaskStatus.FAILED
        task.error_message = error_msg
        db.commit()
        db.close()
        return
    
    task.status = TaskStatus.PRINTING
    db.commit()

    try:
        print_command = ["lp", "-d", printer_name_val]
        if task.page_size:
            print_command.extend(["-o", f"media={task.page_size}"])
        
        if task.color_mode == "color":
            print_command.extend(["-o", "ColorModel=CMYK"])
        elif task.color_mode == "bw":
            print_command.extend(["-o", "ColorModel=Gray"])
        
        print_command.append(file_to_print_path)

        logger.info(f"PrintTask: Executing print command: {' '.join(print_command)}")
        process = subprocess.run(print_command, capture_output=True, text=True, check=False)

        if process.returncode == 0:
            logger.info(f"PrintTask: Successfully sent {task.original_filename} to printer {printer_name_val}.")
            task.status = TaskStatus.COMPLETED
        else:
            error_msg = f"Printing failed for {task.original_filename}. Error: {process.stderr or process.stdout}"
            logger.error(f"PrintTask: {error_msg}")
            task.status = TaskStatus.FAILED
            task.error_message = process.stderr or process.stdout or "Unknown printing error"
        db.commit()

    except Exception as e:
        error_msg = f"Error during print task {task_id}: {e}"
        logger.error(f"PrintTask: {error_msg}")
        task.status = TaskStatus.FAILED
        task.error_message = str(e)
        db.commit()
    finally:
        if is_gdrive_downloaded_file and os.path.exists(file_to_print_path):
            try:
                os.remove(file_to_print_path)
                logger.info(f"PrintTask: Cleaned up temporary GDrive downloaded file: {file_to_print_path}")
                task.gdrive_download_path = None
                db.commit()
            except Exception as e_remove:
                logger.error(f"PrintTask: Failed to remove temporary GDrive file {file_to_print_path}: {e_remove}")
        db.close()
