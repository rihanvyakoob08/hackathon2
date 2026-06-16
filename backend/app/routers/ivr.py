"""
IVR router for KrishiMitra — Twilio voice with live AI responses.

Flow per call:
  1. Twilio hits /ivr/twilio/welcome  → welcome + main menu (DTMF)
  2. Farmer presses 1-5              → /ivr/twilio/menu
  3. Twilio records the farmer       → /ivr/twilio/{intent}/respond
  4. We transcribe via Sarvam STT   → run AI / weather / grievance
  5. Sarvam TTS converts reply       → Twilio <Play>s the audio file
  6. Farmer presses 9 to repeat or hangs up

Key fixes vs the original:
  - Twilio ALWAYS uses Sarvam TTS; no conditional skip.
  - Weather uses fetch_weather() directly, not get_weather_advisory() with "your district".
  - Spray / irrigation intent is detected from the transcript before routing.
  - Every <Record> sends to a dedicated /respond endpoint that transcribes + replies.
  - Session language is set at welcome and persisted; all prompts are localised.
  - All DB commits are wrapped in rollback-safe try/except.
"""

import logging
import os
import re
import uuid
from datetime import datetime
from html import escape
from typing import Any, Optional
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.auth import get_officer
from app.config import settings
from app.database import get_db
from app.models import AnalyticsEvent, Grievance, IvrSession, User
from app.services.ai.sarvam_ai_service import (
    chat_with_ai,
    classify_grievance,
    classify_intent,
)
from app.services.ai.sarvam_service import text_to_speech, transcribe_audio
from app.services.ivr.twilio_outbound import (
    get_outbound_call_status,
    normalize_outbound_language,
    normalize_outbound_purpose,
    normalize_phone_number,
    twilio_error_message,
)
from app.services.location_extractor import extract_location
from app.services.weather_service import WeatherLookupError, fetch_weather
from pydantic import BaseModel
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ivr", tags=["IVR"])
class OutboundCallRequest(BaseModel):
    to_number: str
    language: str = "en"
    purpose: str = "general"
# ---------------------------------------------------------------------------
# Language config
# ---------------------------------------------------------------------------

SUPPORTED_LANGUAGES = {"en", "ta", "kn"}
LANGUAGE_AUDIO_CODES = {"en": "en-IN", "ta": "ta-IN", "kn": "kn-IN"}

WELCOME_PROMPTS = {
    "en": "Welcome to KrishiMitra farmer helpline.",
    "ta": "KrishiMitra விவசாயி உதவி மையத்திற்கு வரவேற்கிறோம்.",
    "kn": "KrishiMitra ರೈತ ಸಹಾಯವಾಣಿಗೆ ಸುಸ್ವಾಗತ.",
}

MENU_PROMPTS = {
    "en": (
        "Press 1 for crop disease and pest help. "
        "Press 2 for weather and spray advice. "
        "Press 3 for government scheme guidance. "
        "Press 4 to register a grievance. "
        "Press 5 to track a grievance. "
        "Press 9 to repeat this menu."
    ),
    "ta": (
        "பயிர் நோய் மற்றும் பூச்சி உதவிக்கு 1 அழுத்தவும். "
        "வானிலை மற்றும் தெளிப்பு ஆலோசனைக்கு 2 அழுத்தவும். "
        "அரசு திட்ட வழிகாட்டுதலுக்கு 3 அழுத்தவும். "
        "புகார் பதிவு செய்ய 4 அழுத்தவும். "
        "புகார் நிலை அறிய 5 அழுத்தவும். "
        "மீண்டும் கேட்க 9 அழுத்தவும்."
    ),
    "kn": (
        "ಬೆಳೆ ರೋಗ ಮತ್ತು ಕೀಟ ಸಹಾಯಕ್ಕೆ 1 ಒತ್ತಿ. "
        "ಹವಾಮಾನ ಮತ್ತು ಸಿಂಪಡಿಸುವ ಸಲಹೆಗೆ 2 ಒತ್ತಿ. "
        "ಸರ್ಕಾರಿ ಯೋಜನೆ ಮಾರ್ಗದರ್ಶನಕ್ಕೆ 3 ಒತ್ತಿ. "
        "ದೂರು ದಾಖಲಿಸಲು 4 ಒತ್ತಿ. "
        "ದೂರು ಸ್ಥಿತಿ ತಿಳಿಯಲು 5 ಒತ್ತಿ. "
        "ಮತ್ತೆ ಕೇಳಲು 9 ಒತ್ತಿ."
    ),
}

