from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.exceptions import AppError, app_error_handler, http_error_handler
from app.services.auth_service import bootstrap_admin

settings = get_settings()
app = FastAPI(title=settings.app_name, version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(HTTPException, http_error_handler)
app.include_router(api_router, prefix="/api/v1")


@app.on_event("startup")
def startup() -> None:
    db = SessionLocal()
    try:
        bootstrap_admin(db, settings.bootstrap_admin_email, settings.bootstrap_admin_password)
    except Exception:
        db.rollback()
    finally:
        db.close()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
