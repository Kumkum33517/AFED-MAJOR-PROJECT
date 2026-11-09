"""Download public datasets used by AFED (no token needed; set HF_TOKEN for gated ones).

  python scripts/download_datasets.py            # procurement sets (small)
  python scripts/download_datasets.py --paysim   # + PaySim (~470 MB)
"""
import os, sys, urllib.error, urllib.request
from getpass import getpass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "data" / "raw"
HF = "https://huggingface.co/datasets/{repo}/resolve/main/{path}"
SETS = {
    # real DC government vendor payments, 53k rows: vendor, agency, amount, date  -> entity baselines
    "dc_procurement": ("abigailhaddad/dc-procurement-raw", ["archive/parquet/contract_payments.parquet"]),
    # synthetic procure-to-pay sample: suppliers, POs, invoices, payments -> schema reference
    "mindweave_p2p": ("mindweave/purchasing-procurement-us", [f"data/{t}.csv" for t in
        "suppliers supplier_invoices supplier_payments purchase_orders purchase_order_lines goods_receipts companies".split()]),
}
if "--paysim" in sys.argv:  # classic labelled fraud benchmark, for the paper's comparison section
    SETS["paysim"] = ("purulalwani/Synthetic-Financial-Datasets-For-Fraud-Detection", ["financial_txns.parquet"])


def fetch(url):
    """Open a Hugging Face URL, asking for a token in the terminal if the dataset turns out to need one."""
    def attempt():
        req = urllib.request.Request(url)
        if os.getenv("HF_TOKEN"): req.add_header("Authorization", f"Bearer {os.environ['HF_TOKEN']}")
        return urllib.request.urlopen(req, timeout=120)
    try:
        return attempt()
    except urllib.error.HTTPError as error:
        if error.code not in (401, 403) or not sys.stdin.isatty(): raise
        os.environ["HF_TOKEN"] = getpass("This dataset needs a Hugging Face token (input hidden): ").strip()
        return attempt()


for name, (repo, files) in SETS.items():
    for f in files:
        dest = ROOT / name / Path(f).name
        if dest.exists():
            print("skip", dest); continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        print("get ", repo, f)
        partial = dest.with_suffix(dest.suffix + ".part")  # an interrupted download must not look finished
        with fetch(HF.format(repo=repo, path=f)) as r, open(partial, "wb") as out:
            out.write(r.read())
        partial.replace(dest)
print("done ->", ROOT)
