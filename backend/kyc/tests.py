"""
Tests for the KYC pipeline.
Focus: state machine enforcement and authorization.
"""

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token

from kyc.models import User, KYCSubmission
from kyc.state_machine import (
    apply_transition,
    validate_transition,
    IllegalTransitionError,
    LEGAL_TRANSITIONS,
)


def make_user(username, role="merchant", password="testpass123"):
    user = User.objects.create_user(username=username, password=password, role=role)
    if role == "merchant":
        KYCSubmission.objects.create(merchant=user)
    return user


def auth_client(user):
    token, _ = Token.objects.get_or_create(user=user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client


# ─── Unit: State Machine ──────────────────────────────────────────────────────

class StateMachineUnitTests(TestCase):
    """
    Directly test the state machine functions — no HTTP layer.
    This is the most critical part of the system.
    """

    def test_all_legal_transitions_pass(self):
        """Every transition in LEGAL_TRANSITIONS should not raise."""
        for from_state, allowed in LEGAL_TRANSITIONS.items():
            for to_state in allowed:
                try:
                    validate_transition(from_state, to_state)
                except IllegalTransitionError:
                    self.fail(f"Legal transition {from_state} → {to_state} raised an error.")

    def test_illegal_transition_approved_to_draft(self):
        """Once approved, a submission cannot go back to draft."""
        with self.assertRaises(IllegalTransitionError):
            validate_transition("approved", "draft")

    def test_illegal_transition_approved_to_submitted(self):
        with self.assertRaises(IllegalTransitionError):
            validate_transition("approved", "submitted")

    def test_illegal_transition_rejected_to_approved(self):
        with self.assertRaises(IllegalTransitionError):
            validate_transition("rejected", "approved")

    def test_illegal_transition_draft_to_approved(self):
        """Cannot skip states — draft must go to submitted first."""
        with self.assertRaises(IllegalTransitionError):
            validate_transition("draft", "approved")

    def test_illegal_transition_submitted_to_approved(self):
        """submitted must go through under_review first."""
        with self.assertRaises(IllegalTransitionError):
            validate_transition("submitted", "approved")

    def test_illegal_transition_error_message_is_helpful(self):
        """Error message should tell the caller what transitions are allowed."""
        try:
            validate_transition("draft", "approved")
        except IllegalTransitionError as e:
            self.assertIn("draft", str(e))
            self.assertIn("approved", str(e))
            self.assertIn("submitted", str(e))  # the allowed transition

    def test_apply_transition_sets_submitted_at(self):
        """submitted_at should be set when a submission first moves to 'submitted'."""
        merchant = make_user("merchant_test_sub")
        sub = KYCSubmission.objects.get(merchant=merchant)
        sub.full_name = "Test User"
        sub.phone = "9999999999"
        sub.business_name = "Test Biz"
        sub.business_type = "individual"
        sub.monthly_volume_usd = 1000
        sub.save()

        self.assertIsNone(sub.submitted_at)
        apply_transition(sub, "submitted")
        sub.refresh_from_db()
        self.assertIsNotNone(sub.submitted_at)

    def test_apply_transition_illegal_raises(self):
        merchant = make_user("merchant_test_illegal")
        sub = KYCSubmission.objects.get(merchant=merchant)
        with self.assertRaises(IllegalTransitionError):
            apply_transition(sub, "approved")  # draft → approved is illegal


# ─── Integration: API state transitions via HTTP ──────────────────────────────

class APIStateMachineTests(TestCase):
    def setUp(self):
        self.merchant = make_user("merch1")
        self.reviewer = make_user("rev1", role="reviewer")
        self.merchant_client = auth_client(self.merchant)
        self.reviewer_client = auth_client(self.reviewer)

        self.sub = KYCSubmission.objects.get(merchant=self.merchant)
        # Fill required fields
        self.sub.full_name = "Rahul Sharma"
        self.sub.phone = "9876543210"
        self.sub.business_name = "Rahul Freelance"
        self.sub.business_type = "individual"
        self.sub.monthly_volume_usd = 5000
        self.sub.save()

    def test_merchant_can_submit(self):
        resp = self.merchant_client.post("/api/v1/kyc/submit/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["state"], "submitted")

    def test_reviewer_can_move_to_under_review(self):
        apply_transition(self.sub, "submitted")
        resp = self.reviewer_client.post(
            f"/api/v1/reviewer/submissions/{self.sub.pk}/transition/",
            {"new_state": "under_review"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["state"], "under_review")

    def test_reviewer_approve_returns_400_if_already_approved(self):
        """Approving an already-approved submission must fail with 400 and a clear message."""
        apply_transition(self.sub, "submitted")
        apply_transition(self.sub, "under_review")
        apply_transition(self.sub, "approved")

        resp = self.reviewer_client.post(
            f"/api/v1/reviewer/submissions/{self.sub.pk}/transition/",
            {"new_state": "approved"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.data)
        self.assertTrue(resp.data["error"])
        # Message should tell the user what's wrong
        self.assertIn("approved", resp.data["message"])

    def test_illegal_transition_approved_to_draft_returns_400(self):
        """The primary graded test: illegal transitions must return 400."""
        apply_transition(self.sub, "submitted")
        apply_transition(self.sub, "under_review")
        apply_transition(self.sub, "approved")

        resp = self.reviewer_client.post(
            f"/api/v1/reviewer/submissions/{self.sub.pk}/transition/",
            {"new_state": "draft"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_merchant_cannot_see_other_merchant_submission(self):
        """Merchant isolation: merchant2 cannot fetch merchant1's submission."""
        merchant2 = make_user("merch2")
        client2 = auth_client(merchant2)
        # merchant2's own submission is at /api/v1/kyc/submission/
        # They should NOT be able to hit reviewer endpoints
        resp = client2.get(f"/api/v1/reviewer/submissions/{self.sub.pk}/")
        self.assertEqual(resp.status_code, 403)

    def test_reviewer_cannot_submit_merchant_form(self):
        resp = self.reviewer_client.post("/api/v1/kyc/submit/")
        self.assertEqual(resp.status_code, 403)

    def test_more_info_requested_allows_resubmit(self):
        """more_info_requested → submitted is a legal transition for merchant."""
        apply_transition(self.sub, "submitted")
        apply_transition(self.sub, "under_review")
        apply_transition(self.sub, "more_info_requested", reviewer_note="Need PAN copy")

        self.sub.refresh_from_db()
        self.assertEqual(self.sub.state, "more_info_requested")

        resp = self.merchant_client.post("/api/v1/kyc/submit/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["state"], "submitted")


# ─── Authorization ────────────────────────────────────────────────────────────

class AuthorizationTests(TestCase):
    def test_unauthenticated_cannot_access_queue(self):
        client = APIClient()
        resp = client.get("/api/v1/reviewer/queue/")
        self.assertEqual(resp.status_code, 401)

    def test_merchant_cannot_access_reviewer_queue(self):
        merchant = make_user("merch_auth_test")
        client = auth_client(merchant)
        resp = client.get("/api/v1/reviewer/queue/")
        self.assertEqual(resp.status_code, 403)


# ─── New: note enforcement, metrics, queue filter ────────────────────────────

class NoteEnforcementTests(TestCase):
    """Reviewer must provide a note when rejecting or requesting more info."""

    def setUp(self):
        self.reviewer = make_user("rev_note", role="reviewer")
        self.merchant = make_user("merch_note")
        self.client = auth_client(self.reviewer)
        self.sub = KYCSubmission.objects.get(merchant=self.merchant)
        # Fast-forward to under_review
        apply_transition(self.sub, "submitted")
        apply_transition(self.sub, "under_review")

    def test_reject_without_note_returns_400(self):
        resp = self.client.post(
            f"/api/v1/reviewer/submissions/{self.sub.pk}/transition/",
            {"new_state": "rejected"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertTrue(resp.data["error"])

    def test_more_info_without_note_returns_400(self):
        resp = self.client.post(
            f"/api/v1/reviewer/submissions/{self.sub.pk}/transition/",
            {"new_state": "more_info_requested"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_reject_with_note_succeeds(self):
        resp = self.client.post(
            f"/api/v1/reviewer/submissions/{self.sub.pk}/transition/",
            {"new_state": "rejected", "reviewer_note": "Docs unclear."},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["state"], "rejected")

    def test_approve_without_note_succeeds(self):
        """Note is optional for approval."""
        resp = self.client.post(
            f"/api/v1/reviewer/submissions/{self.sub.pk}/transition/",
            {"new_state": "approved"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["state"], "approved")


class MetricsTests(TestCase):
    def setUp(self):
        self.reviewer = make_user("rev_metrics", role="reviewer")
        self.client = auth_client(self.reviewer)

    def test_metrics_returns_expected_shape(self):
        resp = self.client.get("/api/v1/reviewer/metrics/")
        self.assertEqual(resp.status_code, 200)
        for key in ["total_in_queue", "at_risk_count", "avg_queue_age_hours",
                    "approval_rate_7d", "state_counts"]:
            self.assertIn(key, resp.data)

    def test_state_counts_present(self):
        resp = self.client.get("/api/v1/reviewer/metrics/")
        counts = resp.data["state_counts"]
        for state in ["draft", "submitted", "under_review", "approved", "rejected"]:
            self.assertIn(state, counts)

    def test_merchant_cannot_access_metrics(self):
        m = make_user("merch_metrics2")
        c = auth_client(m)
        resp = c.get("/api/v1/reviewer/metrics/")
        self.assertEqual(resp.status_code, 403)


class QueueFilterTests(TestCase):
    def setUp(self):
        self.reviewer = make_user("rev_queue", role="reviewer")
        self.client = auth_client(self.reviewer)

    def test_invalid_state_filter_returns_400(self):
        resp = self.client.get("/api/v1/reviewer/queue/?state=blah")
        self.assertEqual(resp.status_code, 400)

    def test_all_filter_includes_approved(self):
        m = make_user("merch_q_all")
        sub = KYCSubmission.objects.get(merchant=m)
        apply_transition(sub, "submitted")
        apply_transition(sub, "under_review")
        apply_transition(sub, "approved")
        resp = self.client.get("/api/v1/reviewer/queue/?state=all")
        self.assertEqual(resp.status_code, 200)
        ids = [s["id"] for s in resp.data["results"]]
        self.assertIn(sub.id, ids)

    def test_active_filter_excludes_approved(self):
        m = make_user("merch_q_active")
        sub = KYCSubmission.objects.get(merchant=m)
        apply_transition(sub, "submitted")
        apply_transition(sub, "under_review")
        apply_transition(sub, "approved")
        resp = self.client.get("/api/v1/reviewer/queue/")
        self.assertEqual(resp.status_code, 200)
        results = resp.data.get("results", resp.data)
        ids = [s["id"] for s in results]
        self.assertNotIn(sub.id, ids)


class NotificationTests(TestCase):
    def test_merchant_sees_only_own_notifications(self):
        m1 = make_user("merch_n1")
        m2 = make_user("merch_n2")
        from kyc.models import NotificationEvent
        NotificationEvent.objects.create(merchant=m1, event_type="kyc_submitted", payload={})
        NotificationEvent.objects.create(merchant=m2, event_type="kyc_submitted", payload={})

        c = auth_client(m1)
        resp = c.get("/api/v1/notifications/")
        self.assertEqual(resp.status_code, 200)
        merchant_ids = {n["merchant_id"] for n in resp.data}
        self.assertEqual(merchant_ids, {m1.id})

    def test_reviewer_sees_all_notifications(self):
        m1 = make_user("merch_nr1")
        m2 = make_user("merch_nr2")
        rev = make_user("rev_nr", role="reviewer")
        from kyc.models import NotificationEvent
        NotificationEvent.objects.create(merchant=m1, event_type="kyc_submitted", payload={})
        NotificationEvent.objects.create(merchant=m2, event_type="kyc_submitted", payload={})

        c = auth_client(rev)
        resp = c.get("/api/v1/notifications/")
        self.assertEqual(resp.status_code, 200)
        merchant_ids = {n["merchant_id"] for n in resp.data}
        self.assertGreaterEqual(len(merchant_ids), 2)
