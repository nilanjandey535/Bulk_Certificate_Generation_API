import uuid
from django.db import models
# Create your models here.


class CertificateJob(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        PARTIAL = "partial", "Partial"
        FAILED = "failed", "Failed"

    id = models.UUIDField(
        primary_key = True,
        default = uuid.uuid4,
        editable = False,
    )

    status = models.CharField(
        max_length = 20,
        choices = Status.choices,
        default = Status.QUEUED,
        db_index = True,
    )

    total_recipients = models.PositiveIntegerField(default = 0)
    processed_count = models.PositiveIntegerField(default = 0)
    success_count = models.PositiveIntegerField(default = 0)
    failure_count = models.PositiveIntegerField(default = 0)

    created_at = models.DateTimeField(auto_now_add = True)
    updated_at = models.DateTimeField(auto_now = True)
    completed_at = models.DateTimeField(
        null = True,
        blank = True,
    )

    class Meta:
        ordering = ["-created_at"]
        indexes =  [
            models.Index(
                fields = ["status", "created_at"],
                name = "certjob_status_created_idx",
            ),
        ]

    def __str__(self):
        return f"Certificate job {self.id}: {self.status}"


class CertificateRecipient(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    id = models.UUIDField(
        primary_key = True,
        default = uuid.uuid4,
        editable = False,
    )

    job = models.ForeignKey(
        CertificateJob,
        on_delete = models.CASCADE,
        related_name = "recipients",
    )

    recipient_name = models.CharField(max_length = 200)
    email = models.EmailField(blank = True)

    metadata = models.JSONField(default = dict, blank= True)

    status = models.CharField(
        max_length = 20,
        choices = Status.choices,
        default = Status.PENDING,
        db_index = True,
    )

    file_key = models.CharField(
        max_length = 500,
        blank = True,
    )

    error_message = models.TextField(blank = True)

    created_at = models.DateTimeField(auto_now_add = True)
    updated_at = models.DateTimeField(auto_now = True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(
                fields = ["job", "status"],
                name = "recipient_job_status_idx",
            ),
        ]

    def __str__(self):
        return f"{self.recipient_name} ({self.status})"
