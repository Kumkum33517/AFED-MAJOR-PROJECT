"""PDF and CSV exports. PDFs are English-only: the built-in fonts have no Devanagari."""
import csv
from datetime import datetime
from io import BytesIO, StringIO
from typing import Any
from xml.sax.saxutils import escape

from fastapi import APIRouter, HTTPException, Query, Response
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import func, or_, select
from sqlalchemy.orm import joinedload

from ml.explain import inr
from ml.features import RULE_LABELS

from ..deps import DB, MAX_ID, CurrentUser, Id, audit, through
from ..models import SEEDED_COMMENT, Alert, Case, Event, Feedback, User, utcnow

router = APIRouter(prefix="/reports", tags=["reports"])

OLIVE, CREAM, INK = colors.HexColor("#2F3A22"), colors.HexColor("#F3EFE4"), colors.HexColor("#1B1A17")
MAX_PDF_ROWS = 5000
_base = getSampleStyleSheet()
TITLE = ParagraphStyle("t", parent=_base["Title"], fontName="Times-Bold", fontSize=22, textColor=OLIVE, alignment=0, spaceAfter=2)
H2 = ParagraphStyle("h", parent=_base["Heading2"], fontName="Times-Bold", fontSize=13, textColor=OLIVE, spaceBefore=10, spaceAfter=4)
BODY = ParagraphStyle("b", parent=_base["BodyText"], fontName="Helvetica", fontSize=9.5, leading=13, textColor=INK)
SMALL = ParagraphStyle("s", parent=BODY, fontSize=8, leading=10)
NOTE = "AFED flags events for human review. A flag is not a finding of wrongdoing."


def _p(text: Any, style: ParagraphStyle = BODY) -> Paragraph:
    # Vendor names come from uploads; Paragraph parses markup, so it has to be escaped.
    return Paragraph(escape(str(text)), style)


def _table(rows: list[list[Any]], widths: list[float]) -> Table:
    table = Table(rows, colWidths=widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), OLIVE), ("TEXTCOLOR", (0, 0), (-1, 0), CREAM),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#D8D0BC")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return table


def _simulated_note(db: DB) -> str:
    count = db.scalar(select(func.count()).select_from(Feedback).where(Feedback.comment == SEEDED_COMMENT)) or 0
    return f" Demo data: {count} review decisions here are simulated from synthetic labels." if count else ""


