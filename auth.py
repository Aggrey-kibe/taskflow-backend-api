"""
routers/auth.py
---------------
Authentication endpoints: register, login, token refresh, upgrade plan.
Routers are thin — they delegate all logic to the service layer.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import (
    TokenRefreshRequest,
    TokenResponse,
    UpgradeResponse,
    UserLogin,
    UserRegister,
    UserResponse,
)
from app.services.auth_service import AuthError, AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])
_service = AuthService()


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
def register(payload: UserRegister, db: Session = Depends(get_db)):
    try:
        user = _service.register(db, payload)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    return user


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login and receive JWT tokens",
)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    try:
        tokens = _service.login(db, payload.email, payload.password)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    return tokens


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Exchange a refresh token for a new token pair",
)
def refresh(payload: TokenRefreshRequest, db: Session = Depends(get_db)):
    try:
        tokens = _service.refresh(db, payload.refresh_token)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    return tokens


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get the currently authenticated user's profile",
)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post(
    "/upgrade",
    response_model=UpgradeResponse,
    summary="Simulate upgrading to Premium (no real payment)",
)
def upgrade_plan(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    In a real system this endpoint would be triggered by a payment webhook
    (Stripe, M-Pesa, etc.) after the user completes a checkout session.
    Here it immediately upgrades the authenticated user for demonstration.
    """
    updated = _service.upgrade_to_premium(db, current_user)
    return UpgradeResponse(
        message="Upgrade successful! You are now a Premium subscriber.",
        subscription_plan=updated.subscription_plan,
        upgraded_at=updated.subscription_upgraded_at,
    )
