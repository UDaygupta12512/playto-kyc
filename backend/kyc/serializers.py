from rest_framework import serializers
from django.contrib.auth import authenticate
from rest_framework.authtoken.models import Token

from kyc.models import User, KYCSubmission, Document, NotificationEvent
from kyc.validators import validate_upload
from kyc.state_machine import get_allowed_transitions




class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)

    class Meta:
        model = User
        fields = ["username", "email", "password", "role"]
        extra_kwargs = {"role": {"default": "merchant"}}

    def validate_role(self, value):
        if value not in ("merchant", "reviewer"):
            raise serializers.ValidationError("role must be 'merchant' or 'reviewer'.")
        return value

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data.get("email", ""),
            password=validated_data["password"],
            role=validated_data.get("role", "merchant"),
        )

        if user.role == "merchant":
            KYCSubmission.objects.create(merchant=user)
        return user


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = authenticate(username=data["username"], password=data["password"])
        if not user:
            raise serializers.ValidationError("Invalid username or password.")
        data["user"] = user
        return data


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email", "role"]




class DocumentSerializer(serializers.ModelSerializer):
    file = serializers.FileField(use_url=True)

    class Meta:
        model = Document
        fields = ["id", "doc_type", "file", "original_filename", "uploaded_at"]
        read_only_fields = ["id", "original_filename", "uploaded_at"]

    def validate_file(self, value):
        """Validate uploaded file types and size."""
        validate_upload(value)
        return value

    def create(self, validated_data):
        file = validated_data["file"]
        validated_data["original_filename"] = file.name
        return super().create(validated_data)




class KYCSubmissionSerializer(serializers.ModelSerializer):
    documents = DocumentSerializer(many=True, read_only=True)
    merchant = UserSerializer(read_only=True)
    is_at_risk = serializers.BooleanField(read_only=True)
    allowed_transitions = serializers.SerializerMethodField()
    queue_age_hours = serializers.SerializerMethodField()

    class Meta:
        model = KYCSubmission
        fields = [
            "id",
            "merchant",
            "full_name",
            "phone",
            "business_name",
            "business_type",
            "monthly_volume_usd",
            "state",
            "reviewer_note",
            "assigned_reviewer",
            "submitted_at",
            "created_at",
            "updated_at",
            "is_at_risk",
            "allowed_transitions",
            "queue_age_hours",
            "documents",
        ]
        read_only_fields = [
            "id",
            "merchant",
            "state",
            "submitted_at",
            "created_at",
            "updated_at",
            "is_at_risk",
            "allowed_transitions",
            "queue_age_hours",
        ]

    def get_allowed_transitions(self, obj):
        return get_allowed_transitions(obj.state)

    def get_queue_age_hours(self, obj):
        from django.utils import timezone
        if obj.submitted_at is None:
            return None
        delta = timezone.now() - obj.submitted_at
        return round(delta.total_seconds() / 3600, 1)


class KYCSubmissionUpdateSerializer(serializers.ModelSerializer):
    """For merchants to update their own draft submission (Steps 1 & 2)."""

    class Meta:
        model = KYCSubmission
        fields = [
            "full_name",
            "phone",
            "business_name",
            "business_type",
            "monthly_volume_usd",
        ]

    def validate(self, data):
        instance = self.instance
        if instance and instance.state not in ("draft", "more_info_requested"):
            raise serializers.ValidationError(
                f"Cannot edit a submission in '{instance.state}' state. "
                "Only draft or more_info_requested submissions can be edited."
            )
        return data




class TransitionSerializer(serializers.Serializer):
    """State transition validator."""
    new_state = serializers.CharField()
    reviewer_note = serializers.CharField(allow_blank=True, required=False, default="")

    def validate_new_state(self, value):
        from kyc.state_machine import ALL_STATES
        if value not in ALL_STATES:
            raise serializers.ValidationError(
                f"'{value}' is not a valid state. Choices: {ALL_STATES}"
            )
        return value




class DashboardMetricsSerializer(serializers.Serializer):
    total_in_queue = serializers.IntegerField()
    at_risk_count = serializers.IntegerField()
    avg_queue_age_hours = serializers.FloatField(allow_null=True)
    approval_rate_7d = serializers.FloatField(allow_null=True)
    total_approved_7d = serializers.IntegerField()
    total_resolved_7d = serializers.IntegerField()




class NotificationEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationEvent
        fields = ["id", "merchant_id", "event_type", "timestamp", "payload"]
