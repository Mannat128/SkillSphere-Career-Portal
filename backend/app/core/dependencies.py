from typing import List, Union
from fastapi import Depends, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.core.security import decode_token
from app.core.exceptions import UnauthorizedException, ForbiddenException
from app.models.user import User, UserRole
from app.models.candidate import Candidate
from app.models.recruiter import Recruiter, RecruiterApprovalStatus

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """Validate bearer token and retrieve the current authenticated User."""
    if not token:
        raise UnauthorizedException("Authentication token required")

    payload = decode_token(token)
    if not payload:
        raise UnauthorizedException("Invalid or expired authentication token")

    email: str = payload.get("sub")
    user_id: int = payload.get("user_id")

    if not email or not user_id:
        raise UnauthorizedException("Invalid token payload")

    user = db.query(User).filter(User.id == user_id, User.email == email).first()
    if not user:
        raise UnauthorizedException("User associated with token no longer exists")

    if not user.is_active:
        raise ForbiddenException("Your account has been deactivated. Please contact support.")

    return user

def require_role(allowed_roles: Union[UserRole, List[UserRole]]):
    """Factory dependency ensuring current user has one of the required roles."""
    if isinstance(allowed_roles, UserRole):
        allowed_roles = [allowed_roles]

    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise ForbiddenException(
                f"Access denied. Requires one of the following roles: {[r.value for r in allowed_roles]}"
            )
        return current_user

    return role_checker

def get_current_candidate(
    current_user: User = Depends(require_role(UserRole.CANDIDATE)),
    db: Session = Depends(get_db)
) -> Candidate:
    """Retrieve Candidate profile for the authenticated candidate user."""
    candidate = db.query(Candidate).filter(Candidate.user_id == current_user.id).first()
    if not candidate:
        # Create candidate profile lazily if not present
        candidate = Candidate(user_id=current_user.id, profile_percentage=20)
        db.add(candidate)
        db.commit()
        db.refresh(candidate)
    return candidate

def get_current_recruiter(
    current_user: User = Depends(require_role(UserRole.RECRUITER)),
    db: Session = Depends(get_db)
) -> Recruiter:
    """Retrieve Recruiter profile for the authenticated recruiter user."""
    recruiter = db.query(Recruiter).filter(Recruiter.user_id == current_user.id).first()
    if not recruiter:
        raise ForbiddenException("Recruiter profile not found. Please complete profile setup.")
    return recruiter

def get_current_admin(
    current_user: User = Depends(require_role(UserRole.ADMIN))
) -> User:
    """Verify that current user is an active Administrator."""
    return current_user
