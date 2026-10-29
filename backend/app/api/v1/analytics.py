from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_roles
from app.models.user import User
from app.services.analytics_service import overview_metrics
from app.validators.engine import validate_database

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview")
def overview(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("instructor", "academic_admin", "support_staff", "platform_admin")),
):
    metrics = overview_metrics(db)
    report = validate_database(db)
    # Pass rate = share of graded/submitted records that raised no finding.
    checked = metrics["total_submissions"] + metrics["total_assignments"]
    flagged = len({(f["affected_entity_type"], f["affected_entity_id"]) for f in report["findings"]})
    metrics["data_quality_pass_rate"] = (max(checked - flagged, 0) / checked) if checked else 1.0
    metrics["data_quality_status"] = report["status"]
    metrics["anomaly_counts"] = report["by_type"]
    metrics["anomaly_total"] = report["anomaly_count"]
    return metrics
