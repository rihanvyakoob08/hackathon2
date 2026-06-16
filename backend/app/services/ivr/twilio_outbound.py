import re
from typing import Any

import httpx

from app.config import settings


E164_PHONE_RE = re.compile(r"^\+[1-9]\d{7,14}$")
SUPPORTED_OUTBOUND_PURPOSES = {"general", "weather", "crop", "scheme", "grievance"}


def normalize_phone_number(number: str, field_name: str = "Phone number") -> str:
    value = "".join((number or "").strip().split())
    if not E164_PHONE_RE.fullmatch(value):
        raise ValueError(f"{field_name} must be in E.164 format, like +919876543210.")
    return value


def normalize_outbound_language(language: str | None) -> str:
    value = (language or settings.IVR_DEFAULT_LANGUAGE or "en").strip().lower()
    return value if value in {"en", "ta", "kn"} else "en"


def normalize_outbound_purpose(purpose: str | None) -> str:
    value = (purpose or "general").strip().lower()
    return value if value in SUPPORTED_OUTBOUND_PURPOSES else "general"


def validate_public_base_url() -> str:
    base_url = settings.PUBLIC_BASE_URL.rstrip("/")
    if not base_url:
        raise ValueError("Set PUBLIC_BASE_URL to your public backend URL before placing IVR calls.")
    if "127.0.0.1" in base_url or "localhost" in base_url:
        raise ValueError("Set PUBLIC_BASE_URL to your public ngrok URL before placing IVR calls.")
    return base_url


def twilio_error_message(response: httpx.Response, from_number: str | None = None) -> str:
    payload: dict[str, Any] = {}
    try:
        payload = response.json()
    except ValueError:
        payload = {}

    error_code = payload.get("code")
    error_text = payload.get("message") or response.text or "Twilio request failed."
    caller_id = from_number or settings.TWILIO_FROM_NUMBER

    if response.status_code in {401, 403}:
        return "Twilio credentials were rejected. Check TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN in backend/app/.env."

    if error_code == 21210:
        return (
            f"Twilio rejected the caller ID {caller_id}. "
            "This number is not verified or purchased on your Twilio account. "
            "Buy a Twilio voice number or verify this caller ID, then update TWILIO_FROM_NUMBER in backend/app/.env."
        )

    return f"Twilio request failed ({response.status_code}): {error_text}"


async def get_outbound_call_status() -> dict[str, Any]:
    from_number = (settings.TWILIO_FROM_NUMBER or "").strip()
    status: dict[str, Any] = {
        "ready": False,
        "from_number": from_number,
        "validated_source": None,
        "public_base_url": settings.PUBLIC_BASE_URL.rstrip("/"),
        "message": "",
    }

    if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
        status["message"] = "Twilio credentials are missing. Set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN in backend/app/.env."
        return status

    if not from_number:
        status["message"] = "TWILIO_FROM_NUMBER is missing in backend/app/.env."
        return status

    try:
        normalized_from = normalize_phone_number(from_number, "TWILIO_FROM_NUMBER")
        status["from_number"] = normalized_from
        validate_public_base_url()
    except ValueError as error:
        status["message"] = str(error)
        return status

    base_url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}"

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            incoming_response = await client.get(
                f"{base_url}/IncomingPhoneNumbers.json",
                params={"PhoneNumber": normalized_from, "PageSize": 1},
                auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
            )
            incoming_response.raise_for_status()
            incoming_numbers = incoming_response.json().get("incoming_phone_numbers", [])
            if incoming_numbers:
                capabilities = incoming_numbers[0].get("capabilities") or {}
                if capabilities.get("voice") is False:
                    status["message"] = (
                        f"Twilio number {normalized_from} is on the account, but voice calling is not enabled for it."
                    )
                    return status

                status["ready"] = True
                status["validated_source"] = "twilio-number"
                status["message"] = f"Outbound caller ID {normalized_from} is configured on this Twilio account."
                return status

            caller_id_response = await client.get(
                f"{base_url}/OutgoingCallerIds.json",
                params={"PhoneNumber": normalized_from, "PageSize": 1},
                auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
            )
            caller_id_response.raise_for_status()
            caller_ids = caller_id_response.json().get("outgoing_caller_ids", [])
            if caller_ids:
                status["ready"] = True
                status["validated_source"] = "verified-caller-id"
                status["message"] = f"Outbound caller ID {normalized_from} is verified on this Twilio account."
                return status
    except httpx.HTTPStatusError as error:
        status["message"] = twilio_error_message(error.response, normalized_from)
        return status
    except httpx.HTTPError as error:
        status["message"] = f"Could not reach Twilio to validate the outbound caller ID: {error}."
        return status

    status["message"] = (
        f"TWILIO_FROM_NUMBER {normalized_from} is not present on this Twilio account. "
        "Buy a voice-capable Twilio number or verify this caller ID, then update backend/app/.env."
    )
    return status