def _pdf(db: DB, story: list[Any], filename: str) -> Response:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm, title=filename)
    doc.build([*story, Spacer(1, 8), _p(f"{NOTE}{_simulated_note(db)} Generated {utcnow():%d %b %Y %H:%M} UTC.", SMALL)])
    return Response(buffer.getvalue(), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


def _alert_table(alerts: list[Alert]) -> Table:
    rows: list[list[Any]] = [["Alert", "Event", "Vendor", "Date", "Amount", "Risk", "Level", "Status"]]
    for a in alerts:
        # Uploaded text goes in a Paragraph so it wraps: a long id would overprint the next column.
        rows.append([str(a.id), _p(a.event.event_id, SMALL), _p(a.event.vendor_name, SMALL), f"{a.event.invoice_date:%d %b %Y}",
                     inr(a.event.amount), f"{a.risk:.2f}", a.level, a.status])
    return _table(rows, [13 * mm, 21 * mm, 46 * mm, 20 * mm, 24 * mm, 11 * mm, 15 * mm, 18 * mm])


def _load(db: DB, query: Any, limit: int | None = None) -> list[Alert]:
    query = query.options(joinedload(Alert.event), joinedload(Alert.assignee))
    return list(db.scalars(query.limit(limit) if limit else query))


def _range_query(date_from: datetime | None, date_to: datetime | None, vendor: str | None) -> Any:
    query = select(Alert).join(Event, Alert.event_pk == Event.id).order_by(Event.invoice_date.desc(), Alert.id)
    if date_from:
        query = query.where(Event.invoice_date >= date_from)
    if date_to:
        query = query.where(Event.invoice_date <= through(date_to))
    if vendor:  # an id or a name: people know vendors by name
        query = query.where(or_(Alert.vendor_id == vendor, Event.vendor_name.icontains(vendor, autoescape=True)))
    return query


@router.get("/alert/{alert_id}.pdf")
def alert_pdf(alert_id: Id, db: DB, user: CurrentUser) -> Response:
    alert = db.get(Alert, alert_id, options=[joinedload(Alert.event)])
    if alert is None:
        raise HTTPException(404, "Alert not found")
    e = alert.event
    lstm = "not run" if alert.lstm_score is None else f"{alert.lstm_score:.2f}"
    story = [_p(f"Alert {alert.id}", TITLE), _p(f"{e.vendor_name} ({alert.vendor_id})"), Spacer(1, 6),
             _table([["Event", "Invoice date", "Amount", "Risk", "Level", "Status", "Model"],
                     [_p(e.event_id, SMALL), f"{e.invoice_date:%d %b %Y}", inr(e.amount), f"{alert.risk:.2f}", alert.level, alert.status, _p(alert.model_version or "", SMALL)]],
                    [24 * mm, 24 * mm, 26 * mm, 14 * mm, 18 * mm, 20 * mm, 40 * mm]),
             _p("Explanation", H2), _p(alert.explanation), _p("Facts", H2)]
    story += [_p(f"- {fact['text']}") for fact in alert.facts]
    story += [_p("Score breakdown", H2),
              _p(f"Isolation Forest {alert.a_score:.2f}, entity deviation {alert.d_score:.2f}, rules {alert.f_score:.2f}, LSTM percentile {lstm}.")]
    if alert.flags:
        story.append(_p("Red flags: " + ", ".join(RULE_LABELS.get(f, f) for f in alert.flags)))
    audit(db, user, "report_exported", "alert", alert.id)
    db.commit()
    return _pdf(db, story, f"afed-alert-{alert.id}.pdf")


@router.get("/case/{case_id}.pdf")
def case_pdf(case_id: Id, db: DB, user: CurrentUser) -> Response:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(404, "Case not found")
    alerts = _load(db, select(Alert).join(Event, Alert.event_pk == Event.id).where(Alert.case_id == case_id).order_by(Event.invoice_date))
    assignee = db.get(User, case.assignee_id) if case.assignee_id else None
    story = [_p(f"Case {case.id}", TITLE), _p(f"{case.vendor_name} ({case.vendor_id})"),
             _p(f"Status: {case.status}. Assignee: {assignee.name if assignee else 'unassigned'}. "
                f"Window: {case.window_start:%d %b %Y} to {case.window_end:%d %b %Y}."),
             _p("Alerts", H2), _alert_table(alerts)]
    if case.notes:
        story.append(_p("Notes", H2))
        story += [_p(f"{n['author']} ({n['at'][:10]}): {n['text']}") for n in case.notes]
    audit(db, user, "report_exported", "case", case.id)
    db.commit()
    return _pdf(db, story, f"afed-case-{case.id}.pdf")


@router.get("/range.pdf")
def range_pdf(db: DB, user: CurrentUser, date_from: datetime | None = None, date_to: datetime | None = None,
              vendor_id: str | None = None) -> Response:
    query = _range_query(date_from, date_to, vendor_id)
    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0
    if not total:
        raise HTTPException(404, "No alerts match that selection")
    alerts = _load(db, query, MAX_PDF_ROWS)
    period = f"{date_from:%d %b %Y}" if date_from else "start"
    period += f" to {date_to:%d %b %Y}" if date_to else " to latest"
    counts = {level: sum(a.level == level for a in alerts) for level in ("Critical", "High", "Medium")}
    story = [_p("AFED alert report", TITLE), _p(f"Period: {period}" + (f". Vendor: {vendor_id}" if vendor_id else "")),
             _p(f"{total:,} alerts in this period." + (f" Showing the newest {len(alerts):,}; export CSV for all of them." if total > len(alerts) else "")),
             _p(", ".join(f"{v} {k}" for k, v in counts.items()) + " listed below."), Spacer(1, 6), _alert_table(alerts)]
    audit(db, user, "report_exported", "report", "range", vendor_id=vendor_id)
    db.commit()
    return _pdf(db, story, "afed-alerts.pdf")


def _safe_cell(value: Any) -> Any:
    """A leading =, +, - or @ would run as a formula in Excel, and vendor names are uploaded data."""
    if isinstance(value, str) and value.lstrip(" \t\r\n")[:1] in ("=", "+", "-", "@", "＝", "＋", "－", "＠"):
        return "'" + value
    return value


@router.get("/alerts.csv")
def alerts_csv(db: DB, user: CurrentUser, date_from: datetime | None = None, date_to: datetime | None = None,
               vendor_id: str | None = None, case_id: int | None = Query(None, ge=1, le=MAX_ID)) -> Response:
    query = _range_query(date_from, date_to, vendor_id)
    if case_id is not None:
        if db.get(Case, case_id) is None:
            raise HTTPException(404, "Case not found")
        query = query.where(Alert.case_id == case_id)
    alerts = _load(db, query)
    if not alerts:
        raise HTTPException(404, "No alerts match that selection")
    simulated = set(db.scalars(select(Feedback.alert_id).where(Feedback.comment == SEEDED_COMMENT)))
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["alert_id", "event_id", "vendor_id", "vendor_name", "invoice_date", "amount", "risk", "level", "status",
                     "simulated_review", "flags", "explanation", "model_version", "case_id"])
    for a in alerts:
        writer.writerow([_safe_cell(v) for v in (a.id, a.event.event_id, a.vendor_id, a.event.vendor_name, f"{a.event.invoice_date:%Y-%m-%d}",
                         a.event.amount, round(a.risk, 4), a.level, a.status, a.id in simulated, ";".join(a.flags), a.explanation, a.model_version, a.case_id)])
    audit(db, user, "report_exported", "report", "csv", vendor_id=vendor_id)
    db.commit()
    return Response(output.getvalue(), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="afed-alerts.csv"'})
