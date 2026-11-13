from typing import Any, Optional
from fastapi import HTTPException, status

class SkillSphereException(HTTPException):
    def __init__(
        self,
        status_code: int,
        detail: str,
        headers: Optional[dict[str, str]] = None
    ):
        super().__init__(status_code=status_code, detail=detail, headers=headers)

class NotFoundException(SkillSphereException):
    def __init__(self, resource: str, identifier: Any = None):
        detail = f"{resource} not found" if identifier is None else f"{resource} with id '{identifier}' not found"
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)

class BadRequestException(SkillSphereException):
    def __init__(self, detail: str):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

class UnauthorizedException(SkillSphereException):
    def __init__(self, detail: str = "Could not validate credentials"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"}
        )

class ForbiddenException(SkillSphereException):
    def __init__(self, detail: str = "You do not have permission to perform this action"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)

class ConflictException(SkillSphereException):
    def __init__(self, detail: str):
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)
