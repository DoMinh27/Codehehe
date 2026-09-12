import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import OperationalError
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from matches.rules import RulesetConfigurationError
from matches.services.room import RoomCodeGenerationError
from social.models import FriendRequest, UserBlock, UserPresence
from social.services.friends import (
    SocialConflict,
    act_on_friend_request,
    block_user,
    heartbeat_presence,
    project_friend_presence,
    remove_friend,
    send_friend_request,
    set_presence_privacy,
    unblock_user,
)
from social.services.notifications import get_notification_state
from social.services.match_invitations import (
    MatchInvitationError,
    MatchInvitationService,
    invitation_result,
    ready_user_ids,
    send_match_invitation,
)


@never_cache
@login_required
@require_GET
def notification_state(request):
    response = JsonResponse(get_notification_state(user=request.user))
    response["Cache-Control"] = "private, no-store"
    return response


def _safe_next(request, fallback="social:friends"):
    candidate = request.POST.get("next", "")
    if candidate and url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return reverse(fallback)


@login_required
@require_POST
def friend_request_send(request):
    try:
        send_friend_request(
            requester=request.user,
            username=request.POST.get("username", "").strip(),
        )
    except SocialConflict as error:
        messages.error(request, str(error))
    else:
        messages.success(request, "Đã gửi lời mời kết bạn")
    return redirect(_safe_next(request))


@never_cache
@login_required
@require_POST
def friend_request_action(request, request_id):
    action = request.POST.get("action", "").lower()
    if request.content_type == "application/json":
        try:
            payload = json.loads(request.body or b"{}")
            action = payload.get("action", "").lower() if isinstance(payload, dict) else ""
        except (json.JSONDecodeError, UnicodeDecodeError):
            response = JsonResponse(
                {"code": "INVALID_JSON", "message": "Dữ liệu không hợp lệ"},
                status=400,
            )
            response["Cache-Control"] = "private, no-store"
            return response
    if action not in {"accept", "decline", "cancel"}:
        response = JsonResponse(
            {"code": "INVALID_ACTION", "message": "Hành động không hợp lệ"},
            status=400,
        )
        response["Cache-Control"] = "private, no-store"
        return response
    try:
        act_on_friend_request(actor=request.user, request_id=request_id, action=action)
    except SocialConflict as error:
        if request.content_type == "application/json":
            response = JsonResponse(
                {"code": error.code, "message": str(error)},
                status=409,
            )
            response["Cache-Control"] = "private, no-store"
            return response
        messages.error(request, str(error))
    else:
        if request.content_type == "application/json":
            response = JsonResponse({"ok": True})
            response["Cache-Control"] = "private, no-store"
            return response
        messages.success(request, "Đã cập nhật lời mời kết bạn")
    return redirect(_safe_next(request))


def _json_payload(request):
    try:
        payload = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


@never_cache
@login_required
@require_POST
def match_invitation_send(request):
    is_json = request.content_type == "application/json"
    payload = _json_payload(request) if is_json else request.POST
    if payload is None:
        response = JsonResponse(
            {"code": "INVALID_JSON", "message": "Dữ liệu không hợp lệ"},
            status=400,
        )
        response["Cache-Control"] = "private, no-store"
        return response
    try:
        invitee_id = int(payload.get("recipient_id"))
    except (TypeError, ValueError):
        error = MatchInvitationError(
            "INVALID_RECIPIENT",
            "Người nhận không hợp lệ",
            400,
        )
    else:
        try:
            invitation = send_match_invitation(
                inviter=request.user,
                invitee_id=invitee_id,
            )
        except MatchInvitationError as caught:
            error = caught
        else:
            if is_json:
                response = JsonResponse(invitation_result(invitation))
                response["Cache-Control"] = "private, no-store"
                return response
            messages.success(request, "Đã gửi lời mời đấu")
            return redirect(_safe_next(request))
    if is_json:
        response = JsonResponse(
            {"code": error.code, "message": error.message},
            status=error.status,
        )
        response["Cache-Control"] = "private, no-store"
        return response
    messages.error(request, error.message)
    return redirect(_safe_next(request))


@never_cache
@login_required
@require_POST
def match_invitation_action(request, invitation_id):
    is_json = request.content_type == "application/json"
    payload = _json_payload(request) if is_json else request.POST
    if payload is None:
        response = JsonResponse(
            {"code": "INVALID_JSON", "message": "Dữ liệu không hợp lệ"},
            status=400,
        )
        response["Cache-Control"] = "private, no-store"
        return response
    action = payload.get("action", "")
    if isinstance(action, str):
        action = action.lower()
    try:
        invitation = MatchInvitationService().act(
            actor=request.user,
            invitation_id=invitation_id,
            action=action,
        )
    except MatchInvitationError as error:
        if is_json:
            response = JsonResponse(
                {"code": error.code, "message": error.message},
                status=error.status,
            )
            response["Cache-Control"] = "private, no-store"
            return response
        messages.error(request, error.message)
    except (RoomCodeGenerationError, RulesetConfigurationError):
        message = "Chưa thể tạo phòng đấu, hãy thử lại"
        if is_json:
            response = JsonResponse(
                {"code": "MATCH_INVITATION_UNAVAILABLE", "message": message},
                status=503,
            )
            response["Cache-Control"] = "private, no-store"
            return response
        messages.error(request, message)
    except OperationalError as error:
        if "locked" not in str(error).lower() and "busy" not in str(error).lower():
            raise
        message = "Máy chủ đang bận, hãy thử lại"
        if is_json:
            response = JsonResponse(
                {"code": "MATCH_INVITATION_BUSY", "message": message},
                status=503,
            )
            response["Cache-Control"] = "private, no-store"
            return response
        messages.error(request, message)
    else:
        result = invitation_result(invitation)
        if is_json:
            response = JsonResponse(result)
            response["Cache-Control"] = "private, no-store"
            return response
        if action == "accept" and result["room_url"]:
            return redirect(result["room_url"])
        messages.success(request, "Đã cập nhật lời mời đấu")
    return redirect(_safe_next(request))


