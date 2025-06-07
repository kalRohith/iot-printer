import os
import shutil
from datetime import datetime, timezone, timedelta
from contextlib import asynccontextmanager

import uvicorn
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import logging

from helper import upload_to_gdrive, get_gdrive_service
from db import (
    Task,
    StorageType,
    TaskStatus,
    get_db,
    prepare_gdrive_download_task,
    print_file_task,
)

load_dotenv()

MAX_FILE_SIZE_MB = 5
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
PRINTER_NAME = os.getenv("PRINTER_NAME")
LOCAL_STORAGE_PATH = "uploads"
GDRIVE_DOWNLOAD_SUBDIR = "gdrive_downloads"
GDRIVE_DOWNLOAD_FULL_PATH = os.path.join(LOCAL_STORAGE_PATH, GDRIVE_DOWNLOAD_SUBDIR)

os.makedirs(LOCAL_STORAGE_PATH, exist_ok=True)
os.makedirs(GDRIVE_DOWNLOAD_FULL_PATH, exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(timezone="UTC")

@asynccontextmanager
async def lifespan(app_instance: FastAPI): # Renamed 'app' parameter to 'app_instance'
    scheduler.start()
    logger.info("APScheduler started.")
    gdrive_service = get_gdrive_service()
    if not gdrive_service:
         logger.warning("Google Drive service could not be initialized at startup. Check credentials.json and GDRIVE_FOLDER_ID.")
    elif not os.getenv("GDRIVE_FOLDER_ID"): 
        logger.warning("GDRIVE_FOLDER_ID is not set. Google Drive uploads will fail.")
    if not PRINTER_NAME:
        logger.warning("PRINTER_NAME is not set. Printing will fail.")
    if not all([os.getenv("SMTP_SERVER"), os.getenv("SMTP_PORT"), os.getenv("SMTP_USERNAME"), os.getenv("SENDER_EMAIL")]):
        logger.warning("SMTP settings are not fully configured in .env. Email notifications may fail.")
    yield
    scheduler.shutdown()
    logger.info("APScheduler shut down.")

# Instantiate the app *once* and use the lifespan context manager
app = FastAPI(title="IoT Printing Backend", lifespan=lifespan)

# Apply CORS Middleware to the correct app instance
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"], 
    allow_headers=["*"], 
)

