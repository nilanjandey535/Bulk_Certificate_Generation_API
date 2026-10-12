
import json
import logging

from django.db import transaction
from django.utils import timezone

from .models import CertificateJob, CertificateRecipient
from .serializers import RecipientInputSerializer
from .pdf_service import generate_certificate_pdf

logger = logging.getLogger(__name__)


@transaction.atomic
def create_certificate_job(recipients):
    valid_recipients = []
    rejected_recipients = []

    for index, recipient_data in enumerate(recipients, start=1):
        serializer = RecipientInputSerializer(data=recipient_data)

        if serializer.is_valid():
            valid_recipients.append(serializer.validated_data)
        else:
            rejected_recipients.append({
                "index": index,
                "errors": serializer.errors,
            })

    rejected_count = len(rejected_recipients)
    valid_count = len(valid_recipients)

    job = CertificateJob.objects.create(
        total_recipients=len(recipients),
        processed_count=rejected_count,
        failure_count=rejected_count,
        status=(
            CertificateJob.Status.QUEUED
            if valid_count
            else CertificateJob.Status.FAILED
        ),
        completed_at=timezone.now() if not valid_count else None,
    )

    for recipient_data in valid_recipients:
        CertificateRecipient.objects.create(
            job=job,
            recipient_name=recipient_data["recipient_name"],
            email=recipient_data.get("email", ""),
            metadata=recipient_data.get("metadata", {}),
            status=CertificateRecipient.Status.PENDING,
        )

    for rejected in rejected_recipients:
        CertificateRecipient.objects.create(
            job=job,
            recipient_name=f"Invalid recipient #{rejected['index']}",
            email="",
            metadata={},
            status=CertificateRecipient.Status.FAILED,
            error_message=json.dumps(rejected["errors"]),
        )

    return job, rejected_recipients, valid_count


def process_certificate_job(job_id):
    """
    Generate PDFs synchronously for all pending recipients.
    A failure for one recipient does not stop the remaining recipients.
    """

    # Claim the job before processing it.
    with transaction.atomic():
        try:
            job = CertificateJob.objects.select_for_update().get(
                id=job_id
            )
        except CertificateJob.DoesNotExist:
            return {
                "status": "not_found",
                "job_id": str(job_id),
            }

        if job.status in {
            CertificateJob.Status.COMPLETED,
            CertificateJob.Status.PARTIAL,
            CertificateJob.Status.FAILED,
        }:
            return {
                "job_id": str(job.id),
                "status": job.status,
            }

        # Avoid processing the same job concurrently.
        if job.status == CertificateJob.Status.PROCESSING:
            return {
                "job_id": str(job.id),
                "status": job.status,
            }

        job.status = CertificateJob.Status.PROCESSING
        job.save(update_fields=["status", "updated_at"])

    # Process each recipient independently.
    recipient_ids = list(
        CertificateRecipient.objects.filter(
            job_id=job_id,
            status=CertificateRecipient.Status.PENDING,
        ).values_list("id", flat=True)
    )

    for recipient_id in recipient_ids:
        with transaction.atomic():
            recipient = (
                CertificateRecipient.objects.select_for_update().get(
                    id=recipient_id
                )
            )

            if recipient.status != CertificateRecipient.Status.PENDING:
                continue

            recipient.status = CertificateRecipient.Status.PROCESSING
            recipient.save(update_fields=["status", "updated_at"])

        try:
            # This call creates and saves the actual PDF.
            file_key = generate_certificate_pdf(recipient)

            recipient.status = CertificateRecipient.Status.COMPLETED
            recipient.file_key = file_key
            recipient.error_message = ""

        except Exception:
            logger.exception(
                "PDF generation failed for recipient %s",
                recipient.id,
            )
            recipient.status = CertificateRecipient.Status.FAILED
            recipient.error_message = (
                "Certificate generation failed. "
                "Check the server logs for details."
            )

        recipient.save(
            update_fields=[
                "status",
                "file_key",
                "error_message",
                "updated_at",
            ]
        )

    # Recalculate counts from the database, including invalid recipients.
    with transaction.atomic():
        job = CertificateJob.objects.select_for_update().get(
            id=job_id
        )

        completed_count = job.recipients.filter(
            status=CertificateRecipient.Status.COMPLETED
        ).count()

        failed_count = job.recipients.filter(
            status=CertificateRecipient.Status.FAILED
        ).count()

        pending_count = job.recipients.filter(
            status__in=[
                CertificateRecipient.Status.PENDING,
                CertificateRecipient.Status.PROCESSING,
            ]
        ).count()

        job.success_count = completed_count
        job.failure_count = failed_count
        job.processed_count = completed_count + failed_count

        if pending_count:
            job.status = CertificateJob.Status.PROCESSING
            job.completed_at = None
        elif completed_count and failed_count:
            job.status = CertificateJob.Status.PARTIAL
            job.completed_at = timezone.now()
        elif completed_count:
            job.status = CertificateJob.Status.COMPLETED
            job.completed_at = timezone.now()
        else:
            job.status = CertificateJob.Status.FAILED
            job.completed_at = timezone.now()

        job.save(
            update_fields=[
                "status",
                "success_count",
                "failure_count",
                "processed_count",
                "completed_at",
                "updated_at",
            ]
        )

    return {
        "job_id": str(job.id),
        "status": job.status,
        "total_recipients": job.total_recipients,
        "processed_count": job.processed_count,
        "success_count": job.success_count,
        "failure_count": job.failure_count,
    }
