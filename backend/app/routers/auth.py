from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.core.config import settings
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_verification_token,
    decode_token
)
from app.core.exceptions import BadRequestException, UnauthorizedException, NotFoundException, ConflictException
from app.core.dependencies import get_current_user
from app.models.user import User, UserRole, EmailVerificationToken, PasswordResetToken
from app.models.candidate import Candidate
from app.models.recruiter import Recruiter, Company, RecruiterApprovalStatus
from app.models.audit import AuditLog
from app.models.notification import Notification
from app.schemas.auth import (
    UserRegisterRequest,
    RecruiterRegisterRequest,
    LoginRequest,
    TokenResponse,
    UserResponse,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    VerifyEmailRequest
)
from app.services.email_service import EmailService
import datetime

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_candidate(req: UserRegisterRequest, db: Session = Depends(get_db)):
    """Register a new Job Seeker / Candidate account."""
    existing = db.query(User).filter(User.email == req.email.lower()).first()
    if existing:
        raise ConflictException("An account with this email address already exists")

    # Create User
    user = User(
        email=req.email.lower(),
        full_name=req.full_name,
        hashed_password=get_password_hash(req.password),
        role=UserRole.CANDIDATE,
        is_active=True,
        is_verified=False
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Initialize Candidate profile
    candidate = Candidate(
        user_id=user.id,
        profile_percentage=25
    )
    db.add(candidate)

    # Issue email verification token
    raw_token = create_verification_token(user.email, token_type="email_verify")
    expires = datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    token_record = EmailVerificationToken(
        user_id=user.id,
        token=raw_token,
        expires_at=expires
    )
    db.add(token_record)

    # In-app notification
    notif = Notification(
        user_id=user.id,
        title="Welcome to SkillSphere!",
        message="Your account has been created. Please complete your profile and upload your resume to discover matching opportunities.",
        type="INFO"
    )
    db.add(notif)

    # Audit log
    audit = AuditLog(
        user_id=user.id,
        action="USER_REGISTERED",
        entity_type="user",
        entity_id=user.id,
        details={"role": "CANDIDATE"}
    )
    db.add(audit)
    db.commit()

    # Dispatch verification email (or log in dev mode)
    EmailService.send_verification_email(user.email, raw_token)

    return user

@router.post("/register-recruiter", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_recruiter(req: RecruiterRegisterRequest, db: Session = Depends(get_db)):
    """Register a new Recruiter account with company profile setup."""
    existing = db.query(User).filter(User.email == req.email.lower()).first()
    if existing:
        raise ConflictException("An account with this email address already exists")

    # Find or create company
    company = db.query(Company).filter(Company.name == req.company_name.strip()).first()
    if not company:
        company = Company(
            name=req.company_name.strip(),
            website=req.company_website,
            location=req.company_location,
            industry=req.industry,
            description=req.company_description
        )
        db.add(company)
        db.commit()
        db.refresh(company)

    # Create User
    user = User(
        email=req.email.lower(),
        full_name=req.full_name,
        hashed_password=get_password_hash(req.password),
        role=UserRole.RECRUITER,
        is_active=True,
        is_verified=False
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Create Recruiter profile (Pending admin verification)
    recruiter = Recruiter(
        user_id=user.id,
        company_id=company.id,
        designation=req.designation,
        approval_status=RecruiterApprovalStatus.PENDING
    )
    db.add(recruiter)

    # Issue email verification token
    raw_token = create_verification_token(user.email, token_type="email_verify")
    expires = datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    token_record = EmailVerificationToken(
        user_id=user.id,
        token=raw_token,
        expires_at=expires
    )
    db.add(token_record)

    # In-app notification
    notif = Notification(
        user_id=user.id,
        title="Recruiter Account Created",
        message="Your recruiter profile is under review by the platform administrator. You will be notified once approved.",
        type="RECRUITER"
    )
    db.add(notif)

    # Audit log
    audit = AuditLog(
        user_id=user.id,
        action="RECRUITER_REGISTERED",
        entity_type="recruiter",
        entity_id=user.id,
        details={"company": req.company_name}
    )
    db.add(audit)
    db.commit()

    EmailService.send_verification_email(user.email, raw_token)

    return user

@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate with email and password, returning JWT access token."""
    user = db.query(User).filter(User.email == req.email.lower()).first()
    if not user or not verify_password(req.password, user.hashed_password):
        raise UnauthorizedException("Invalid email address or password")

    if not user.is_active:
        raise UnauthorizedException("Account is disabled. Please contact the administrator.")

    # Audit log
    audit = AuditLog(
        user_id=user.id,
        action="LOGIN_SUCCESS",
        entity_type="user",
        entity_id=user.id
    )
    db.add(audit)
    db.commit()

    access_token = create_access_token(
        subject=user.email,
        role=user.role.value,
        user_id=user.id
    )

    user_data = {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value,
        "is_active": user.is_active,
        "is_verified": user.is_verified,
        "avatar_url": user.avatar_url
    }

    # Include recruiter status if applicable
    if user.role == UserRole.RECRUITER and user.recruiter_profile:
        user_data["recruiter_status"] = user.recruiter_profile.approval_status.value
        user_data["company_name"] = user.recruiter_profile.company.name if user.recruiter_profile.company else None

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user_data
    }

@router.post("/verify-email")
def verify_email(req: VerifyEmailRequest, db: Session = Depends(get_db)):
    """Verify user email address using token."""
    token_record = db.query(EmailVerificationToken).filter(
        EmailVerificationToken.token == req.token,
        EmailVerificationToken.is_used == False
    ).first()

    if not token_record:
        raise BadRequestException("Invalid or already used verification token")

    if token_record.expires_at < datetime.datetime.utcnow():
        raise BadRequestException("Verification token has expired")

    user = db.query(User).filter(User.id == token_record.user_id).first()
    if not user:
        raise NotFoundException("User")

    user.is_verified = True
    token_record.is_used = True
    db.commit()

    return {"message": "Email address verified successfully"}

@router.post("/forgot-password")
def forgot_password(req: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Request a password reset link."""
    user = db.query(User).filter(User.email == req.email.lower()).first()
    if not user:
        # Avoid user enumeration by returning a generic response
        return {"message": "If this email is registered, a password reset link has been dispatched."}

    raw_token = create_verification_token(user.email, token_type="password_reset")
    expires = datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    token_record = PasswordResetToken(
        user_id=user.id,
        token=raw_token,
        expires_at=expires
    )
    db.add(token_record)
    db.commit()

    EmailService.send_password_reset_email(user.email, raw_token)
    return {"message": "If this email is registered, a password reset link has been dispatched."}

@router.post("/reset-password")
def reset_password(req: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Reset account password using valid reset token."""
    token_record = db.query(PasswordResetToken).filter(
        PasswordResetToken.token == req.token,
        PasswordResetToken.is_used == False
    ).first()

    if not token_record:
        raise BadRequestException("Invalid or already used password reset token")

    if token_record.expires_at < datetime.datetime.utcnow():
        raise BadRequestException("Password reset token has expired")

    user = db.query(User).filter(User.id == token_record.user_id).first()
    if not user:
        raise NotFoundException("User")

    user.hashed_password = get_password_hash(req.new_password)
    token_record.is_used = True
    db.commit()

    return {"message": "Password reset successfully. You may now log in with your new credentials."}

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Get current authenticated user profile."""
    return current_user
