from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from app.database import get_db
from app.models import User, Grievance, DiseaseReport, SchemeCheck, AnalyticsEvent, IvrSession
from app.auth import get_officer

router = APIRouter(prefix="/officer", tags=["Officer"])


@router.get("/dashboard")
async def get_dashboard(
    current_user: User = Depends(get_officer),
    db: Session = Depends(get_db)
):
    """Officer analytics dashboard."""
    # Total counts
    total_farmers = db.query(User).filter(User.role == "farmer").count()
    total_grievances = db.query(Grievance).count()
    total_disease_reports = db.query(DiseaseReport).count()
    total_ivr_sessions = db.query(IvrSession).count()
    resolved_grievances = db.query(Grievance).filter(Grievance.status == "resolved").count()
    pending_grievances = db.query(Grievance).filter(Grievance.status != "resolved").count()

    resolution_rate = (resolved_grievances / total_grievances * 100) if total_grievances > 0 else 0

    # Top diseases
    top_diseases = (
        db.query(DiseaseReport.disease_name, func.count(DiseaseReport.id).label("count"))
        .filter(DiseaseReport.disease_name.isnot(None))
        .group_by(DiseaseReport.disease_name)
        .order_by(func.count(DiseaseReport.id).desc())
        .limit(5)
        .all()
    )

    # Grievance by category
    grievance_by_cat = (
        db.query(Grievance.category, func.count(Grievance.id).label("count"))
        .group_by(Grievance.category)
        .all()
    )

    # Scheme demand
    scheme_demand = (
        db.query(SchemeCheck.scheme_name, func.count(SchemeCheck.id).label("count"))
        .group_by(SchemeCheck.scheme_name)
        .order_by(func.count(SchemeCheck.id).desc())
        .limit(5)
        .all()
    )

    # District-wise grievances
    district_stats = (
        db.query(
            Grievance.district,
            func.count(Grievance.id).label("total"),
            func.sum(case((Grievance.status == "resolved", 1), else_=0)).label("resolved")
        )
        .filter(Grievance.district.isnot(None))
        .group_by(Grievance.district)
        .order_by(func.count(Grievance.id).desc())
        .limit(10)
        .all()
    )

    # Monthly grievance trends (last 6 months)
    from datetime import datetime, timedelta
    monthly_trends = []
    for i in range(5, -1, -1):
        month_start = datetime.utcnow().replace(day=1) - timedelta(days=30 * i)
        month_end = month_start + timedelta(days=31)
        count = db.query(Grievance).filter(
            Grievance.created_at >= month_start,
            Grievance.created_at < month_end
        ).count()
        monthly_trends.append({
            "month": month_start.strftime("%b %Y"),
            "count": count
        })

    return {
        "total_farmers": total_farmers,
        "total_grievances": total_grievances,
        "total_disease_reports": total_disease_reports,
        "total_ivr_sessions": total_ivr_sessions,
        "resolved_grievances": resolved_grievances,
        "pending_grievances": pending_grievances,
        "resolution_rate": round(resolution_rate, 1),
        "top_diseases": [{"name": d[0], "count": d[1]} for d in top_diseases],
        "grievance_by_category": [{"category": str(g[0].value) if hasattr(g[0], 'value') else str(g[0]), "count": g[1]} for g in grievance_by_cat],
        "scheme_demand": [{"scheme": s[0], "count": s[1]} for s in scheme_demand],
        "district_stats": [{"district": d[0], "total": d[1], "resolved": d[2] or 0} for d in district_stats],
        "monthly_trends": monthly_trends
    }


@router.get("/disease-reports")
async def get_disease_reports(
    district: str = None,
    disease: str = None,
    limit: int = 50,
    current_user: User = Depends(get_officer),
    db: Session = Depends(get_db)
):
    query = db.query(DiseaseReport)
    if district:
        query = query.filter(DiseaseReport.district == district)
    if disease:
        query = query.filter(DiseaseReport.disease_name.ilike(f"%{disease}%"))

    reports = query.order_by(DiseaseReport.created_at.desc()).limit(limit).all()
    return [
        {
            "id": r.id,
            "crop_type": r.crop_type,
            "disease_name": r.disease_name,
            "severity": r.severity,
            "district": r.district,
            "farmer": r.user.full_name if r.user else None,
            "created_at": r.created_at
        }
        for r in reports
    ]