RECORD_PROMPTS = {
    "crop": {
        "en": "After the beep, say your crop name and symptoms. For example: paddy leaves are turning yellow with brown spots.",
        "ta": "பீப் ஒலிக்குப் பிறகு, உங்கள் பயிர் பெயரையும் அறிகுறிகளையும் சொல்லுங்கள்.",
        "kn": "ಬೀಪ್ ನಂತರ, ನಿಮ್ಮ ಬೆಳೆ ಹೆಸರು ಮತ್ತು ರೋಗಲಕ್ಷಣಗಳನ್ನು ಹೇಳಿ.",
    },
    "weather": {
        "en": "After the beep, say your district or city and what you want to do. For example: can I spray today in Coimbatore?",
        "ta": "பீப் ஒலிக்குப் பிறகு, உங்கள் மாவட்டம் அல்லது நகரத்தையும் நீங்கள் என்ன செய்ய விரும்புகிறீர்கள் என்பதையும் சொல்லுங்கள்.",
        "kn": "ಬೀಪ್ ನಂತರ, ನಿಮ್ಮ ಜಿಲ್ಲೆ ಅಥವಾ ನಗರ ಮತ್ತು ನೀವು ಏನು ಮಾಡಲು ಬಯಸುತ್ತೀರಿ ಎಂದು ಹೇಳಿ.",
    },
    "scheme": {
        "en": "After the beep, say the scheme name or describe what support you need. For example: PM Kisan eligibility.",
        "ta": "பீப் ஒலிக்குப் பிறகு, திட்டத்தின் பெயரையோ அல்லது உங்களுக்கு என்ன ஆதரவு தேவை என்பதையோ சொல்லுங்கள்.",
        "kn": "ಬೀಪ್ ನಂತರ, ಯೋಜನೆಯ ಹೆಸರು ಅಥವಾ ನಿಮಗೆ ಯಾವ ಸಹಾಯ ಬೇಕು ಎಂದು ಹೇಳಿ.",
    },
    "grievance": {
        "en": "After the beep, describe your grievance clearly. Mention the application number, district, and date if you know them.",
        "ta": "பீப் ஒலிக்குப் பிறகு, உங்கள் புகாரை தெளிவாக விவரிக்கவும். விண்ணப்ப எண், மாவட்டம் மற்றும் தேதி தெரிந்தால் சொல்லுங்கள்.",
        "kn": "ಬೀಪ್ ನಂತರ, ನಿಮ್ಮ ದೂರನ್ನು ಸ್ಪಷ್ಟವಾಗಿ ವಿವರಿಸಿ.",
    },
    "track": {
        "en": "After the beep, say or enter the last five digits of your grievance tracking number.",
        "ta": "பீப் ஒலிக்குப் பிறகு, உங்கள் புகார் கண்காணிப்பு எண்ணின் கடைசி ஐந்து இலக்கங்களை சொல்லுங்கள் அல்லது உள்ளிடவும்.",
        "kn": "ಬೀಪ್ ನಂತರ, ನಿಮ್ಮ ದೂರು ಟ್ರ್ಯಾಕಿಂಗ್ ಸಂಖ್ಯೆಯ ಕೊನೆಯ ಐದು ಅಂಕಿಗಳನ್ನು ಹೇಳಿ ಅಥವಾ ನಮೂದಿಸಿ.",
    },
}

FALLBACK_RESPONSES = {
    "crop": {
        "en": "I could not hear your crop symptoms clearly. Please call again and describe the crop name and visible symptoms after the beep.",
        "ta": "உங்கள் பயிர் அறிகுறிகளை தெளிவாக கேட்க முடியவில்லை. மீண்டும் அழைக்கவும்.",
        "kn": "ನಿಮ್ಮ ಬೆಳೆ ರೋಗಲಕ್ಷಣಗಳನ್ನು ಸ್ಪಷ್ಟವಾಗಿ ಕೇಳಲಾಗಲಿಲ್ಲ. ದಯವಿಟ್ಟು ಮತ್ತೆ ಕರೆ ಮಾಡಿ.",
    },
    "weather": {
        "en": "I need your district name for weather advice. Please call again and say your district after the beep.",
        "ta": "வானிலை ஆலோசனைக்கு உங்கள் மாவட்டப் பெயர் தேவை. மீண்டும் அழைக்கவும்.",
        "kn": "ಹವಾಮಾನ ಸಲಹೆಗೆ ನಿಮ್ಮ ಜಿಲ್ಲೆಯ ಹೆಸರು ಬೇಕು. ದಯವಿಟ್ಟು ಮತ್ತೆ ಕರೆ ಮಾಡಿ.",
    },
    "grievance": {
        "en": "I could not register your grievance clearly. Please call again and describe the issue after the beep.",
        "ta": "உங்கள் புகாரை பதிவு செய்ய முடியவில்லை. மீண்டும் அழைக்கவும்.",
        "kn": "ನಿಮ್ಮ ದೂರನ್ನು ದಾಖಲಿಸಲಾಗಲಿಲ್ಲ. ದಯವಿಟ್ಟು ಮತ್ತೆ ಕರೆ ಮಾಡಿ.",
    },
}

MENU_DIGIT_TO_INTENT = {
    "1": "crop",
    "2": "weather",
    "3": "scheme",
    "4": "grievance",
    "5": "track",
}

REPEAT_MENU_PROMPT = {
    "en": "Press 9 to return to the main menu, or hang up to end the call.",
    "ta": "முதன்மை மெனுவிற்குத் திரும்ப 9 அழுத்தவும், அல்லது அழைப்பை முடிக்க தொலைபேசியை வைக்கவும்.",
    "kn": "ಮುಖ್ಯ ಮೆನುಗೆ ಹಿಂತಿರುಗಲು 9 ಒತ್ತಿ, ಅಥವಾ ಕರೆ ಮುಗಿಸಲು ಫೋನ್ ಇಡಿ.",
}

