import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import User, Conversation, FarmerProfile
from app.schemas import ChatRequest, ChatResponse
from app.auth import get_current_user
from app.services.ai.sarvam_ai_service import chat_with_ai, check_scheme_eligibility, classify_intent, get_weather_advisory

router = APIRouter(prefix="/chat", tags=["Chat"])

SUPPORTED_SCHEMES = [
    "PM-KISAN",
    "Krushak Yojana",
    "PM Fasal Bima Yojana",
    "Kisan Credit Card",
    "National Agriculture Market (eNAM)",
    "Pradhan Mantri Krishi Sinchayee Yojana",
    "Soil Health Card Scheme",
]


def detect_scheme_name(message: str) -> str:
    lowered = message.lower()
    aliases = {
        "PM-KISAN": ["pm-kisan", "pm kisan", "kisan samman", "samman nidhi"],
        "PM Fasal Bima Yojana": ["fasal bima", "pmfby", "crop insurance", "insurance"],
        "Kisan Credit Card": ["kisan credit", "kcc", "credit card", "crop loan"],
        "Soil Health Card Scheme": ["soil health", "soil card"],
        "National Agriculture Market (eNAM)": ["enam", "e-nam", "national agriculture market", "market"],
        "Pradhan Mantri Krishi Sinchayee Yojana": ["sinchayee", "pmksy", "irrigation"],
        "Krushak Yojana": ["krushak", "kalia"],
    }
    for scheme, words in aliases.items():
        if any(word in lowered for word in words):
            return scheme
    return "PM-KISAN"


def format_scheme_result(result: dict) -> str:
    status = result.get("eligibility_status")
    if status == "eligible":
        heading = "Eligible"
    elif status == "not_eligible":
        heading = "Not eligible"
    else:
        heading = "Needs verification"
    documents = ", ".join(result.get("required_documents") or [])
    alternatives = ", ".join(result.get("alternative_schemes") or [])
    parts = [
        f"{heading}: {result.get('scheme_name')}",
        result.get("eligibility_reason", ""),
        f"Benefits: {result.get('benefits', '-')}",
        f"Documents: {documents or '-'}",
        f"Next step: {result.get('application_steps', '-')}",
    ]
    if alternatives:
        parts.append(f"Alternatives: {alternatives}")
    return "\n\n".join(part for part in parts if part)


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    session_id = request.session_id or str(uuid.uuid4())

    # Load conversation history for this session
    history_records = (
        db.query(Conversation)
        .filter(
            Conversation.user_id == current_user.id,
            Conversation.session_id == session_id
        )
        .order_by(Conversation.created_at.asc())
        .limit(20)
        .all()
    )

    history = [{"role": r.role, "content": r.content} for r in history_records]

    # Classify intent
    intent = await classify_intent(request.message)

    # Build context from farmer profile
    context = {}
    farmer_profile = current_user.farmer_profile
    if farmer_profile:
        p = farmer_profile
        context = {
            "district": p.district,
            "primary_crop": p.primary_crop,
            "land_size": p.land_size_acres,
            "state": p.state,
            "farmer_category": p.farmer_category,
            "annual_income": p.annual_income,
        }

    # Route to specific handler or general AI
    if intent == "weather" and context.get("district"):
        response_text = await get_weather_advisory(
            crop_type=context.get("primary_crop", "crop"),
            district=context.get("district", "your district"),
            query=request.message,
            language=request.language
        )
    elif intent == "scheme":
        scheme_result = await check_scheme_eligibility(
            scheme_name=detect_scheme_name(request.message),
            state=context.get("state"),
            land_ownership="unknown",
            farmer_category=context.get("farmer_category"),
            annual_income=context.get("annual_income"),
            language=request.language,
        )
        response_text = format_scheme_result(scheme_result)
    else:
        response_text = await chat_with_ai(
            message=request.message,
            history=history,
            language=request.language,
            context=context if context else None
        )

    # Store conversation
    db.add(Conversation(
        user_id=current_user.id,
        session_id=session_id,
        role="user",
        content=request.message,
        intent=intent,
        language=request.language
    ))
    db.add(Conversation(
        user_id=current_user.id,
        session_id=session_id,
        role="assistant",
        content=response_text,
        intent=intent,
        language=request.language
    ))
    db.commit()

    return ChatResponse(
        response=response_text,
        intent=intent,
        session_id=session_id
    )


@router.get("/history")
async def get_chat_history(
    session_id: str = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Conversation).filter(Conversation.user_id == current_user.id)
    if session_id:
        query = query.filter(Conversation.session_id == session_id)
    messages = query.order_by(Conversation.created_at.desc()).limit(limit).all()
    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "intent": m.intent,
            "session_id": m.session_id,
            "created_at": m.created_at
        }
        for m in reversed(messages)
    ]


@router.get("/sessions")
async def get_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get list of chat sessions for current user."""
    from sqlalchemy import func, distinct
    sessions = (
        db.query(
            Conversation.session_id,
            func.min(Conversation.created_at).label("started_at"),
            func.count(Conversation.id).label("message_count")
        )
        .filter(Conversation.user_id == current_user.id)
        .group_by(Conversation.session_id)
        .order_by(func.min(Conversation.created_at).desc())
        .limit(20)
        .all()
    )
    return [{"session_id": s.session_id, "started_at": s.started_at, "message_count": s.message_count} for s in sessions]
