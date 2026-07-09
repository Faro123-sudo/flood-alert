from fastapi import Request, HTTPException
from starlette.responses import RedirectResponse

from app.config import settings


def require_admin(request: Request):
    if not request.session.get("admin"):
        raise HTTPException(status_code=303, detail="Login required")


def verify_password(password: str) -> bool:
    return password == settings.admin_password