# ---------------------------------------------------------------------------
# TwiML builder
# ---------------------------------------------------------------------------


def _xml(*parts: str) -> Response:
    body = '<?xml version="1.0" encoding="UTF-8"?><Response>' + "".join(parts) + "</Response>"
    return Response(content=body, media_type="application/xml")


def _say(text: str, language: str = "en") -> str:
    """Twilio <Say> with correct language code."""
    lang_map = {"en": "en-IN", "ta": "ta-IN", "kn": "kn-IN"}
    lang_attr = lang_map.get(language, "en-IN")
    return f'<Say language="{lang_attr}">{escape(text)}</Say>'


def _play(url: str) -> str:
    return f"<Play>{escape(url)}</Play>"


def _gather_dtmf(action_url: str, prompt_twiml: str, num_digits: int = 1, timeout: int = 8) -> str:
    return (
        f'<Gather numDigits="{num_digits}" timeout="{timeout}" action="{escape(action_url)}" method="POST">'
        f"{prompt_twiml}"
        f"</Gather>"
    )


def _record(action_url: str, prompt_twiml: str, max_length: int = 30, timeout: int = 5) -> str:
    """Prompt then record. Twilio sends the recording URL to action_url."""
    return (
        f"{prompt_twiml}"
        f'<Record action="{escape(action_url)}" method="POST" '
        f'maxLength="{max_length}" timeout="{timeout}" '
        f'playBeep="true" transcribe="false"/>'
    )


def _public_url(path: str) -> str:
    base = settings.PUBLIC_BASE_URL.rstrip("/")
    prefix = getattr(settings, "PUBLIC_WEBHOOK_PREFIX", "").strip("/")
    full_path = f"/{prefix}{path}" if prefix else path
    return f"{base}{full_path}"


def _build_outbound_welcome_url(language: str, purpose: str) -> str:
    query = urlencode(
        {
            "language": normalize_outbound_language(language),
            "purpose": normalize_outbound_purpose(purpose),
        }
    )
    return f"{_public_url('/ivr/twilio/welcome')}?{query}"


# ---------------------------------------------------------------------------
# TTS helper — always runs for Twilio
# ---------------------------------------------------------------------------


async def _tts_play(text: str, language: str, session_id: str) -> str:
    """
    Convert text to speech via Sarvam and save to disk.
    Returns a <Play> tag with the public URL, or a <Say> tag as fallback.
    """
    lang_code = LANGUAGE_AUDIO_CODES.get(language, "en-IN")
    try:
        audio_bytes = await text_to_speech(text, lang_code)
        if audio_bytes:
            directory = os.path.join(settings.UPLOAD_DIR, "ivr")
            os.makedirs(directory, exist_ok=True)
            filename = f"{session_id}-{uuid.uuid4().hex[:8]}.wav"
            filepath = os.path.join(directory, filename)
            with open(filepath, "wb") as f:
                f.write(audio_bytes)
            public_path = _public_url(f"/uploads/ivr/{filename}")
            return _play(public_path)
    except Exception as exc:
        logger.warning("TTS failed for session %s: %s — using <Say> fallback", session_id, exc)
    return _say(text, language)


# ---------------------------------------------------------------------------
# Transcription helper
# ---------------------------------------------------------------------------


async def _transcribe_recording(recording_url: str, language: str) -> str:
    """
    Download Twilio recording and transcribe via Sarvam STT.
    Returns empty string on any failure.
    """
    if not recording_url:
        return ""
    lang_code = LANGUAGE_AUDIO_CODES.get(language, "en-IN")
    try:
        async with httpx.AsyncClient(
            timeout=30,
            auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
            follow_redirects=True,
        ) as client:
            resp = await client.get(recording_url + ".wav")
            resp.raise_for_status()
            audio_bytes = resp.content
        result = await transcribe_audio(audio_bytes, lang_code, "recording.wav")
        transcript = (result or {}).get("transcript", "").strip()
        logger.info("STT transcript [%s]: %s", language, transcript[:120])
        return transcript
    except Exception as exc:
        logger.warning("Transcription failed: %s", exc)
        return ""


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def _safe_commit(db: Session) -> None:
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise


def _get_or_create_session(db: Session, phone: str) -> IvrSession:
    phone = (phone or "unknown-caller").replace("whatsapp:", "").strip()
    session = (
        db.query(IvrSession)
        .filter(IvrSession.phone_number == phone, IvrSession.status == "active")
        .order_by(IvrSession.updated_at.desc())
        .first()
    )
    if session:
        return session
    session = IvrSession(
        session_id=str(uuid.uuid4()),
        phone_number=phone,
        provider="twilio",
        language="en",
        current_state="MAIN_MENU",
        context={},
        status="active",
    )
    db.add(session)
    _safe_commit(db)
    db.refresh(session)
    _log_event(db, "ivr_call_started", session, {})
    return session


