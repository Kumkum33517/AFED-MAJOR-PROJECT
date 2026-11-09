"""One command to a working demo: users, dataset, pipeline, alerts, cases, reviews and notifications.

    python scripts/seed.py                 # synthetic labelled data, resets the local database
    python scripts/seed.py --csv data/public_sf.csv   # the same with another AFED-schema CSV
    python scripts/seed.py --dataset nspcl            # a dataset from data/processed (see DATASETS.md)

On a real database the demo accounts get random passwords, printed once, unless --demo-passwords is passed.
"""
import argparse
import random
import secrets
import sys
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "data")]

import pandas as pd  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.auth import hash_password  # noqa: E402
from app.config import DATASET_CSV, IS_SQLITE  # noqa: E402
from app.db import Base, SessionLocal, engine, init_db  # noqa: E402
from app.deps import audit, notify  # noqa: E402
from app.models import SEEDED_COMMENT, Alert, Case, Feedback, Run, User, utcnow  # noqa: E402
from app.services import execute_run, get_settings, ingest  # noqa: E402
from generate_synthetic import generate  # noqa: E402
from ml.evaluate import print_report  # noqa: E402
from ml.features import read_csv  # noqa: E402

DEMO_USERS = [("admin@afed.app", "Asha Menon", "Admin"), ("analyst@afed.app", "Arun Kumar", "Analyst"),
              ("reviewer@afed.app", "Rekha Sharma", "Reviewer"), ("viewer@afed.app", "Vikram Iyer", "Viewer")]
DEMO_PASSWORD = "afed1234"
SIMULATED_REVIEWS = 60


def reset_database() -> None:
    init_db()
    if IS_SQLITE:
        Base.metadata.drop_all(engine)
        init_db()
        return
    # Rows, not tables: dropping would fail on profiles, and forcing it would remove every RLS policy.
    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())


def seed_users(public_password: bool) -> None:
    with SessionLocal() as db:
        for email, name, role in DEMO_USERS:
            password = DEMO_PASSWORD if public_password else secrets.token_urlsafe(12)
            db.add(User(email=email, name=name, role=role, password_hash=hash_password(password)))
            if not public_password:
                print(f"  {email}  {password}")
        db.commit()


def seed_reviews() -> int:
    """Simulated decisions on labelled alerts, so feedback analytics and recalibration have data.

    Each decision follows the event's true label, and every one carries SEEDED_COMMENT, which
    the Evaluation page counts and discloses. Unlabelled data gets none. Recalibration ignores
    them, because they are copies of the labels that evaluation is measured against.
    """
    rng = random.Random(42)
    with SessionLocal() as db:
        reviewer = db.scalar(select(User).where(User.role == "Reviewer"))
        pool = [a for a in db.scalars(select(Alert)) if a.event.is_anomaly is not None]
        chosen = rng.sample(pool, min(SIMULATED_REVIEWS, len(pool)))
        now = utcnow()
        for i, alert in enumerate(chosen):
            confirmed = bool(alert.event.is_anomaly)
            alert.status = "Confirmed" if confirmed else "Dismissed"
            alert.assignee_id = reviewer.id
            reason = "Verified with documents" if confirmed else "Legitimate business reason"
            db.add(Feedback(alert_id=alert.id, user_id=reviewer.id, action=alert.status, label=int(confirmed), reason=reason,
                            comment=SEEDED_COMMENT, created_at=now - timedelta(days=7 * (i % 8))))
            audit(db, reviewer, f"alert_{alert.status.lower()}", "alert", alert.id, reason=reason, comment=SEEDED_COMMENT)
        db.commit()
        return len(chosen)


def seed_assignments() -> None:
    with SessionLocal() as db:
        reviewer = db.scalar(select(User).where(User.role == "Reviewer"))
        top = db.scalars(select(Alert).where(Alert.status == "Pending").order_by(Alert.risk.desc()).limit(3)).all()
        for alert in top:
            alert.assignee_id = reviewer.id
        notify(db, [reviewer.id], "assignment", f"{len(top)} alerts assigned to you", "The highest-risk pending alerts.", "/alerts?status=Pending")
        db.commit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--csv", type=Path, help="AFED-schema CSV to load instead of generating synthetic data")
    parser.add_argument("--dataset", help="a processed dataset name, such as nspcl or delaware, from data/processed")
    parser.add_argument("--reset-remote", action="store_true", help="required to wipe a non-SQLite database")
    parser.add_argument("--demo-passwords", action="store_true", help="on a real database, keep the published demo password")
    args = parser.parse_args()
    if not IS_SQLITE and not args.reset_remote:
        sys.exit("DATABASE_URL points at a real database and seeding drops every table. Pass --reset-remote to confirm.")

    print("Resetting the database...")
    reset_database()
    public_password = IS_SQLITE or args.demo_passwords
    if not public_password:
        print("Demo account passwords, shown once:")
    seed_users(public_password)

    if args.dataset:
        sys.path.insert(0, str(ROOT.parent / "data" / "scripts"))
        from common import PROCESSED, to_afed  # the adapter from the common dataset schema
        source = PROCESSED / f"{args.dataset}.parquet"
        if not source.exists():
            sys.exit(f"{source} not found. Run data/scripts/load_{args.dataset}.py first.")
        path = ROOT / "data" / f"dataset_{args.dataset}.csv"
        to_afed(pd.read_parquet(source)).to_csv(path, index=False)
    elif args.csv:
        path = args.csv
    else:
        path = DATASET_CSV
        print("Generating the synthetic dataset...")
        generate(42).to_csv(path, index=False)

    with SessionLocal() as db:
        get_settings(db)
        print(f"Loaded {ingest(db, read_csv(path)):,} events from {path.name}")
        admin = db.scalar(select(User).where(User.role == "Admin"))
        run = Run(source=f"Seed: {path.name}", created_by=admin.id)
        db.add(run)
        db.commit()
        run_id = run.id

    print("Running the pipeline...")
    execute_run(run_id)

    with SessionLocal() as db:
        run = db.get(Run, run_id)
        if run.status != "completed":
            sys.exit(f"Run failed: {run.error}")
        reviews = seed_reviews()
        seed_assignments()
        cases = db.scalars(select(Case)).all()
        print(f"\nModel {run.model_version}: {run.rows:,} events, {run.alerts_count:,} alerts, {len(cases):,} cases, {reviews} simulated reviews")
        if run.metrics:
            print_report(run.metrics)
    if public_password:
        print(f"\nDemo accounts (password {DEMO_PASSWORD}): " + ", ".join(e for e, _, _ in DEMO_USERS))
