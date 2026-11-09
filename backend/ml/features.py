"""Validation, entity baselines, entity-relative deviations and deterministic red flags."""
import re
from bisect import bisect_left, insort
from collections import Counter, defaultdict, deque
from datetime import timedelta
from itertools import islice
from typing import Any

import numpy as np
import pandas as pd

REQUIRED = ["event_id", "vendor_id", "amount", "invoice_date"]
OPTIONAL = ["invoice_number", "vendor_name", "category", "department", "approver_id", "created_by", "approval_date",
            "processing_days", "bank_account", "vendor_created", "po_amount"]
LABELS = ["is_anomaly", "anomaly_type"]
DATE_COLUMNS = ["invoice_date", "approval_date", "vendor_created"]
# Column widths from app/models.py. SQLite ignores them, but Postgres would reject the whole upload.
TEXT_LIMITS: dict[str, int] = {
    "event_id": 80, "vendor_id": 120, "invoice_number": 120, "vendor_name": 255, "category": 120, "department": 120,
    "approver_id": 120, "created_by": 120, "bank_account": 80, "anomaly_type": 60,
}
TEXT_COLUMNS = list(TEXT_LIMITS)
LABEL_VALUES = {"1": 1.0, "1.0": 1.0, "true": 1.0, "yes": 1.0, "y": 1.0, "0": 0.0, "0.0": 0.0, "false": 0.0, "no": 0.0, "n": 0.0}

UNCATEGORISED = "Uncategorised"
MIN_HISTORY = 8           # below this a vendor borrows its peer group's baseline
VENDOR_WINDOW = 500       # rolling baseline: a vendor's last 500 invoices
GROUP_WINDOW = 5_000      # and the last 5,000 for a peer group or the whole population
MAX_BAD_ROW_SHARE = 0.05  # above this the file is rejected rather than quietly thinned out
MAX_ROWS = 500_000
DUPLICATE_SCAN = 1_000    # Newest invoices checked per event, so one vendor's flood cannot go quadratic
EARLIEST_DATE = pd.Timestamp("1990-01-01")

# Severity of each rule, combined with noisy-OR into rule_score.
RULES: dict[str, float] = {
    "duplicate_invoice": 0.80, "invoice_splitting": 0.85, "sod_violation": 0.80, "bank_change": 0.75,
    "new_vendor_large": 0.65, "burst": 0.55, "off_hours_approval": 0.45, "rushed_approval": 0.45,
    "round_amount": 0.45, "near_limit": 0.20,
}
RULE_LABELS: dict[str, str] = {
    "duplicate_invoice": "Duplicate invoice", "invoice_splitting": "Invoice splitting", "sod_violation": "Segregation of duties",
    "bank_change": "Bank account change", "new_vendor_large": "New vendor, large payment", "burst": "Invoice burst",
    "off_hours_approval": "Off-hours approval", "rushed_approval": "Rushed approval", "round_amount": "Round amount",
    "near_limit": "Near approval limit",
}

_TIME_THEN_OFFSET = re.compile(r"(\d{1,2}:\d{2}(?::\d{2}(?:\.\d+)?)?)\s*(?:Z|UTC|[+-]\d{2}(?::?\d{2})?)$", re.IGNORECASE)
_NUMERIC_DATE = r"^\s*(\d{1,2})[/.\-](\d{1,2})[/.\-]\d{2,4}"


def read_csv(source: Any) -> pd.DataFrame:
    """Read every column as text; prepare() converts them after mapping.

    Letting pandas infer types here would strip leading zeros from ids and turn YYYYMMDD into 1970.
    Raises ValueError with a message fit to show to the person who uploaded the file.
    """
    for encoding in ("utf-8-sig", "cp1252"):  # Excel's default "CSV" export is cp1252
        try:
            if hasattr(source, "seek"):
                source.seek(0)
            return pd.read_csv(source, dtype=str, encoding=encoding)
        except UnicodeDecodeError:
            continue
        except pd.errors.EmptyDataError:
            raise ValueError("The file is empty") from None
        except pd.errors.ParserError as error:
            raise ValueError(f"The file could not be read as CSV: {error}") from None
    raise ValueError("The file is not UTF-8 or Windows-1252 text")


