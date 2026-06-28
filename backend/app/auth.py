from fastapi import Depends, HTTPException, Header, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User

def get_current_user(x_digital_id: str = Header(None), db: Session = Depends(get_db)):
    """
    Dependency to fetch the currently authenticated user based on the X-Digital-Id request header.
    """
    if not x_digital_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials missing (X-Digital-Id header required)"
        )
    user = db.query(User).filter(User.digital_id == x_digital_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid digital ID credential reference"
        )
    return user

def require_role(*allowed_roles):
    """
    Dependency to ensure the current authenticated user belongs to one of the allowed roles.
    Checks are case-insensitive.
    """
    allowed_roles_lower = [r.lower() for r in allowed_roles]
    def checker(current_user: User = Depends(get_current_user)):
        if current_user.role.lower() not in allowed_roles_lower:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access Denied: Insufficient permissions"
            )
        return current_user
    return checker