@login_required
@require_POST
def friendship_remove(request, user_id):
    try:
        remove_friend(actor=request.user, other_user_id=user_id)
    except SocialConflict as error:
        messages.error(request, str(error))
    else:
        messages.success(request, "Đã hủy kết bạn")
    return redirect("social:friends")


@login_required
@require_POST
def user_block(request, user_id):
    try:
        block_user(actor=request.user, other_user_id=user_id)
    except SocialConflict as error:
        messages.error(request, str(error))
    else:
        messages.success(request, "Đã chặn tài khoản")
    return redirect("social:friends")


@login_required
@require_POST
def user_unblock(request, user_id):
    unblock_user(actor=request.user, other_user_id=user_id)
    messages.success(request, "Đã bỏ chặn tài khoản")
    return redirect(f"{reverse('social:friends')}?tab=blocked")


@never_cache
@login_required
@require_POST
def presence_heartbeat(request):
    heartbeat_presence(user=request.user)
    response = JsonResponse({"ok": True})
    response["Cache-Control"] = "private, no-store"
    return response


@login_required
@require_POST
def presence_privacy(request):
    set_presence_privacy(
        user=request.user,
        visible=request.POST.get("show_presence") == "on",
    )
    messages.success(request, "Đã cập nhật trạng thái hoạt động")
    return redirect("social:friends")


@never_cache
@login_required
@require_GET
def friends_state(request):
    now = timezone.now()
    rows = project_friend_presence(user=request.user, now=now)
    viewer_ready = request.user.pk in ready_user_ids([request.user.pk], now=now)
    response = JsonResponse(
        {
            "server_time": now.isoformat(),
            "match_invitation_url": reverse("social:match-invitation-send"),
            "friends": [
                {
                    "id": row.user.pk,
                    "username": row.user.username,
                    "initial": (row.user.username[:1] or "?").upper(),
                    "status": row.status,
                    "status_label": row.status_label,
                    "can_invite": (
                        viewer_ready
                        and row.status == "READY"
                        and row.match_invitation is None
                    ),
                    "match_invitation": (
                        {
                            "id": str(row.match_invitation.pk),
                            "direction": (
                                "OUTGOING"
                                if row.match_invitation.inviter_id == request.user.pk
                                else "INCOMING"
                            ),
                            "action_url": reverse(
                                "social:match-invitation-action",
                                kwargs={"invitation_id": row.match_invitation.pk},
                            ),
                            "expires_at": row.match_invitation.expires_at.isoformat(),
                        }
                        if row.match_invitation
                        else None
                    ),
                }
                for row in rows
            ],
        }
    )
    response["Cache-Control"] = "private, no-store"
    return response


@never_cache
@login_required
@require_GET
def friends(request):
    now = timezone.now()
    tab = request.GET.get("tab", "friends")
    if tab not in {"friends", "requests", "blocked"}:
        tab = "friends"

    rows = project_friend_presence(user=request.user, now=now)
    incoming = (
        FriendRequest.objects.filter(status=FriendRequest.Status.PENDING, expires_at__gt=now)
        .filter(Q(user_low=request.user) | Q(user_high=request.user))
        .exclude(requester=request.user)
        .select_related("requester")
        .order_by("expires_at", "created_at")
    )
    outgoing = (
        FriendRequest.objects.filter(
            requester=request.user,
            status=FriendRequest.Status.PENDING,
            expires_at__gt=now,
        )
        .select_related("user_low", "user_high")
        .order_by("expires_at", "created_at")
    )
    blocked = UserBlock.objects.filter(blocker=request.user).select_related("blocked")
    if tab == "requests":
        incoming_page = Paginator(incoming, 20).get_page(request.GET.get("incoming_page"))
        outgoing_page = Paginator(outgoing, 20).get_page(request.GET.get("outgoing_page"))
        page_obj = None
    elif tab == "blocked":
        page_obj = Paginator(blocked, 20).get_page(request.GET.get("page"))
        incoming_page = outgoing_page = None
    else:
        page_obj = Paginator(rows, 20).get_page(request.GET.get("page"))
        incoming_page = outgoing_page = None
    presence = UserPresence.objects.filter(user=request.user).first()
    viewer_ready = request.user.pk in ready_user_ids([request.user.pk], now=now)
    return render(
        request,
        "social/friends.html",
        {
            "tab": tab,
            "page_obj": page_obj,
            "incoming_requests": incoming_page,
            "outgoing_requests": outgoing_page,
            "show_presence": presence.show_presence_to_friends if presence else True,
            "viewer_ready": viewer_ready,
        },
    )
