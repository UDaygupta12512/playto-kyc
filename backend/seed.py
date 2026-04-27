#!/usr/bin/env python
"""
Seed script: creates test data for the Playto KYC demo.

Run with: python seed.py
(from inside the backend directory with DJANGO_SETTINGS_MODULE set)

Creates:
- 1 reviewer:   username=reviewer1, password=reviewer123
- 2 merchants:
    merchant1 (draft state)       username=merchant1, password=merchant123
    merchant2 (under_review state) username=merchant2, password=merchant123
"""

import os
import sys
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "playto_kyc.settings")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from django.utils import timezone
from datetime import timedelta
from rest_framework.authtoken.models import Token

from kyc.models import User, KYCSubmission, NotificationEvent
from kyc.state_machine import apply_transition


def create_or_get(username, password, role):
    user, created = User.objects.get_or_create(
        username=username,
        defaults={"role": role, "email": f"{username}@playto.dev"},
    )
    if created:
        user.set_password(password)
        user.save()
        print(f"  Created {role}: {username}")
    else:
        print(f"  {role.title()} '{username}' already exists — skipping creation")
    token, _ = Token.objects.get_or_create(user=user)
    return user, token.key


def seed():
    print("\n=== Seeding Playto KYC Demo Data ===\n")


    reviewer, rev_token = create_or_get("reviewer1", "reviewer123", "reviewer")


    merch1, m1_token = create_or_get("merchant1", "merchant123", "merchant")
    sub1, _ = KYCSubmission.objects.get_or_create(merchant=merch1)
    if sub1.state == "draft" and not sub1.full_name:
        sub1.full_name = "Arjun Kapoor"
        sub1.phone = "9876543210"
        sub1.business_name = ""  # intentionally incomplete — still in draft
        sub1.state = "draft"
        sub1.save()
        print(f"  KYC for merchant1 is in DRAFT (incomplete)")


    merch2, m2_token = create_or_get("merchant2", "merchant123", "merchant")
    sub2, _ = KYCSubmission.objects.get_or_create(merchant=merch2)
    if sub2.state == "draft":
        sub2.full_name = "Priya Nair"
        sub2.phone = "9123456789"
        sub2.business_name = "Priya Designs Studio"
        sub2.business_type = "sole_proprietorship"
        sub2.monthly_volume_usd = 12000
        sub2.save()

        # Transition to submitted (backdated so SLA flag fires)
        apply_transition(sub2, "submitted")
        # Backdate submitted_at by 30 hours to trigger at_risk flag
        sub2.submitted_at = timezone.now() - timedelta(hours=30)
        sub2.save(update_fields=["submitted_at"])

        apply_transition(sub2, "under_review")
        sub2.assigned_reviewer = reviewer
        sub2.save(update_fields=["assigned_reviewer"])
        print(f"  KYC for merchant2 is UNDER_REVIEW (SLA at_risk = True)")

        NotificationEvent.objects.create(
            merchant=merch2,
            event_type="kyc_submitted",
            payload={"submission_id": sub2.id, "state": "submitted"},
        )
        NotificationEvent.objects.create(
            merchant=merch2,
            event_type="kyc_under_review",
            payload={"submission_id": sub2.id, "state": "under_review", "reviewer_id": reviewer.id},
        )


    merch3, m3_token = create_or_get("merchant3", "merchant123", "merchant")
    sub3, _ = KYCSubmission.objects.get_or_create(merchant=merch3)
    if sub3.state == "draft":
        sub3.full_name = "Rahul Mehta"
        sub3.phone = "9000011111"
        sub3.business_name = "Rahul SaaS Co"
        sub3.business_type = "pvt_ltd"
        sub3.monthly_volume_usd = 50000
        sub3.save()
        apply_transition(sub3, "submitted")
        apply_transition(sub3, "under_review")
        apply_transition(sub3, "approved", reviewer_note="All documents verified. Clean profile.")
        print(f"  KYC for merchant3 is APPROVED")

    print("\n=== Credentials ===")
    print(f"\n  Reviewer:")
    print(f"    username: reviewer1 | password: reviewer123 | token: {rev_token}")
    print(f"\n  Merchant (draft):")
    print(f"    username: merchant1 | password: merchant123 | token: {m1_token}")
    print(f"\n  Merchant (under_review, at_risk):")
    print(f"    username: merchant2 | password: merchant123 | token: {m2_token}")
    print(f"\n  Merchant (approved):")
    print(f"    username: merchant3 | password: merchant123 | token: {m3_token}")
    print("\n=== Done ===\n")


if __name__ == "__main__":
    seed()
