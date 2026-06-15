from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserRegister(BaseModel):
    email: str
    password: str = Field(min_length=6)
    full_name: str
    phone: Optional[str] = None
    role: str = "farmer"
    preferred_language: str = "ta"


class UserLogin(BaseModel):
    email: str
    password: str


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    preferred_language: Optional[str] = None


class UserOut(ORMModel):
    id: int
    email: str
    phone: Optional[str] = None
    full_name: str
    role: str
    preferred_language: str
    is_active: bool
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class FarmerProfileCreate(BaseModel):
    state: Optional[str] = None
    district: Optional[str] = None
    village: Optional[str] = None
    land_size_acres: Optional[float] = None
    primary_crop: Optional[str] = None
    irrigation_type: Optional[str] = None
    farmer_category: Optional[str] = None
    annual_income: Optional[float] = None


class FarmerProfileOut(FarmerProfileCreate, ORMModel):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime


class ChatRequest(BaseModel):
    message: str
    language: str = "ta"
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    intent: str
    session_id: str


class GrievanceCreate(BaseModel):
    category: str
    title: str
    description: str
    district: Optional[str] = None


class GrievanceOut(ORMModel):
    id: int
    tracking_id: str
    farmer_id: int
    category: str
    title: str
    description: str
    status: str
    district: Optional[str] = None
    expected_resolution_days: int
    resolution_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class GrievanceStatusUpdate(BaseModel):
    status: str
    notes: Optional[str] = None
    assigned_officer_id: Optional[int] = None


class SchemeCreate(BaseModel):
    name: str
    description: Optional[str] = None
    eligibility_criteria: Optional[Dict[str, Any]] = None
    benefits: Optional[str] = None
    required_documents: Optional[List[str]] = None
    application_process: Optional[str] = None
    is_active: bool = True


class SchemeOut(SchemeCreate, ORMModel):
    id: int
    created_at: datetime
    updated_at: datetime


class SchemeCheckRequest(BaseModel):
    scheme_name: str
    state: Optional[str] = None
    land_ownership: Optional[str] = None
    farmer_category: Optional[str] = None
    annual_income: Optional[float] = None


class SchemeCheckOut(ORMModel):
    id: int
    user_id: int
    scheme_name: str
    state: Optional[str] = None
    land_ownership: Optional[str] = None
    farmer_category: Optional[str] = None
    annual_income: Optional[float] = None
    is_eligible: Optional[bool] = None
    eligibility_reason: Optional[str] = None
    alternative_schemes: Optional[List[str]] = None
    created_at: datetime


class VoiceTranscribeOut(BaseModel):
    transcript: str
    language: str
    confidence: Optional[float] = None


class VoiceSpeakRequest(BaseModel):
    text: str
    language: str = "ta-IN"