def _get_session(db: Session, session_id: Optional[str], phone: Optional[str] = None) -> IvrSession:
    if session_id:
        s = db.query(IvrSession).filter(IvrSession.session_id == session_id).first()
        if s:
            return s
    return _get_or_create_session(db, phone or "unknown-caller")


def _update_session(db: Session, session: IvrSession, **kwargs: Any) -> None:
    for key, value in kwargs.items():
        if value is not None:
            setattr(session, key, value)
    session.updated_at = datetime.utcnow()
    _safe_commit(db)


def _log_event(db: Session, event_type: str, session: IvrSession, payload: dict) -> None:
    try:
        db.add(AnalyticsEvent(
            event_type=event_type,
            data={"session_id": session.session_id, "phone_number": session.phone_number, **payload},
        ))
        _safe_commit(db)
    except Exception as exc:
        logger.warning("Analytics log failed: %s", exc)


def _get_or_create_farmer(db: Session, phone: str) -> User:
    farmer = db.query(User).filter(User.phone == phone).first()
    if farmer:
        return farmer
    safe = re.sub(r"\W+", "", phone) or uuid.uuid4().hex[:10]
    farmer = User(
        email=f"ivr-{safe}@krishimitra.local",
        phone=phone,
        full_name=f"IVR Farmer {phone}",
        hashed_password="ivr-user",
        role="farmer",
        preferred_language="en",
        is_active=True,
    )
    db.add(farmer)
    _safe_commit(db)
    db.refresh(farmer)
    return farmer


# ---------------------------------------------------------------------------
# AI response builders
# ---------------------------------------------------------------------------


def _voice_safe(text: str, limit: int = 600) -> str:
    """Strip markdown and truncate for voice delivery."""
    import re as _re
    text = _re.sub(r"\*\*(.*?)\*\*", r"\1", text or "")
    text = _re.sub(r"(?m)^\s*#{1,6}\s*", "", text)
    text = _re.sub(r"(?m)^\s*[-*]\s+", "", text)
    text = _re.sub(r"\n{2,}", ". ", text)
    text = _re.sub(r"\s+", " ", text).strip()
    return text[:limit]


async def _ai_crop_response(transcript: str, language: str, phone: str) -> str:
    if not transcript:
        return FALLBACK_RESPONSES["crop"].get(language, FALLBACK_RESPONSES["crop"]["en"])
    try:
        answer = await chat_with_ai(
            message=transcript,
            history=[],
            language=language,
            context={"channel": "ivr", "phone_number": phone},
            channel="ivr",
        )
        return _voice_safe(answer)
    except Exception as exc:
        logger.exception("IVR crop AI failed: %s", exc)
        return FALLBACK_RESPONSES["crop"].get(language, FALLBACK_RESPONSES["crop"]["en"])


async def _ai_weather_response(transcript: str, language: str, session: IvrSession) -> str:
    if not transcript:
        return FALLBACK_RESPONSES["weather"].get(language, FALLBACK_RESPONSES["weather"]["en"])

    # Try to get location from transcript first, then from session context
    location = extract_location(transcript)
    if not location:
        context = session.context or {}
        location = context.get("district") or context.get("location")

    if not location:
        return FALLBACK_RESPONSES["weather"].get(language, FALLBACK_RESPONSES["weather"]["en"])

    try:
        weather = await fetch_weather(location)
    except WeatherLookupError:
        no_loc = {
            "en": f"Could not find weather for {location}. Please check the district name.",
            "ta": f"{location} க்கான வானிலை கிடைக்கவில்லை. மாவட்டப் பெயரை சரிபார்க்கவும்.",
            "kn": f"{location} ಗಾಗಿ ಹವಾಮಾನ ಸಿಗಲಿಲ್ಲ. ಜಿಲ್ಲೆಯ ಹೆಸರು ಪರಿಶೀಲಿಸಿ.",
        }
        return no_loc.get(language, no_loc["en"])
    except Exception as exc:
        logger.warning("IVR fetch_weather failed: %s", exc)
        unavailable = {
            "en": "Weather service is temporarily unavailable. If rain is likely or wind is high, delay pesticide spraying.",
            "ta": "வானிலை சேவை தற்காலிகமாக கிடைக்கவில்லை. மழை வாய்ப்பு அல்லது காற்று அதிகமாக இருந்தால் பூச்சிக்கொல்லி தெளிப்பை தாமதப்படுத்துங்கள்.",
            "kn": "ಹವಾಮಾನ ಸೇವೆ ತಾತ್ಕಾಲಿಕವಾಗಿ ಲಭ್ಯವಿಲ್ಲ. ಮಳೆ ಅಥವಾ ಗಾಳಿ ಹೆಚ್ಚಿದ್ದರೆ ಕೀಟನಾಶಕ ಸಿಂಪಡಣೆ ಮುಂದೂಡಿ.",
        }
        return unavailable.get(language, unavailable["en"])

    # Detect what the farmer actually wants from the transcript
    t_lower = transcript.lower()
    is_spray = any(w in t_lower for w in ["spray", "pesticide", "fungicide", "herbicide", "தெளிக்க", "ಸಿಂಪಡಿಸ"])
    is_irrigate = any(w in t_lower for w in ["irrigat", "water", "drip", "flood", "நீர்", "ನೀರು"])

    spray = weather["spray_window"]
    irrigation = weather["irrigation"]
    forecast = weather["forecast_3days"]
    resolved = weather["resolved_location"]
    current = weather["current"]

    if is_spray:
        decision = spray["decision"].replace("_", " ")
        reply = (
            f"Spray advice for {resolved}. {decision}. {spray['reason']} "
            f"Wind is {spray['wind_speed_kmh']} kilometres per hour. "
            f"Rain chance today is {spray['rain_probability_percent']} percent. "
            f"Three day forecast: {forecast}."
        )
    elif is_irrigate:
        decision = irrigation["decision"].replace("_", " ")
        reply = (
            f"Irrigation advice for {resolved}. {decision}. {irrigation['reason']} "
            f"Expected rainfall over three days is {irrigation['forecast_rain_3d_mm']} millimetres."
        )
    else:
        # General weather query — use farmer report, voice-trimmed
        report = weather.get("farmer_report", "")
        reply = _voice_safe(report, limit=500)

    # Translate if not English
    if language != "en":
        try:
            from app.services.ai.sarvam_service import translate_text
            reply = await translate_text(reply, source_lang="en-IN", target_lang=LANGUAGE_AUDIO_CODES[language])
        except Exception as exc:
            logger.warning("IVR weather translation failed: %s", exc)

    return _voice_safe(reply)


