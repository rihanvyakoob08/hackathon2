from typing import Optional

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import get_officer
from app.config import settings
from app.database import get_db
from app.models import User
from app.services.ai.sarvam_service import transcribe_audio
from app.services.ivr.ivr_service import IvrService


router = APIRouter(prefix="/ivr", tags=["IVR"])
ivr_service = IvrService()


def public_url(path: str) -> str:
    prefix = settings.PUBLIC_WEBHOOK_PREFIX.strip("/")
    full_path = f"/{prefix}{path}" if prefix else path
    return f"{settings.PUBLIC_BASE_URL.rstrip('/')}{full_path}"


def public_asset_base_url() -> str:
    prefix = settings.PUBLIC_WEBHOOK_PREFIX.strip("/")
    return f"{settings.PUBLIC_BASE_URL.rstrip()}/{prefix}".rstrip("/") if prefix else settings.PUBLIC_BASE_URL.rstrip("/")


class IncomingCall(BaseModel):
    phone_number: str
    provider: str = "mock"


class OutboundCall(BaseModel):
    to_number: str


@router.post("/incoming")
async def incoming_call(payload: IncomingCall, db: Session = Depends(get_db)):
    return await ivr_service.incoming_call(db, payload.phone_number, payload.provider)


@router.post("/callback")
async def callback(
    session_id: Optional[str] = Form(None),
    phone_number: Optional[str] = Form(None),
    provider: str = Form("mock"),
    digits: Optional[str] = Form(None),
    text: Optional[str] = Form(None),
    tracking_id: Optional[str] = Form(None),
    audio: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    try:
        return await ivr_service.handle_callback(
            db,
            session_id=session_id,
            phone_number=phone_number,
            provider=provider,
            digits=digits,
            text=text,
            tracking_id=tracking_id,
            audio=audio,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/session/{session_id}")
async def get_session(session_id: str, db: Session = Depends(get_db)):
    session = ivr_service.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="IVR session not found")
    return session


@router.get("/sessions")
async def get_recent_sessions(
    limit: int = 20,
    current_user: User = Depends(get_officer),
    db: Session = Depends(get_db),
):
    return ivr_service.recent_sessions(db, limit)


@router.post("/twilio/call")
async def place_twilio_call(payload: OutboundCall, current_user: User = Depends(get_officer)):
    base_url = settings.PUBLIC_BASE_URL.rstrip("/")
    if base_url.startswith("http://127.0.0.1") or base_url.startswith("http://localhost"):
        raise HTTPException(status_code=400, detail="Set PUBLIC_BASE_URL to your public ngrok URL before placing Twilio calls.")
    try:
        result = await ivr_service.provider("twilio").place_call(payload.to_number, public_url("/ivr/twilio/incoming"))
        return {"message": "Call initiated", "call_sid": result.get("sid"), "status": result.get("status")}
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/twilio/test-call")
async def place_twilio_test_call(payload: OutboundCall, current_user: User = Depends(get_officer)):
    twiml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        "<Say>KrishiMitra test call is working. This call does not use your public webhook tunnel.</Say>"
        "</Response>"
    )
    try:
        result = await ivr_service.provider("twilio").place_twiml_call(payload.to_number, twiml)
        return {"message": "Test call initiated", "call_sid": result.get("sid"), "status": result.get("status")}
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.api_route("/twilio/ping", methods=["GET", "POST"])
async def twilio_ping():
    twiml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        "<Say>KrishiMitra webhook reached successfully.</Say>"
        "</Response>"
    )
    return Response(content=twiml, media_type="application/xml")


@router.post("/twilio/incoming")
async def twilio_incoming(
    From: Optional[str] = Form(None),
    To: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    print(f"Twilio incoming webhook reached. From={From}, To={To}")
    try:
        phone_number = To or From or "unknown-twilio-caller"
        action = await ivr_service.incoming_call(db, phone_number, "twilio")
        twiml = ivr_service.provider("twilio").to_twiml(
            _action_from_rendered(action),
            session_id=action["session"]["session_id"],
            callback_url=public_url("/ivr/twilio/callback"),
            public_base_url=public_asset_base_url(),
        )
    except Exception as error:
        print(f"Twilio incoming failed: {error}")
        twiml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<Response>"
            "<Say>KrishiMitra server received the call, but the IVR had an internal error. Please check backend logs.</Say>"
            "</Response>"
        )
    return Response(content=twiml, media_type="application/xml")


@router.post("/twilio/callback")
async def twilio_callback(
    session_id: str,
    From: Optional[str] = Form(None),
    Digits: Optional[str] = Form(None),
    RecordingUrl: Optional[str] = Form(None),
    SpeechResult: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    print(f"Twilio callback reached. session_id={session_id}, From={From}, Digits={Digits}, RecordingUrl={RecordingUrl}")
    try:
        text = SpeechResult
        if RecordingUrl and not text:
            text = await _transcribe_twilio_recording(session_id, RecordingUrl, db)

        action = await ivr_service.handle_callback(
            db,
            session_id=session_id,
            phone_number=From,
            provider="twilio",
            digits=Digits,
            text=text,
        )
        twiml = ivr_service.provider("twilio").to_twiml(
            _action_from_rendered(action),
            session_id=action["session"]["session_id"],
            callback_url=public_url("/ivr/twilio/callback"),
            public_base_url=public_asset_base_url(),
        )
    except Exception as error:
        print(f"Twilio callback failed: {error}")
        twiml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<Response>"
            "<Say>KrishiMitra received your input, but could not continue. Please check backend logs.</Say>"
            "</Response>"
        )
    return Response(content=twiml, media_type="application/xml")


def _action_from_rendered(rendered: dict):
    from app.services.ivr.ivr_models import IvrAction

    return IvrAction(
        type="prompt",
        prompt=rendered.get("prompt", ""),
        audio_url=rendered.get("audio_url"),
        collect_digits=rendered.get("action") == "collect_digits",
        max_digits=rendered.get("max_digits", 1),
        record=rendered.get("action") == "record",
        next_state=rendered.get("next_state"),
        metadata=rendered.get("metadata") or {},
    )


async def _transcribe_twilio_recording(session_id: str, recording_url: str, db: Session) -> str:
    session = ivr_service.get_session(db, session_id)
    language = session.get("language") if session else "ta"
    audio_url = recording_url if recording_url.endswith(".wav") else f"{recording_url}.wav"
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(audio_url, auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN))
    if response.status_code >= 400:
        raise HTTPException(status_code=400, detail=f"Could not download Twilio recording: {response.text}")
    lang_code = {"ta": "ta-IN", "kn": "kn-IN", "en": "en-IN"}.get(language or "ta", "ta-IN")
    result = await transcribe_audio(response.content, lang_code, "twilio-recording.wav")
    return result.get("transcript") or ""
