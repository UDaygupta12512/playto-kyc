from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from kyc.models import User, KYCSubmission, Document, NotificationEvent


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ["username", "email", "role", "is_active"]
    list_filter = ["role"]
    fieldsets = UserAdmin.fieldsets + (("Role", {"fields": ("role",)}),)


@admin.register(KYCSubmission)
class KYCSubmissionAdmin(admin.ModelAdmin):
    list_display = ["id", "merchant", "state", "submitted_at", "is_at_risk"]
    list_filter = ["state"]
    search_fields = ["merchant__username", "business_name"]
    readonly_fields = ["created_at", "updated_at", "submitted_at"]


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ["id", "submission", "doc_type", "uploaded_at"]


@admin.register(NotificationEvent)
class NotificationEventAdmin(admin.ModelAdmin):
    list_display = ["id", "merchant", "event_type", "timestamp"]
    list_filter = ["event_type"]
