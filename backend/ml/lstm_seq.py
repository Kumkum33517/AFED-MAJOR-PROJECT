"""Shared sequence model over every vendor's recent events.

forecast (default): reads the previous W events and predicts the current one.
autoencoder:        reconstructs a window ending at the current event, kept for comparison.
Either way the output is a per-feature squared error, the event's temporal deviation.
"""
from typing import Any

import numpy as np
import pandas as pd

try:
    import torch
    from torch import nn
except ImportError:  # The pipeline still runs without torch, minus the temporal signal.
    torch = None

SEQ_FEATURES = ["amt_z", "freq_z", "proc_z"]
CLIP = 6.0
HIDDEN = 32


def build_windows(df: pd.DataFrame, window: int) -> tuple[np.ndarray, np.ndarray]:
    """Return (n, window, 3) past events per row and (n, 3) current events, scaled to [-1, 1].

    `df` is chronological, so each vendor's positions are already in order. Short histories are zero-padded on the left.
    """
    values = (df[SEQ_FEATURES].to_numpy(dtype=np.float32).clip(-CLIP, CLIP)) / CLIP
    past = np.zeros((len(df), window, len(SEQ_FEATURES)), dtype=np.float32)
    for positions in df.groupby("vendor_id", sort=False).indices.values():
        for k, row in enumerate(positions):
            history = positions[max(0, k - window):k]
            if len(history):
                past[row, window - len(history):] = values[history]
    return past, values


if torch is not None:
    class Forecaster(nn.Module):
        def __init__(self, n_features: int) -> None:
            super().__init__()
            self.lstm = nn.LSTM(n_features, HIDDEN, num_layers=2, batch_first=True)
            self.head = nn.Linear(HIDDEN, n_features)

        def forward(self, x: "torch.Tensor") -> "torch.Tensor":
            return self.head(self.lstm(x)[0][:, -1])

    class Autoencoder(nn.Module):
        def __init__(self, n_features: int) -> None:
            super().__init__()
            self.encoder = nn.LSTM(n_features, HIDDEN // 2, batch_first=True)
            self.decoder = nn.LSTM(HIDDEN // 2, HIDDEN // 2, batch_first=True)
            self.head = nn.Linear(HIDDEN // 2, n_features)

        def forward(self, x: "torch.Tensor") -> "torch.Tensor":
            summary = self.encoder(x)[1][0][-1]
            repeated = summary.unsqueeze(1).repeat(1, x.shape[1], 1)
            return self.head(self.decoder(repeated)[0])


def run_lstm(df: pd.DataFrame, window: int = 10, mode: str = "forecast", epochs: int = 12,
             seed: int = 42, train_rows: np.ndarray | None = None) -> dict[str, Any]:
    """Train on this run's events (or only on `train_rows`, a boolean mask) and return predictions, errors and weights.

    Every event is scored either way. Training on the earlier events only (v2 evidence) keeps the later period
    out of the model that judges it.
    """
    n = len(SEQ_FEATURES)
    if torch is None:
        return {"available": False, "pred": np.zeros((len(df), n)), "errors": np.zeros((len(df), n)), "state": None}

    torch.manual_seed(seed)
    past, current = build_windows(df, window)
    if mode == "autoencoder":
        x = torch.from_numpy(np.concatenate([past[:, 1:], current[:, None, :]], axis=1))
        target, model = x, Autoencoder(n)
    else:
        x, target, model = torch.from_numpy(past), torch.from_numpy(current), Forecaster(n)

    optimiser = torch.optim.Adam(model.parameters(), lr=3e-3)
    loss_fn = nn.MSELoss()
    model.train()
    pool = None if train_rows is None else torch.from_numpy(np.flatnonzero(train_rows))
    for _ in range(epochs):
        order = torch.randperm(len(x)) if pool is None else pool[torch.randperm(len(pool))]
        for batch in order.split(256):
            optimiser.zero_grad()
            loss_fn(model(x[batch]), target[batch]).backward()
            optimiser.step()

    model.eval()
    with torch.no_grad():
        output = torch.cat([model(chunk) for chunk in x.split(4096)]).numpy()
    prediction = output[:, -1, :] if mode == "autoencoder" else output
    prediction = prediction * CLIP
    actual = current * CLIP
    return {"available": True, "pred": prediction, "errors": (prediction - actual) ** 2, "state": model.state_dict()}