async def _ai_scheme_response(transcript: str, language: str) -> str:
    if not transcript:
        generic = {
            "en": "For PM Kisan or any subsidy, keep Aadhaar, bank account, land record, and e-K-Y-C ready. Eligibility depends on official rules.",
            "ta": "PM கிசான் அல்லது மானியங்களுக்கு ஆதார், வங்கி கணக்கு, நில ஆவணம் மற்றும் e-KYC தயாராக வையுங்கள்.",
            "kn": "PM ಕಿಸಾನ್ ಅಥವಾ ಸಬ್ಸಿಡಿಗೆ ಆಧಾರ್, ಬ್ಯಾಂಕ್ ಖಾತೆ, ಭೂ ದಾಖಲೆ ಮತ್ತು e-KYC ಸಿದ್ಧವಾಗಿರಲಿ.",
        }
        return generic.get(language, generic["en"])
    try:
        answer = await chat_with_ai(
            message=transcript,
            history=[],
            language=language,
            context={"channel": "ivr", "intent": "scheme"},
            channel="ivr",
        )
        return _voice_safe(answer)
    except Exception as exc:
        logger.exception("IVR scheme AI failed: %s", exc)
        return {
            "en": "Scheme information is temporarily unavailable. Please visit your nearest agriculture office.",
            "ta": "திட்ட தகவல் தற்காலிகமாக கிடைக்கவில்லை. அருகில் உள்ள வேளாண்மை அலுவலகத்தை சந்திக்கவும்.",
            "kn": "ಯೋಜನೆ ಮಾಹಿತಿ ತಾತ್ಕಾಲಿಕವಾಗಿ ಲಭ್ಯವಿಲ್ಲ. ಸಮೀಪದ ಕೃಷಿ ಕಚೇರಿಗೆ ಭೇಟಿ ನೀಡಿ.",
        }.get(language, "Scheme information is temporarily unavailable.")


async def _register_grievance(db: Session, transcript: str, session: IvrSession, language: str) -> str:
    if not transcript:
        return FALLBACK_RESPONSES["grievance"].get(language, FALLBACK_RESPONSES["grievance"]["en"])
    farmer = _get_or_create_farmer(db, session.phone_number)
    try:
        category = await classify_grievance(transcript)
    except Exception:
        category = "general"
    tracking_id = f"KM-2026-{uuid.uuid4().hex[:5].upper()}"
    grievance = Grievance(
        tracking_id=tracking_id,
        farmer_id=farmer.id,
        category=category,
        title=transcript[:90] or "IVR grievance",
        description=transcript,
        status="submitted",
        expected_resolution_days=30,
    )
    db.add(grievance)
    try:
        _safe_commit(db)
    except Exception as exc:
        logger.exception("IVR grievance DB commit failed: %s", exc)
        return {
            "en": "Sorry, your grievance could not be saved. Please call again.",
            "ta": "மன்னிக்கவும், உங்கள் புகாரை சேமிக்க முடியவில்லை. மீண்டும் அழைக்கவும்.",
            "kn": "ಕ್ಷಮಿಸಿ, ನಿಮ್ಮ ದೂರನ್ನು ಉಳಿಸಲಾಗಲಿಲ್ಲ. ದಯವಿಟ್ಟು ಮತ್ತೆ ಕರೆ ಮಾಡಿ.",
        }.get(language, "Sorry, your grievance could not be saved.")
    _log_event(db, "ivr_grievance_created", session, {"tracking_id": tracking_id, "category": category})
    return {
        "en": f"Your grievance has been registered. Your tracking number is {' '.join(tracking_id)}. Please save this number.",
        "ta": f"உங்கள் புகார் பதிவு செய்யப்பட்டது. கண்காணிப்பு எண் {' '.join(tracking_id)}. இந்த எண்ணை சேமித்து வையுங்கள்.",
        "kn": f"ನಿಮ್ಮ ದೂರನ್ನು ದಾಖಲಿಸಲಾಗಿದೆ. ಟ್ರ್ಯಾಕಿಂಗ್ ಸಂಖ್ಯೆ {' '.join(tracking_id)}. ಈ ಸಂಖ್ಯೆಯನ್ನು ಉಳಿಸಿಕೊಳ್ಳಿ.",
    }.get(language, f"Grievance registered. Tracking number is {tracking_id}.")


