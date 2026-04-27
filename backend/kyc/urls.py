from django.urls import path
from kyc import views

urlpatterns = [
    path("auth/register/", views.register, name="register"),
    path("auth/login/", views.login, name="login"),
    path("auth/me/", views.me, name="me"),
    path("kyc/submission/", views.MySubmissionView.as_view(), name="my-submission"),
    path("kyc/submit/", views.merchant_submit, name="merchant-submit"),
    path("kyc/documents/<str:doc_type>/", views.upload_document, name="upload-document"),
    path("reviewer/queue/", views.ReviewerQueueView.as_view(), name="reviewer-queue"),
    path("reviewer/submissions/", views.ReviewerAllSubmissionsView.as_view(), name="reviewer-submissions"),
    path("reviewer/submissions/<int:pk>/", views.ReviewerSubmissionDetailView.as_view(), name="reviewer-submission-detail"),
    path("reviewer/submissions/<int:pk>/transition/", views.reviewer_transition, name="reviewer-transition"),
    path("reviewer/metrics/", views.dashboard_metrics, name="dashboard-metrics"),
    path("notifications/", views.notification_events, name="notification-events"),
    path("health/", views.health, name="health"),
]
