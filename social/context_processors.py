from django.conf import settings


def notification_settings(request):
    del request
    return {
        "social_notification_visible_poll_seconds": (
            settings.SOCIAL_NOTIFICATION_VISIBLE_POLL_SECONDS
        ),
        "social_notification_hidden_poll_seconds": (
            settings.SOCIAL_NOTIFICATION_HIDDEN_POLL_SECONDS
        ),
        "social_presence_heartbeat_seconds": settings.SOCIAL_PRESENCE_HEARTBEAT_SECONDS,
    }
