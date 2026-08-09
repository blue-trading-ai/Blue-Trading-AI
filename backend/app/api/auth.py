from __future__ import annotations

import logging
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    Request,
    HTTPException,
    status,
)
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import (
    get_current_auth_session,
    get_current_user,
    get_db,
)
from app.core.security import (
    create_access_token,
    create_refresh_token_jwt,
    decode_refresh_token,
    ensure_password_changed,
    get_access_token_expiry,
    hash_password,
    verify_and_update_password,
)
from app.models.account_action_token import (
    TOKEN_PURPOSE_EMAIL_VERIFICATION,
    TOKEN_PURPOSE_PASSWORD_RESET,
    TOKEN_REVOKE_PASSWORD_CHANGED,
)
from app.models.auth_session import (
    AuthSession,
    SESSION_REVOKE_ALL_DEVICES,
    SESSION_REVOKE_LOGOUT,
    SESSION_REVOKE_PASSWORD_CHANGED,
)
from app.models.role_permission import (
    ROLE_OWNER,
)
from app.models.refresh_token import (
    REFRESH_REVOKE_ALL_DEVICES,
    REFRESH_REVOKE_LOGOUT,
    REFRESH_REVOKE_PASSWORD_CHANGED,
    RefreshToken,
)
from app.models.user import (
    ACCOUNT_STATUS_APPROVED,
    ACCOUNT_STATUS_PENDING,
    ACCOUNT_STATUS_REJECTED,
    ACCOUNT_STATUS_SUSPENDED,
    DEFAULT_LOGIN_LOCKOUT_MINUTES,
    DEFAULT_MAX_FAILED_LOGIN_ATTEMPTS,
    User,
)
from app.schemas.user import UserCreate
from app.models.security_audit_log import (
    AUDIT_EVENT_ACCOUNT_LOCKED,
    AUDIT_EVENT_LOGIN_FAILURE,
    AUDIT_EVENT_LOGIN_SUCCESS,
    AUDIT_EVENT_PASSWORD_CHANGED,
    AUDIT_EVENT_REGISTRATION,
    AUDIT_OUTCOME_BLOCKED,
    AUDIT_OUTCOME_FAILURE,
    AUDIT_OUTCOME_SUCCESS,
)
from app.services.email_service import (
    EmailConfigurationError,
    EmailDeliveryError,
    email_delivery_configured,
    send_password_reset_email,
    send_verification_email,
)
from app.services.account_action_token_service import (
    ExpiredAccountActionTokenError,
    InvalidAccountActionTokenError,
    RevokedAccountActionTokenError,
    UsedAccountActionTokenError,
    account_action_token_public_payload,
    consume_account_action_token,
    create_account_action_token,
    revoke_all_user_tokens,
    validate_account_action_token,
)
from app.services.auth_session_service import (
    create_auth_session,
    generate_jwt_id,
    hash_jwt_id,
    list_user_sessions,
    revoke_all_user_sessions,
    revoke_auth_session,
    session_public_payload,
)
from app.services.role_permission_service import (
    ensure_owner_role,
    get_access_snapshot,
    seed_default_roles_and_permissions,
)
from app.services.refresh_token_service import (
    ExpiredRefreshTokenError,
    InvalidRefreshTokenError,
    RefreshTokenReuseError,
    RevokedRefreshTokenError,
    create_refresh_token,
    generate_family_id,
    generate_token_id,
    get_refresh_token_expiry,
    revoke_all_user_refresh_tokens,
    revoke_refresh_family,
    revoke_session_refresh_tokens,
    validate_refresh_token,
)
from app.services.security_audit_service import audit_event


LOGGER = logging.getLogger(__name__)

PROJECT_NAME = "Blue-Trading-AI"
AUTH_VERSION = 42
ACCESS_TOKEN_TYPE = "bearer"

PLANS_ENABLED = settings.PLANS_ENABLED
SUBSCRIPTIONS_ENABLED = settings.SUBSCRIPTIONS_ENABLED
PAYMENTS_ENABLED = settings.PAYMENTS_ENABLED
OWNER_APPROVAL_REQUIRED = settings.OWNER_APPROVAL_REQUIRED

MAX_FAILED_LOGIN_ATTEMPTS = DEFAULT_MAX_FAILED_LOGIN_ATTEMPTS
LOGIN_LOCKOUT_MINUTES = DEFAULT_LOGIN_LOCKOUT_MINUTES

def _email_delivery_connected() -> bool:
    """
    Resolve email-delivery readiness at request time.

    This avoids a stale module-import snapshot after provider or
    environment-variable changes.
    """
    return email_delivery_configured()


EXPOSE_DEVELOPMENT_TOKENS = bool(
    settings.EXPOSE_DEVELOPMENT_TOKENS
)

DUMMY_LOGIN_PASSWORD_HASH = hash_password(
    "BlueTradingAI-Dummy-Login-Password-2026!"
)



class RefreshRequest(BaseModel):
    refresh_token: str


class EmailVerificationRequest(BaseModel):
    token: str = Field(
        ...,
        min_length=20,
        max_length=500,
    )


class ForgotPasswordRequest(BaseModel):
    email: str = Field(
        ...,
        min_length=3,
        max_length=255,
    )


class ResetPasswordRequest(BaseModel):
    token: str = Field(
        ...,
        min_length=20,
        max_length=500,
    )

    new_password: str = Field(
        ...,
        min_length=10,
        max_length=128,
    )


