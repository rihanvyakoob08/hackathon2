from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from app.database import get_db
from app.models import User, Grievance, DiseaseReport, SchemeCheck, Scheme, AnalyticsEvent
from app.schemas import SchemeCreate, SchemeOut
from app.auth import get_admin, get_current_user, hash_password

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/users")
async def get_all_users(
    role: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_admin),
    db: Session = Depends(get_db)
):
    query = db.query(User)
    if role:
        query = query.filter(User.role == role)
    total = query.count()
    users = query.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "total": total,
        "data": [
            {
                "id": u.id,
                "email": u.email,
                "full_name": u.full_name,
                "role": u.role,
                "is_active": u.is_active,
                "preferred_language": u.preferred_language,
                "created_at": u.created_at
            }
            for u in users
        ]
    }


@router.put("/users/{user_id}/toggle-active")
async def toggle_user_active(
    user_id: int,
    current_user: User = Depends(get_admin),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = not user.is_active
    db.commit()
    return {"message": f"User {'activated' if user.is_active else 'deactivated'}", "is_active": user.is_active}


@router.put("/users/{user_id}/role")
async def update_user_role(
    user_id: int,
    role: str,
    current_user: User = Depends(get_admin),
    db: Session = Depends(get_db)
):
    if role not in ["farmer", "officer", "admin"]:
        raise HTTPException(status_code=400, detail="Invalid role")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.role = role
    db.commit()
    return {"message": "Role updated", "role": role}


@router.get("/analytics")
async def get_analytics(
    current_user: User = Depends(get_admin),
    db: Session = Depends(get_db)
):
    """Complete platform analytics."""
    return {
        "users": {
            "total": db.query(User).count(),
            "farmers": db.query(User).filter(User.role == "farmer").count(),
            "officers": db.query(User).filter(User.role == "officer").count(),
            "admins": db.query(User).filter(User.role == "admin").count(),
            "active": db.query(User).filter(User.is_active == True).count(),
        },
        "grievances": {
            "total": db.query(Grievance).count(),
            "submitted": db.query(Grievance).filter(Grievance.status == "submitted").count(),
            "assigned": db.query(Grievance).filter(Grievance.status == "assigned").count(),
            "in_progress": db.query(Grievance).filter(Grievance.status == "in_progress").count(),
            "resolved": db.query(Grievance).filter(Grievance.status == "resolved").count(),
        },
        "disease_reports": {
            "total": db.query(DiseaseReport).count(),
            "unique_diseases": db.query(DiseaseReport.disease_name).distinct().count(),
        },
        "schemes": {
            "total_checks": db.query(SchemeCheck).count(),
            "eligible": db.query(SchemeCheck).filter(SchemeCheck.is_eligible == True).count(),
            "not_eligible": db.query(SchemeCheck).filter(SchemeCheck.is_eligible == False).count(),
        }
    }


@router.get("/schemes", response_model=List[SchemeOut])
async def get_schemes(
    current_user: User = Depends(get_admin),
    db: Session = Depends(get_db)
):
    return db.query(Scheme).all()


@router.post("/schemes", response_model=SchemeOut)
async def create_scheme(
    data: SchemeCreate,
    current_user: User = Depends(get_admin),
    db: Session = Depends(get_db)
):
    if db.query(Scheme).filter(Scheme.name == data.name).first():
        raise HTTPException(status_code=400, detail="Scheme already exists")
    scheme = Scheme(**data.model_dump())
    db.add(scheme)
    db.commit()
    db.refresh(scheme)
    return scheme


@router.put("/schemes/{scheme_id}")
async def update_scheme(
    scheme_id: int,
    data: SchemeCreate,
    current_user: User = Depends(get_admin),
    db: Session = Depends(get_db)
):
    scheme = db.query(Scheme).filter(Scheme.id == scheme_id).first()
    if not scheme:
        raise HTTPException(status_code=404, detail="Scheme not found")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(scheme, field, value)
    db.commit()
    return scheme


@router.delete("/schemes/{scheme_id}")
async def delete_scheme(
    scheme_id: int,
    current_user: User = Depends(get_admin),
    db: Session = Depends(get_db)
):
    scheme = db.query(Scheme).filter(Scheme.id == scheme_id).first()
    if not scheme:
        raise HTTPException(status_code=404, detail="Scheme not found")
    scheme.is_active = False
    db.commit()
    return {"message": "Scheme deactivated"}