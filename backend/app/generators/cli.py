import argparse
import json

from app.core.database import SessionLocal
from app.generators.config import SEED
from app.generators.pipeline import generate_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Synthetic dataset generator")
    parser.add_argument("--mode", choices=["starter", "full"], default="starter")
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--no-export", action="store_true")
    args = parser.parse_args()
    db = SessionLocal()
    try:
        result = generate_dataset(
            db,
            mode=args.mode,
            seed=args.seed,
            force=args.force,
            export=not args.no_export,
        )
        print(json.dumps(result, indent=2, default=str))
    finally:
        db.close()


if __name__ == "__main__":
    main()
