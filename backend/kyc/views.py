from django.utils import timezone
from django.db.models import Avg, Count, Q, F, ExpressionWrapper, DurationField
from datetime import timedelta

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework.views import APIView

from kyc.models import User, KYCSubmission, Document, NotificationEvent
from kyc.serializers import (
    RegisterSerializer,
    LoginSerializer,
    UserSerializer,
    KYCSubmissionSerializer,
    KYCSubmissionUpdateSerializer,
    TransitionSerializer,
    DocumentSerializer,
    DashboardMetricsSerializer,
    NotificationEventSerializer,
)
from kyc.permissions import IsMerchant, IsReviewer, IsSubmissionOwner
from kyc.state_machine import apply_transition, IllegalTransitionError
from kyc.utils import log_notification




@api_view(["POST"])
@permission_classes([AllowAny])
def register(request):
    serializer = RegisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.save()
    token, _ = Token.objects.get_or_create(user=user)
    return Response(
        {"token": token.key, "user": UserSerializer(user).data},
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def login(request):
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.validated_data["user"]
    token, _ = Token.objects.get_or_create(user=user)
    return Response({"token": token.key, "user": UserSerializer(user).data})


@api_view(["GET"])
def me(request):
    return Response(UserSerializer(request.user).data)




class MySubmissionView(APIView):
    permission_classes = [IsMerchant]

    def _get_submission(self, user):
        sub, _ = KYCSubmission.objects.get_or_create(merchant=user)
        return sub

    def get(self, request):
        sub = self._get_submission(request.user)
        return Response(KYCSubmissionSerializer(sub).data)

    def patch(self, request):
        sub = self._get_submission(request.user)
        serializer = KYCSubmissionUpdateSerializer(sub, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(KYCSubmissionSerializer(sub).data)


@api_view(["POST"])
@permission_classes([IsMerchant])
def merchant_submit(request):
    """Submit KYC."""
    try:
        sub = KYCSubmission.objects.get(merchant=request.user)
    except KYCSubmission.DoesNotExist:
        return Response(
            {"error": True, "message": "No KYC submission found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Validate fields
    def is_blank(val):
        return val is None or str(val).strip() == ""

    required = ["full_name", "phone", "business_name", "business_type", "monthly_volume_usd"]
    missing = [f for f in required if is_blank(getattr(sub, f))]
    if missing:
        labels = {
            "full_name": "Full Name",
            "phone": "Phone Number",
            "business_name": "Business Name",
            "business_type": "Business Type",
            "monthly_volume_usd": "Monthly Volume",
        }
        return Response(
            {
                "error": True,
                "message": f"Please complete all required fields: {', '.join(labels.get(f, f) for f in missing)}",
                "missing_fields": missing,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        apply_transition(sub, "submitted")
    except IllegalTransitionError as e:
        return Response({"error": True, "message": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    log_notification(
        merchant=request.user,
        event_type="kyc_submitted",
        payload={"submission_id": sub.id, "state": "submitted", "resubmission": sub.submitted_at is not None},
    )

    return Response(KYCSubmissionSerializer(sub).data)




class ReviewerQueueView(APIView):
    """Reviewer queue."""
    permission_classes = [IsReviewer]

    ACTIVE_STATES = ["submitted", "under_review", "more_info_requested"]

    def get(self, request):
        state_filter = request.query_params.get("state", "active")

        if state_filter == "active":
            states = self.ACTIVE_STATES
        elif state_filter == "all":
            states = ["submitted", "under_review", "more_info_requested", "approved", "rejected", "draft"]
        elif state_filter in ("submitted", "under_review", "more_info_requested", "approved", "rejected", "draft"):
            states = [state_filter]
        else:
            return Response(
                {"error": True, "message": f"Invalid state filter '{state_filter}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        submissions = (
            KYCSubmission.objects.filter(state__in=states)
            .select_related("merchant", "assigned_reviewer")
            .prefetch_related("documents")
            .order_by("submitted_at", "created_at")
        )
        serializer = KYCSubmissionSerializer(submissions, many=True)
        return Response({
            "count": submissions.count(),
            "results": serializer.data,
        })


class ReviewerAllSubmissionsView(APIView):
    """All submissions."""
    permission_classes = [IsReviewer]

    def get(self, request):
        state = request.query_params.get("state")
        qs = KYCSubmission.objects.select_related("merchant").prefetch_related("documents")
        if state:
            qs = qs.filter(state=state)
        qs = qs.order_by("-updated_at")
        return Response(KYCSubmissionSerializer(qs, many=True).data)


class ReviewerSubmissionDetailView(APIView):
    permission_classes = [IsReviewer]

    def get(self, request, pk):
        try:
            sub = (
                KYCSubmission.objects.select_related("merchant", "assigned_reviewer")
                .prefetch_related("documents")
                .get(pk=pk)
            )
        except KYCSubmission.DoesNotExist:
            return Response(
                {"error": True, "message": "Submission not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(KYCSubmissionSerializer(sub).data)


@api_view(["POST"])
@permission_classes([IsReviewer])
def reviewer_transition(request, pk):
    """Transition submission state."""
    try:
        sub = KYCSubmission.objects.select_related("merchant").get(pk=pk)
    except KYCSubmission.DoesNotExist:
        return Response(
            {"error": True, "message": "Submission not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    serializer = TransitionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    new_state = serializer.validated_data["new_state"]
    note = serializer.validated_data.get("reviewer_note", "")

    # Note required for rejection/more info
    if new_state in ("rejected", "more_info_requested") and not note.strip():
        return Response(
            {"error": True, "message": f"A reviewer note is required when moving to '{new_state}'."},
            status=status.HTTP_400_BAD_REQUEST,
        )


    if new_state == "under_review" and sub.assigned_reviewer is None:
        sub.assigned_reviewer = request.user
        sub.save(update_fields=["assigned_reviewer"])

    try:
        old_state = apply_transition(sub, new_state, reviewer_note=note)
    except IllegalTransitionError as e:
        return Response({"error": True, "message": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    log_notification(
        merchant=sub.merchant,
        event_type=f"kyc_{new_state}",
        payload={
            "submission_id": sub.id,
            "old_state": old_state,
            "new_state": new_state,
            "reviewer_note": note,
            "reviewer_id": request.user.id,
            "reviewer_username": request.user.username,
        },
    )

    return Response(KYCSubmissionSerializer(sub).data)




@api_view(["GET"])
@permission_classes([IsReviewer])
def dashboard_metrics(request):
    """Dashboard stats."""
    active_states = ["submitted", "under_review", "more_info_requested"]
    now = timezone.now()
    sla_cutoff = now - timedelta(hours=24)
    seven_days_ago = now - timedelta(days=7)

    queue_qs = KYCSubmission.objects.filter(state__in=active_states)

    total_in_queue = queue_qs.count()
    at_risk_count = queue_qs.filter(submitted_at__lt=sla_cutoff).count()

    avg_age = None
    if total_in_queue > 0:
        avg_duration = queue_qs.filter(submitted_at__isnull=False).aggregate(
            avg_age=Avg(
                ExpressionWrapper(now - F("submitted_at"), output_field=DurationField())
            )
        )["avg_age"]
        if avg_duration:
            avg_age = round(avg_duration.total_seconds() / 3600, 1)

    recent = KYCSubmission.objects.filter(
        state__in=["approved", "rejected"],
        updated_at__gte=seven_days_ago,
    )
    total_approved_7d = recent.filter(state="approved").count()
    total_resolved_7d = recent.count()
    approval_rate_7d = (
        round(total_approved_7d / total_resolved_7d * 100, 1)
        if total_resolved_7d > 0
        else None
    )


    state_counts = {
        s: KYCSubmission.objects.filter(state=s).count()
        for s in ["draft", "submitted", "under_review", "more_info_requested", "approved", "rejected"]
    }
    state_counts["active"] = total_in_queue

    data = {
        "total_in_queue": total_in_queue,
        "at_risk_count": at_risk_count,
        "avg_queue_age_hours": avg_age,
        "approval_rate_7d": approval_rate_7d,
        "total_approved_7d": total_approved_7d,
        "total_resolved_7d": total_resolved_7d,
        "state_counts": state_counts,
    }
    return Response(data)




@api_view(["POST", "DELETE"])
@permission_classes([IsMerchant])
def upload_document(request, doc_type):
    """Upload or delete documents."""
    valid_types = [d[0] for d in Document.DOC_TYPE_CHOICES]
    if doc_type not in valid_types:
        return Response(
            {"error": True, "message": f"Invalid doc_type '{doc_type}'. Must be one of: {valid_types}"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    sub, _ = KYCSubmission.objects.get_or_create(merchant=request.user)

    if sub.state not in ("draft", "more_info_requested"):
        return Response(
            {"error": True, "message": f"Cannot upload documents when submission is in '{sub.state}' state."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if request.method == "DELETE":
        deleted, _ = Document.objects.filter(submission=sub, doc_type=doc_type).delete()
        if deleted == 0:
            return Response(
                {"error": True, "message": f"No document of type '{doc_type}' found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    # POST: validate presence
    if "file" not in request.FILES:
        return Response(
            {"error": True, "message": "No file provided. Include a 'file' field in the multipart form."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Upsert: delete existing then create new
    Document.objects.filter(submission=sub, doc_type=doc_type).delete()

    serializer = DocumentSerializer(data={"doc_type": doc_type, "file": request.FILES["file"]})
    serializer.is_valid(raise_exception=True)
    doc = serializer.save(submission=sub)

    return Response(DocumentSerializer(doc).data, status=status.HTTP_201_CREATED)




@api_view(["GET"])
@permission_classes([IsAuthenticated])
def notification_events(request):
    """Notification audit log."""
    qs = NotificationEvent.objects.select_related("merchant").all()
    if request.user.role == "merchant":
        qs = qs.filter(merchant=request.user)
    elif merchant_id := request.query_params.get("merchant_id"):
        qs = qs.filter(merchant_id=merchant_id)

    # Optional submission filter
    if submission_id := request.query_params.get("submission_id"):
        qs = qs.filter(payload__submission_id=submission_id)

    qs = qs.order_by("-timestamp")[:100]
    return Response(NotificationEventSerializer(qs, many=True).data)




@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    return Response({"status": "ok", "time": timezone.now().isoformat()})