router = APIRouter(
    prefix="/auth",
    tags=["Authentication - Version 41"],
)


class PasswordChangeRequest(BaseModel):
    """
    Request body for changing the current user's password.
    """

    current_password: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )

    new_password: str = Field(
        ...,
        min_length=10,
        max_length=128,
    )



def _send_verification_email_safely(
    *,
    user: User,
    raw_token: str,
) -> tuple[bool, str | None]:
    """
    Send a verification email without exposing SMTP details.
    """

    if not _email_delivery_connected():
        LOGGER.warning(
            "Verification email skipped because email delivery is not configured."
        )
        return False, "Email delivery is not configured."

    try:
        send_verification_email(
            to_email=user.email,
            username=getattr(user, "username", None) or "Trader",
            raw_token=raw_token,
        )
        return True, None
    except EmailConfigurationError:
        LOGGER.exception(
            "Verification email configuration failed."
        )
        return False, "Email delivery failed."
    except EmailDeliveryError:
        LOGGER.exception(
            "Verification email delivery failed."
        )
        return False, "Email delivery failed."


def _send_password_reset_email_safely(
    *,
    user: User,
    raw_token: str,
) -> tuple[bool, str | None]:
    """
    Send a password-reset email without exposing SMTP details.
    """

    if not _email_delivery_connected():
        LOGGER.warning(
            "Password-reset email skipped because email delivery is not configured."
        )
        return False, "Email delivery is not configured."

    try:
        send_password_reset_email(
            to_email=user.email,
            username=getattr(user, "username", None) or "Trader",
            raw_token=raw_token,
        )
        return True, None
    except EmailConfigurationError:
        LOGGER.exception(
            "Password-reset email configuration failed."
        )
        return False, "Email delivery failed."
    except EmailDeliveryError:
        LOGGER.exception(
            "Password-reset email delivery failed."
        )
        return False, "Email delivery failed."


def _normalise_email(email: str) -> str:
    return str(email or "").strip().lower()


def _normalise_username(username: str) -> str:
    return str(username or "").strip()


def _is_owner_email(email: str) -> bool:
    return (
        _normalise_email(email)
        == settings.owner_email_normalised
    )


def _public_user(user: User) -> dict[str, Any]:
    return {
        "id": getattr(user, "id", None),
        "username": user.username,
        "email": user.email,
        "is_email_verified": bool(
            getattr(user, "is_email_verified", False)
        ),
        "email_verified_at": getattr(
            user,
            "email_verified_at",
            None,
        ),
        "email_verification_requested_at": getattr(
            user,
            "email_verification_requested_at",
            None,
        ),
        "roles": [],
        "permissions": [],
        "is_active": bool(user.is_active),
        "account_status": user.account_status,
        "is_approved": bool(user.is_approved),
        "can_access_platform": bool(
            user.can_access_platform
        ),
        "is_owner": _is_owner_email(user.email),
        "password_version": int(
            user.password_version or 1
        ),
        "password_changed_at": user.password_changed_at,
        "failed_login_attempts": int(
            user.failed_login_attempts or 0
        ),
        "last_failed_login_at": user.last_failed_login_at,
        "locked_until": user.locked_until,
        "is_login_locked": bool(user.is_login_locked),
        "lockout_seconds_remaining": int(
            user.lockout_seconds_remaining
        ),
        "last_login_at": user.last_login_at,
        "approved_at": user.approved_at,
        "created_at": user.created_at,
    }


def _account_access_error(
    user: User,
) -> HTTPException:
    account_status = str(
        user.account_status or ACCOUNT_STATUS_PENDING
    ).strip().upper()

    if account_status == ACCOUNT_STATUS_PENDING:
        detail = (
            "Your account is pending owner approval. "
            "You cannot access Blue-Trading-AI yet."
        )
    elif account_status == ACCOUNT_STATUS_REJECTED:
        detail = (
            "Your Blue-Trading-AI access request was rejected."
        )
    elif account_status == ACCOUNT_STATUS_SUSPENDED:
        detail = (
            "Your Blue-Trading-AI account is suspended."
        )
    else:
        detail = (
            "Your account is not approved for platform access."
        )

    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "message": detail,
            "account_status": account_status,
            "owner_approval_required": True,
            "can_access_platform": False,
        },
    )


