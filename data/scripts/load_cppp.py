"""Central Public Procurement Portal (CPPP) awards of contract, as scraped and published on Hugging Face.

Source: https://huggingface.co/datasets/rumourscape/tenders (4,921,960 award records, 2011-2026). The uploader
declares CC BY 4.0; the source portals' own terms are not stated, so only this script is committed.
Size: the full parquet is 1.72 GB. Only seven columns are read (about 280 MB), fetched by HTTP range requests
from each parquet file and cached per file, so an interrupted run resumes.
Events are contract awards, not payments. Bidders are matched by a normalised name (no bidder id is published),
then pseudonymised; the buying organisation is the counterparty.
"""
import io
import json

import pandas as pd
import pyarrow.parquet as pq

from common import RAW, finish, get, hashed, normalise_name

PARQUET_INDEX = "https://datasets-server.huggingface.co/parquet?dataset=rumourscape/tenders"
COLUMNS = ["tender_id", "selected_bidder", "organisation_name", "contract_value_amount", "contract_at", "aoc_at", "tender_type"]


class RangeReader(io.RawIOBase):
    """A seekable file over HTTP range requests, so only the requested columns are transferred."""

    def __init__(self, url: str, size: int) -> None:
        self.url, self.size, self.pos = url, size, 0

    def seekable(self) -> bool:
        return True

    def readable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.pos

    def seek(self, offset: int, whence: int = 0) -> int:
        self.pos = offset if whence == 0 else self.pos + offset if whence == 1 else self.size + offset
        return self.pos

    def readinto(self, buffer: bytearray) -> int:
        count = min(len(buffer), self.size - self.pos)
        if count <= 0:
            return 0
        data = get(self.url, headers={"Range": f"bytes={self.pos}-{self.pos + count - 1}"}, timeout=120).content[:count]
        buffer[:len(data)] = data
        self.pos += len(data)
        return len(data)


def main() -> None:
    files = get(PARQUET_INDEX, timeout=60).json()["parquet_files"]
    parts = []
    for number, info in enumerate(files):
        cached = RAW / "cppp" / f"part_{number}.parquet"
        if not cached.exists():
            cached.parent.mkdir(parents=True, exist_ok=True)
            # Unbuffered on purpose: a read-ahead buffer would re-download a large block on every seek. With
            # pre_buffer, Arrow requests exactly the needed column chunks and merges neighbouring ranges.
            reader = RangeReader(info["url"], info["size"])
            pq.ParquetFile(reader, pre_buffer=True).read(columns=COLUMNS).to_pandas().to_parquet(cached, index=False)
            print(f"  part {number + 1} of {len(files)} cached", flush=True)
        parts.append(pd.read_parquet(cached))
    (RAW / "cppp" / "parquet_index.json").write_text(json.dumps(files))
    raw = pd.concat(parts, ignore_index=True).drop_duplicates()
    bidder = normalise_name(raw["selected_bidder"].fillna(""))
    when = pd.to_datetime(raw["contract_at"].fillna(raw["aoc_at"]), errors="coerce", format="mixed")
    df = pd.DataFrame({
        "event_id": "CPPP-" + raw["tender_id"].astype(str) + "-" + raw.groupby("tender_id").cumcount().astype(str),
        "entity_id": hashed(bidder.where(bidder != ""), "cppp"),
        "counterparty_id": hashed(raw["organisation_name"].str.strip().str.upper(), "cppp-org"),
        "amount": raw["contract_value_amount"], "event_timestamp": when, "category": raw["tender_type"],
    })
    finish(df, "cppp", "INR", "supplier")


if __name__ == "__main__":
    main()
