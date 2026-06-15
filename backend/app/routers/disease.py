import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional, List
from app.database import get_db
from app.models import User, DiseaseReport, FarmerProfile, AnalyticsEvent
from app.auth import get_current_user
from app.services.ai.sarvam_ai_service import analyze_crop_image
from app.config import settings

router = APIRouter(prefix="/disease", tags=["Disease Detection"])

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_SIZE = 10 * 1024 * 1024  # 10MB


@router.post("/analyze")
async def analyze_disease(
    image: UploadFile = File(...),
    crop_type: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Validate file
    ext = os.path.splitext(image.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Invalid file type. Upload JPG, PNG, or WebP.")

    content = await image.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="File too large. Max 10MB allowed.")

    # Save image
    filename = f"{uuid.uuid4()}{ext}"
    image_path = os.path.join(settings.UPLOAD_DIR, filename)
    with open(image_path, "wb") as f:
        f.write(content)

    # Analyze with AI
    analysis = await analyze_crop_image(image_path, crop_type)

    # Get district from farmer profile
    district = None
    if current_user.farmer_profile:
        district = current_user.farmer_profile.district

    # Store report
    report = DiseaseReport(
        user_id=current_user.id,
        crop_type=crop_type,
        image_path=image_path,
        disease_name=analysis.get("disease_name"),
        pest_name=analysis.get("pest_name"),
        severity=analysis.get("severity"),
        confidence_score=analysis.get("confidence_score"),
        description=analysis.get("description"),
        treatment=analysis.get("treatment"),
        district=district
    )
    db.add(report)

    # Log analytics
    db.add(AnalyticsEvent(
        event_type="disease_report",
        user_id=current_user.id,
        data={"disease": analysis.get("disease_name"), "crop": crop_type, "severity": analysis.get("severity")},
        district=district
    ))
    db.commit()
    db.refresh(report)

    return {
        "id": report.id,
        "crop_type": report.crop_type,
        "disease_name": report.disease_name,
        "pest_name": report.pest_name,
        "severity": report.severity,
        "confidence_score": report.confidence_score,
        "description": report.description,
        "treatment": report.treatment,
        "preventive_measures": analysis.get("preventive_measures"),
        "image_url": f"/uploads/{filename}",
        "created_at": report.created_at
    }


@router.get("/reports")
async def get_my_reports(
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    reports = (
        db.query(DiseaseReport)
        .filter(DiseaseReport.user_id == current_user.id)
        .order_by(DiseaseReport.created_at.desc())
        .limit(limit)
        .all()
    )
    return reports


@router.get("/reports/{report_id}")
async def get_report(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    report = db.query(DiseaseReport).filter(
        DiseaseReport.id == report_id,
        DiseaseReport.user_id == current_user.id
    ).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report
