from django.test import TestCase
import tempfile
from rest_framework import status
from rest_framework.test import APITestCase

from .models import CertificateJob, CertificateRecipient
from pathlib import Path
from unittest.mock import patch

from django.test import override_settings
from .services import process_certificate_job

from .pdf_service import generate_certificate_pdf

class CertificateJobCreationTests(APITestCase):
    url = "/api/v1/certificate-jobs/"

    def test_create_job_with_valid_recipients(self):
        payload = {
            "recipients": [
                {
                    "recipient_name": "Aarav Sharma",
                    "email": "aarav@example.com",
                },
                {
                    "recipient_name": "Priya Das",
                    "email": "priya@example.com",
                },
            ]
        }

        response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )
        self.assertEqual(response.data["accepted_count"], 2)
        self.assertEqual(response.data["rejected_count"], 0)
        self.assertEqual(response.data["status"], "completed")

        job = CertificateJob.objects.get(
            id=response.data["job_id"]
        )
        self.assertEqual(job.recipients.count(), 2)

    def test_invalid_recipient_does_not_block_valid_ones(self):
        payload = {
            "recipients": [
                {
                    "recipient_name": "Aarav Sharma",
                    "email": "aarav@example.com",
                },
                {
                    "recipient_name": "Priya Das",
                    "email": "invalid-email",
                },
            ]
        }

        response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )
        self.assertEqual(response.data["accepted_count"], 1)
        self.assertEqual(response.data["rejected_count"], 1)

        job = CertificateJob.objects.get(
            id=response.data["job_id"]
        )

        self.assertEqual(job.recipients.count(), 2)
        self.assertEqual(job.success_count, 1)
        self.assertEqual(job.failure_count, 1)
        self.assertEqual(job.processed_count, 2)
        self.assertEqual(job.status, CertificateJob.Status.PARTIAL)

        failed_recipient = job.recipients.get(
            status=CertificateRecipient.Status.FAILED
        )
        self.assertIn("email", failed_recipient.error_message)

    def test_empty_recipient_list_is_rejected(self):
        response = self.client.post(
            self.url,
            {"recipients": []},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(CertificateJob.objects.count(), 0)

    def test_missing_recipient_name_is_rejected_individually(self):
        response = self.client.post(
            self.url,
            {
                "recipients": [
                    {
                        "email": "missing-name@example.com",
                    },
                    {
                        "recipient_name": "Valid Recipient",
                        "email": "valid@example.com",
                    },
                ]
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )
        self.assertEqual(response.data["accepted_count"], 1)
        self.assertEqual(response.data["rejected_count"], 1)

    def test_all_invalid_recipients_produce_failed_job(self):
        response = self.client.post(
            self.url,
            {
                "recipients": [
                    {"email": "invalid@example.com"},
                ]
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )
        self.assertEqual(response.data["accepted_count"], 0)
        self.assertEqual(response.data["status"], "failed")


class CertificateRetrievalTests(APITestCase):
    def setUp(self):
        self.job = CertificateJob.objects.create(
            total_recipients=2,
            processed_count=1,
            failure_count=1,
        )

        self.recipient = CertificateRecipient.objects.create(
            job=self.job,
            recipient_name="Aarav Sharma",
            email="aarav@example.com",
            status=CertificateRecipient.Status.PENDING,
        )

        self.failed_recipient = CertificateRecipient.objects.create(
            job=self.job,
            recipient_name="Invalid recipient #2",
            status=CertificateRecipient.Status.FAILED,
            error_message='{"email": ["Enter a valid email address."]}',
        )

    def test_retrieve_job_status(self):
        response = self.client.get(
            f"/api/v1/certificate-jobs/{self.job.id}/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "queued")
        self.assertEqual(response.data["total_recipients"], 2)
        self.assertEqual(response.data["progress_percentage"], 50.0)

    def test_list_job_recipients(self):
        response = self.client.get(
            f"/api/v1/certificate-jobs/{self.job.id}/recipients/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(len(response.data["results"]), 2)

    def test_retrieve_one_recipient(self):
        response = self.client.get(
            f"/api/v1/certificate-jobs/{self.job.id}/"
            f"recipients/{self.recipient.id}/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["recipient_name"],
            "Aarav Sharma",
        )

    def test_recipient_cannot_be_retrieved_through_wrong_job(self):
        other_job = CertificateJob.objects.create(
            total_recipients=0,
        )

        response = self.client.get(
            f"/api/v1/certificate-jobs/{other_job.id}/"
            f"recipients/{self.recipient.id}/"
        )

        self.assertEqual(response.status_code, 404)

    def test_unknown_job_returns_404(self):
        import uuid

        response = self.client.get(
            f"/api/v1/certificate-jobs/{uuid.uuid4()}/"
        )

        self.assertEqual(response.status_code, 404)

    
    def test_download_generated_certificate(self):
        import tempfile
        from pathlib import Path
        from django.test import override_settings

        with tempfile.TemporaryDirectory() as temp_dir:
            storage_root = Path(temp_dir)
            relative_key = (
                f"certificates/{self.job.id}/{self.recipient.id}.pdf"
            )
            pdf_path = storage_root / relative_key
            pdf_path.parent.mkdir(parents=True, exist_ok=True)
            pdf_path.write_bytes(b"%PDF-1.4 test certificate")

            self.recipient.status = CertificateRecipient.Status.COMPLETED
            self.recipient.file_key = relative_key
            self.recipient.save(
                update_fields=["status", "file_key", "updated_at"]
            )

            with override_settings(CERTIFICATE_STORAGE_ROOT=storage_root):
                response = self.client.get(
                    f"/api/v1/certificate-jobs/{self.job.id}/"
                    f"recipients/{self.recipient.id}/download/"
                )

            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                response["Content-Type"],
                "application/pdf",
            )
            self.assertIn(
                ".pdf",
                response["Content-Disposition"],
            )

            response.close()



class CertificatePDFGenerationTests(APITestCase):
    def setUp(self):
        self.storage = tempfile.TemporaryDirectory()
        self.addCleanup(self.storage.cleanup)

        self.storage_override = override_settings(
            CERTIFICATE_STORAGE_ROOT=Path(self.storage.name)
        )
        self.storage_override.enable()
        self.addCleanup(self.storage_override.disable)

        self.job = CertificateJob.objects.create(
            total_recipients=1,
        )

        self.recipient = CertificateRecipient.objects.create(
            job=self.job,
            recipient_name="Aarav Sharma",
            email="aarav@example.com",
            metadata={
                "course_name": "Python Development",
                "organization_name": "Test Institute",
                "completion_date": "12 October 2026",
            },
        )

    def test_pdf_generation_creates_valid_pdf_file(self):
        file_key = generate_certificate_pdf(self.recipient)

        pdf_path = Path(self.storage.name) / file_key

        self.assertTrue(pdf_path.is_file())
        self.assertGreater(pdf_path.stat().st_size, 0)

        with pdf_path.open("rb") as pdf_file:
            self.assertEqual(pdf_file.read(5), b"%PDF-")

    @patch(
        "certificates.services.generate_certificate_pdf",
        side_effect=[RuntimeError("Simulated PDF failure"), "certificates/test.pdf"],
    )
    def test_one_generation_failure_does_not_stop_other_recipients(
        self, mock_generate
    ):
        second_recipient = CertificateRecipient.objects.create(
            job=self.job,
            recipient_name="Priya Das",
            email="priya@example.com",
            metadata={"course_name": "Web Development"},
        )

        result = process_certificate_job(self.job.id)

        self.recipient.refresh_from_db()
        second_recipient.refresh_from_db()
        self.job.refresh_from_db()

        self.assertEqual(mock_generate.call_count, 2)

        self.assertEqual(
            self.recipient.status,
            CertificateRecipient.Status.FAILED,
        )
        self.assertIn(
            "generation failed",
            self.recipient.error_message.lower(),
        )

        self.assertEqual(
            second_recipient.status,
            CertificateRecipient.Status.COMPLETED,
        )
        self.assertEqual(
            second_recipient.file_key,
            "certificates/test.pdf",
        )

        self.assertEqual(self.job.status, CertificateJob.Status.PARTIAL)
        self.assertEqual(self.job.success_count, 1)
        self.assertEqual(self.job.failure_count, 1)
        self.assertEqual(self.job.processed_count, 2)
        self.assertEqual(result["status"], CertificateJob.Status.PARTIAL)
