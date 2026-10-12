from django.urls import path

from .views import (
    certificate_job_detail,
    certificate_job_recipients,
    certificate_recipient_detail,
    create_certificate_job_view,
    get_certificate_job_status,
    download_certificate,
    health_check,
)

app_name = "certificates"

urlpatterns = [
    path("health/", health_check, name="health-check"),
    path(
        "certificate-jobs/",
        create_certificate_job_view,
        name="create-certificate-job",
    ),

    path(
        "certificate-jobs/<uuid:job_id>/",
        certificate_job_detail,
        name="certificate-job-detail",
    ),

    path(
        "certificate-jobs/<uuid:job_id>/recipients/",
        certificate_job_recipients,
        name="certificate-job-recipients",
    ),

    path(
        "certificate-jobs/<uuid:job_id>/recipients/<uuid:recipient_id>/",
        certificate_recipient_detail,
        name="certificate-recipient-detail",
    ),

    path(
        "certificate-jobs/<uuid:job_id>/recipients/<uuid:recipient_id>/download/",
        download_certificate,
        name="download-certificate",
    ),
]