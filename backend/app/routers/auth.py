from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, FarmerProfile, OfficerProfile
from app.schemas import UserRegister, UserLogin, Token, UserOut, UserUpdate, FarmerProfileCreate, FarmerProfileOut
from app.auth import hash_password, verify_password, create_access_token, get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(data: UserRegister, db: Session = Depends(get_db)):
    # Check existing
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=data.email,
        phone=data.phone,
        full_name=data.full_name,
        hashed_password=hash_password(data.password),
        role=data.role,
        preferred_language=data.preferred_language
    )
    db.add(user)
    db.flush()

    # Create corresponding profile
    if data.role == "farmer":
        db.add(FarmerProfile(user_id=user.id))
    elif data.role == "officer":
        db.add(OfficerProfile(user_id=user.id))

    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": str(user.id), "role": user.role})
    return Token(access_token=token, token_type="bearer", user=UserOut.model_validate(user))


@router.post("/login", response_model=Token)
async def login(data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    token = create_access_token({"sub": str(user.id), "role": user.role})
    return Token(access_token=token, token_type="bearer", user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.put("/me", response_model=UserOut)
async def update_me(
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(current_user, field, value)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.get("/me/profile", response_model=FarmerProfileOut)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    profile = db.query(FarmerProfile).filter(FarmerProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@router.put("/me/profile", response_model=FarmerProfileOut)
async def update_my_profile(
    data: FarmerProfileCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    profile = db.query(FarmerProfile).filter(FarmerProfile.user_id == current_user.id).first()
    if not profile:
        profile = FarmerProfile(user_id=current_user.id)
        db.add(profile)

    for field, value in data.model_dump(exclude_none=True).items():
        setattr(profile, field, value)

    db.commit()
    db.refresh(profile)
    return profile