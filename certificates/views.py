from pathlib import Path

from django.shortcuts import render
from django.shortcuts import get_object_or_404
from django.conf import settings
from django.http import FileResponse
from drf_spectacular.utils import extend_schema, OpenApiParameter

# Create your views here.
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import LimitOffsetPagination

from .serializers import BulkJobCreateSerializer
from .services import (create_certificate_job, process_certificate_job)

from .models import CertificateJob, CertificateRecipient
from .serializers import (
    CertificateJobReadSerializer,
    CertificateRecipientReadSerializer,
)


@api_view(["GET"])
def health_check(request):
    return Response(
        {
            "status": "ok",
            "service": "Bulk Certificate Generator API",
            "message": "API is running.",
        },
        status=status.HTTP_200_OK,
    )

@extend_schema(
    operation_id="create_certificate_job",
    summary="Create a bulk certificate generation job",
    description="Submit recipients to generate individual PDF certificates.",
    request=BulkJobCreateSerializer,
    responses={201: None},
)
@api_view(["POST"])
def create_certificate_job_view(request):
    request_serializer = BulkJobCreateSerializer(
        data=request.data
    )

    request_serializer.is_valid(raise_exception=True)

    recipients = request_serializer.validated_data["recipients"]

    job, rejected, accepted_count = create_certificate_job(
        recipients
    )

    generation_result = None

    if accepted_count:
        generation_result = process_certificate_job(job.id)
        job.refresh_from_db()

    return Response(
        {
            "job_id": str(job.id),
            "status": job.status,
            "total_recipients": job.total_recipients,
            "accepted_count": accepted_count,
            "rejected_count": len(rejected),
            "rejected_recipients": rejected,
        },
        status=status.HTTP_201_CREATED,
    )

@api_view(["GET"])
def certificate_job_detail(request, job_id):
    job = get_object_or_404(
        CertificateJob,
        id=job_id,
    )

    serializer = CertificateJobReadSerializer(job)

    return Response(serializer.data)


class RecipientPagination(LimitOffsetPagination):
    default_limit = 50
    max_limit = 100


@api_view(["GET"])
def certificate_job_recipients(request, job_id):
    job = get_object_or_404(
        CertificateJob,
        id=job_id,
    )

    recipients = CertificateRecipient.objects.filter(
        job=job,
    ).order_by("created_at", "id")

    paginator = RecipientPagination()
    page = paginator.paginate_queryset(
        recipients,
        request,
    )

    serializer = CertificateRecipientReadSerializer(
        page,
        many=True,
    )

    return paginator.get_paginated_response(serializer.data)


@api_view(["GET"])
def certificate_recipient_detail(
    request,
    job_id,
    recipient_id,
):
    recipient = get_object_or_404(
        CertificateRecipient.objects.select_related("job"),
        id=recipient_id,
        job_id=job_id,
    )

    serializer = CertificateRecipientReadSerializer(recipient)

    return Response(serializer.data)

@api_view(["GET"])
def get_certificate_job_status(request, job_id):
    job = get_object_or_404(
        CertificateJob,
        id=job_id,
    )

    recipients = job.recipients.all()

    total = job.total_recipients
    processed = job.processed_count

    progress = (
        round((processed / total) * 100, 2)
        if total > 0
        else 0
    )

    recipient_results = [
        {
            "recipient_id": str(recipient.id),
            "recipient_name": recipient.recipient_name,
            "email": recipient.email,
            "status": recipient.status,
            "error_message": recipient.error_message,
        }
        for recipient in recipients
    ]

    return Response({
        "job_id": str(job.id),
        "status": job.status,
        "progress_percent": progress,
        "total_recipients": total,
        "processed_count": processed,
        "success_count": job.success_count,
        "failure_count": job.failure_count,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "completed_at": job.completed_at,
        "recipients": recipient_results,
    })

@extend_schema(
    operation_id="download_certificate",
    summary="Download a generated certificate",
    description="Downloads the PDF certificate for a successfully processed recipient.",
    responses={
        200: {
            "type": "string",
            "format": "binary",
            "description": "Certificate PDF file",
        },
        400: {"description": "Invalid certificate file path"},
        404: {"description": "Certificate or file not found"},
        409: {"description": "Certificate is not available yet"},
    },
)

@api_view(["GET"])
def download_certificate(request, job_id, recipient_id):
    """
    Download a generated certificate PDF belonging to a specific job.
    """

    recipient = get_object_or_404(
        CertificateRecipient,
        id=recipient_id,
        job_id=job_id,
    )

    if recipient.status != CertificateRecipient.Status.COMPLETED:
        return Response(
            {
                "error": "This recipient's certificate is not available yet."
            },
            status=status.HTTP_409_CONFLICT,
        )

    if not recipient.file_key:
        return Response(
            {"error": "No certificate file is associated with this recipient."},
            status=status.HTTP_404_NOT_FOUND,
        )

    storage_root = Path(
        settings.CERTIFICATE_STORAGE_ROOT
    ).resolve()

    file_path = (storage_root / recipient.file_key).resolve()

    # Ensure the stored path cannot escape private storage.
    if not file_path.is_relative_to(storage_root):
        return Response(
            {"error": "Invalid certificate file path."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not file_path.is_file():
        return Response(
            {"error": "Certificate PDF file was not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    return FileResponse(
        file_path.open("rb"),
        as_attachment=True,
        filename=f"certificate-{recipient.id}.pdf",
        content_type="application/pdf",
    )
