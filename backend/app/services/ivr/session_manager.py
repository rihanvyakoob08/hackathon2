import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.models import IvrSession
from app.services.ivr.ivr_models import IvrState


class IvrSessionManager:
    def get(self, db: Session, session_id: str) -> Optional[IvrSession]:
        return db.query(IvrSession).filter(IvrSession.session_id == session_id).first()

    def get_active_by_phone(self, db: Session, phone_number: str) -> Optional[IvrSession]:
        return (
            db.query(IvrSession)
            .filter(IvrSession.phone_number == phone_number, IvrSession.status == "active")
            .order_by(IvrSession.updated_at.desc())
            .first()
        )

    def create(self, db: Session, phone_number: str, provider: str = "mock") -> IvrSession:
        session = IvrSession(
            session_id=str(uuid.uuid4()),
            phone_number=phone_number,
            provider=provider,
            current_state=IvrState.LANGUAGE_SELECTION.value,
            context={},
            status="active",
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return session

    def get_or_create(self, db: Session, phone_number: str, provider: str = "mock") -> IvrSession:
        existing = self.get_active_by_phone(db, phone_number)
        if existing:
            if existing.provider != provider:
                existing.provider = provider
                db.commit()
                db.refresh(existing)
            return existing
        return self.create(db, phone_number, provider)

    def update(
        self,
        db: Session,
        session: IvrSession,
        *,
        state: IvrState | str | None = None,
        language: str | None = None,
        context: dict | None = None,
        status: str | None = None,
        intent: str | None = None,
        transcript: str | None = None,
    ) -> IvrSession:
        if state:
            session.current_state = state.value if isinstance(state, IvrState) else state
        if language:
            session.language = language
        if context is not None:
            session.context = dict(context)
        if status:
            session.status = status
        if intent:
            session.last_intent = intent
        if transcript:
            session.last_transcript = transcript
        db.commit()
        db.refresh(session)
        return session