def clean_text(values: pd.Series) -> pd.Series:
    """Trim, collapse control characters and whitespace, and treat blanks as missing."""
    text = values.astype("string").str.replace(r"[\x00-\x1f\x7f\s]+", " ", regex=True).str.strip()
    return text.where(text != "")


def parse_numbers(values: pd.Series) -> pd.Series:
    """Numbers with Indian or Western grouping commas. Infinity counts as invalid."""
    text = values.astype("string").str.replace(",", "", regex=False).str.strip()
    numbers = pd.to_numeric(text.astype("object"), errors="coerce").astype(float)
    return numbers.where(np.isfinite(numbers))


def parse_labels(values: pd.Series) -> pd.Series:
    """0/1 and yes/no spellings. Anything else is unlabelled, never counted as normal."""
    return values.astype("string").str.strip().str.lower().map(LABEL_VALUES).astype(float)


def _date_fields(text: pd.Series) -> tuple[pd.Series, pd.Series]:
    fields = text.str.extract(_NUMERIC_DATE)
    return pd.to_numeric(fields[0], errors="coerce"), pd.to_numeric(fields[1], errors="coerce")


def parse_dates(values: pd.Series) -> pd.Series:
    """Text or datetimes to naive datetimes, NaT where unusable.

    Numeric dates are read day first, the Indian convention, unless the column proves otherwise.
    A UTC offset is dropped and the recorded clock time kept: off-hours rules mean the local time.
    """
    if pd.api.types.is_datetime64_any_dtype(values):
        parsed = values.dt.tz_localize(None) if values.dt.tz is not None else values
    else:
        text = values.astype("string").str.strip().str.replace(_TIME_THEN_OFFSET, r"\1", regex=True)
        first, second = _date_fields(text)
        month_first = bool((second > 12).any() and not (first > 12).any())

        def read(mask: pd.Series, **options: Any) -> pd.Series:
            return pd.to_datetime(text.where(mask).astype("object"), errors="coerce", **options)

        # ISO dates must be read on their own: pandas swaps 2025-03-04 to April when dayfirst is on.
        iso = text.str.match(r"\d{4}[-/.]\d{1,2}[-/.]\d{1,2}").fillna(False).astype(bool)
        compact = text.str.fullmatch(r"\d{8}").fillna(False).astype(bool)  # ERP style YYYYMMDD
        numeric = text.str.fullmatch(r"\d+(\.\d+)?").fillna(False).astype(bool)  # serials and epochs are not dates
        parsed = read(iso, format="mixed").fillna(read(compact, format="%Y%m%d"))
        parsed = parsed.fillna(read(~iso & ~numeric, format="mixed", dayfirst=not month_first))
    latest = pd.Timestamp.now() + pd.DateOffset(years=1)
    return parsed.where((parsed >= EARLIEST_DATE) & (parsed <= latest))


def _ambiguous_dates(values: pd.Series) -> bool:
    """True when numeric dates could be read either way and nothing in the column settles it."""
    if pd.api.types.is_datetime64_any_dtype(values):
        return False
    first, second = _date_fields(values.astype("string"))
    return bool(first.notna().any() and not (first > 12).any() and not (second > 12).any())