def _track_grievance(db: Session, digits_or_speech: str, language: str) -> str:
    clean = "".join(ch for ch in (digits_or_speech or "") if ch.isalnum())
    if not clean:
        return {
            "en": "I did not receive a tracking number. Please call again.",
            "ta": "கண்காணிப்பு எண் கிடைக்கவில்லை. மீண்டும் அழைக்கவும்.",
            "kn": "ಟ್ರ್ಯಾಕಿಂಗ್ ಸಂಖ್ಯೆ ದೊರೆಯಲಿಲ್ಲ. ದಯವಿಟ್ಟು ಮತ್ತೆ ಕರೆ ಮಾಡಿ.",
        }.get(language, "I did not receive a tracking number.")
    grievance = (
        db.query(Grievance)
        .filter(Grievance.tracking_id.ilike(f"%{clean}"))
        .order_by(Grievance.created_at.desc())
        .first()
    )
    if not grievance:
        return {
            "en": f"No grievance found for tracking number ending in {clean}. Please check the number.",
            "ta": f"{clean} கொண்ட கண்காணிப்பு எண்ணுக்கு புகார் எதுவும் கிடைக்கவில்லை.",
            "kn": f"{clean} ಕೊನೆಗೊಳ್ಳುವ ಟ್ರ್ಯಾಕಿಂಗ್ ಸಂಖ್ಯೆಗೆ ದೂರು ಸಿಗಲಿಲ್ಲ.",
        }.get(language, f"No grievance found for {clean}.")
    return {
        "en": f"Tracking number {grievance.tracking_id}. Current status is {grievance.status}. Expected resolution in {grievance.expected_resolution_days} days.",
        "ta": f"கண்காணிப்பு எண் {grievance.tracking_id}. தற்போதைய நிலை {grievance.status}. {grievance.expected_resolution_days} நாட்களில் தீர்வு எதிர்பார்க்கப்படுகிறது.",
        "kn": f"ಟ್ರ್ಯಾಕಿಂಗ್ ಸಂಖ್ಯೆ {grievance.tracking_id}. ಪ್ರಸ್ತುತ ಸ್ಥಿತಿ {grievance.status}. {grievance.expected_resolution_days} ದಿನಗಳಲ್ಲಿ ಪರಿಹಾರ ನಿರೀಕ್ಷಿತ.",
    }.get(language, f"Tracking number {grievance.tracking_id}. Status: {grievance.status}.")


# ---------------------------------------------------------------------------
# Session language detection from Twilio params
# ---------------------------------------------------------------------------


def _get_language(session: IvrSession) -> str:
    lang = (session.language or "en").split("-")[0].lower()
    return lang if lang in SUPPORTED_LANGUAGES else "en"


# ---------------------------------------------------------------------------
# Shared finish block: reply + "press 9 for menu"
# ---------------------------------------------------------------------------


async def _finish(reply_text: str, session: IvrSession, db: Session) -> Response:
    language = _get_language(session)
    reply_audio = await _tts_play(reply_text, language, session.session_id)
    repeat_prompt = REPEAT_MENU_PROMPT.get(language, REPEAT_MENU_PROMPT["en"])
    repeat_audio = await _tts_play(repeat_prompt, language, session.session_id)
    menu_url = _public_url(f"/ivr/twilio/welcome?session_id={session.session_id}")
    hangup_prompt = {
        "en": "Thank you for calling KrishiMitra. Goodbye.",
        "ta": "KrishiMitra அழைத்தமைக்கு நன்றி. வணக்கம்.",
        "kn": "KrishiMitra ಗೆ ಕರೆ ಮಾಡಿದ್ದಕ್ಕೆ ಧನ್ಯವಾದ.",
    }.get(language, "Thank you for calling KrishiMitra.")
    hangup_audio = await _tts_play(hangup_prompt, language, session.session_id)

    dtmf_content = _gather_dtmf(
        action_url=menu_url,
        prompt_twiml=repeat_audio,
        num_digits=1,
        timeout=6,
    )
    return _xml(reply_audio, dtmf_content, hangup_audio, "<Hangup/>")


# ---------------------------------------------------------------------------
# Webhook endpoints
# ---------------------------------------------------------------------------