@app.post("/add-task/")
async def add_task(
    file: UploadFile = File(...),
    time_to_print_ts: int = Form(...), 
    color_mode: str = Form(...), 
    page_size: str = Form(...), 
    uploader_email: str = Form(...), 
    db: Session = Depends(get_db) # get_db is now imported from db.py
):
    if color_mode not in ["color", "bw"]:
        raise HTTPException(status_code=400, detail="Invalid color_mode. Must be 'color' or 'bw'.")
    if not uploader_email: 
        raise HTTPException(status_code=400, detail="uploader_email is required.")

    temp_file_id = f"temp_{datetime.now(timezone.utc).timestamp()}_{file.filename}"
    temp_file_path = os.path.join(LOCAL_STORAGE_PATH, temp_file_id)
    try:
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    finally:
        file.file.close()

    file_size = os.path.getsize(temp_file_path)
    
    storage_type_val: StorageType # Imported from db.py
    file_identifier_val: str

    gdrive_service_available = get_gdrive_service() is not None and os.getenv("GDRIVE_FOLDER_ID") is not None

    if file_size > MAX_FILE_SIZE_BYTES:
        if not gdrive_service_available:
            os.remove(temp_file_path) 
            raise HTTPException(status_code=500, detail="File is large, but Google Drive is not configured/available for upload.")
        logger.info(f"File {file.filename} is larger than {MAX_FILE_SIZE_MB}MB. Uploading to Google Drive.")
        try:
            gdrive_file_id = upload_to_gdrive(temp_file_path, file.filename) 
            storage_type_val = StorageType.GDRIVE
            file_identifier_val = gdrive_file_id
            os.remove(temp_file_path) 
            logger.info(f"Removed local temp file {temp_file_path} after GDrive upload.")
        except (ConnectionError, ValueError, Exception) as e: 
            os.remove(temp_file_path) 
            logger.error(f"Failed to upload {file.filename} to GDrive: {e}")
            raise HTTPException(status_code=500, detail=f"Google Drive upload failed: {str(e)}")
    else:
        final_local_path = os.path.join(LOCAL_STORAGE_PATH, f"local_{datetime.now(timezone.utc).timestamp()}_{file.filename}")
        shutil.move(temp_file_path, final_local_path)
        storage_type_val = StorageType.LOCAL
        file_identifier_val = final_local_path
        logger.info(f"File {file.filename} stored locally at {final_local_path}.")

    try:
        print_datetime = datetime.fromtimestamp(time_to_print_ts, tz=timezone.utc)
    except ValueError:
        if storage_type_val == StorageType.LOCAL and os.path.exists(file_identifier_val):
            os.remove(file_identifier_val)
        raise HTTPException(status_code=400, detail="Invalid time_to_print_ts. Must be a valid Unix timestamp.")

    if print_datetime <= datetime.now(timezone.utc) + timedelta(minutes=1): 
        if storage_type_val == StorageType.LOCAL and os.path.exists(file_identifier_val):
            os.remove(file_identifier_val)
        raise HTTPException(status_code=400, detail="time_to_print must be in the future (at least 1 minute ahead).")

    new_task = Task( # Task model imported from db.py
        original_filename=file.filename,
        uploader_email=uploader_email, 
        storage_type=storage_type_val,
        file_identifier=file_identifier_val,
        time_to_print=print_datetime,
        color_mode=color_mode,
        page_size=page_size,
        status=TaskStatus.SCHEDULED # TaskStatus imported from db.py
    )
    db.add(new_task)
    db.commit()
    db.refresh(new_task)

    print_job_id = f"print_task_{new_task.id}"
    
    if new_task.storage_type == StorageType.GDRIVE:
        download_time = print_datetime - timedelta(minutes=10)
        if download_time <= datetime.now(timezone.utc):
            logger.warning(f"Task {new_task.id}: Calculated GDrive download time {download_time.isoformat()} is in the past/present. Scheduling download immediately.")
            download_time = datetime.now(timezone.utc) + timedelta(seconds=5) 
        
        scheduler.add_job(
            prepare_gdrive_download_task, # Imported from db.py
            'date',
            run_date=download_time,
            args=[new_task.id, scheduler, GDRIVE_DOWNLOAD_FULL_PATH], # Pass scheduler and path
            id=f"download_task_{new_task.id}",
            replace_existing=True
        )
        logger.info(f"Task {new_task.id} (GDrive): Download scheduled for {download_time.isoformat()}.")

    scheduler.add_job(
        print_file_task, # Imported from db.py
        'date',
        run_date=print_datetime,
        args=[new_task.id, PRINTER_NAME], # Pass printer_name
        id=print_job_id, 
        replace_existing=True
    )
    logger.info(f"Task {new_task.id} for {file.filename} (print) scheduled for {print_datetime.isoformat()}")

    return {
        "message": "Task added successfully",
        "task_id": new_task.id,
        "filename": file.filename,
        "uploader_email": new_task.uploader_email,
        "storage": new_task.storage_type.value, # .value for Enum
        "print_time": new_task.time_to_print.isoformat(),
        "status": new_task.status.value # .value for Enum
    }

@app.get("/tasks/{task_id}")
async def get_task_status(task_id: int, db: Session = Depends(get_db)): # get_db from db.py
    # Task model is imported from db.py
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@app.get("/tasks/")
async def list_tasks(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)): # get_db from db.py
    # Task model is imported from db.py
    tasks = db.query(Task).order_by(Task.created_at.desc()).offset(skip).limit(limit).all()
    return tasks

if __name__ == "__main__":
    # GDRIVE_FOLDER_ID is checked by get_gdrive_service in helper.py, PRINTER_NAME is checked at startup
    # For a more robust check, you could ensure PRINTER_NAME is not None here too.
    if not os.getenv("PRINTER_NAME"): # Simplified check, full checks in startup
        logger.critical("CRITICAL: PRINTER_NAME is not set in .env file. Application might not work as expected.")
    uvicorn.run(app, host="0.0.0.0", port=8000)

