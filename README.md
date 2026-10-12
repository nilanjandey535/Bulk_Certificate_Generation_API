# Bulk Certificate Generator API

A Django REST Framework API for accepting bulk certificate requests, validating recipient data, generating individual PDF certificates, tracking processing results, and downloading generated certificates.

## Features

- Submit multiple recipients in a single request.
- Validate recipient data individually so invalid records do not automatically block valid recipients.
- Generate individual PDF certificates using a predefined template.
- Store certificate files on the server's configured storage directory.
- Track job and recipient processing statuses.
- Record recipient-specific validation and generation errors.
- Retrieve job details, recipient lists, and individual recipient details.
- Download generated certificates through a dedicated API endpoint.
- Explore API endpoints using Swagger UI and the OpenAPI schema.
- Run automated tests using Django's test framework.

## Technology Stack

- **Backend:** Python, Django, Django REST Framework
- **Database:** PostgreSQL
- **PDF generation:** ReportLab
- **API documentation:** drf-spectacular / Swagger UI
- **Testing:** Django TestCase and Django REST Framework APIClient

## Project Structure

The project is organized around a Django application named `certificates`.

```text
Certificate_Generator_API/
├── manage.py
├── README.md
├── <django_project_package>/
│   ├── settings.py
│   └── urls.py
└── certificates/
    ├── models.py
    ├── serializers.py
    ├── services.py
    ├── pdf_service.py
    ├── views.py
    ├── urls.py
    └── tests.py
```

The project-package name and any additional files may differ depending on the actual repository structure.

### Main application modules

- `models.py` — defines certificate jobs and individual recipient records.
- `serializers.py` — validates incoming recipient data and serializes API responses.
- `services.py` — creates jobs, records rejected recipients, processes certificates, and updates processing results.
- `pdf_service.py` — generates PDF certificates and stores them under the configured storage directory.
- `views.py` — implements API endpoints for job creation, status retrieval, recipient retrieval, and PDF downloads.
- `tests.py` — contains automated tests for job creation, retrieval, PDF generation, and failure handling.

## Requirements

Before running the project, ensure that the following software is installed:

Python

PostgreSQL

pip, Python's package installer

This project is configured to run directly in the existing Python environment. A separate virtual environment is not required by the current setup.

Install the required Python packages:

pip install django djangorestframework drf-spectacular psycopg2-binary reportlab

If a requirements.txt file is available in the project, install the dependencies listed there instead:

pip install -r requirements.txt

## Configuration

### 1. Configure PostgreSQL

Create a PostgreSQL database and configure Django's `DATABASES` setting to use it.

Example configuration:

```python
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "your_database_name",
        "USER": "your_database_user",
        "PASSWORD": "your_database_password",
        "HOST": "localhost",
        "PORT": "PORT number",
    }
}
```

Replace the example values with your local PostgreSQL configuration. Do not commit real passwords or other secrets to version control.

### 2. Configure certificate storage

The application uses `CERTIFICATE_STORAGE_ROOT` as the root directory for generated PDF files. Confirm that this setting exists in Django settings and points to a writable directory.

For example:

```python
from pathlib import Path

CERTIFICATE_STORAGE_ROOT = BASE_DIR / "certificate_storage"
```

Use the actual `BASE_DIR` definition in your project. Keep generated certificate files out of public static-file directories unless public access is explicitly intended.

### 3. Apply database migrations

```powershell
python manage.py makemigrations
python manage.py migrate
```

If the migrations are already committed and up to date, `python manage.py migrate` is normally sufficient.

## Running the API

Start the Django development server:

```powershell
python manage.py runserver
```

The local base URL is:

```text
http://127.0.0.1:8000/
```

## API Endpoints

