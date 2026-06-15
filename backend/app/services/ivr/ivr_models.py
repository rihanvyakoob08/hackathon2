from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class IvrState(str, Enum):
    LANGUAGE_SELECTION = "LANGUAGE_SELECTION"
    MAIN_MENU = "MAIN_MENU"
    RECORD_QUERY = "RECORD_QUERY"
    SCHEME_STATE = "SCHEME_STATE"
    SCHEME_LAND = "SCHEME_LAND"
    SCHEME_INCOME = "SCHEME_INCOME"
    GRIEVANCE_RECORD = "GRIEVANCE_RECORD"
    TRACK_GRIEVANCE = "TRACK_GRIEVANCE"
    COMPLETE = "COMPLETE"


class IvrIntent(str, Enum):
    DISEASE_QUERY = "DISEASE_QUERY"
    WEATHER_QUERY = "WEATHER_QUERY"
    SCHEME_QUERY = "SCHEME_QUERY"
    GRIEVANCE_QUERY = "GRIEVANCE_QUERY"
    CROP_RECOMMENDATION = "CROP_RECOMMENDATION"
    GENERAL_QUERY = "GENERAL_QUERY"


class IvrAction(BaseModel):
    type: str
    prompt: str
    audio_url: Optional[str] = None
    collect_digits: bool = False
    max_digits: int = 1
    record: bool = False
    next_state: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class IvrCallbackPayload(BaseModel):
    session_id: Optional[str] = None
    phone_number: Optional[str] = None
    provider: str = "mock"
    digits: Optional[str] = None
    text: Optional[str] = None
    tracking_id: Optional[str] = None
