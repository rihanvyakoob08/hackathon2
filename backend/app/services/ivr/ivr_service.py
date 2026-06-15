import os
import random
import uuid
from typing import Optional

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.models import AnalyticsEvent, Grievance, IvrSession, User
from app.services.ai.sarvam_ai_service import (
    chat_with_ai,
    check_scheme_eligibility,
    classify_grievance,
    classify_intent,
    get_weather_advisory,
)
from app.services.ai.sarvam_service import text_to_speech, transcribe_audio
from app.services.ivr.localization import language_prompt, normalise_language, prompt_for
from app.services.ivr.ivr_models import IvrAction, IvrIntent, IvrState
from app.services.ivr.providers import ExotelProvider, MockTelephonyProvider, TwilioProvider
from app.services.ivr.session_manager import IvrSessionManager
from app.services.ivr.state_machine import (
    SCHEME_LAND_DIGITS,
    SCHEME_STATE_DIGITS,
    language_from_digits,
    menu_intent,
    route_state_from_menu,
)


LANGUAGE_AUDIO_CODES = {
    "ta": "ta-IN",
    "kn": "kn-IN",
    "en": "en-IN",
}

PROMPTS = {
    "language": "Welcome to KrishiMitra. Press 1 for Tamil. Press 2 for Kannada. Press 3 for English.",
    "menu": "Press 1 to ask a farming question. Press 2 for scheme eligibility. Press 3 to register a grievance. Press 4 to track a grievance. Press 5 for crop recommendations.",
    "record": "Ask your farming question after the beep.",
    "grievance": "Describe your grievance after the beep.",
    "tracking": "Enter the last five digits of your grievance tracking number.",
    "scheme_state": "For state, press 1 for Tamil Nadu. Press 2 for Karnataka.",
    "scheme_land": "For land ownership, press 1 if you own land. Press 2 if tenant or sharecropper. Press 3 if landless.",
    "scheme_income": "Enter annual income in rupees, then submit.",
}

LOCALIZED_PROMPTS = {
    "ta": {
        "menu": "விவசாய கேள்விக்கு 1 அழுத்தவும். திட்ட தகுதிக்கு 2 அழுத்தவும். புகார் பதிவு செய்ய 3 அழுத்தவும். புகார் நிலை அறிய 4 அழுத்தவும். பயிர் பரிந்துரைக்கு 5 அழுத்தவும்.",
        "record": "பீப் ஒலிக்குப் பிறகு உங்கள் விவசாய கேள்வியை கேளுங்கள்.",
        "grievance": "பீப் ஒலிக்குப் பிறகு உங்கள் புகாரை சொல்லுங்கள்.",
        "tracking": "உங்கள் புகார் எண்ணின் கடைசி ஐந்து இலக்கங்களை உள்ளிடவும்.",
        "scheme_state": "மாநிலத்திற்கு, தமிழ்நாடு என்றால் 1 அழுத்தவும். கர்நாடகா என்றால் 2 அழுத்தவும்.",
        "scheme_land": "நில உரிமைக்கு, சொந்த நிலம் என்றால் 1. குத்தகை அல்லது பகிர்வு விவசாயி என்றால் 2. நிலமில்லாதவர் என்றால் 3.",
        "scheme_income": "உங்கள் வருடாந்திர வருமானத்தை ரூபாயில் உள்ளிடவும்.",
    },
    "kn": {
        "menu": "ಕೃಷಿ ಪ್ರಶ್ನೆಗೆ 1 ಒತ್ತಿ. ಯೋಜನೆ ಅರ್ಹತೆಗೆ 2 ಒತ್ತಿ. ದೂರು ದಾಖಲಿಸಲು 3 ಒತ್ತಿ. ದೂರು ಸ್ಥಿತಿ ತಿಳಿಯಲು 4 ಒತ್ತಿ. ಬೆಳೆ ಶಿಫಾರಸಿಗೆ 5 ಒತ್ತಿ.",
        "record": "ಬೀಪ್ ನಂತರ ನಿಮ್ಮ ಕೃಷಿ ಪ್ರಶ್ನೆಯನ್ನು ಕೇಳಿ.",
        "grievance": "ಬೀಪ್ ನಂತರ ನಿಮ್ಮ ದೂರನ್ನು ವಿವರಿಸಿ.",
        "tracking": "ನಿಮ್ಮ ದೂರು ಸಂಖ್ಯೆಯ ಕೊನೆಯ ಐದು ಅಂಕಿಗಳನ್ನು ನಮೂದಿಸಿ.",
        "scheme_state": "ರಾಜ್ಯಕ್ಕೆ, ತಮಿಳುನಾಡು ಎಂದರೆ 1 ಒತ್ತಿ. ಕರ್ನಾಟಕ ಎಂದರೆ 2 ಒತ್ತಿ.",
        "scheme_land": "ಭೂಸ್ವಾಮ್ಯಕ್ಕೆ, ಸ್ವಂತ ಭೂಮಿ ಎಂದರೆ 1. ಬಾಡಿಗೆ ಅಥವಾ ಹಂಚಿಕೆ ರೈತ ಎಂದರೆ 2. ಭೂಹೀನ ಎಂದರೆ 3.",
        "scheme_income": "ನಿಮ್ಮ ವಾರ್ಷಿಕ ಆದಾಯವನ್ನು ರೂಪಾಯಿಯಲ್ಲಿ ನಮೂದಿಸಿ.",
    },
}


