"""
services/auth_service.py
------------------------
Business logic for authentication.
Services never import FastAPI — they are framework-agnostic.
This means they can be unit-tested without spinning up a server.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.schemas.user import TokenResponse, UserRegister


class AuthError(Exception):
    """Raised for authentication / registration business rule violations."""
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class AuthService:

    def register(self, db: Session, payload: UserRegister) -> User:
        """
        Create a new user account.
        Raises AuthError(409) if the email is already registered.
        """
        existing = db.query(User).filter(User.email == payload.email).first()
        if existing:
            raise AuthError("Email already registered", status_code=409)

        user = User(
            email=payload.email,
            full_name=payload.full_name,
            hashed_password=hash_password(payload.password),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    def login(self, db: Session, email: str, password: str) -> TokenResponse:
        """
        Validate credentials and return a token pair.
        We intentionally use the same generic error message for both
        "user not found" and "wrong password" to avoid user enumeration.
        """
        user = db.query(User).filter(User.email == email).first()
        if not user or not verify_password(password, user.hashed_password):
            raise AuthError("Invalid email or password", status_code=401)

        if not user.is_active:
            raise AuthError("Account is deactivated", status_code=403)

        return TokenResponse(
            access_token=create_access_token(subject=user.id),
            refresh_token=create_refresh_token(subject=user.id),
        )

    def refresh(self, db: Session, refresh_token: str) -> TokenResponse:
        """
        Issue a new access token given a valid refresh token.
        Refresh tokens are single-use by convention (rotate on each call).
        """
        from jose import JWTError

        try:
            payload = decode_token(refresh_token)
        except JWTError:
            raise AuthError("Invalid or expired refresh token", status_code=401)

        if payload.get("type") != "refresh":
            raise AuthError("Token is not a refresh token", status_code=401)

        user_id = payload.get("sub")
        user = db.query(User).filter(User.id == int(user_id)).first()
        if not user or not user.is_active:
            raise AuthError("User not found or deactivated", status_code=401)

        return TokenResponse(
            access_token=create_access_token(subject=user.id),
            refresh_token=create_refresh_token(subject=user.id),  # rotate
        )

    def upgrade_to_premium(self, db: Session, user: User) -> User:
        """
        Simulate a payment flow — mark the user as premium.
        In production this would be called by a Stripe/M-Pesa webhook.
        """
        from app.models.user import SubscriptionPlan
        user.subscription_plan = SubscriptionPlan.PREMIUM
        user.subscription_upgraded_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(user)
        return user
