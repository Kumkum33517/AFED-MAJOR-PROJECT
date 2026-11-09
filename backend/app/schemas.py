"""Request and response bodies."""
from datetime import datetime
from typing import Annotated, Any, Literal, Optional

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

Role = Literal["Admin", "Analyst", "Reviewer", "Viewer"]
Language = Literal["en", "hi"]
MAX_ID = 2**31 - 1
Identifier = Annotated[int, Field(ge=1, le=MAX_ID)]


def _no_nul(value: str) -> str:
    if "\x00" in value:  # Postgres text cannot hold it, so it would surface as a 500
        raise ValueError("must not contain NUL characters")
    return value


Text = Annotated[str, AfterValidator(_no_nul)]
Finite = Annotated[float, Field(allow_inf_nan=False)]


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    name: str
    role: str
    is_active: bool
    preferences: dict[str, Any]
    last_login: Optional[datetime] = None


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class Preferences(BaseModel):
    theme: Optional[Literal["light", "dark"]] = None
    language: Optional[Language] = None


class ProfileUpdate(BaseModel):
    name: Optional[Text] = Field(None, min_length=1, max_length=120)
    preferences: Optional[Preferences] = None


class PasswordChange(BaseModel):
    current_password: str = Field(max_length=200)
    new_password: Text = Field(min_length=8, max_length=72)


class ForgotPassword(BaseModel):
    email: Text = Field(max_length=255)


class ReviewAction(BaseModel):
    reason: Text = Field(min_length=1, max_length=120)
    comment: Text = Field("", max_length=2000)


class BulkAction(BaseModel):
    ids: list[Identifier] = Field(min_length=1, max_length=500)
    action: Literal["assign", "confirm", "dismiss", "escalate"]
    assignee_id: Optional[Identifier] = None
    reason: Text = Field("Bulk action", max_length=120)
    comment: Text = Field("", max_length=2000)


class AssignBody(BaseModel):
    assignee_id: Optional[Identifier] = None


class CaseUpdate(BaseModel):
    status: Optional[Literal["Open", "Investigating", "Closed"]] = None
    assignee_id: Optional[Identifier] = None


class CaseNote(BaseModel):
    text: Text = Field(min_length=1, max_length=4000)


Cell = str | float | int | bool | None


class EventIn(BaseModel):
    """One invoice under AFED's own column names (frontend/public/samples/afed_template.csv).

    Fixed fields with extra="forbid", so a misspelt or unknown key is refused while parsing. Required columns
    are checked with the rest of validation, so a batch gets the same messages as an upload.
    """
    model_config = ConfigDict(extra="forbid")
    event_id: Cell = None
    vendor_id: Cell = None
    amount: Cell = None
    invoice_date: Cell = None
    invoice_number: Cell = None
    vendor_name: Cell = None
    category: Cell = None
    department: Cell = None
    approver_id: Cell = None
    created_by: Cell = None
    approval_date: Cell = None
    processing_days: Cell = None
    bank_account: Cell = None
    vendor_created: Cell = None
    po_amount: Cell = None
    is_anomaly: Cell = None
    anomaly_type: Cell = None


class EventBatch(BaseModel):
    """Invoices pushed by another system to /upload/events."""
    source: Text = Field(min_length=1, max_length=60)  # shown in the run history, e.g. "SAP nightly export"
    events: list[EventIn] = Field(min_length=1, max_length=50_000)


class MappingBody(BaseModel):
    upload_id: str = Field(pattern=r"^[0-9a-f]{32}$")  # used in a file path, so keep it strict
    mapping: dict[str, str]  # AFED column -> column in the uploaded file


class Invite(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=255)
    name: Text = Field(min_length=1, max_length=120)
    role: Role


class UserUpdate(BaseModel):
    role: Optional[Role] = None
    is_active: Optional[bool] = None


class Weights(BaseModel):
    w1: Finite = Field(ge=0, le=1)
    w2: Finite = Field(ge=0, le=1)
    w3: Finite = Field(ge=0, le=1)


class Thresholds(BaseModel):
    medium: Finite = Field(gt=0, lt=1)
    high: Finite = Field(gt=0, lt=1)
    critical: Finite = Field(gt=0, lt=1)


class LstmSettings(BaseModel):
    window: int = Field(ge=2, le=50)
    mode: Literal["forecast", "autoencoder"]
    epochs: int = Field(ge=1, le=100)
    in_forest: bool = True


class SettingsBody(BaseModel):
    approval_limit: Finite = Field(gt=0)
    weights: Weights
    thresholds: Thresholds
    contamination: str | Finite  # "auto" or a fraction, checked in the router
    lstm: LstmSettings
    rules: dict[str, bool]
    qwen_provider: Literal["template", "hf_api", "ollama", "local"]
