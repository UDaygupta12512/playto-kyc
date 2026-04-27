

from rest_framework.permissions import BasePermission


class IsMerchant(BasePermission):
    """Merchant role requirement."""

    message = "Only merchants can perform this action."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == "merchant"
        )


class IsReviewer(BasePermission):
    """Reviewer role requirement."""

    message = "Only reviewers can perform this action."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == "reviewer"
        )


class IsMerchantOrReviewer(BasePermission):
    """Authenticated merchants OR reviewers."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in ("merchant", "reviewer")
        )


class IsSubmissionOwner(BasePermission):
    """Check if user owns submission or is reviewer."""

    message = "You do not have permission to access this submission."

    def has_object_permission(self, request, view, obj):
        if request.user.role == "reviewer":
            return True
        # Merchant: must own the submission
        return obj.merchant_id == request.user.id