def validate(df: pd.DataFrame) -> dict[str, Any]:
    """Report problems before a run. A few bad rows are dropped with a warning; many reject the file."""
    errors: list[str] = []
    warnings: list[str] = []
    report: dict[str, Any] = {"rows": len(df), "errors": errors, "warnings": warnings, "ok": False,
                              "dropped_rows": 0, "missing_optional": [c for c in OPTIONAL if c not in df.columns]}
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        errors.append(f"Missing required columns: {', '.join(missing)}")
        return report
    if df.empty:
        errors.append("The file has no data rows")
        return report
    if len(df) > MAX_ROWS:
        errors.append(f"The file has {len(df):,} rows, above the limit of {MAX_ROWS:,}. Split it into smaller files.")
        return report

    amount = parse_numbers(df["amount"])
    checks = {
        "a non-numeric amount": amount.isna(), "a zero or negative amount": amount <= 0,
        "an unreadable or implausible invoice_date": parse_dates(df["invoice_date"]).isna(),
        "no event_id": clean_text(df["event_id"]).isna(), "no vendor_id": clean_text(df["vendor_id"]).isna(),
    }
    for column, limit in TEXT_LIMITS.items():
        if column in df.columns:
            checks[f"{column} longer than {limit} characters"] = clean_text(df[column]).str.len().gt(limit).fillna(False).astype(bool)

    bad = pd.Series(False, index=df.index)
    for label, mask in checks.items():
        bad |= mask
        if mask.any():
            sample = ", ".join(str(i + 2) for i in df.index[mask][:5])  # +2: header row, 1-based lines
            count = int(mask.sum())
            warnings.append(f"{count:,} row{'' if count == 1 else 's'} with {label} (e.g. line {sample})")
    if bad.mean() > MAX_BAD_ROW_SHARE:
        errors.append(f"{bad.mean():.1%} of rows are invalid, above the {MAX_BAD_ROW_SHARE:.0%} allowed")

    duplicates = int(clean_text(df["event_id"]).dropna().duplicated().sum())
    if duplicates:
        warnings.append(f"{duplicates:,} duplicate event_id values: only the first of each is kept")

    optional_checks = [("approval_date", parse_dates, "an unreadable approval_date"), ("vendor_created", parse_dates, "an unreadable vendor_created"),
                       ("processing_days", parse_numbers, "a non-numeric processing_days"), ("is_anomaly", parse_labels, "a label that is not 0/1 or yes/no")]
    for column, parser, label in optional_checks:
        if column in df.columns:
            unusable = int((clean_text(df[column]).notna() & parser(df[column]).isna()).sum())
            if unusable:
                warnings.append(f"{unusable:,} row{'' if unusable == 1 else 's'} with {label}, treated as missing")

    for column in DATE_COLUMNS:
        if column in df.columns and _ambiguous_dates(df[column]):
            warnings.append(f"{column} has dates such as 03/04/2025 that could be either order. They are read as day first. "
                            "If this file is month first, convert the column to YYYY-MM-DD.")
    for column, effect in [("approval_date", "off-hours rule disabled"), ("bank_account", "bank change rule disabled"),
                           ("created_by", "segregation of duties rule disabled"), ("vendor_created", "new vendor rule disabled"),
                           ("category", "peer baselines unavailable")]:
        if column not in df.columns:
            warnings.append(f"No {column} column: {effect}")
    report["dropped_rows"] = len(df) - len(prepare(df))
    report["ok"] = not errors
    return report


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    """Convert types, add absent optional columns as empty, drop unusable rows and sort oldest first."""
    df = df.copy()
    for column in OPTIONAL + LABELS:
        if column not in df.columns:
            df[column] = pd.NA
    for column in TEXT_COLUMNS:
        df[column] = clean_text(df[column])
    for column in DATE_COLUMNS:
        df[column] = parse_dates(df[column])
    df["amount"] = parse_numbers(df["amount"])
    df["po_amount"] = parse_numbers(df["po_amount"])
    df["is_anomaly"] = parse_labels(df["is_anomaly"])

    too_long = pd.Series(False, index=df.index)
    for column, limit in TEXT_LIMITS.items():
        too_long |= df[column].str.len().gt(limit).fillna(False).astype(bool)
    df = df[~too_long].dropna(subset=["event_id", "vendor_id", "amount", "invoice_date"])
    df = df[df["amount"] > 0].drop_duplicates("event_id")

    for column in TEXT_COLUMNS:
        df[column] = df[column].astype("object").where(df[column].notna(), None)
    df["category"] = df["category"].fillna(UNCATEGORISED)
    df["vendor_name"] = df["vendor_name"].fillna(df["vendor_id"])
    days = (df["approval_date"].dt.normalize() - df["invoice_date"].dt.normalize()).dt.days
    df["processing_days"] = parse_numbers(df["processing_days"]).fillna(days)
    return df.sort_values(["invoice_date", "event_id"], kind="stable").reset_index(drop=True)