The API routes use the `/api/v1/` prefix.

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/v1/health/` | Check whether the API is running. |
| `POST` | `/api/v1/certificate-jobs/` | Submit a bulk certificate generation job. |
| `GET` | `/api/v1/certificate-jobs/{job_id}/` | Retrieve job details and status. |
| `GET` | `/api/v1/certificate-jobs/{job_id}/recipients/` | Retrieve recipients associated with a job. |
| `GET` | `/api/v1/certificate-jobs/{job_id}/recipients/{recipient_id}/` | Retrieve an individual recipient's details. |
| `GET` | `/api/v1/certificate-jobs/{job_id}/recipients/{recipient_id}/download/` | Download a successfully generated PDF certificate. |

Confirm the exact route names against the project's URL configuration before publishing the documentation.

## Health Check

Send a `GET` request to:

```http
GET /api/v1/health/
```

A successful response indicates that the API is running.

## Create a Bulk Certificate Job

Send a `POST` request to:

```http
POST /api/v1/certificate-jobs/
Content-Type: application/json
```

Example request:

```json
{
  "recipients": [
    {
      "recipient_name": "Aarav Sharma",
      "email": "aarav@example.com",
      "metadata": {
        "course_name": "Python Development",
        "organization_name": "Example Institute",
        "completion_date": "12 October 2026"
      }
    },
    {
      "recipient_name": "Priya Das",
      "email": "priya@example.com",
      "metadata": {
        "course_name": "Web Development",
        "organization_name": "Example Institute",
        "completion_date": "12 October 2026"
      }
    }
  ]
}
```

The `metadata` values supply certificate-specific information. Use the field names expected by the configured certificate template and PDF-generation service.

The API validates recipient records individually. Invalid recipients can be recorded as rejected while valid recipients proceed through processing. The bulk request serializer enforces a maximum of 500 recipients.

A successful job-creation response includes fields such as:

- `job_id` — the identifier of the created job.
- `status` — the resulting job status.
- `total_recipients` — the total number of submitted recipients.
- `accepted_count` — the number accepted for processing.
- `rejected_count` — the number rejected during validation.
- `rejected_recipients` — details of rejected records.

The creation endpoint currently processes accepted recipients synchronously before returning its response. Therefore, PDF generation time affects the response time for large requests.

## Job and Recipient Tracking

Each certificate job maintains overall processing information. Individual recipient records store their own statuses and, when applicable, error details and generated-file references.

The job statuses defined by the application are:

| Status | Meaning |
|---|---|
| `queued` | The job is waiting to be processed. |
| `processing` | Certificate processing is underway. |
| `completed` | All recipients were processed successfully. |
| `partial` | The job contains both successful and failed recipients. |
| `failed` | No recipients were successfully completed, or the job failed according to the service's status rules. |

Recipient records separately track whether an individual certificate is pending, completed, or failed.

The job's counters include total recipients, processed recipients, successful recipients, and failed recipients. The exact API response fields are determined by the configured read serializer and view.

### Retrieve job details

```http
GET /api/v1/certificate-jobs/{job_id}/
```

Use the returned job information to inspect the job's status and counters.

### List job recipients

```http
GET /api/v1/certificate-jobs/{job_id}/recipients/
```

The recipient listing uses limit-offset pagination. The configured default page size is 50 and the maximum page size is 100.

### Retrieve an individual recipient

```http
GET /api/v1/certificate-jobs/{job_id}/recipients/{recipient_id}/
```

The recipient must belong to the specified job. A recipient requested through the wrong job returns `404 Not Found`.

## Download a Certificate

```http
GET /api/v1/certificate-jobs/{job_id}/recipients/{recipient_id}/download/
```

The download endpoint checks that:

- The recipient belongs to the requested job.
- The recipient has completed processing.
- A file reference is present.
- The resolved file path stays inside the configured certificate storage directory.
- The certificate file exists.

A successful request returns a PDF attachment. An unavailable certificate can return `409 Conflict`, while missing records or files return `404 Not Found`. An invalid storage path returns `400 Bad Request`.

Generated PDFs are stored on the server; this project does not require a frontend to use the API.

## Error Handling

Recipient-level failures are recorded separately so one PDF-generation failure does not automatically stop processing other recipients. Validation and generation errors can be inspected through recipient records.

At the API level, standard HTTP status codes indicate whether requests succeeded or failed. Consult the actual endpoint responses and Swagger documentation for the precise response schemas.

## API Documentation

With the development server running, open:

- **Swagger UI:** `http://127.0.0.1:8000/api/docs/`
- **OpenAPI schema:** `http://127.0.0.1:8000/api/schema/`

Use Swagger UI to inspect available operations, request bodies, response definitions, and test API requests.

## Automated Testing

Run the full test suite:

```powershell
python manage.py test certificates
```

Run a specific test class:

```powershell
python manage.py test certificates.tests.CertificateJobCreationTests
python manage.py test certificates.tests.CertificateRetrievalTests
python manage.py test certificates.tests.CertificatePDFGenerationTests
```

The tests cover areas including job creation, recipient validation, retrieval endpoints, PDF file generation, and isolation of certificate-generation failures.

A passing test run should be confirmed before considering the project fully verified. If tests fail, inspect the traceback and resolve the underlying issue before treating the test suite as complete.

## Current Design Considerations

- **Synchronous processing:** - Jobs are processed within the creation request to keep the current implementation simple and avoid additional background-worker infrastructure. This supports straightforward processing and error tracking, but large batches can increase response times. Celery and Redis are not currently used.
- **File storage:** generated PDFs are stored locally under the configured storage root.
- **Recipient-level failure handling:** individual validation or generation failures are recorded without necessarily stopping processing for other recipients.
- **Pagination:** recipient listings use limit-offset pagination.
- **Scalability:** the configured limit is 500 recipients per request. Large requests may take longer because processing is synchronous.
- **Security:** the download endpoint validates file paths and checks recipient ownership through the requested job.

## Future Improvements

Possible future extensions include background processing for large jobs, configurable certificate templates, cloud-based file storage, authentication and authorization, and more detailed operational monitoring. These are future enhancements rather than claims about the current implementation.

## License

Add the project's chosen license and ownership information here before public distribution.