"""Colombia SECOP II electronic contracts (Socrata jbjy-vk9h on datos.gov.co). Licence: CC BY-SA 4.0, so any derived
data keeps that licence; only this script is committed.

Source: https://www.datos.gov.co/Gastos-Gubernamentales/SECOP-II-Contratos-Electr-nicos/jbjy-vk9h (5.7M contracts).
Privacy: only these columns are ever requested, so personal fields (individuals' ID numbers, legal representatives,
bank account numbers, supervisor names) are never downloaded. Only company suppliers (document type NIT) are used,
and their tax numbers are hashed all the same.
Subset: contracts signed from 1 Jan 2022, from a seeded random sample of suppliers with 24 to 5,000 contracts.
Events are contract signatures (not payments); processing_time_days is signature to contract start.
Amounts are Colombian pesos, converted to INR at the documented rate in common.py.
"""
import json

import pandas as pd

from common import RAW, finish, get, hashed, socrata

BASE, DATASET = "https://www.datos.gov.co", "jbjy-vk9h"
WHERE = "tipodocproveedor = 'NIT' AND fecha_de_firma >= '2022-01-01' AND valor_del_contrato > 0"
COLUMNS = "id_contrato, documento_proveedor, nit_entidad, sector, valor_del_contrato, fecha_de_firma, fecha_de_inicio_del_contrato"
MIN_CONTRACTS, MAX_CONTRACTS, TARGET_ROWS, SEED = 24, 5_000, 300_000, 42


def sampled_suppliers() -> list[str]:
    path = RAW / "secop" / "supplier_sample.json"
    if path.exists():
        return json.loads(path.read_text())
    counts = get(f"{BASE}/resource/{DATASET}.json", timeout=900, params={
        "$select": "documento_proveedor, count(*) as n", "$where": WHERE, "$group": "documento_proveedor",
        "$having": f"count(*) >= {MIN_CONTRACTS}", "$limit": 500_000}).json()
    frame = pd.DataFrame(counts).assign(n=lambda d: d["n"].astype(int))
    eligible = frame[frame["n"] <= MAX_CONTRACTS].sample(frac=1, random_state=SEED)
    chosen = eligible[eligible["n"].cumsum() <= TARGET_ROWS]["documento_proveedor"].tolist()
    print(f"{len(frame):,} suppliers have {MIN_CONTRACTS}+ contracts; sampled {len(chosen):,}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(chosen))
    return chosen


def main() -> None:
    suppliers = sampled_suppliers()
    frames = []
    for start in range(0, len(suppliers), 25):  # long IN lists make this server answer 503
        ids = ", ".join("'" + s.replace("'", "''") + "'" for s in suppliers[start:start + 25])
        frames.append(socrata(BASE, DATASET, {"$select": COLUMNS, "$where": f"{WHERE} AND documento_proveedor IN ({ids})", "$order": ":id"},
                              RAW / "secop" / f"contracts_{start // 25:04d}.csv"))
    raw = pd.concat(frames, ignore_index=True).drop_duplicates()
    signed = pd.to_datetime(raw["fecha_de_firma"], errors="coerce")
    started = pd.to_datetime(raw["fecha_de_inicio_del_contrato"], errors="coerce")
    lag = (started - signed).dt.days
    df = pd.DataFrame({
        "event_id": "SECOP-" + raw["id_contrato"].astype(str),
        "entity_id": hashed(raw["documento_proveedor"].str.strip(), "secop"),
        "counterparty_id": "CO-" + raw["nit_entidad"].astype(str), "amount": raw["valor_del_contrato"],
        "event_timestamp": signed, "processing_time_days": lag.where(lag >= 0), "category": raw["sector"],
    })
    finish(df, "secop", "COP", "supplier")


if __name__ == "__main__":
    main()
