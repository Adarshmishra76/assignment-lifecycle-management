import json

from app.core.database import SessionLocal
from app.validators.engine import validate_database, write_validation_report


def main() -> None:
    db = SessionLocal()
    try:
        report = validate_database(db)
        write_validation_report(report)
        print(json.dumps({k: report[k] for k in ("status", "anomaly_count", "by_type", "examples")}, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()