class IvrService:
    def __init__(self):
        self.sessions = IvrSessionManager()
        self.providers = {
            "mock": MockTelephonyProvider(),
            "exotel": ExotelProvider(),
            "twilio": TwilioProvider(),
        }

    def provider(self, name: str):
        return self.providers.get(name, self.providers["mock"])

    async def incoming_call(self, db: Session, phone_number: str, provider: str = "mock") -> dict:
        session = self.sessions.get_or_create(db, phone_number, provider)
        if session.current_state != IvrState.LANGUAGE_SELECTION.value:
            action = await self._action(session, self._prompt(session, "menu"), collect_digits=True, next_state=IvrState.MAIN_MENU)
        else:
            action = await self._action(session, language_prompt(), collect_digits=True, next_state=IvrState.LANGUAGE_SELECTION)
        self._log_event(db, "ivr_call_started", session, {"provider": provider})
        return self._render(session, action)

    async def handle_callback(
        self,
        db: Session,
        *,
        session_id: Optional[str],
        phone_number: Optional[str],
        provider: str,
        digits: Optional[str] = None,
        text: Optional[str] = None,
        tracking_id: Optional[str] = None,
        audio: Optional[UploadFile] = None,
    ) -> dict:
        session = self._resolve_session(db, session_id, phone_number, provider)
        state = IvrState(session.current_state)

        if state == IvrState.LANGUAGE_SELECTION:
            language = normalise_language(language_from_digits(digits))
            self.sessions.update(db, session, language=language, state=IvrState.MAIN_MENU, context=session.context or {})
            action = await self._action(session, self._prompt(session, "menu"), collect_digits=True, next_state=IvrState.MAIN_MENU)
            return self._render(session, action)

        if state == IvrState.MAIN_MENU:
            next_state = route_state_from_menu(digits)
            intent = menu_intent(digits).value
            context = dict(session.context or {})
            context["menu_digit"] = digits
            self.sessions.update(db, session, state=next_state, context=context, intent=intent)
            return await self._prompt_for_state(db, session, next_state)

        if state == IvrState.RECORD_QUERY:
            transcript = await self._input_text(audio, text, session)
            response = await self._answer_open_query(db, session, transcript)
            self.sessions.update(db, session, state=IvrState.MAIN_MENU, transcript=transcript)
            action = await self._action(session, f"{response} {self._prompt(session, 'menu')}", collect_digits=True, next_state=IvrState.MAIN_MENU)
            return self._render(session, action)

        if state == IvrState.GRIEVANCE_RECORD:
            transcript = await self._input_text(audio, text, session)
            response = await self._register_grievance(db, session, transcript)
            self.sessions.update(db, session, state=IvrState.MAIN_MENU, transcript=transcript)
            action = await self._action(session, f"{response} {self._prompt(session, 'menu')}", collect_digits=True, next_state=IvrState.MAIN_MENU)
            return self._render(session, action)

        if state == IvrState.TRACK_GRIEVANCE:
            response = self._track_grievance(db, tracking_id or digits or "")
            self.sessions.update(db, session, state=IvrState.MAIN_MENU)
            action = await self._action(session, f"{response} {self._prompt(session, 'menu')}", collect_digits=True, next_state=IvrState.MAIN_MENU)
            return self._render(session, action)

        if state in {IvrState.SCHEME_STATE, IvrState.SCHEME_LAND, IvrState.SCHEME_INCOME}:
            return await self._handle_scheme_flow(db, session, state, digits or text or "")

        action = await self._action(session, self._prompt(session, "menu"), collect_digits=True, next_state=IvrState.MAIN_MENU)
        return self._render(session, action)

    def get_session(self, db: Session, session_id: str) -> dict | None:
        session = self.sessions.get(db, session_id)
        if not session:
            return None
        return self._session_payload(session)

    def recent_sessions(self, db: Session, limit: int = 20) -> list[dict]:
        sessions = db.query(IvrSession).order_by(IvrSession.updated_at.desc()).limit(limit).all()
        return [self._session_payload(session) for session in sessions]

    async def _prompt_for_state(self, db: Session, session: IvrSession, state: IvrState) -> dict:
        if state == IvrState.SCHEME_STATE:
            action = await self._action(session, self._prompt(session, "scheme_state"), collect_digits=True, next_state=state)
        elif state == IvrState.GRIEVANCE_RECORD:
            action = await self._action(session, self._prompt(session, "grievance"), record=True, next_state=state)
        elif state == IvrState.TRACK_GRIEVANCE:
            action = await self._action(session, self._prompt(session, "tracking"), collect_digits=True, max_digits=5, next_state=state)
        else:
            action = await self._action(session, self._prompt(session, "record"), record=True, next_state=state)
        return self._render(session, action)

    async def _handle_scheme_flow(self, db: Session, session: IvrSession, state: IvrState, value: str) -> dict:
        context = dict(session.context or {})
        if state == IvrState.SCHEME_STATE:
            context["state"] = SCHEME_STATE_DIGITS.get(value, "Tamil Nadu")
            self.sessions.update(db, session, state=IvrState.SCHEME_LAND, context=context)
            action = await self._action(session, self._prompt(session, "scheme_land"), collect_digits=True, next_state=IvrState.SCHEME_LAND)
            return self._render(session, action)

        if state == IvrState.SCHEME_LAND:
            context["land_ownership"] = SCHEME_LAND_DIGITS.get(value, "unknown")
            self.sessions.update(db, session, state=IvrState.SCHEME_INCOME, context=context)
            action = await self._action(session, self._prompt(session, "scheme_income"), collect_digits=True, max_digits=7, next_state=IvrState.SCHEME_INCOME)
            return self._render(session, action)

        annual_income = float("".join(ch for ch in value if ch.isdigit()) or 0)
        context["annual_income"] = annual_income
        result = await check_scheme_eligibility(
            scheme_name="PM-KISAN",
            state=context.get("state"),
            land_ownership=context.get("land_ownership"),
            farmer_category="small",
            annual_income=annual_income,
            language=session.language or "ta",
        )
        response = self._scheme_summary(result)
        self.sessions.update(db, session, state=IvrState.MAIN_MENU, context=context, intent=IvrIntent.SCHEME_QUERY.value)
        self._log_event(db, "ivr_scheme_check", session, {"scheme": "PM-KISAN", "status": result.get("eligibility_status")})
        action = await self._action(session, f"{response} {self._prompt(session, 'menu')}", collect_digits=True, next_state=IvrState.MAIN_MENU)
        return self._render(session, action)

    async def _answer_open_query(self, db: Session, session: IvrSession, transcript: str) -> str:
        intent = await classify_intent(transcript)
        language = session.language or "ta"
        if intent == "weather":
            response = await get_weather_advisory("crop", "your district", transcript, language)
        else:
            response = await chat_with_ai(
                transcript,
                [],
                language,
                context={"channel": "ivr", "agent": settings.IVR_AGENT_NAME, "phone_number": session.phone_number},
                channel="ivr",
            )
        self.sessions.update(db, session, intent=intent)
        self._log_event(db, "ivr_query", session, {"intent": intent, "transcript": transcript})
        return self._voice_safe(response)

    async def _register_grievance(self, db: Session, session: IvrSession, transcript: str) -> str:
        farmer = self._find_or_create_farmer(db, session.phone_number)
        category = await classify_grievance(transcript)
        tracking_id = self._tracking_id()
        while db.query(Grievance).filter(Grievance.tracking_id == tracking_id).first():
            tracking_id = self._tracking_id()
        grievance = Grievance(
            tracking_id=tracking_id,
            farmer_id=farmer.id,
            category=category,
            title=f"IVR {category}",
            description=transcript,
            status="submitted",
            expected_resolution_days=30,
        )
        db.add(grievance)
        db.commit()
        self._log_event(db, "ivr_grievance_created", session, {"tracking_id": tracking_id, "category": category})
        return f"Grievance registered. Your tracking number is {tracking_id}."

    def _track_grievance(self, db: Session, digits: str) -> str:
        clean = "".join(ch for ch in digits if ch.isalnum())
        grievance = (
            db.query(Grievance)
            .filter(Grievance.tracking_id.ilike(f"%{clean}"))
            .order_by(Grievance.created_at.desc())
            .first()
        )
        if not grievance:
            return "No grievance was found for that tracking number."
        return f"Tracking number {grievance.tracking_id}. Status is {grievance.status}."

    async def _input_text(self, audio: Optional[UploadFile], text: Optional[str], session: IvrSession) -> str:
        if text:
            return text
        if not audio:
            return "The caller did not provide a recording."
        content = await audio.read()
        result = await transcribe_audio(content, LANGUAGE_AUDIO_CODES.get(session.language or "ta", "ta-IN"), audio.filename)
        return result.get("transcript") or "The recording could not be transcribed."

    async def _action(
        self,
        session: IvrSession,
        prompt: str,
        *,
        collect_digits: bool = False,
        max_digits: int = 1,
        record: bool = False,
        next_state: IvrState | None = None,
    ) -> IvrAction:
        audio_url = await self._tts(prompt, session)
        return IvrAction(
            type="prompt",
            prompt=prompt,
            audio_url=audio_url,
            collect_digits=collect_digits,
            max_digits=max_digits,
            record=record,
            next_state=next_state.value if next_state else None,
            metadata={"language": normalise_language(session.language)},
        )

    async def _tts(self, prompt: str, session: IvrSession) -> str | None:
        if session.provider == "twilio" and not settings.IVR_TWILIO_USE_SARVAM_AUDIO:
            return None
        audio = await text_to_speech(prompt, LANGUAGE_AUDIO_CODES.get(session.language or "ta", "ta-IN"))
        if not audio:
            return None
        directory = os.path.join(settings.UPLOAD_DIR, "ivr")
        os.makedirs(directory, exist_ok=True)
        filename = f"{session.session_id}-{uuid.uuid4().hex}.wav"
        path = os.path.join(directory, filename)
        with open(path, "wb") as audio_file:
            audio_file.write(audio)
        return f"/uploads/ivr/{filename}"

    def _render(self, session: IvrSession, action: IvrAction) -> dict:
        rendered = self.provider(session.provider).render(action)
        rendered.update({"session": self._session_payload(session), "next_state": action.next_state, "metadata": action.metadata})
        return rendered

    def _resolve_session(self, db: Session, session_id: Optional[str], phone_number: Optional[str], provider: str) -> IvrSession:
        if session_id:
            session = self.sessions.get(db, session_id)
            if session:
                return session
        if phone_number:
            return self.sessions.get_or_create(db, phone_number, provider)
        raise ValueError("session_id or phone_number is required")

    def _find_or_create_farmer(self, db: Session, phone_number: str) -> User:
        farmer = db.query(User).filter(User.phone == phone_number).first()
        if farmer:
            return farmer
        farmer = User(
            email=f"ivr-{phone_number.strip('+')}@krishimitra.local",
            phone=phone_number,
            full_name=f"IVR Farmer {phone_number}",
            hashed_password="ivr-user",
            role="farmer",
            preferred_language=normalise_language(None),
            is_active=True,
        )
        db.add(farmer)
        db.commit()
        db.refresh(farmer)
        return farmer

    def _tracking_id(self) -> str:
        return f"KM-{random.randint(2026, 2026)}-{random.randint(10000, 99999)}"

    def _scheme_summary(self, result: dict) -> str:
        status = result.get("eligibility_status", "requires_verification").replace("_", " ")
        reason = result.get("eligibility_reason", "")
        return f"Scheme eligibility result. Status: {status}. {reason}"

    def _voice_safe(self, text: str) -> str:
        return text[: settings.IVR_RESPONSE_MAX_CHARS]

    def _prompt(self, session: IvrSession, key: str) -> str:
        return prompt_for(session.language, key)

    def _session_payload(self, session: IvrSession) -> dict:
        return {
            "session_id": session.session_id,
            "phone_number": session.phone_number,
            "provider": session.provider,
            "language": session.language,
            "current_state": session.current_state,
            "context": session.context or {},
            "status": session.status,
            "last_intent": session.last_intent,
            "last_transcript": session.last_transcript,
            "updated_at": session.updated_at,
        }

    def _log_event(self, db: Session, event_type: str, session: IvrSession, payload: dict) -> None:
        db.add(
            AnalyticsEvent(
                event_type=event_type,
                data={"session_id": session.session_id, "phone_number": session.phone_number, **payload},
            )
        )
        db.commit()