def _quantile(values: list[float], p: float) -> float:
    position = p * (len(values) - 1)
    low = int(position)
    high = min(low + 1, len(values) - 1)
    return values[low] + (values[high] - values[low]) * (position - low)


class History:
    """The last `size` values of each measure, kept sorted so medians need no re-sorting.

    Rolling, not all-time: an all-time list grows without limit, and inserting into it goes
    quadratic for a vendor with hundreds of thousands of invoices.
    """
    __slots__ = ("size", "amount", "gap", "proc", "_order")

    def __init__(self, size: int = VENDOR_WINDOW) -> None:
        self.size = size
        self.amount: list[float] = []
        self.gap: list[float] = []
        self.proc: list[float] = []
        self._order = {"amount": deque(), "gap": deque(), "proc": deque()}

    def _push(self, name: str, value: float) -> None:
        values, order = getattr(self, name), self._order[name]
        insort(values, value)
        order.append(value)
        if len(order) > self.size:
            values.pop(bisect_left(values, order.popleft()))

    def add(self, log_amount: float, log_gap: float, proc: float) -> None:
        self._push("amount", log_amount)
        if not np.isnan(log_gap):
            self._push("gap", log_gap)
        if not np.isnan(proc):
            self._push("proc", proc)


def _centre_and_scale(values: list[float], floor: float) -> tuple[float, float]:
    """Median and robust sigma (IQR / 1.349). The floor stops very steady vendors producing huge z-scores."""
    if not values:
        return float("nan"), floor
    return _quantile(values, 0.5), max((_quantile(values, 0.75) - _quantile(values, 0.25)) / 1.349, floor)


