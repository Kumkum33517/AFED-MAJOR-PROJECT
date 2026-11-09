"""Stack every processed dataset into data/processed/unified.parquet and record checksums of the raw downloads.

    python build_unified.py

Real and synthetic rows stay distinguishable by `source_dataset` and `is_synthetic`. Injected anomalies are
never written here; they exist only inside evaluation runs.
The data itself is not committed (several licences forbid it): only scripts and data/checksums.sha256.
"""
import hashlib

import pandas as pd

from common import COLUMNS, DATA, PROCESSED, RAW

OWN = ["nspcl", "mplads", "bbmp_2024", "bbmp_2010_2019", "cppp", "ocds_hp", "ocds_assam", "delaware", "secop", "chicago", "icai"]


def checksums() -> None:
    lines = []
    for name in OWN:
        for path in sorted((RAW / name).rglob("*")) if (RAW / name).exists() else []:
            if path.is_file() and not path.name.endswith(".part"):
                lines.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  raw/{path.relative_to(RAW)}")
    (DATA / "checksums.sha256").write_text("\n".join(lines) + "\n")
    print(f"{len(lines)} raw files checksummed -> data/checksums.sha256")


def main() -> None:
    parts = [pd.read_parquet(p) for p in sorted(PROCESSED.glob("*.parquet")) if p.stem != "unified"]
    unified = pd.concat(parts, ignore_index=True)[COLUMNS]
    assert unified["event_id"].is_unique, "event ids must be unique across datasets"
    unified.to_parquet(PROCESSED / "unified.parquet", index=False)
    summary = unified.groupby("source_dataset").agg(
        events=("event_id", "size"), entities=("entity_id", "nunique"), synthetic=("is_synthetic", "first"),
        labelled=("label", lambda s: int(s.notna().sum())), first=("event_timestamp", "min"), last=("event_timestamp", "max"),
        currency=("currency", "first"))
    long = unified.groupby(["source_dataset", "entity_id"]).size().ge(24).groupby(level=0).sum()
    summary["entities_24_plus"] = long
    print(summary.to_string())
    print(f"\nunified: {len(unified):,} events -> {PROCESSED / 'unified.parquet'}")
    checksums()


if __name__ == "__main__":
    main()
