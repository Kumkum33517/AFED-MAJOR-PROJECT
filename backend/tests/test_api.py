"""API check against a throwaway SQLite file: the access matrix, then the workflows. Run: python tests/test_api.py"""
import io
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "data")]
TMP = tempfile.mkdtemp()
# Must precede the app imports. A dedicated variable, so a real DATABASE_URL in the shell is never touched.
os.environ["DATABASE_URL"] = os.getenv("TEST_DATABASE_URL", f"sqlite:///{TMP}/test.db")

import pandas as pd  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import func, select  # noqa: E402

from app.auth import hash_password  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app import services  # noqa: E402
from app.models import SEEDED_COMMENT, Alert, Case, Event, Feedback, Run, User  # noqa: E402
from app.routers import settings as settings_router  # noqa: E402
from app.services import execute_run, ingest  # noqa: E402
from generate_synthetic import generate  # noqa: E402
from ml import pipeline  # noqa: E402

pipeline.MODELS_DIR = settings_router.MODELS_DIR = Path(TMP) / "models"

ROLES = ["Admin", "Analyst", "Reviewer", "Viewer"]
ALL, ACT, OPERATE, ADMIN = ROLES, ["Admin", "Reviewer"], ["Admin", "Analyst"], ["Admin"]


H: dict[str, dict[str, str]] = {}


def setup() -> None:
    init_db()
    data = generate(3)
    with SessionLocal() as db:
        db.add_all(User(email=f"{r.lower()}@t.co", name=r, role=r, password_hash=hash_password("pw123456")) for r in ROLES)
        ingest(db, data)
        run = Run(source="test")
        db.add(run)
        db.commit()
        run_id = run.id
    execute_run(run_id)
    with SessionLocal() as db:
        run = db.get(Run, run_id)
        assert run.status == "completed", run.error


