
import time

from django.core.management.base import BaseCommand
from django.db import transaction

from certificates.models import CertificateJob
from certificates.services import process_certificate_job


class Command(BaseCommand):
    help = "Find queued certificate jobs in PostgreSQL."

    def add_arguments(self, parser):
        parser.add_argument(
            "--once",
            action="store_true",
            help="Check for queued jobs once and exit.",
        )
        parser.add_argument(
            "--interval",
            type=int,
            default=5,
            help="Seconds to wait between checks.",
        )

    def handle(self, *args, **options):
        run_once = options["once"]
        interval = max(1, options["interval"])

        self.stdout.write(
            self.style.SUCCESS(
                "Certificate worker started."
            )
        )

        while True:
            job_id = self.claim_next_job()

            if job_id:
                self.stdout.write(f"Processing job: {job_id}")

                try:
                    process_certificate_job(job_id)
                    self.stdout.write(self.style.SUCCESS(f"Finished job: {job_id}"))

                except Exception as exc:
                    self.stderr.write(self.style.ERROR(f"Could not process {job_id}: {exc}"))
            
            else:
                self.stdout.write(
                    "No queued jobs found."
                )

            if run_once:
                break

            time.sleep(interval)

    def claim_next_job(self):
        with transaction.atomic():
            job = (
                CertificateJob.objects
                .select_for_update(skip_locked=True)
                .filter(status=CertificateJob.Status.QUEUED)
                .order_by("created_at")
                .first()
            )

            if job is None:
                return None

            job.status = CertificateJob.Status.PROCESSING
            job.save(update_fields=["status", "updated_at"])

            return job.id