@router.get("/")
def auth_home() -> dict[str, Any]:
    return {
        "status": "success",
        "message": (
            "Blue-Trading-AI Account Security "
            "Authentication System is working"
        ),
        "project": PROJECT_NAME,
        "auth_version": AUTH_VERSION,
        "password_hashing_enabled": True,
        "password_change_enabled": True,
        "password_versioning_enabled": True,
        "old_token_revocation_enabled": True,
        "failed_login_tracking_enabled": True,
        "temporary_login_lockout_enabled": True,
        "security_audit_logging_enabled": True,
        "registration_audit_enabled": True,
        "login_success_audit_enabled": True,
        "login_failure_audit_enabled": True,
        "account_lockout_audit_enabled": True,
        "password_change_audit_enabled": True,
        "maximum_failed_login_attempts": (
            MAX_FAILED_LOGIN_ATTEMPTS
        ),
        "login_lockout_minutes": LOGIN_LOCKOUT_MINUTES,
        "jwt_authentication_enabled": True,
        "database_session_validation_enabled": True,
        "individual_session_revocation_enabled": True,
        "logout_enabled": True,
        "revoke_all_devices_enabled": True,
        "session_activity_tracking_enabled": True,
        "raw_tokens_stored": False,
        "refresh_tokens_enabled": True,
        "refresh_token_rotation_enabled": True,
        "refresh_token_reuse_detection_enabled": True,
        "refresh_token_family_revocation_enabled": True,
        "email_verification_enabled": True,
        "password_reset_enabled": True,
        "one_time_token_hashing_enabled": True,
        "single_use_account_tokens_enabled": True,
        "email_delivery_connected": _email_delivery_connected(),
        "smtp_email_delivery_enabled": _email_delivery_connected(),
        "verification_email_delivery_enabled": True,
        "password_reset_email_delivery_enabled": True,
        "roles_and_permissions_enabled": True,
        "owner_role_bootstrap_enabled": True,
        "default_user_role_on_approval": True,
        "development_tokens_exposed": (
            EXPOSE_DEVELOPMENT_TOKENS
        ),
        "protected_routes_enabled": True,
        "owner_approval_required": OWNER_APPROVAL_REQUIRED,
        "new_account_default_status": ACCOUNT_STATUS_PENDING,
        "plans_enabled": PLANS_ENABLED,
        "subscriptions_enabled": SUBSCRIPTIONS_ENABLED,
        "payments_enabled": PAYMENTS_ENABLED,
    }


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
)
def register_user(
    user: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Register a new account.

    Normal users start as PENDING.
    The exact OWNER_EMAIL account is approved automatically.
    """

    email = _normalise_email(user.email)
    username = _normalise_username(user.username)

    existing_user = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    existing_username = (
        db.query(User)
        .filter(User.username == username)
        .first()
    )

    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This username is already in use.",
        )

    new_user = User(
        username=username,
        email=email,
        hashed_password=hash_password(user.password),
        password_version=1,
        is_active=True,
        account_status=ACCOUNT_STATUS_PENDING,
    )

    if _is_owner_email(email):
        new_user.approve(
            approved_by="OWNER_EMAIL_BOOTSTRAP"
        )

    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
    except IntegrityError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "The account could not be created because "
                "the username or email already exists."
            ),
        ) from exc

    new_user.register_email_verification_request()
    db.commit()
    db.refresh(new_user)

    seed_default_roles_and_permissions(
        db,
        commit=True,
    )

    if _is_owner_email(email):
        ensure_owner_role(
            db,
            user_id=int(new_user.id),
            commit=True,
        )

    verification_record, verification_token = (
        create_account_action_token(
            db,
            user_id=int(new_user.id),
            email=new_user.email,
            purpose=TOKEN_PURPOSE_EMAIL_VERIFICATION,
            request=request,
            commit=True,
        )
    )

    verification_email_sent, verification_email_error = (
        _send_verification_email_safely(
            user=new_user,
            raw_token=verification_token,
        )
    )

    if _is_owner_email(email):
        message = (
            "Owner account registered and approved successfully."
        )
        access_granted = True
    else:
        message = (
            "Registration completed. Your account is pending "
            "owner approval."
        )
        access_granted = False

    audit_event(
        db=db,
        event_type=AUDIT_EVENT_REGISTRATION,
        outcome=AUDIT_OUTCOME_SUCCESS,
        request=request,
        actor_user=new_user,
        target_user=new_user,
        message=message,
        details={
            "account_status": new_user.account_status,
            "is_owner": _is_owner_email(new_user.email),
            "access_granted": access_granted,
            "email_verification_required": True,
            "verification_token_id": (
                verification_record.token_id
            ),
            "verification_email_sent": (
                verification_email_sent
            ),
            "verification_email_error": (
                verification_email_error
            ),
            "assigned_roles": (
                list(
                    get_access_snapshot(
                        db,
                        user_id=int(new_user.id),
                    ).roles
                )
            ),
        },
    )

    return {
        "status": "success",
        "message": message,
        "access_granted": access_granted,
        "owner_approval_required": True,
        "email_verification_required": True,
        "email_delivery_connected": _email_delivery_connected(),
        "verification_email_sent": verification_email_sent,
        "verification_email_error": verification_email_error,
        "verification_expires_at": (
            verification_record.expires_at
        ),
        "development_verification_token": (
            verification_token
            if EXPOSE_DEVELOPMENT_TOKENS
            else None
        ),
        "access": get_access_snapshot(
            db,
            user_id=int(new_user.id),
        ).to_dict(),
        "user": _public_user(new_user),
    }



@router.post("/request-email-verification")
def request_email_verification(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Issue a new single-use email-verification token.
    """

    database_user = (
        db.query(User)
        .filter(User.id == int(current_user.id))
        .first()
    )

    if database_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User account no longer exists.",
        )

    if bool(database_user.is_email_verified):
        return {
            "status": "success",
            "message": "Email address is already verified.",
            "email_verified": True,
            "user": _public_user(database_user),
        }

    database_user.register_email_verification_request()
    db.commit()
    db.refresh(database_user)

    token_record, raw_token = create_account_action_token(
        db,
        user_id=int(database_user.id),
        email=database_user.email,
        purpose=TOKEN_PURPOSE_EMAIL_VERIFICATION,
        request=request,
        commit=True,
    )

    verification_email_sent, verification_email_error = (
        _send_verification_email_safely(
            user=database_user,
            raw_token=raw_token,
        )
    )

    audit_event(
        db=db,
        event_type="EMAIL_VERIFICATION_REQUESTED",
        outcome=AUDIT_OUTCOME_SUCCESS,
        request=request,
        actor_user=database_user,
        target_user=database_user,
        message="Email verification requested.",
        details={
            "token_id": token_record.token_id,
            "expires_at": token_record.expires_at,
            "email_delivery_connected": (
                _email_delivery_connected()
            ),
            "verification_email_sent": (
                verification_email_sent
            ),
            "verification_email_error": (
                verification_email_error
            ),
        },
    )

    return {
        "status": "success",
        "message": (
            "Verification email sent."
            if verification_email_sent
            else "Email verification token created."
        ),
        "email_delivery_connected": _email_delivery_connected(),
        "verification_email_sent": verification_email_sent,
        "verification_email_error": verification_email_error,
        "expires_at": token_record.expires_at,
        "development_verification_token": (
            raw_token
            if EXPOSE_DEVELOPMENT_TOKENS
            else None
        ),
    }


