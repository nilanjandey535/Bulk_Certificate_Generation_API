from rest_framework import serializers
from .models import CertificateJob, CertificateRecipient


class RecipientInputSerializer(serializers.Serializer):
    recipient_name = serializers.CharField(
        max_length=200,
        trim_whitespace=True,
    )

    email = serializers.EmailField(
        required=False,
        allow_blank=True,
    )

    metadata = serializers.JSONField(
        required=False,
        default=dict,
    )

    def validate_metadata(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                "Metadata must be a JSON object."
            )
        return value


class BulkJobCreateSerializer(serializers.Serializer):
    recipients = serializers.ListField(
        child=serializers.JSONField(),
        allow_empty=False,
        max_length=500,
    )

class CertificateJobReadSerializer(serializers.ModelSerializer):
    progress_percentage = serializers.SerializerMethodField()

    class Meta:
        model = CertificateJob
        fields = [
            "id",
            "status",
            "total_recipients",
            "processed_count",
            "success_count",
            "failure_count",
            "progress_percentage",
            "created_at",
            "updated_at",
            "completed_at",
        ]
        read_only_fields = fields

    def get_progress_percentage(self, obj):
        if obj.total_recipients == 0:
            return 0

        return round(
            obj.processed_count / obj.total_recipients * 100,
            2,
        )


class CertificateRecipientReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = CertificateRecipient
        fields = [
            "id",
            "recipient_name",
            "email",
            "metadata",
            "status",
            "file_key",
            "error_message",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields