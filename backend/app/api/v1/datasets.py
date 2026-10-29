from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_roles
from app.generators.pipeline import DATA, generate_dataset
from app.models.user import User
from app.validators.engine import validate_database, write_validation_report

router = APIRouter(prefix="/datasets", tags=["datasets"])


class GenerateRequest(BaseModel):
    mode: str = "starter"
    seed: int = 20261022
    force: bool = False
    export: bool = True


@router.post("/generate")
def generate(
    payload: GenerateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("platform_admin")),
):
    try:
        return generate_dataset(db, mode=payload.mode, seed=payload.seed, force=payload.force, export=payload.export)
    except ValueError as exc:
        message = str(exc)
        if "not empty" in message:
            raise ConflictError(message) from exc
        raise ValidationAppError(message) from exc


@router.post("/validate")
def validate(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("platform_admin", "academic_admin")),
):
    report = validate_database(db)
    write_validation_report(report)
    return report


@router.get("/exports")
def list_exports(user: User = Depends(require_roles("platform_admin", "academic_admin"))):
    out = []
    if DATA.exists():
        for mode_dir in sorted(p for p in DATA.iterdir() if p.is_dir() and p.name in {"starter", "full"}):
            for f in sorted(mode_dir.iterdir()):
                if f.is_file():
                    out.append({"mode": mode_dir.name, "filename": f.name, "size_bytes": f.stat().st_size})
    return {"files": out}


@router.get("/exports/{mode}/{filename}")
def download_export(
    mode: str,
    filename: str,
    user: User = Depends(require_roles("platform_admin", "academic_admin")),
):
    if mode not in {"starter", "full"} or "/" in filename or "\\" in filename or filename.startswith("."):
        raise NotFoundError("Export file not found")
    path = DATA / mode / filename
    if not path.is_file():
        raise NotFoundError("Export file not found")
    return FileResponse(path, filename=filename)
