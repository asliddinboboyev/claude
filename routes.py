import uuid
from datetime import datetime
from fastapi import HTTPException

from models import ChatRequest, ChatResponse
from risk_engine import analyze_risk
from ai_service import generate_reply, SESSIONS, SESSION_META


def health():
    from .config import OPENAI_MODEL
    from .ai_service import TABIB_SYSTEM_PROMPT
    return {
        "status": "ok",
        "service": "Tabib AI",
        "model": OPENAI_MODEL,
        "prompt_loaded_chars": len(TABIB_SYSTEM_PROMPT),
        "timestamp": datetime.utcnow().isoformat(),
    }


def chat(payload: ChatRequest) -> ChatResponse:
    message = payload.message.strip()

    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    session_id = payload.session_id or str(uuid.uuid4())

    risk_data = analyze_risk(message)
    reply = generate_reply(session_id, message, risk_data)

    SESSION_META.setdefault(session_id, {})
    SESSION_META[session_id].update({
        "patient_id": payload.patient_id,
        "last_risk_level": risk_data["risk_level"],
        "last_risk_flags": risk_data["risk_flags"],
        "last_seen": datetime.utcnow().isoformat(),
    })

    return ChatResponse(
        session_id=session_id,
        reply=reply,
        risk_level=risk_data["risk_level"],
        risk_flags=risk_data["risk_flags"],
        detected_language=risk_data["detected_language"],
        timestamp=datetime.utcnow().isoformat(),
    )


def get_session(session_id: str):
    return {
        "session_id": session_id,
        "meta": SESSION_META.get(session_id, {}),
        "messages": SESSIONS.get(session_id, []),
    }


def delete_session(session_id: str):
    SESSIONS.pop(session_id, None)
    SESSION_META.pop(session_id, None)
    return {"message": "Session deleted"}


# New endpoint: status for app integration
def status():
    return {
        "app_connected": True,
        "version": "1.0.0",
        "active_sessions": len(SESSIONS),
        "timestamp": datetime.utcnow().isoformat(),
    }