@router.post("/verify-email")
def verify_email(
    payload: EmailVerificationRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Verify an email address using one single-use token.
    """

    try:
        token_record = validate_account_action_token(
            db,
            raw_token=payload.token,
            purpose=TOKEN_PURPOSE_EMAIL_VERIFICATION,
        )
    except ExpiredAccountActionTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Email-verification token has expired.",
        ) from exc
    except UsedAccountActionTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email-verification token was already used.",
        ) from exc
    except (
        InvalidAccountActionTokenError,
        RevokedAccountActionTokenError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email-verification token is invalid.",
        ) from exc

    user = (
        db.query(User)
        .filter(User.id == int(token_record.user_id))
        .first()
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User account no longer exists.",
        )

    if _normalise_email(user.email) != token_record.email:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Account email no longer matches this token.",
        )

    user.mark_email_verified()

    consume_account_action_token(
        db,
        raw_token=payload.token,
        purpose=TOKEN_PURPOSE_EMAIL_VERIFICATION,
        user_id=int(user.id),
        email=user.email,
        commit=False,
    )

    try:
        db.commit()
        db.refresh(user)
    except Exception:
        db.rollback()
        raise

    audit_event(
        db=db,
        event_type="EMAIL_VERIFIED",
        outcome=AUDIT_OUTCOME_SUCCESS,
        request=request,
        actor_user=user,
        target_user=user,
        message="Email address verified successfully.",
        details={
            "token_id": token_record.token_id,
        },
    )

    return {
        "status": "success",
        "message": "Email address verified successfully.",
        "email_verified": True,
        "user": _public_user(user),
    }


@router.post("/forgot-password")
def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Create a password-reset token without revealing whether an
    account exists.
    """

    email = _normalise_email(payload.email)

    user = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    raw_token: str | None = None
    expires_at = None
    password_reset_email_sent = False
    password_reset_email_error: str | None = None

    if user is not None and bool(user.is_active):
        token_record, raw_token = create_account_action_token(
            db,
            user_id=int(user.id),
            email=user.email,
            purpose=TOKEN_PURPOSE_PASSWORD_RESET,
            request=request,
            commit=True,
        )
        expires_at = token_record.expires_at

        password_reset_email_sent, password_reset_email_error = (
            _send_password_reset_email_safely(
                user=user,
                raw_token=raw_token,
            )
        )

        audit_event(
            db=db,
            event_type="PASSWORD_RESET_REQUESTED",
            outcome=AUDIT_OUTCOME_SUCCESS,
            request=request,
            actor_user=user,
            target_user=user,
            message="Password reset requested.",
            details={
                "token_id": token_record.token_id,
                "expires_at": token_record.expires_at,
                "email_delivery_connected": (
                    _email_delivery_connected()
                ),
                "password_reset_email_sent": (
                    password_reset_email_sent
                ),
                "password_reset_email_error": (
                    password_reset_email_error
                ),
            },
        )

    response = {
        "status": "success",
        "message": (
            "If an active account exists for that email, "
            "password-reset instructions have been created."
        ),
    }

    if EXPOSE_DEVELOPMENT_TOKENS and raw_token:
        response.update(
            {
                "development_password_reset_token": (
                    raw_token
                ),
                "password_reset_expires_at": expires_at,
                "password_reset_email_sent": (
                    password_reset_email_sent
                ),
                "password_reset_email_error": (
                    password_reset_email_error
                ),
            }
        )

    return response


@router.post("/reset-password")
def reset_password(
    payload: ResetPasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Reset a password using one valid single-use token.
    """

    try:
        token_record = validate_account_action_token(
            db,
            raw_token=payload.token,
            purpose=TOKEN_PURPOSE_PASSWORD_RESET,
        )
    except ExpiredAccountActionTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Password-reset token has expired.",
        ) from exc
    except UsedAccountActionTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Password-reset token was already used.",
        ) from exc
    except (
        InvalidAccountActionTokenError,
        RevokedAccountActionTokenError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Password-reset token is invalid.",
        ) from exc

    user = (
        db.query(User)
        .filter(User.id == int(token_record.user_id))
        .first()
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User account no longer exists.",
        )

    if _normalise_email(user.email) != token_record.email:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Account email no longer matches this token.",
        )

    try:
        new_password_hash = hash_password(
            payload.new_password
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    user.set_password_hash(new_password_hash)

    consume_account_action_token(
        db,
        raw_token=payload.token,
        purpose=TOKEN_PURPOSE_PASSWORD_RESET,
        user_id=int(user.id),
        email=user.email,
        commit=False,
    )

    try:
        db.commit()
        db.refresh(user)
    except Exception:
        db.rollback()
        raise

    revoked_sessions = revoke_all_user_sessions(
        db,
        user_id=int(user.id),
        reason=SESSION_REVOKE_PASSWORD_CHANGED,
        commit=True,
    )

    revoked_refresh_tokens = revoke_all_user_refresh_tokens(
        db,
        user_id=int(user.id),
        reason=REFRESH_REVOKE_PASSWORD_CHANGED,
        commit=True,
    )

    revoked_action_tokens = revoke_all_user_tokens(
        db,
        user_id=int(user.id),
        reason=TOKEN_REVOKE_PASSWORD_CHANGED,
        commit=True,
    )

    audit_event(
        db=db,
        event_type="PASSWORD_RESET_COMPLETED",
        outcome=AUDIT_OUTCOME_SUCCESS,
        request=request,
        actor_user=user,
        target_user=user,
        message="Password reset completed successfully.",
        details={
            "token_id": token_record.token_id,
            "password_version": user.password_version,
            "revoked_sessions": revoked_sessions,
            "revoked_refresh_tokens": (
                revoked_refresh_tokens
            ),
            "revoked_action_tokens": (
                revoked_action_tokens
            ),
        },
    )

    return {
        "status": "success",
        "message": (
            "Password reset successfully. "
            "All existing sessions were revoked."
        ),
        "relogin_required": True,
        "password_version": user.password_version,
        "password_changed_at": user.password_changed_at,
        "revoked_sessions": revoked_sessions,
        "revoked_refresh_tokens": revoked_refresh_tokens,
        "revoked_action_tokens": revoked_action_tokens,
    }


@router.post("/login")
def login_user(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    email = _normalise_email(form_data.username)

    existing_user = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect email or password.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not existing_user:
        verify_and_update_password(
            form_data.password,
            DUMMY_LOGIN_PASSWORD_HASH,
        )

        audit_event(
            db=db,
            event_type=AUDIT_EVENT_LOGIN_FAILURE,
            outcome=AUDIT_OUTCOME_FAILURE,
            request=request,
            actor_email=email,
            target_email=email,
            message="Login failed.",
            details={
                "reason": "UNKNOWN_EMAIL_OR_INVALID_PASSWORD",
            },
        )
        raise credentials_error

    if existing_user.is_login_locked:
        audit_event(
            db=db,
            event_type=AUDIT_EVENT_ACCOUNT_LOCKED,
            outcome=AUDIT_OUTCOME_BLOCKED,
            request=request,
            actor_user=existing_user,
            target_user=existing_user,
            message="Login blocked because account is locked.",
            details={
                "locked_until": (
                    existing_user.locked_until.isoformat()
                    if existing_user.locked_until
                    else None
                ),
                "lockout_seconds_remaining": (
                    existing_user.lockout_seconds_remaining
                ),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail={
                "message": (
                    "Too many failed login attempts. "
                    "Try again after the temporary lockout expires."
                ),
                "locked_until": (existing_user.locked_until.isoformat() if existing_user.locked_until else None),
                "lockout_seconds_remaining": (
                    existing_user.lockout_seconds_remaining
                ),
            },
        )

    password_valid, upgraded_hash = verify_and_update_password(
        form_data.password,
        existing_user.hashed_password,
    )

    if not password_valid:
        existing_user.register_failed_login(
            max_attempts=MAX_FAILED_LOGIN_ATTEMPTS,
            lockout_minutes=LOGIN_LOCKOUT_MINUTES,
        )
        db.commit()
        db.refresh(existing_user)

        audit_event(
            db=db,
            event_type=AUDIT_EVENT_LOGIN_FAILURE,
            outcome=(
                AUDIT_OUTCOME_BLOCKED
                if existing_user.is_login_locked
                else AUDIT_OUTCOME_FAILURE
            ),
            request=request,
            actor_user=existing_user,
            target_user=existing_user,
            message=(
                "Account locked after repeated failed logins."
                if existing_user.is_login_locked
                else "Login failed."
            ),
            details={
                "failed_login_attempts": (
                    existing_user.failed_login_attempts
                ),
                "is_login_locked": existing_user.is_login_locked,
                "locked_until": (
                    existing_user.locked_until.isoformat()
                    if existing_user.locked_until
                    else None
                ),
            },
        )

        if existing_user.is_login_locked:
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail={
                    "message": (
                        "Too many failed login attempts. "
                        "Your account is temporarily locked."
                    ),
                    "locked_until": (existing_user.locked_until.isoformat() if existing_user.locked_until else None),
                    "lockout_seconds_remaining": (
                        existing_user.lockout_seconds_remaining
                    ),
                },
            )

        raise credentials_error

    if upgraded_hash:
        existing_user.hashed_password = upgraded_hash

    owner_email_configured = bool(
        str(settings.OWNER_EMAIL or "").strip()
    )
    account_matches_owner = _is_owner_email(
        existing_user.email
    )

    if existing_user.account_status == ACCOUNT_STATUS_PENDING:
        LOGGER.warning(
            "Owner bootstrap diagnostic: "
            "owner_email_configured=%s "
            "account_matches_owner=%s "
            "account_status=%s",
            owner_email_configured,
            account_matches_owner,
            existing_user.account_status,
        )

    if (
        account_matches_owner
        and existing_user.account_status
        == ACCOUNT_STATUS_PENDING
    ):
        existing_user.approve(
            approved_by="OWNER_EMAIL_BOOTSTRAP"
        )

    if (
        not existing_user.is_active
        or existing_user.account_status
        != ACCOUNT_STATUS_APPROVED
    ):
        if upgraded_hash:
            db.commit()
            db.refresh(existing_user)

        raise _account_access_error(existing_user)

    existing_user.register_successful_login()
    db.commit()
    db.refresh(existing_user)

    token_expiry = get_access_token_expiry()
    refresh_expiry = get_refresh_token_expiry()

    # The database-backed login session must remain valid for the
    # refresh-token lifetime, not merely for the short access-token
    # lifetime. Access JWT expiry remains independent below.
    auth_session, jwt_id = create_auth_session(
        db,
        user_id=int(existing_user.id),
        password_version=int(
            existing_user.password_version or 1
        ),
        expires_at=refresh_expiry,
        request=request,
        commit=True,
    )

    try:
        token = create_access_token(
            {
                "sub": str(existing_user.email),
                "user_id": existing_user.id,
                "username": existing_user.username,
                "email": existing_user.email,
                "account_status": (
                    existing_user.account_status
                ),
                "owner_approved": True,
                "is_owner": _is_owner_email(
                    existing_user.email
                ),
                "password_version": int(
                    existing_user.password_version or 1
                ),
                "login_security_version": 38,
            },
            session_id=auth_session.session_id,
            jwt_id=jwt_id,
            expires_at=token_expiry,
        )
    except Exception:
        revoke_auth_session(
            db,
            session_id=auth_session.session_id,
            reason="TOKEN_CREATION_FAILED",
            user_id=int(existing_user.id),
            commit=True,
        )
        raise


    refresh_token_id = generate_token_id()
    refresh_family_id = generate_family_id()

    refresh_token = create_refresh_token_jwt(
        {
            "sub": str(existing_user.email),
            "user_id": existing_user.id,
            "username": existing_user.username,
            "email": existing_user.email,
            "password_version": int(
                existing_user.password_version or 1
            ),
        },
        token_id=refresh_token_id,
        session_id=auth_session.session_id,
        family_id=refresh_family_id,
        expires_at=refresh_expiry,
    )

    try:
        refresh_record, _ = create_refresh_token(
            db,
            user_id=int(existing_user.id),
            session_id=auth_session.session_id,
            password_version=int(
                existing_user.password_version or 1
            ),
            request=request,
            expires_at=refresh_expiry,
            family_id=refresh_family_id,
            raw_token=refresh_token,
            token_id=refresh_token_id,
            commit=True,
        )
    except Exception:
        revoke_auth_session(
            db,
            session_id=auth_session.session_id,
            reason="REFRESH_TOKEN_STORAGE_FAILED",
            user_id=int(existing_user.id),
            commit=True,
        )
        raise

    audit_event(
        db=db,
        event_type=AUDIT_EVENT_LOGIN_SUCCESS,
        outcome=AUDIT_OUTCOME_SUCCESS,
        request=request,
        actor_user=existing_user,
        target_user=existing_user,
        message="Login successful.",
        details={
            "password_version": existing_user.password_version,
            "is_owner": _is_owner_email(existing_user.email),
            "session_id": auth_session.session_id,
            "session_expires_at": auth_session.expires_at,
            "access_token_expires_at": token_expiry,
            "refresh_token_expires_at": refresh_record.expires_at,
            "session_uses_refresh_lifetime": True,
            "database_session_validation": True,
            "refresh_token_enabled": True,
            "refresh_token_family_id": refresh_record.family_id,
        },
    )

    return {
        "access_token": token,
        "refresh_token": refresh_token,
        "token_type": ACCESS_TOKEN_TYPE,
        "refresh_token_type": "bearer",
        "access_token_expires_at": token_expiry,
        "refresh_token_expires_at": refresh_record.expires_at,
        "refresh_token_rotated": False,
        "refresh_token_family_id": refresh_record.family_id,
        "access_granted": True,
        "owner_approval_required": True,
        "failed_login_attempts_reset": True,
        "session": session_public_payload(
            auth_session,
            current_session_id=auth_session.session_id,
        ),
        "user": _public_user(existing_user),
    }


@router.post("/change-password")
def change_password(
    payload: PasswordChangeRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    current_session: AuthSession = Depends(
        get_current_auth_session
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Change the authenticated user's password securely.

    The current password must be correct.
    The new password must be strong and different.
    All previously issued JWT tokens become invalid immediately.
    """

    try:
        validated_new_password = ensure_password_changed(
            current_password=payload.current_password,
            new_password=payload.new_password,
            current_password_hash=(
                current_user.hashed_password
            ),
        )
    except ValueError as exc:
        message = str(exc)

        status_code = (
            status.HTTP_401_UNAUTHORIZED
            if message == "Current password is incorrect."
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )

        raise HTTPException(
            status_code=status_code,
            detail=message,
        ) from exc

    database_user = (
        db.query(User)
        .filter(User.id == current_user.id)
        .first()
    )

    if not database_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User account no longer exists.",
        )

    database_user.set_password_hash(
        hash_password(validated_new_password)
    )

    db.commit()
    db.refresh(database_user)

    revoked_sessions = revoke_all_user_sessions(
        db,
        user_id=int(database_user.id),
        reason=SESSION_REVOKE_PASSWORD_CHANGED,
        commit=True,
    )

    revoked_refresh_tokens = revoke_all_user_refresh_tokens(
        db,
        user_id=int(database_user.id),
        reason=REFRESH_REVOKE_PASSWORD_CHANGED,
        commit=True,
    )

    revoked_action_tokens = revoke_all_user_tokens(
        db,
        user_id=int(database_user.id),
        reason=TOKEN_REVOKE_PASSWORD_CHANGED,
        commit=True,
    )

    audit_event(
        db=db,
        event_type=AUDIT_EVENT_PASSWORD_CHANGED,
        outcome=AUDIT_OUTCOME_SUCCESS,
        request=request,
        actor_user=database_user,
        target_user=database_user,
        message="Password changed successfully.",
        details={
            "password_version": database_user.password_version,
            "old_tokens_revoked": True,
            "revoked_sessions": revoked_sessions,
            "revoked_refresh_tokens": revoked_refresh_tokens,
            "revoked_action_tokens": revoked_action_tokens,
            "current_session_id": current_session.session_id,
        },
    )

    return {
        "status": "success",
        "message": (
            "Password changed successfully. "
            "All existing login sessions were revoked. "
            "Please log in again."
        ),
        "relogin_required": True,
        "old_tokens_revoked": True,
        "revoked_sessions": revoked_sessions,
        "revoked_refresh_tokens": revoked_refresh_tokens,
        "revoked_action_tokens": revoked_action_tokens,
        "password_version": database_user.password_version,
        "password_changed_at": database_user.password_changed_at,
    }




@router.post("/refresh")
def refresh_access_token(
    payload: RefreshRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Rotate a valid refresh token and issue a new token pair.
    """

    decoded = decode_refresh_token(
        payload.refresh_token
    )

    if decoded is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token.",
        )

    try:
        old_record = validate_refresh_token(
            db,
            raw_token=payload.refresh_token,
        )
    except RefreshTokenReuseError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "Refresh-token reuse was detected. "
                "All related tokens were revoked."
            ),
        )
    except (
        InvalidRefreshTokenError,
        ExpiredRefreshTokenError,
        RevokedRefreshTokenError,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is invalid, expired or revoked.",
        )

    if str(decoded.get("jti")) != str(old_record.token_id):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token identifier mismatch.",
        )

    if str(decoded.get("sid")) != str(old_record.session_id):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token session mismatch.",
        )

    if str(decoded.get("fid")) != str(old_record.family_id):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token family mismatch.",
        )

    user = (
        db.query(User)
        .filter(User.id == int(old_record.user_id))
        .first()
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token user no longer exists.",
        )

    try:
        decoded_user_id = int(
            decoded.get("user_id")
        )
    except (TypeError, ValueError):
        decoded_user_id = -1

    decoded_subject = _normalise_email(
        str(decoded.get("sub") or "")
    )
    decoded_email = _normalise_email(
        str(decoded.get("email") or decoded_subject)
    )
    decoded_username = _normalise_username(
        str(decoded.get("username") or "")
    )

    if (
        decoded_user_id != int(user.id)
        or decoded_subject != _normalise_email(user.email)
        or decoded_email != _normalise_email(user.email)
        or decoded_username != _normalise_username(user.username)
    ):
        revoke_refresh_family(
            db,
            family_id=old_record.family_id,
            reason="REFRESH_IDENTITY_MISMATCH",
            commit=True,
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token user identity mismatch.",
        )

    if (
        not bool(user.is_active)
        or str(user.account_status).upper()
        != ACCOUNT_STATUS_APPROVED
    ):
        revoke_session_refresh_tokens(
            db,
            session_id=old_record.session_id,
            reason="ACCOUNT_NOT_APPROVED",
            commit=True,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is not approved for access.",
        )

    current_password_version = int(
        user.password_version or 1
    )

    if (
        int(decoded.get("password_version"))
        != current_password_version
        or int(old_record.password_version)
        != current_password_version
    ):
        revoke_session_refresh_tokens(
            db,
            session_id=old_record.session_id,
            reason=REFRESH_REVOKE_PASSWORD_CHANGED,
            commit=True,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Password changed. Please log in again.",
        )

    access_expiry = get_access_token_expiry()
    new_access_jwt_id = generate_jwt_id()

    new_access_token = create_access_token(
        {
            "sub": str(user.email),
            "user_id": user.id,
            "username": user.username,
            "email": user.email,
            "account_status": user.account_status,
            "owner_approved": True,
            "is_owner": _is_owner_email(user.email),
            "password_version": current_password_version,
            "login_security_version": 38,
        },
        session_id=old_record.session_id,
        jwt_id=new_access_jwt_id,
        expires_at=access_expiry,
    )

    new_refresh_token_id = generate_token_id()

    new_refresh_token = create_refresh_token_jwt(
        {
            "sub": str(user.email),
            "user_id": user.id,
            "username": user.username,
            "email": user.email,
            "password_version": current_password_version,
        },
        token_id=new_refresh_token_id,
        session_id=old_record.session_id,
        family_id=old_record.family_id,
        expires_at=old_record.expires_at,
    )

    try:
        new_record, _ = create_refresh_token(
            db,
            user_id=int(user.id),
            session_id=old_record.session_id,
            password_version=current_password_version,
            request=request,
            expires_at=old_record.expires_at,
            family_id=old_record.family_id,
            parent_token_id=old_record.token_id,
            raw_token=new_refresh_token,
            token_id=new_refresh_token_id,
            commit=False,
        )

        old_record.mark_rotated(
            replacement_token_id=new_refresh_token_id
        )

        auth_session = (
            db.query(AuthSession)
            .filter(
                AuthSession.session_id
                == old_record.session_id
            )
            .first()
        )

        if auth_session is None:
            raise RuntimeError(
                "Authentication session is missing."
            )

        auth_session.token_jti_hash = hash_jwt_id(
            new_access_jwt_id
        )
        auth_session.password_version = (
            current_password_version
        )
        auth_session.touch()

        db.commit()
        db.refresh(old_record)
        db.refresh(new_record)
        db.refresh(auth_session)
    except Exception:
        db.rollback()
        revoke_refresh_family(
            db,
            family_id=old_record.family_id,
            reason="ROTATION_FAILED",
            commit=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Secure refresh-token rotation failed.",
        )

    return {
        "status": "success",
        "message": "Token pair refreshed successfully.",
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
        "refresh_token_type": "bearer",
        "access_token_expires_at": access_expiry,
        "refresh_token_expires_at": new_record.expires_at,
        "session_id": new_record.session_id,
        "refresh_token_rotated": True,
        "refresh_token_family_id": new_record.family_id,
    }


@router.post("/logout")
def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    current_session: AuthSession = Depends(
        get_current_auth_session
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Revoke only the current login session.
    """

    revoked = revoke_auth_session(
        db,
        session_id=current_session.session_id,
        reason=SESSION_REVOKE_LOGOUT,
        user_id=int(current_user.id),
        commit=True,
    )

    revoked_refresh_tokens = revoke_session_refresh_tokens(
        db,
        session_id=current_session.session_id,
        reason=REFRESH_REVOKE_LOGOUT,
        commit=True,
    )

    if not revoked:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Current session was not found.",
        )

    return {
        "status": "success",
        "message": "Logged out successfully.",
        "session_id": current_session.session_id,
        "session_revoked": True,
        "revoked_refresh_tokens": revoked_refresh_tokens,
        "relogin_required": True,
    }


@router.get("/sessions")
def get_sessions(
    current_user: User = Depends(get_current_user),
    current_session: AuthSession = Depends(
        get_current_auth_session
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    List the authenticated user's recent login sessions.
    """

    sessions = list_user_sessions(
        db,
        user_id=int(current_user.id),
        active_only=False,
        limit=100,
    )

    return {
        "status": "success",
        "current_session_id": current_session.session_id,
        "total_sessions": len(sessions),
        "sessions": [
            session_public_payload(
                auth_session,
                current_session_id=(
                    current_session.session_id
                ),
            )
            for auth_session in sessions
        ],
    }


@router.post("/sessions/{session_id}/revoke")
def revoke_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    current_session: AuthSession = Depends(
        get_current_auth_session
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Revoke one session belonging to the current user.
    """

    revoked = revoke_auth_session(
        db,
        session_id=session_id,
        reason="USER_REVOKED_DEVICE",
        user_id=int(current_user.id),
        commit=True,
    )

    if not revoked:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Session not found or does not belong "
                "to the current user."
            ),
        )

    revoked_refresh_tokens = revoke_session_refresh_tokens(
        db,
        session_id=session_id,
        reason="USER_REVOKED_DEVICE",
        commit=True,
    )

    return {
        "status": "success",
        "message": "Session revoked successfully.",
        "session_id": session_id,
        "session_revoked": True,
        "revoked_refresh_tokens": revoked_refresh_tokens,
        "was_current_session": (
            session_id == current_session.session_id
        ),
        "relogin_required": (
            session_id == current_session.session_id
        ),
    }


@router.post("/sessions/revoke-all")
def revoke_all_sessions(
    keep_current: bool = False,
    current_user: User = Depends(get_current_user),
    current_session: AuthSession = Depends(
        get_current_auth_session
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Revoke all sessions for the current user.

    Set keep_current=true to keep the current device signed in.
    """

    exclude_session_id = (
        current_session.session_id
        if keep_current
        else None
    )

    revoked_count = revoke_all_user_sessions(
        db,
        user_id=int(current_user.id),
        reason=SESSION_REVOKE_ALL_DEVICES,
        exclude_session_id=exclude_session_id,
        commit=True,
    )

    revoked_refresh_tokens = revoke_all_user_refresh_tokens(
        db,
        user_id=int(current_user.id),
        reason=REFRESH_REVOKE_ALL_DEVICES,
        exclude_session_id=exclude_session_id,
        commit=True,
    )

    return {
        "status": "success",
        "message": (
            "All other sessions were revoked."
            if keep_current
            else "All sessions were revoked."
        ),
        "revoked_sessions": revoked_count,
        "revoked_refresh_tokens": revoked_refresh_tokens,
        "current_session_preserved": bool(
            keep_current
        ),
        "relogin_required": not keep_current,
    }


@router.get("/profile")
def profile(
    current_user: Any = Depends(get_current_user),
) -> dict[str, Any]:
    if isinstance(current_user, User):
        user_payload: Any = _public_user(current_user)
    else:
        user_payload = current_user

    return {
        "status": "success",
        "message": (
            "Protected profile accessed by an approved user."
        ),
        "access_granted": True,
        "user": user_payload,
    }


@router.get("/me")
def read_current_user(
    current_user: Any = Depends(get_current_user),
) -> dict[str, Any]:
    if isinstance(current_user, User):
        return _public_user(current_user)

    if isinstance(current_user, dict):
        return current_user

    return {
        "user": current_user,
    }


__all__ = [
    "PasswordChangeRequest",
    "get_db",
    "router",
]