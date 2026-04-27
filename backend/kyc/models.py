from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    ROLE_MERCHANT = "merchant"
    ROLE_REVIEWER = "reviewer"
    ROLE_CHOICES = [
        (ROLE_MERCHANT, "Merchant"),
        (ROLE_REVIEWER, "Reviewer"),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_MERCHANT)

    class Meta:
        db_table = "users"

    def is_merchant(self):
        return self.role == self.ROLE_MERCHANT

    def is_reviewer(self):
        return self.role == self.ROLE_REVIEWER


class KYCSubmission(models.Model):
    STATE_DRAFT = "draft"
    STATE_SUBMITTED = "submitted"
    STATE_UNDER_REVIEW = "under_review"
    STATE_APPROVED = "approved"
    STATE_REJECTED = "rejected"
    STATE_MORE_INFO = "more_info_requested"

    STATE_CHOICES = [
        (STATE_DRAFT, "Draft"),
        (STATE_SUBMITTED, "Submitted"),
        (STATE_UNDER_REVIEW, "Under Review"),
        (STATE_APPROVED, "Approved"),
        (STATE_REJECTED, "Rejected"),
        (STATE_MORE_INFO, "More Info Requested"),
    ]

    BUSINESS_TYPE_CHOICES = [
        ("individual", "Individual / Freelancer"),
        ("sole_proprietorship", "Sole Proprietorship"),
        ("partnership", "Partnership"),
        ("pvt_ltd", "Private Limited"),
        ("llp", "LLP"),
        ("other", "Other"),
    ]

    merchant = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="kyc_submission",
        limit_choices_to={"role": "merchant"},
    )

    full_name = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=20, blank=True)

    business_name = models.CharField(max_length=255, blank=True)
    business_type = models.CharField(
        max_length=50, choices=BUSINESS_TYPE_CHOICES, blank=True
    )
    monthly_volume_usd = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )

    state = models.CharField(
        max_length=30, choices=STATE_CHOICES, default=STATE_DRAFT, db_index=True
    )
    reviewer_note = models.TextField(blank=True)
    assigned_reviewer = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_submissions",
        limit_choices_to={"role": "reviewer"},
    )

    submitted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "kyc_submissions"
        ordering = ["submitted_at"]

    def __str__(self):
        return f"KYC#{self.pk} — {self.merchant.username} [{self.state}]"

    @property
    def is_at_risk(self) -> bool:
        """SLA flag: true if in queue for >24 hours."""
        SLA_HOURS = 24
        at_risk_states = {
            self.STATE_SUBMITTED,
            self.STATE_UNDER_REVIEW,
            self.STATE_MORE_INFO,
        }
        if self.state not in at_risk_states or self.submitted_at is None:
            return False
        age = timezone.now() - self.submitted_at
        return age.total_seconds() > SLA_HOURS * 3600


class Document(models.Model):
    DOC_PAN = "pan"
    DOC_AADHAAR = "aadhaar"
    DOC_BANK_STATEMENT = "bank_statement"

    DOC_TYPE_CHOICES = [
        (DOC_PAN, "PAN Card"),
        (DOC_AADHAAR, "Aadhaar Card"),
        (DOC_BANK_STATEMENT, "Bank Statement"),
    ]

    submission = models.ForeignKey(
        KYCSubmission, on_delete=models.CASCADE, related_name="documents"
    )
    doc_type = models.CharField(max_length=30, choices=DOC_TYPE_CHOICES)
    file = models.FileField(upload_to="kyc_docs/")
    original_filename = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "kyc_documents"
        unique_together = [("submission", "doc_type")]

    def __str__(self):
        return f"{self.doc_type} for KYC#{self.submission_id}"


class NotificationEvent(models.Model):
    merchant = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notification_events",
    )
    event_type = models.CharField(max_length=100)  # e.g. "kyc_submitted", "kyc_approved"
    timestamp = models.DateTimeField(auto_now_add=True)
    payload = models.JSONField()  # Includes state, note, reviewer_id, etc.

    class Meta:
        db_table = "notification_events"
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.event_type} for user#{self.merchant_id} at {self.timestamp}"