@router.api_route("/twilio/welcome", methods=["GET", "POST"])
@router.api_route("/twilio/incoming", methods=["GET", "POST"])
async def twilio_welcome(
    request: Request,
    From: Optional[str] = Form(None),
    To: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Entry point for every inbound call."""
    # Support GET (browser test) and POST (Twilio)
    if request.method == "GET":
        phone = request.query_params.get("From") or request.query_params.get("phone") or "browser-test"
        session_id = request.query_params.get("session_id")
    else:
        phone = From or To or "unknown-caller"
        session_id = None

    requested_language = normalize_outbound_language(request.query_params.get("language"))
    requested_purpose = normalize_outbound_purpose(request.query_params.get("purpose"))

    if session_id:
        session = _get_session(db, session_id, phone)
    else:
        # New call — close any stale active session for this number first
        stale = (
            db.query(IvrSession)
            .filter(IvrSession.phone_number == phone.replace("whatsapp:", "").strip(), IvrSession.status == "active")
            .first()
        )
        if stale:
            _update_session(db, stale, status="completed")
        session = _get_or_create_session(db, phone)

    session_context = dict(session.context or {})
    session_context["purpose"] = requested_purpose
    if requested_purpose != "general":
        session_context["preferred_intent"] = requested_purpose
    else:
        session_context.pop("preferred_intent", None)

    _update_session(db, session, language=requested_language, context=session_context)
    language = _get_language(session)
    preferred_intent = session_context.get("preferred_intent")

    if preferred_intent in RECORD_PROMPTS:
        _update_session(db, session, current_state=preferred_intent.upper(), last_intent=preferred_intent)
        welcome_text = WELCOME_PROMPTS.get(language, WELCOME_PROMPTS["en"])
        prompt_text = RECORD_PROMPTS[preferred_intent].get(language, RECORD_PROMPTS[preferred_intent]["en"])
        prompt_audio = await _tts_play(f"{welcome_text} {prompt_text}", language, session.session_id)
        action_url = _public_url(f"/ivr/twilio/{preferred_intent}/respond?session_id={session.session_id}")
        return _xml(_record(action_url, prompt_audio, max_length=30, timeout=5))

    _update_session(db, session, current_state="MAIN_MENU")

    welcome_text = WELCOME_PROMPTS.get(language, WELCOME_PROMPTS["en"])
    menu_text = MENU_PROMPTS.get(language, MENU_PROMPTS["en"])
    full_prompt = f"{welcome_text} {menu_text}"

    prompt_audio = await _tts_play(full_prompt, language, session.session_id)
    menu_action = _public_url(f"/ivr/twilio/menu?session_id={session.session_id}")
    no_input_audio = await _tts_play(
        {
            "en": "I did not receive input. Returning to the main menu.",
            "ta": "உள்ளீடு கிடைக்கவில்லை. முதன்மை மெனுவிற்கு திரும்புகிறோம்.",
            "kn": "ಒಳಹರಿವು ಸಿಗಲಿಲ್ಲ. ಮುಖ್ಯ ಮೆನುಗೆ ಹಿಂತಿರುಗುತ್ತಿದ್ದೇವೆ.",
        }.get(language, "I did not receive input."),
        language,
        session.session_id,
    )
    redirect_url = _public_url(f"/ivr/twilio/welcome?session_id={session.session_id}")

    return _xml(
        _gather_dtmf(menu_action, prompt_audio, num_digits=1, timeout=10),
        no_input_audio,
        f'<Redirect method="POST">{escape(redirect_url)}</Redirect>',
    )


@router.api_route("/twilio/menu", methods=["GET", "POST"])
async def twilio_menu(
    session_id: Optional[str] = None,
    From: Optional[str] = Form(None),
    Digits: Optional[str] = Form(None),
    SpeechResult: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Handle DTMF digit from main menu and route to the right intent."""
    session = _get_session(db, session_id, From)
    language = _get_language(session)
    digit = (Digits or "").strip()

    if digit == "9" or not digit:
        return await twilio_welcome.__wrapped__(
            request=None, From=session.phone_number, To=None, db=db
        ) if False else _xml(
            f'<Redirect method="POST">{escape(_public_url(f"/ivr/twilio/welcome?session_id={session.session_id}"))}</Redirect>'
        )

    intent = MENU_DIGIT_TO_INTENT.get(digit)
    if not intent:
        redirect_url = _public_url(f"/ivr/twilio/welcome?session_id={session.session_id}")
        return _xml(f'<Redirect method="POST">{escape(redirect_url)}</Redirect>')

    _update_session(db, session, current_state=intent.upper(), last_intent=intent)
    _log_event(db, "ivr_menu_selection", session, {"digit": digit, "intent": intent})

    # For track, gather digits; for everything else, record voice
    if intent == "track":
        prompt_text = RECORD_PROMPTS["track"].get(language, RECORD_PROMPTS["track"]["en"])
        prompt_audio = await _tts_play(prompt_text, language, session.session_id)
        action_url = _public_url(f"/ivr/twilio/track/respond?session_id={session.session_id}")
        return _xml(
            _gather_dtmf(action_url, prompt_audio, num_digits=5, timeout=12)
        )

    prompt_text = RECORD_PROMPTS[intent].get(language, RECORD_PROMPTS[intent]["en"])
    prompt_audio = await _tts_play(prompt_text, language, session.session_id)
    action_url = _public_url(f"/ivr/twilio/{intent}/respond?session_id={session.session_id}")
    return _xml(_record(action_url, prompt_audio, max_length=30, timeout=5))


# ---------------------------------------------------------------------------
# /respond endpoints — one per intent
# ---------------------------------------------------------------------------


@router.api_route("/twilio/crop/respond", methods=["GET", "POST"])
async def twilio_crop_respond(
    session_id: Optional[str] = None,
    From: Optional[str] = Form(None),
    RecordingUrl: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    session = _get_session(db, session_id, From)
    language = _get_language(session)
    transcript = await _transcribe_recording(RecordingUrl or "", language)
    _update_session(db, session, last_transcript=transcript, current_state="MAIN_MENU")
    _log_event(db, "ivr_crop_query", session, {"transcript": transcript})
    reply = await _ai_crop_response(transcript, language, session.phone_number)
    return await _finish(reply, session, db)


@router.api_route("/twilio/weather/respond", methods=["GET", "POST"])
async def twilio_weather_respond(
    session_id: Optional[str] = None,
    From: Optional[str] = Form(None),
    RecordingUrl: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    session = _get_session(db, session_id, From)
    language = _get_language(session)
    transcript = await _transcribe_recording(RecordingUrl or "", language)
    _update_session(db, session, last_transcript=transcript, current_state="MAIN_MENU")
    _log_event(db, "ivr_weather_query", session, {"transcript": transcript})
    reply = await _ai_weather_response(transcript, language, session)
    return await _finish(reply, session, db)


@router.api_route("/twilio/scheme/respond", methods=["GET", "POST"])
async def twilio_scheme_respond(
    session_id: Optional[str] = None,
    From: Optional[str] = Form(None),
    RecordingUrl: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    session = _get_session(db, session_id, From)
    language = _get_language(session)
    transcript = await _transcribe_recording(RecordingUrl or "", language)
    _update_session(db, session, last_transcript=transcript, current_state="MAIN_MENU")
    _log_event(db, "ivr_scheme_query", session, {"transcript": transcript})
    reply = await _ai_scheme_response(transcript, language)
    return await _finish(reply, session, db)


@router.api_route("/twilio/grievance/respond", methods=["GET", "POST"])
async def twilio_grievance_respond(
    session_id: Optional[str] = None,
    From: Optional[str] = Form(None),
    RecordingUrl: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    session = _get_session(db, session_id, From)
    language = _get_language(session)
    transcript = await _transcribe_recording(RecordingUrl or "", language)
    reply = await _register_grievance(db, transcript, session, language)
    _update_session(db, session, last_transcript=transcript, current_state="MAIN_MENU")
    return await _finish(reply, session, db)


@router.api_route("/twilio/track/respond", methods=["GET", "POST"])
async def twilio_track_respond(
    session_id: Optional[str] = None,
    From: Optional[str] = Form(None),
    Digits: Optional[str] = Form(None),
    SpeechResult: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    session = _get_session(db, session_id, From)
    language = _get_language(session)
    input_value = Digits or SpeechResult or ""
    _update_session(db, session, last_transcript=input_value, current_state="MAIN_MENU")
    _log_event(db, "ivr_track_query", session, {"input": input_value})
    reply = _track_grievance(db, input_value, language)
    return await _finish(reply, session, db)


# ---------------------------------------------------------------------------
# Outbound call endpoint (for officers)
# ---------------------------------------------------------------------------



@router.get("/twilio/outbound-status")
async def twilio_outbound_status(current_user: User = Depends(get_officer)):
    status = await get_outbound_call_status()
    status["webhook_url"] = _public_url("/ivr/twilio/welcome")
    return status


@router.post("/twilio/call")
async def place_outbound_call(
    payload: OutboundCallRequest,
    current_user: User = Depends(get_officer),
):
    to_number = normalize_phone_number(payload.to_number, "Farmer phone number")
    outbound_status = await get_outbound_call_status()
    if not outbound_status["ready"]:
        raise HTTPException(status_code=400, detail=outbound_status["message"])

    welcome_url = _build_outbound_welcome_url(payload.language, payload.purpose)

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Calls.json",
            data={
                "To": to_number,
                "From": outbound_status["from_number"],
                "Url": welcome_url,
            },
            auth=(
                settings.TWILIO_ACCOUNT_SID,
                settings.TWILIO_AUTH_TOKEN,
            ),
        )

    if resp.status_code >= 400:
        raise HTTPException(
            status_code=400,
            detail=twilio_error_message(resp, outbound_status["from_number"]),
        )

    data = resp.json()

    return {
        "call_sid": data.get("sid"),
        "status": data.get("status"),
        "from_number": outbound_status["from_number"],
        "to_number": to_number,
        "language": payload.language,
        "purpose": payload.purpose,
    }
@router.api_route("/twilio/ping", methods=["GET", "POST"])
async def twilio_ping():
    return _xml(_say("KrishiMitra IVR webhook reached successfully.", "en"))
