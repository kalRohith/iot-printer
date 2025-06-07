import os
import logging
import smtplib
from email.mime.text import MIMEText

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from dotenv import load_dotenv

load_dotenv() # Load environment variables from .env

logger = logging.getLogger(__name__)

# Google Drive Configuration
GDRIVE_CREDENTIALS_FILE = "credentials.json"
GDRIVE_FOLDER_ID = os.getenv("GDRIVE_FOLDER_ID")

# Email Configuration
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = os.getenv("SMTP_PORT")
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SENDER_EMAIL = os.getenv("SENDER_EMAIL")


def get_gdrive_service():
    try:
        if not os.path.exists(GDRIVE_CREDENTIALS_FILE):
            logger.error(f"{GDRIVE_CREDENTIALS_FILE} not found.")
            return None
        creds = Credentials.from_service_account_file(
            GDRIVE_CREDENTIALS_FILE,
            scopes=['https://www.googleapis.com/auth/drive.file']
        )
        service = build('drive', 'v3', credentials=creds)
        return service
    except Exception as e:
        logger.error(f"Failed to initialize Google Drive service: {e}")
        return None

def upload_to_gdrive(file_path: str, filename: str):
    service = get_gdrive_service()
    if not service:
        # Exception will be raised by the caller based on this return
        raise ConnectionError("Google Drive service not available for upload.")
    if not GDRIVE_FOLDER_ID:
        raise ValueError("GDRIVE_FOLDER_ID not configured for upload.")

    try:
        file_metadata = {
            'name': filename,
            'parents': [GDRIVE_FOLDER_ID]
        }
        media = MediaFileUpload(file_path, resumable=True)
        file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        logger.info(f"File {filename} uploaded to Google Drive with ID: {file.get('id')}")
        return file.get('id')
    except Exception as e:
        logger.error(f"Google Drive upload failed for {filename}: {e}")
        raise # Re-raise the exception to be handled by the caller

def download_from_gdrive(file_id: str, destination_path: str):
    service = get_gdrive_service()
    if not service:
        raise ConnectionError("Google Drive service not available for download.")
    try:
        request = service.files().get_media(fileId=file_id)
        os.makedirs(os.path.dirname(destination_path), exist_ok=True) # Ensure directory exists
        with open(destination_path, 'wb') as fh:
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
                if status: # status can be None when done is True
                    logger.info(f"Download {int(status.progress() * 100)}%.")
        logger.info(f"File {file_id} downloaded to {destination_path}")
        return destination_path
    except Exception as e:
        logger.error(f"Google Drive download failed for file ID {file_id}: {e}")
        if os.path.exists(destination_path): # Clean up partial download
            os.remove(destination_path)
        raise # Re-raise the exception

def send_email(to_email: str, subject: str, body: str):
    if not all([SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, SENDER_EMAIL]):
        logger.error("SMTP settings not fully configured. Cannot send email.")
        return False
    
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = SENDER_EMAIL
    msg['To'] = to_email

    try:
        with smtplib.SMTP(SMTP_SERVER, int(SMTP_PORT)) as server:
            server.starttls()  # Enable security
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(SENDER_EMAIL, to_email, msg.as_string())
        logger.info(f"Email sent to {to_email} with subject: {subject}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return False

