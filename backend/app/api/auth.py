from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    hash_password,
    verify_password,
)
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    RegisterRequest,
    UserOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new researcher account",
)
def register(
    req: RegisterRequest,
    db: Session = Depends(get_db),
) -> AuthResponse:
    clean_email = str(req.email).strip().lower()
    clean_name = req.full_name.strip()

    # Check if account with email already exists (case-insensitive)
    existing_user = db.execute(
        select(User).where(func.lower(User.email) == clean_email)
    ).scalar_one_or_none()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    # Hash password using Argon2
    hashed_pw = hash_password(req.password)

    new_user = User(
        full_name=clean_name,
        email=clean_email,
        password_hash=hashed_pw,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Issue access token
    access_token = create_access_token(subject=new_user.user_id)

    return AuthResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserOut.model_validate(new_user),
    )


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Authenticate with email and password",
)
def login(
    req: LoginRequest,
    db: Session = Depends(get_db),
) -> AuthResponse:
    clean_email = str(req.email).strip().lower()

    user = db.execute(
        select(User).where(func.lower(User.email) == clean_email)
    ).scalar_one_or_none()

    if not user:
        # Constant-time-ish mitigation against timing enumeration attacks
        verify_password(req.password, DUMMY_PASSWORD_HASH)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    access_token = create_access_token(subject=user.user_id)

    return AuthResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserOut.model_validate(user),
    )


@router.get(
    "/me",
    response_model=UserOut,
    summary="Get current authenticated user profile",
)
def get_me(
    current_user: User = Depends(get_current_user),
) -> UserOut:
    return UserOut.model_validate(current_user)
