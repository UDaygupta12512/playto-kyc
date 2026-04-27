from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status


def custom_exception_handler(exc, context):
    """Global error handler for consistent API responses."""
    response = exception_handler(exc, context)

    if response is not None:
        original_data = response.data

        # DRF non_field_errors or plain strings
        if isinstance(original_data, list):
            message = "; ".join(str(e) for e in original_data)
        elif isinstance(original_data, dict):
            # Pick the first meaningful key
            first_key = next(iter(original_data), "detail")
            val = original_data[first_key]
            if isinstance(val, list):
                message = str(val[0])
            else:
                message = str(val)
        else:
            message = str(original_data)

        response.data = {
            "error": True,
            "message": message,
            "detail": original_data,
        }

    return response


def log_notification(merchant, event_type: str, payload: dict) -> None:
    """Log notification event for async processing."""
    from kyc.models import NotificationEvent

    NotificationEvent.objects.create(
        merchant=merchant,
        event_type=event_type,
        payload=payload,
    )
