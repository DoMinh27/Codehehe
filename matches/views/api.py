"""Shared JSON request parsing and API error responses."""

import json
from dataclasses import dataclass

from django.http import JsonResponse


@dataclass(frozen=True)
class ApiPayloadError(Exception):
    code: str
    message: str
    status: int = 400


def parse_json_object(request) -> dict:
    try:
        payload = json.loads(request.body)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ApiPayloadError(
            code="INVALID_JSON",
            message="Request body must be valid JSON.",
        ) from error
    if not isinstance(payload, dict):
        raise ApiPayloadError(
            code="INVALID_BODY",
            message="Request body must be a JSON object.",
        )
    return payload


def api_error(*, code: str, message: str, status: int) -> JsonResponse:
    return JsonResponse(
        {
            "code": code,
            "message": message,
        },
        status=status,
    )
