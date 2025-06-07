# IoT Printer Application

A full-stack application for scheduling and managing print tasks with a modern React frontend and FastAPI backend.

## Frontend

The frontend is built with React and Material-UI, providing a modern and intuitive user interface for managing print tasks.

### Frontend Setup

1. Navigate to the frontend directory:

```bash
cd printer-frontend
```

2. Install dependencies:

```bash
npm install
```

3. Start the development server:

```bash
npm start
```

The frontend will be available at `http://localhost:3000`.

### Frontend Features

- **Dashboard**: Overview of print tasks with statistics and quick actions
- **Upload Form**: Easy-to-use interface for scheduling new print tasks
- **Task List**: Comprehensive view of all print tasks with filtering and pagination
- **Task Status**: Detailed view of individual task status and information

### Frontend Dependencies

- React 18
- Material-UI (MUI)
- React Router
- Axios
- Date-fns

## Backend

This project provides a FastAPI backend for scheduling and managing print tasks. It supports storing files locally or on Google Drive (for larger files) and printing them at a specified time.

## Project Setup

Refer to the comprehensive setup guide provided previously for installing dependencies, setting up SQLite, Google Drive API, environment variables, and running tests.

**Key Dependencies:** FastAPI, Uvicorn, SQLAlchemy, APScheduler, Google API Client, python-dotenv, python-multipart.

**Environment Variables (`.env` file):**

- `GDRIVE_FOLDER_ID`: Your Google Drive Folder ID for large file uploads.
- `PRINTER_NAME`: Name of your CUPS printer.
- `SMTP_SERVER`: SMTP server for email notifications.
- `SMTP_PORT`: SMTP port.
- `SMTP_USERNAME`: SMTP username.
- `SMTP_PASSWORD`: SMTP password (or App Password for Gmail).
- `SENDER_EMAIL`: Email address to send notifications from.

**Google Credentials:**
Place your Google Cloud service account JSON key file as `credentials.json` in the project root.

## Running the Application

```bash
uvicorn backend:app --host 0.0.0.0 --port 8000 --reload
```

The API documentation (Swagger UI) will be available at `http://<your-ip>:8000/docs`.

## API Endpoints

### 1. Add a New Print Task

- **Endpoint:** `POST /add-task/`
- **Description:** Adds a new print task to the system. Files larger than 5MB are uploaded to Google Drive; smaller files are stored locally.
- **Request Type:** `multipart/form-data`
- **Form Data Parameters:**
  - `file`: The file to be printed (binary file upload).
  - `time_to_print_ts`: `integer` (Unix timestamp, UTC) - The scheduled time for printing. Must be at least 1 minute in the future.
  - `color_mode`: `string` - Printing color mode. Allowed values: `"color"`, `"bw"`.
  - `page_size`: `string` - Page size for printing (e.g., `"A4"`, `"Letter"`).
  - `uploader_email`: `string` - Email address of the person uploading the task, for notifications.
- **Success Response (200 OK):**
  ```json
  {
    "message": "Task added successfully",
    "task_id": 1,
    "filename": "mydocument.pdf",
    "uploader_email": "user@example.com",
    "storage": "local", // or "gdrive"
    "print_time": "2023-10-27T10:30:00Z", // ISO 8601 format
    "status": "scheduled"
  }
  ```
- **Error Responses:**
  - `400 Bad Request`: If input validation fails (e.g., invalid `color_mode`, `time_to_print_ts` in the past, missing `uploader_email`).
    ```json
    {
      "detail": "Invalid color_mode. Must be 'color' or 'bw'."
    }
    ```
    ```json
    {
      "detail": "time_to_print must be in the future (at least 1 minute ahead)."
    }
    ```
  - `500 Internal Server Error`: If Google Drive upload fails for a large file, or if GDrive is not configured for a large file.
    ```json
    {
      "detail": "File is large, but Google Drive is not configured/available for upload."
    }
    ```
    ```json
    {
      "detail": "Google Drive upload failed: <error_message>"
    }
    ```

### 2. Get Task Status

- **Endpoint:** `GET /tasks/{task_id}`
- **Description:** Retrieves the status and details of a specific print task.
- **Path Parameters:**
  - `task_id`: `integer` - The ID of the task.
- **Success Response (200 OK):**
  ```json
  {
    "id": 1,
    "original_filename": "mydocument.pdf",
    "uploader_email": "user@example.com",
    "storage_type": "local", // or "gdrive"
    "file_identifier": "uploads/local_1698387491.332973_mydocument.pdf", // or GDrive file ID
    "gdrive_download_path": null, // or path if downloaded from GDrive
    "time_to_print": "2023-10-27T10:30:00+00:00", // ISO 8601 format with timezone
    "color_mode": "bw",
    "page_size": "A4",
    "status": "scheduled", // "pending", "downloading", "printing", "completed", "failed"
    "created_at": "2023-10-27T09:30:00.123456+00:00", // ISO 8601 format with timezone
    "error_message": null // or error details if status is "failed"
  }
  ```
- **Error Responses:**
  - `404 Not Found`: If the task with the given ID does not exist.
    ```json
    {
      "detail": "Task not found"
    }
    ```

### 3. List Tasks

- **Endpoint:** `GET /tasks/`
- **Description:** Retrieves a list of print tasks, ordered by creation date (descending). Supports pagination.
- **Query Parameters:**
  - `skip`: `integer` (optional, default: `0`) - Number of tasks to skip.
  - `limit`: `integer` (optional, default: `10`) - Maximum number of tasks to return.
- **Success Response (200 OK):**
  An array of task objects, similar to the one returned by "Get Task Status".
  ```json
  [
    {
      "id": 2,
      "original_filename": "anotherdoc.docx",
      "uploader_email": "another@example.com",
      "storage_type": "gdrive",
      "file_identifier": "gdrive_file_id_xyz",
      "gdrive_download_path": null,
      "time_to_print": "2023-10-28T12:00:00+00:00",
      "color_mode": "color",
      "page_size": "Letter",
      "status": "scheduled",
      "created_at": "2023-10-27T11:00:00.654321+00:00",
      "error_message": null
    },
    {
      "id": 1,
      "original_filename": "mydocument.pdf"
      // ... other fields ...
    }
  ]
  ```

## Task States (`status` field)

- `pending`: Initial state before scheduling (not typically seen via API after creation).
- `scheduled`: Task is successfully created and scheduled for printing (and GDrive download if applicable).
- `downloading`: If the file is on Google Drive, this state indicates it's currently being downloaded.
- `printing`: The task is currently being sent to the printer.
- `completed`: The print job was successfully sent to the printer.
- `failed`: The task failed at some stage (e.g., GDrive download error, printing error). The `error_message` field will contain details.

## Notes

- Timestamps are handled in UTC.
- Email notifications are sent for GDrive download failures.
- Temporary files (uploaded files, GDrive downloads) are managed by the backend.