def add_baselines(df: pd.DataFrame) -> pd.DataFrame:
    """One chronological pass. Every statistic for an event uses strictly earlier events only."""
    n = len(df)
    columns = ["base_log_amount", "base_log_scale", "base_gap", "base_proc", "gap_days", "amt_z", "freq_z", "proc_z",
               "count_7d", "history_len", "expected_week", "dup_days", "dup_amount"]
    out = {c: np.full(n, np.nan) for c in columns}
    source = np.empty(n, dtype=object)
    usual_bank = np.empty(n, dtype=object)
    dup_of = np.empty(n, dtype=object)

    vendors: dict[str, History] = defaultdict(History)
    peers: dict[str, History] = defaultdict(lambda: History(GROUP_WINDOW))
    population = History(GROUP_WINDOW)
    seen: dict[str, int] = defaultdict(int)  # all earlier invoices, beyond the rolling window
    first_date: dict[str, pd.Timestamp] = {}
    last_date: dict[str, pd.Timestamp] = {}
    fortnight: dict[str, deque] = defaultdict(deque)  # the vendor's (date, amount, event_id) in the last 14 days
    week: dict[str, deque] = defaultdict(deque)       # the vendor's dates in the last 7 days
    banks: dict[str, deque] = defaultdict(lambda: deque(maxlen=10))
    fourteen_days, seven_days = timedelta(days=14), timedelta(days=7)

    log_amounts = np.log(df["amount"].to_numpy(dtype=float))
    rows = zip(df["vendor_id"], df["category"], df["invoice_date"], df["amount"], df["processing_days"],
               df["bank_account"], df["event_id"])
    for i, (vendor, category, date, amount, proc, bank, event_id) in enumerate(rows):
        own = vendors[vendor]
        has_peers = category != UNCATEGORISED  # "no category" is not a peer group
        if len(own.amount) >= MIN_HISTORY:
            base, source[i] = own, "vendor"
        elif has_peers and len(peers[category].amount) >= MIN_HISTORY:
            base, source[i] = peers[category], "peer"
        else:
            base, source[i] = population, "global"

        med_amount, scale_amount = _centre_and_scale(base.amount, 0.15)
        med_gap, scale_gap = _centre_and_scale(base.gap, 0.25)
        med_proc, scale_proc = _centre_and_scale(base.proc, 0.75)

        gap = (date - last_date[vendor]).total_seconds() / 86400 if vendor in last_date else float("nan")
        log_gap = np.log1p(gap) if not np.isnan(gap) else float("nan")
        usual_gap = np.expm1(med_gap) if not np.isnan(med_gap) else np.nan

        out["base_log_amount"][i], out["base_log_scale"][i] = med_amount, scale_amount
        out["base_gap"][i], out["base_proc"][i], out["gap_days"][i] = usual_gap, med_proc, gap
        out["amt_z"][i] = (log_amounts[i] - med_amount) / scale_amount
        out["freq_z"][i] = (med_gap - log_gap) / scale_gap  # positive means sooner than usual
        out["proc_z"][i] = (proc - med_proc) / scale_proc   # negative means faster than usual
        out["history_len"][i] = seen[vendor]

        # A vendor's own volume, not its median gap: one billing several times a day has a median gap of zero.
        if seen[vendor] >= MIN_HISTORY:
            weeks = max((date - first_date[vendor]).days / 7, 1.0)
            out["expected_week"][i] = seen[vendor] / weeks
        elif not np.isnan(usual_gap):
            out["expected_week"][i] = 7 / max(usual_gap, 0.5)

        dates = week[vendor]
        while dates and date - dates[0] >= seven_days:
            dates.popleft()
        out["count_7d"][i] = len(dates) + 1

        window = fortnight[vendor]
        while window and date - window[0][0] > fourteen_days:
            window.popleft()
        for d, previous, previous_id in islice(reversed(window), DUPLICATE_SCAN):
            if abs(amount - previous) / max(amount, previous) <= 0.002:
                dup_of[i], out["dup_days"][i], out["dup_amount"][i] = previous_id, (date - d).days, previous
                break

        account_history = banks[vendor]
        if len(account_history) >= 2:
            usual_bank[i] = Counter(account_history).most_common(1)[0][0]

        own.add(log_amounts[i], log_gap, proc)
        if has_peers:
            peers[category].add(log_amounts[i], log_gap, proc)
        population.add(log_amounts[i], log_gap, proc)
        seen[vendor] += 1
        first_date.setdefault(vendor, date)
        last_date[vendor] = date
        dates.append(date)
        window.append((date, amount, event_id))
        if bank is not None:
            account_history.append(bank)

    for column, values in out.items():
        df[column] = values
    df["baseline_source"], df["usual_bank"], df["dup_of"] = source, usual_bank, dup_of
    df["baseline_amount"] = np.exp(df["base_log_amount"])
    df["amt_ratio"] = df["amount"] / df["baseline_amount"]
    df["burst_ratio"] = df["count_7d"] / df["expected_week"]
    df[["amt_z", "freq_z", "proc_z"]] = df[["amt_z", "freq_z", "proc_z"]].fillna(0.0)
    df["amt_ratio"] = df["amt_ratio"].fillna(1.0)
    df["burst_ratio"] = df["burst_ratio"].fillna(1.0)
    # Unknown stays unknown: the first row in a file says nothing about when a vendor was onboarded.
    df["vendor_age_days"] = (df["invoice_date"] - df["vendor_created"]).dt.days.clip(lower=0)
    return df


