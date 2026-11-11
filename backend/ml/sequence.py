"""Change and trend features per vendor (v2, behind settings["sequence_features"]). Earlier events only.

Every value at an event uses that event and the vendor's earlier events, never a later one, so scoring a batch
gives each event the value it would have had on the day it arrived. tests/test_afed.py checks this by truncating.

  seq_amt_ewma_z   log amount against an exponentially weighted mean and spread of the vendor's earlier amounts
  seq_amt_cusum    one-sided CUSUM of amount z-scores (amt_z): small rises that persist add up (slow drift)
  seq_gap_ewma_z   log gap against the weighted mean and spread of earlier gaps; negative means sooner
  seq_gap_cusum    one-sided CUSUM of "sooner than usual" z-scores (freq_z): a lasting rise in billing frequency
  seq_amt_trend    least-squares slope of log amount over the last 6 invoices, per invoice
  seq_gap_ratio    this gap over the median of the vendor's earlier gaps
"""
import numpy as np
import pandas as pd

SEQUENCE_FEATURES = ["seq_amt_ewma_z", "seq_amt_cusum", "seq_gap_ewma_z", "seq_gap_cusum", "seq_amt_trend", "seq_gap_ratio"]
ALPHA = 2 / (8 + 1)   # EWMA span of 8 invoices
SLACK = 0.5           # CUSUM allowance, in z units: steady noise does not accumulate
TREND_WINDOW = 6
MIN_SPREAD = 0.05     # floor on the EWMA spread, as for the baselines, so very steady vendors do not explode


def _ewma_z(values: pd.Series, vendors: pd.Series) -> pd.Series:
    """(value - EWMA of earlier values) / EW spread of earlier values, 0 while there is no earlier value."""
    earlier = values.groupby(vendors).shift(1)
    grouped = earlier.groupby(vendors)
    mean = grouped.transform(lambda s: s.ewm(alpha=ALPHA, ignore_na=True).mean())
    spread = grouped.transform(lambda s: s.ewm(alpha=ALPHA, ignore_na=True).std()).fillna(0).clip(lower=MIN_SPREAD)
    return ((values - mean) / spread).fillna(0.0)


def _cusum(z: np.ndarray, positions: dict) -> np.ndarray:
    out = np.zeros(len(z))
    for rows in positions.values():
        total = 0.0
        for i in rows:
            total = max(0.0, total + z[i] - SLACK)
            out[i] = total
    return out


def _trend(log_amount: pd.Series, vendors: pd.Series) -> pd.Series:
    index = log_amount.groupby(vendors).cumcount().astype(float)
    xy = index * log_amount
    roll = lambda s: s.groupby(vendors).transform(lambda g: g.rolling(TREND_WINDOW, min_periods=3).sum())  # noqa: E731
    n = log_amount.groupby(vendors).transform(lambda g: g.rolling(TREND_WINDOW, min_periods=3).count())
    sx, sy, sxy, sxx = roll(index), roll(log_amount), roll(xy), roll(index ** 2)
    denominator = n * sxx - sx ** 2
    return ((n * sxy - sx * sy) / denominator.where(denominator > 0)).fillna(0.0)


def add_sequence_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add SEQUENCE_FEATURES to a frame from compute_features (chronological, with amt_z, freq_z and gap_days)."""
    df = df.copy()
    vendors = df["vendor_id"]
    log_amount = np.log(df["amount"].astype(float))
    log_gap = np.log1p(df["gap_days"].astype(float))
    positions = df.groupby("vendor_id", sort=False).indices
    df["seq_amt_ewma_z"] = _ewma_z(log_amount, vendors)
    df["seq_gap_ewma_z"] = _ewma_z(log_gap, vendors)
    df["seq_amt_cusum"] = _cusum(df["amt_z"].fillna(0).to_numpy(dtype=float), positions)
    df["seq_gap_cusum"] = _cusum(df["freq_z"].fillna(0).to_numpy(dtype=float), positions)
    df["seq_amt_trend"] = _trend(log_amount, vendors)
    earlier_median = df["gap_days"].groupby(vendors).transform(lambda s: s.shift(1).expanding().median())
    df["seq_gap_ratio"] = (df["gap_days"] / earlier_median.clip(lower=0.5)).fillna(1.0).clip(0, 50)
    return df
