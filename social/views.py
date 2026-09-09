from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from social.services.notifications import get_notification_state


@never_cache
@login_required
@require_GET
def notification_state(request):
    response = JsonResponse(get_notification_state(user=request.user))
    response["Cache-Control"] = "private, no-store"
    return response