def add_red_flags(df: pd.DataFrame, settings: dict[str, Any]) -> pd.DataFrame:
    """Deterministic rules as flag_<name> columns, then noisy-OR into rule_score."""
    limit = float(settings["approval_limit"])
    near = df["amount"].between(0.9 * limit, limit)
    approval = df["approval_date"]
    # Decided per row, because a date-only approval sits at midnight and that is not a night-time approval.
    timed = approval.notna() & (approval != approval.dt.normalize())
    seconds = approval.dt.hour * 3600 + approval.dt.minute * 60 + approval.dt.second
    night = timed & ((approval.dt.hour < 7) | (seconds > 21 * 3600))
    weekend = approval.dt.day_of_week >= 5
    df["approval_timed"] = timed

    split_counts = pd.Series(0, index=df.index)
    for _, group in df[near].groupby("vendor_id"):
        dates = group["invoice_date"].to_numpy()
        ends = np.searchsorted(dates, dates + np.timedelta64(3, "D"), side="right")
        for start, end in enumerate(ends):
            if end - start >= 3:
                members = group.index[start:end]
                split_counts.loc[members] = np.maximum(split_counts.loc[members], int(end - start))
    df["split_count"] = split_counts

    flags = {
        "duplicate_invoice": df["dup_of"].notna(),
        "invoice_splitting": split_counts >= 3,
        "round_amount": (df["amount"] >= 10_000) & (df["amount"] % 10_000 == 0),
        "off_hours_approval": approval.notna() & (weekend | night),
        "rushed_approval": df["processing_days"].between(0, 1, inclusive="left") & (df["base_proc"] >= 2),
        "burst": (df["count_7d"] >= 3) & (df["burst_ratio"] >= 2.5),
        "new_vendor_large": (df["vendor_age_days"] < 45) & ((df["amount"] >= 0.6 * limit) | (df["amt_ratio"] >= 3)),
        "bank_change": df["bank_account"].notna() & df["usual_bank"].notna() & (df["bank_account"] != df["usual_bank"]),
        "sod_violation": df["created_by"].notna() & (df["created_by"] == df["approver_id"]),
        "near_limit": near,
    }
    enabled = settings["rules"]
    survive = np.ones(len(df))
    for name, weight in RULES.items():
        fired = flags[name].fillna(False).astype(bool) & enabled.get(name, True)
        df[f"flag_{name}"] = fired.astype(int)
        survive *= 1 - weight * fired.to_numpy()
    df["rule_score"] = 1 - survive
    df["flag_count"] = df[[f"flag_{name}" for name in RULES]].sum(axis=1)
    return df


def compute_features(df: pd.DataFrame, settings: dict[str, Any]) -> pd.DataFrame:
    df = add_baselines(prepare(df))
    df = add_red_flags(df, settings)
    # Timing fields default to neutral values so files without approvals still score.
    df["log_amount"] = np.log(df["amount"])
    df["approval_hour"] = df["approval_date"].dt.hour.where(df["approval_timed"]).fillna(12)
    df["approval_dow"] = df["approval_date"].dt.day_of_week.fillna(2)
    df["category_code"] = df["category"].astype("category").cat.codes
    df["proc_days_f"] = df["processing_days"].fillna(df["processing_days"].median()).fillna(0)
    df["gap_days_f"] = df["gap_days"].fillna(df["gap_days"].median()).fillna(0)
    df["vendor_age_f"] = df["vendor_age_days"].fillna(df["vendor_age_days"].median()).fillna(0)
    df["log_amt_ratio"] = np.log(df["amt_ratio"].clip(lower=1e-3))
    df["po_ratio"] = (df["amount"] / df["po_amount"]).fillna(1.0).clip(0, 20)
    return df


def entity_baselines(df: pd.DataFrame) -> pd.DataFrame:
    """Latest baseline per vendor, for profile pages. Uses all of a vendor's events, not a past-only slice."""
    def summarise(group: pd.DataFrame) -> pd.Series:
        accounts = group["bank_account"].dropna()
        return pd.Series({
            "entity_name": group["vendor_name"].iloc[-1], "category": group["category"].iloc[-1],
            "baseline_source": group["baseline_source"].iloc[-1],
            "median_amount": group["amount"].median(), "p25_amount": group["amount"].quantile(0.25),
            "p75_amount": group["amount"].quantile(0.75), "median_gap_days": group["gap_days"].median(),
            "median_processing_days": group["processing_days"].median(), "history_len": len(group),
            "usual_bank_account": accounts.mode().iloc[0] if len(accounts) else None,
        })
    return pd.DataFrame([summarise(g).rename(v) for v, g in df.groupby("vendor_id", sort=False)]).rename_axis("entity_id").reset_index()