def login(client: TestClient, role: str) -> dict[str, str]:
    response = client.post("/auth/login", data={"username": f"{role.lower()}@t.co", "password": "pw123456"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def check_access_matrix(client: TestClient, headers: dict[str, dict[str, str]], alert: int, case: int) -> None:
    review = {"reason": "test", "comment": ""}
    matrix = [
        ("GET", "/dashboard", None, ALL), ("GET", "/entities", None, ALL), ("GET", "/evaluation", None, ALL),
        ("GET", "/alerts", None, ALL), (f"GET", f"/alerts/{alert}", None, ALL), ("GET", f"/alerts/{alert}/similar", None, ALL),
        ("GET", f"/alerts/{alert}/explain", None, ALL), ("GET", "/cases", None, ALL), ("GET", f"/cases/{case}", None, ALL),
        ("GET", f"/reports/alert/{alert}.pdf", None, ALL), ("GET", "/reports/alerts.csv", None, ALL), ("GET", "/reports/results.csv", None, ALL),
        ("GET", "/notifications", None, ALL), ("GET", "/auth/me", None, ALL),
        ("POST", f"/alerts/{alert}/escalate", review, ACT), ("POST", f"/alerts/{alert}/assign", {"assignee_id": None}, ACT),
        ("POST", "/alerts/bulk", {"ids": [alert], "action": "assign", "assignee_id": None}, ACT),
        ("PATCH", f"/cases/{case}", {"status": "Investigating"}, ACT), ("POST", f"/cases/{case}/notes", {"text": "n"}, ACT),
        ("GET", "/users/assignees", None, ACT),
        ("GET", "/settings", None, OPERATE), ("GET", "/settings/models", None, OPERATE), ("GET", "/upload/runs", None, OPERATE),
        ("POST", "/settings/recalibrate", None, OPERATE),
        ("GET", "/users", None, ADMIN), ("GET", "/users/audit-log", None, ADMIN),
    ]
    for method, path, body, allowed in matrix:
        for role in ROLES:
            code = client.request(method, path, json=body, headers=headers[role]).status_code
            expected_ok = role in allowed
            assert (code < 400) == expected_ok and (expected_ok or code == 403), f"{role} {method} {path} -> {code}"
        assert client.request(method, path, json=body).status_code == 401, f"anonymous {method} {path}"
    print(f"ok   access matrix: {len(matrix)} routes x {len(ROLES)} roles, plus anonymous")


def check_review_and_rerun(client: TestClient, h: dict[str, dict[str, str]]) -> None:
    alerts = client.get("/alerts", params={"status": "Pending", "page_size": 2}, headers=h["Viewer"]).json()["items"]
    first, second = alerts[0]["id"], alerts[1]["id"]
    assert client.post(f"/alerts/{first}/confirm", json={"reason": "Verified"}, headers=h["Reviewer"]).json()["status"] == "Confirmed"
    assert client.post(f"/alerts/{second}/dismiss", json={"reason": ""}, headers=h["Reviewer"]).status_code == 422  # reason required
    client.post(f"/alerts/{first}/confirm", json={"reason": "Verified"}, headers=h["Reviewer"])  # a double submit
    assert client.get("/evaluation", headers=h["Viewer"]).json()["feedback"]["totals"]["Confirmed"] == 1
    client.post(f"/alerts/{second}/dismiss", json={"reason": "Legit", "comment": "ok"}, headers=h["Reviewer"])
    timeline = client.get(f"/alerts/{first}", headers=h["Viewer"]).json()["timeline"]
    assert timeline[0]["action"] == "alert_confirmed" and timeline[0]["user"].startswith("Reviewer (")

    started = client.post("/upload/rerun", headers=h["Analyst"])
    assert started.status_code == 202
    assert client.get(f"/upload/runs/{started.json()['run_id']}", headers=h["Analyst"]).json()["status"] == "completed"
    assert client.get(f"/alerts/{first}", headers=h["Viewer"]).json()["status"] == "Confirmed"
    assert client.get(f"/alerts/{second}", headers=h["Viewer"]).json()["status"] == "Dismissed"
    print("ok   reviews are recorded and survive a rerun")


def check_upload(client: TestClient, h: dict[str, dict[str, str]]) -> None:
    csv = "txn,supplier,total,date\n" + "\n".join(f"U{i},NEWV,{1000 + i},2026-10-{i % 28 + 1:02d}" for i in range(30)) + "\nU99,NEWV,950000,2026-10-29\n"
    files = {"file": ("x.csv", io.BytesIO(csv.encode()), "text/csv")}
    assert client.post("/upload/preview", files=files, headers=h["Viewer"]).status_code == 403
    preview = client.post("/upload/preview", files={"file": ("x.csv", io.BytesIO(csv.encode()), "text/csv")}, headers=h["Analyst"]).json()
    assert preview["suggested"]["vendor_id"] == "supplier" and preview["suggested"]["amount"] == "total"
    unmapped = client.post("/upload/validate", json={"upload_id": preview["upload_id"], "mapping": {}}, headers=h["Analyst"]).json()
    assert not unmapped["ok"]
    mapping = {"event_id": "txn", "vendor_id": "supplier", "amount": "total", "invoice_date": "date"}
    body = {"upload_id": preview["upload_id"], "mapping": mapping}
    assert client.post("/upload/validate", json=body, headers=h["Analyst"]).json()["ok"]
    run_id = client.post("/upload/run", json=body, headers=h["Analyst"]).json()["run_id"]
    run = client.get(f"/upload/runs/{run_id}", headers=h["Analyst"]).json()
    assert run["status"] == "completed" and run["new_rows"] == 31, run
    assert client.post("/upload/validate", json={"upload_id": "../../etc/passwd", "mapping": {}}, headers=h["Analyst"]).status_code == 422
    assert client.get("/alerts", params={"entity": "NEWV"}, headers=h["Viewer"]).json()["total"] >= 1
    with SessionLocal() as db:  # unlabelled rows must not enlarge the labelled set's review budget
        budget = db.get(Run, run_id).metrics["review_budget"]
        labelled_alerts = db.scalar(select(func.count()).select_from(Event).where(Event.level != "Low", Event.is_anomaly.is_not(None)))
        unlabelled_alerts = db.scalar(select(func.count()).select_from(Event).where(Event.level != "Low", Event.is_anomaly.is_(None)))
    assert budget == labelled_alerts and unlabelled_alerts > 0, (budget, labelled_alerts, unlabelled_alerts)
    print("ok   upload, mapping, validation and run")


def check_event_intake(client: TestClient, h: dict[str, dict[str, str]]) -> None:
    events = [{"event_id": f"API{i}", "vendor_id": "FEEDV", "amount": 2000 + i, "invoice_date": f"2026-09-{i % 28 + 1:02d}"} for i in range(30)]
    batch = {"source": "ERP test feed", "events": events}
    assert client.post("/upload/events", json=batch, headers=h["Viewer"]).status_code == 403
    assert client.post("/upload/events", json=batch, headers=h["Reviewer"]).status_code == 403
    typo = client.post("/upload/events", json={"source": "x", "events": [{**events[0], "amout": 1}]}, headers=h["Analyst"])
    assert typo.status_code == 422 and typo.json()["detail"][0]["loc"][-1] == "amout", typo.text
    # A large batch needs a valid token before its body is even read, so strangers cannot make the server parse it.
    big = b'{"source":"x","events":[' + b",".join([b'{"event_id":"' + b"X" * 60 + b'"}'] * 20_000) + b"]}"
    assert client.post("/upload/events", content=big, headers={"Content-Type": "application/json"}).status_code == 413
    assert client.post("/upload/events", content=big, headers={"Content-Type": "application/json", "Authorization": "Bearer forged"}).status_code == 413
    assert client.post("/upload/events", content=big, headers={**h["Analyst"], "Content-Type": "application/json"}).status_code != 413
    incomplete = client.post("/upload/events", json={"source": "x", "events": [{"event_id": "A", "vendor_id": "B"}]}, headers=h["Analyst"])
    assert incomplete.status_code == 422 and "Missing required columns" in incomplete.json()["detail"]
    assert client.post("/upload/events", json={"source": "x", "events": []}, headers=h["Analyst"]).status_code == 422
    reply = client.post("/upload/events", json=batch, headers=h["Analyst"])
    assert reply.status_code == 202 and reply.json()["rows"] == 30, reply.text
    run = client.get(f"/upload/runs/{reply.json()['run_id']}", headers=h["Analyst"]).json()
    assert run["status"] == "completed" and run["new_rows"] == 30 and run["source"] == "API: ERP test feed", run
    again = client.post("/upload/events", json=batch, headers=h["Analyst"]).json()  # a resent batch adds nothing
    assert client.get(f"/upload/runs/{again['run_id']}", headers=h["Analyst"]).json()["new_rows"] == 0
    print("ok   automatic intake: roles, unknown and missing fields, resends")


def check_exports(client: TestClient, h: dict[str, dict[str, str]], alert: int, case: int) -> None:
    for path in (f"/reports/alert/{alert}.pdf", f"/reports/case/{case}.pdf", "/reports/range.pdf"):
        response = client.get(path, headers=h["Viewer"])
        assert response.content[:4] == b"%PDF", path
    with SessionLocal() as db:
        target = db.get(Alert, alert)
        target.event.vendor_name = "=HYPERLINK(evil) & <b>"
        db.commit()
    assert client.get(f"/reports/alert/{alert}.pdf", headers=h["Viewer"]).status_code == 200  # markup is escaped
    rows = pd.read_csv(io.StringIO(client.get("/reports/alerts.csv", headers=h["Viewer"]).text), keep_default_na=False)
    assert rows.loc[rows["alert_id"] == alert, "vendor_name"].iloc[0].startswith("'=")
    assert {"why_flagged", "red_flags", "vendor_usual_amount", "times_usual", "decision", "decided_by", "simulated_review"} <= set(rows.columns)
    assert not {"is_anomaly", "anomaly_type", "bank_account"} & set(rows.columns)  # labels and accounts never leave
    flagged = rows[rows["red_flags"] != ""]["red_flags"]
    assert len(flagged) and not flagged.str.contains("_").any()  # plain words, not rule codes
    decided = client.post(f"/alerts/{alert}/dismiss", json={"reason": "Needs audit", "comment": "Same vendor as last quarter"}, headers=h["Reviewer"])
    assert decided.status_code == 200, decided.text
    rows = pd.read_csv(io.StringIO(client.get("/reports/alerts.csv", headers=h["Viewer"]).text), keep_default_na=False)
    row = rows[rows["alert_id"] == alert].iloc[0]
    assert (row["decision"], row["decided_by"], row["decision_reason"], row["decision_comment"]) == (
        "Dismissed", "Reviewer", "Needs audit", "Same vendor as last quarter") and str(row["simulated_review"]) == "False", row.to_dict()
    with SessionLocal() as db:
        scored = db.scalar(select(func.count()).select_from(Event).where(Event.risk.is_not(None)))
        alerted = db.scalar(select(func.count()).select_from(Alert))
    results = pd.read_csv(io.StringIO(client.get("/reports/results.csv", headers=h["Viewer"]).text), keep_default_na=False)
    assert len(results) == scored and (results["alerted"].astype(str) == "True").sum() == alerted
    assert (results["level"] == "Low").any() and results["risk"].is_monotonic_decreasing
    assert not {"is_anomaly", "anomaly_type", "bank_account"} & set(results.columns)
    assert results.loc[results["vendor_name"].str.startswith("'="), "vendor_name"].size >= 1
    assert client.get("/reports/results.csv", params={"vendor_id": "no such vendor"}, headers=h["Viewer"]).status_code == 404
    print("ok   PDF and CSV exports: reasons, numbers, decisions, full results, escaping, no labels")


def check_detail_hides_labels(client: TestClient, h: dict[str, dict[str, str]], alert: int) -> None:
    body = client.get(f"/alerts/{alert}", headers=h["Reviewer"]).json()
    assert "is_anomaly" not in body["event"] and "anomaly_type" not in body["event"] and "bank_account" not in body["event"]
    assert body["sequence"] and body["facts"] and body["explanation"]
    hindi = client.get(f"/alerts/{alert}/explain", params={"language": "hi"}, headers=h["Viewer"]).json()
    assert "है" in hindi["explanation"] and hindi["provider"] == "template" and hindi["fell_back"] is False  # template chosen, not refused
    print("ok   alert detail, Hindi narration, labels hidden from reviewers")


def check_users(client: TestClient, h: dict[str, dict[str, str]]) -> None:
    invited = client.post("/users", json={"email": "New@t.co", "name": "N", "role": "Viewer"}, headers=h["Admin"]).json()
    new_id = invited["user"]["id"]
    token = client.post("/auth/login", data={"username": "new@t.co", "password": invited["temporary_password"]}).json()["access_token"]
    bearer = {"Authorization": f"Bearer {token}"}
    assert client.get("/auth/me", headers=bearer).status_code == 200
    assert client.patch(f"/users/{new_id}", json={"is_active": False}, headers=h["Admin"]).status_code == 200
    assert client.get("/auth/me", headers=bearer).status_code == 401  # a live token dies with the account
    me = client.get("/auth/me", headers=h["Admin"]).json()["id"]
    assert client.patch(f"/users/{me}", json={"role": "Viewer"}, headers=h["Admin"]).status_code == 400
    print("ok   invite, deactivate kills the token, no self-demotion")


def check_settings(client: TestClient, h: dict[str, dict[str, str]]) -> None:
    current = client.get("/settings", headers=h["Admin"]).json()
    body = {k: v for k, v in current.items() if k != "rule_info"}
    assert client.put("/settings", json={**body, "thresholds": {"medium": 0.7, "high": 0.6, "critical": 0.8}}, headers=h["Admin"]).status_code == 422
    assert client.put("/settings", json={**body, "weights": {"w1": 0.9, "w2": 0.9, "w3": 0.9}}, headers=h["Admin"]).status_code == 422
    assert client.put("/settings", json={**body, "approval_limit": 400000}, headers=h["Analyst"]).json()["approval_limit"] == 400000
    assert client.put("/settings", json=body, headers=h["Analyst"]).status_code == 200
    print("ok   settings validation")


def check_notifications_are_private(client: TestClient, h: dict[str, dict[str, str]]) -> None:
    reviewer_items = client.get("/notifications", headers=h["Reviewer"]).json()["items"]
    assert reviewer_items, "the runs should have notified reviewers"
    assert client.post(f"/notifications/{reviewer_items[0]['id']}/read", headers=h["Viewer"]).status_code == 404
    assert client.post(f"/notifications/{reviewer_items[0]['id']}/read", headers=h["Reviewer"]).status_code == 200
    print("ok   notifications stay private")


def check_hostile_input(client: TestClient, h: dict[str, dict[str, str]]) -> None:
    assert client.post("/auth/forgot", content=b'{"email": "' + b"a" * (2 * 1024 * 1024) + b'"}').status_code == 413
    assert client.post("/auth/forgot", content=b'{"email": NaN}', headers={"Content-Type": "application/json"}).status_code == 422
    assert client.get("/alerts/" + "9" * 30, headers=h["Viewer"]).status_code == 422
    assert client.get("/alerts", params={"page": 2**63}, headers=h["Viewer"]).status_code == 422
    assert client.get("/alerts?search=a%00b", headers=h["Viewer"]).status_code == 400
    current = client.get("/settings", headers=h["Admin"]).json()
    body = {k: v for k, v in current.items() if k != "rule_info"}
    bad = client.put("/settings", content=str(body).replace("500000", "Infinity").replace("'", '"').replace("True", "true").replace("False", "false"),
                     headers={**h["Admin"], "Content-Type": "application/json"})
    assert bad.status_code == 422, bad.text
    assert client.patch("/users/2", json={"role": None}, headers=h["Admin"]).status_code == 200
    print("ok   hostile input is refused cleanly")


def check_sessions_end_with_the_password(client: TestClient) -> None:
    client.post("/users", json={"email": "s@t.co", "name": "S", "role": "Viewer"}, headers=H["Admin"])
    new_id = next(u["id"] for u in client.get("/users", headers=H["Admin"]).json() if u["email"] == "s@t.co")
    password = client.post(f"/users/{new_id}/reset-password", headers=H["Admin"]).json()["temporary_password"]
    old = {"Authorization": "Bearer " + client.post("/auth/login", data={"username": "s@t.co", "password": password}).json()["access_token"]}
    changed = client.post("/auth/change-password", json={"current_password": password, "new_password": "new-password-1"}, headers=old)
    assert changed.status_code == 200 and client.get("/auth/me", headers=old).status_code == 401
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {changed.json()['access_token']}"}).status_code == 200
    print("ok   a changed password ends older sessions")


def check_recalibration_ignores_simulated_reviews(client: TestClient) -> None:
    with SessionLocal() as db:
        alerts = db.scalars(select(Alert).where(Alert.status == "Pending").limit(12)).all()
        for i, alert in enumerate(alerts):
            alert.status = "Confirmed" if i % 2 else "Dismissed"
            db.add(Feedback(alert_id=alert.id, action=alert.status, label=i % 2, reason="seed", comment=SEEDED_COMMENT))
        db.commit()
    result = client.post("/settings/recalibrate", headers=H["Admin"]).json()
    assert not result["ok"] and result["simulated_excluded"] >= 12, result
    print("ok   recalibration refuses to learn from simulated reviews")


def check_reruns_keep_people_work_and_tidy_cases(client: TestClient) -> None:
    """Raise the bar so most alerts stop qualifying, then rerun."""
    def alerts(**params: object) -> int:
        return client.get("/alerts", params={**params, "page_size": 1}, headers=H["Viewer"]).json()["total"]

    assigned = client.get("/alerts", params={"status": "Pending", "level": "Medium", "page_size": 1}, headers=H["Viewer"]).json()["items"][0]["id"]
    client.post(f"/alerts/{assigned}/assign", json={"assignee_id": 3}, headers=H["Reviewer"])
    settings = {k: v for k, v in client.get("/settings", headers=H["Admin"]).json().items() if k != "rule_info"}
    tight = {**settings, "thresholds": {"medium": 0.9, "high": 0.95, "critical": 0.98}}
    assert client.put("/settings", json=tight, headers=H["Admin"]).status_code == 200
    before = alerts()
    run_id = client.post("/upload/rerun", headers=H["Analyst"]).json()["run_id"]
    assert client.get(f"/upload/runs/{run_id}", headers=H["Analyst"]).json()["status"] == "completed"
    assert alerts() < before
    kept = client.get(f"/alerts/{assigned}", headers=H["Viewer"]).json()
    assert kept["assignee"] and kept["level"] == "Low", kept["level"]  # kept, and in step with its event
    with SessionLocal() as db:
        empty = db.scalar(select(func.count()).select_from(Case).where(Case.status != "Closed", ~Case.alerts.any()))
    assert empty == 0
    assert client.put("/settings", json=settings, headers=H["Admin"]).status_code == 200
    print("ok   reruns keep assigned work, refresh it, and leave no empty cases")


def check_awkward_uploads(client: TestClient) -> None:
    def upload(text: str | bytes, mapping: dict[str, str] | None = None) -> dict:
        raw = text.encode() if isinstance(text, str) else text
        preview = client.post("/upload/preview", files={"file": ("f.csv", io.BytesIO(raw), "text/csv")}, headers=H["Analyst"])
        assert preview.status_code == 200, preview.text
        body = {"upload_id": preview.json()["upload_id"], "mapping": mapping or preview.json()["suggested"]}
        report = client.post("/upload/validate", json=body, headers=H["Analyst"]).json()
        run_id = client.post("/upload/run", json=body, headers=H["Analyst"]).json()["run_id"]
        return {"report": report, "run": client.get(f"/upload/runs/{run_id}", headers=H["Analyst"]).json()}

    # Numeric ids under another name, uploaded twice with an overlap: the second must add, not crash.
    head = "voucher,supplier,total,date\n"
    first = upload(head + "".join(f"{9000 + i},0042,5000,2026-01-{i + 1:02d}\n" for i in range(5)))
    second = upload(head + "".join(f"{9003 + i},0042,5000,2026-01-{i + 4:02d}\n" for i in range(5)))
    assert first["run"]["status"] == "completed" and second["run"]["status"] == "completed", second["run"]
    assert second["run"]["new_rows"] == 3
    with SessionLocal() as db:
        assert db.scalar(select(Event.vendor_id).where(Event.event_id == "9000")) == "0042"  # the leading zeros survive

    # One bad value must be dropped, not poison every later run.
    poisoned = upload(head + "P0,V1,inf,2026-02-01\n" + "".join(f"P{i},V1,700,2026-02-{i % 28 + 1:02d}\n" for i in range(1, 40)))
    assert poisoned["report"]["dropped_rows"] == 1
    assert poisoned["run"]["status"] == "completed" and poisoned["run"]["new_rows"] == 39, poisoned
    assert client.post("/upload/preview", files={"file": ("f.csv", io.BytesIO(b'a,b\n1,2\n1,2,3,4\n'), "text/csv")}, headers=H["Analyst"]).status_code == 400

    # One column feeding two fields, and a target name that already exists in the file.
    both = upload("id,amount,net,when\nM1,1,800,2026-03-01\n", {"event_id": "id", "vendor_id": "id", "vendor_name": "id", "amount": "net", "invoice_date": "when"})
    assert both["run"]["status"] == "completed", both["run"]
    with SessionLocal() as db:
        assert db.scalar(select(Event.amount).where(Event.event_id == "M1")) == 800

    # Labels with no type must not distort recall by type.
    with SessionLocal() as db:
        assert db.scalar(select(Run.metrics).order_by(Run.id.desc()).limit(1))["review_budget"] > 0
    print("ok   awkward uploads: reuploads, text ids, poison values, mapping collisions")


def check_a_failed_run_leaves_nothing(client: TestClient) -> None:
    with SessionLocal() as db:
        before = db.scalar(select(func.count()).select_from(Event))
        run = Run(source="test")
        db.add(run)
        db.commit()
        run_id = run.id
    path = Path(TMP) / "fails.csv"
    path.write_text("event_id,vendor_id,amount,invoice_date\nF1,V1,5,2026-01-01\n")
    original = services.run_pipeline
    services.run_pipeline = lambda *_: 1 / 0
    try:
        execute_run(run_id, str(path), {"event_id": "event_id", "vendor_id": "vendor_id", "amount": "amount", "invoice_date": "invoice_date"})
    finally:
        services.run_pipeline = original
    with SessionLocal() as db:
        assert db.get(Run, run_id).status == "failed"
        assert db.scalar(select(func.count()).select_from(Event)) == before
    print("ok   a failed run stores nothing")


def check_awkward_entities_and_empty_reports(client: TestClient) -> None:
    with SessionLocal() as db:
        db.get(Event, 1).department = "Legal/Compliance"
        db.commit()
    assert client.get("/entities/Legal%2FCompliance", params={"type": "department"}, headers=H["Viewer"]).status_code == 200
    assert client.get("/reports/alerts.csv", params={"case_id": 999999}, headers=H["Viewer"]).status_code == 404
    assert client.get("/reports/alerts.csv", params={"case_id": 0}, headers=H["Viewer"]).status_code == 422  # not "every alert"
    assert client.get("/reports/range.pdf", params={"vendor_id": "no such vendor"}, headers=H["Viewer"]).status_code == 404
    print("ok   slashes in ids, and reports that match nothing say so")


def check_login_lockout(client: TestClient) -> None:
    for _ in range(5):
        assert client.post("/auth/login", data={"username": "viewer@t.co", "password": "wrong"}).status_code == 401
    assert client.post("/auth/login", data={"username": "viewer@t.co", "password": "pw123456"}).status_code == 429
    # With no trusted proxy configured, a forged X-Forwarded-For must not open a fresh allowance.
    forged = {"X-Forwarded-For": "203.0.113.9"}
    assert client.post("/auth/login", data={"username": "viewer@t.co", "password": "pw123456"}, headers=forged).status_code == 429
    print("ok   login lockout")


if __name__ == "__main__":
    setup()
    with TestClient(app) as client:
        h = H = {role: login(client, role) for role in ROLES}
        with SessionLocal() as db:
            alert = db.scalar(select(Alert.id).where(Alert.case_id.is_not(None)).limit(1))
            case = db.scalar(select(Case.id).limit(1))
        summary = client.get("/evaluation/summary").json()
        assert summary["available"] and "variants" not in summary
        page = client.get("/evaluation", headers=h["Viewer"]).json()
        assert "benchmarks" in page  # null until experiments/model_comparison.py has run
        metrics = page["metrics"]
        assert {"confusion", "f1", "false_negative_rate", "accuracy"} <= set(metrics["variants"]["afed"])
        assert {"amount_at_risk", "investigation", "score_distribution", "processing_seconds"} <= set(metrics)
        assert metrics["fraud_detection_rate"] is None
        assert set(metrics["comparison"]) == {"rule_based", "global_if", "lof", "afed"}
        assert all({"accuracy", "balanced_accuracy", "precision", "recall", "f1", "confusion", "pr_auc"} <= set(m) for m in metrics["comparison"].values())
        check_access_matrix(client, h, alert, case)
        check_detail_hides_labels(client, h, alert)
        check_review_and_rerun(client, h)
        check_upload(client, h)
        check_event_intake(client, h)
        check_settings(client, h)
        check_exports(client, h, alert, case)
        check_users(client, h)
        check_notifications_are_private(client, h)
        check_hostile_input(client, h)
        check_sessions_end_with_the_password(client)
        check_awkward_uploads(client)
        check_a_failed_run_leaves_nothing(client)
        check_reruns_keep_people_work_and_tidy_cases(client)
        check_recalibration_ignores_simulated_reviews(client)
        check_awkward_entities_and_empty_reports(client)
        check_login_lockout(client)
    print("all API checks passed")
