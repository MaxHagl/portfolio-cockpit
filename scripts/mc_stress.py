"""Deterministic historical stress replay.

For each named episode (2000, 2008, 2020), reconstruct what the current portfolio
weights would have done using proxy indices for each holding. Outputs peak drawdown,
days to trough, days to recovery.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from mc_data import load_index, to_business_day_returns


# Stress windows (extended for recovery measurement)
EPISODES = {
    "dotcom2000":  ("2000-01-03", "2007-05-31",  "Dotcom collapse + recovery (2000-2007)"),
    "gfc2008":     ("2007-10-09", "2013-03-28",  "Global Financial Crisis + recovery (2007-2013)"),
    "covid2020":   ("2020-01-02", "2021-12-31",  "COVID crash + V-shape recovery (2020-2021)"),
}


# Episode-specific proxy mapping. Choose proxies that cover full window.
# For 2000: only SPX/NDX have data → can't separate EM, lump in
# For 2008: IXN exists, EEM exists → use full mapping
# For 2020: full mapping works fine
EPISODE_MAPPING = {
    "dotcom2000": {
        "VWCE":   "SPX",
        "SWDA":   "SPX",
        "BGF":    "NDX",
        "XDWT":   "NDX",
        "A3DRHJ": "SPX",  # No EM index pre-2003 — use SPX as substitute
    },
    "gfc2008": {
        "VWCE":   "SPX",   # URTH starts 2012, use SPX
        "SWDA":   "SPX",
        "BGF":    "IXN",
        "XDWT":   "IXN",
        "A3DRHJ": "EEM",
    },
    "covid2020": {
        "VWCE":   "URTH",
        "SWDA":   "URTH",
        "BGF":    "IXN",
        "XDWT":   "IXN",
        "A3DRHJ": "EEM",
    },
}


def run_stress_replay(weights: dict[str, float], starting_eur: float) -> dict:
    """Replay each episode on the synthetic portfolio."""
    results = {}
    for ep_key, (start, end, desc) in EPISODES.items():
        port_rets = _build_episode_portfolio_returns(weights, start, end, ep_key)
        if port_rets is None or len(port_rets) < 30:
            results[ep_key] = {
                "description": desc,
                "available": False,
                "note": "insufficient proxy data for this window",
            }
            continue
        wealth = starting_eur * np.cumprod(1 + port_rets.values)
        peak = np.maximum.accumulate(wealth)
        dd = wealth / peak - 1
        trough_idx = int(np.argmin(dd))
        peak_idx_at_trough = int(np.argmax(wealth[:trough_idx + 1]))
        peak_dd = float(dd[trough_idx])

        # Days to recover (find first day after trough where wealth >= peak before trough)
        peak_value = wealth[peak_idx_at_trough]
        recovery_idx = None
        for i in range(trough_idx, len(wealth)):
            if wealth[i] >= peak_value:
                recovery_idx = i
                break

        days_to_trough = trough_idx - peak_idx_at_trough
        days_to_recover = (recovery_idx - peak_idx_at_trough) if recovery_idx else None
        terminal_eur = float(wealth[-1])

        results[ep_key] = {
            "description": desc,
            "available": True,
            "windowStart": str(port_rets.index[0].date()),
            "windowEnd": str(port_rets.index[-1].date()),
            "peakDrawdown": peak_dd,
            "daysToTrough": days_to_trough,
            "daysToRecover": days_to_recover,
            "terminalEur": terminal_eur,
            "peakEur": float(peak_value),
            "troughEur": float(wealth[trough_idx]),
        }
    return results


def _build_episode_portfolio_returns(
    weights: dict[str, float], start: str, end: str, ep_key: str
) -> pd.Series | None:
    """Build daily portfolio returns over the episode window using episode-specific proxies."""
    mapping = EPISODE_MAPPING.get(ep_key, EPISODE_MAPPING["covid2020"])
    aligned = {}
    for hid, w in weights.items():
        if w == 0:
            continue
        ix_id = mapping.get(hid, "SPX")
        rets = to_business_day_returns(load_index(ix_id))
        rets = rets.loc[start:end]
        if len(rets) > 0:
            aligned[hid] = rets

    if not aligned:
        return None
    df = pd.concat(aligned, axis=1, join="inner").dropna(how="any")
    if len(df) == 0:
        return None
    # Weight each column
    weight_arr = np.array([weights[c] for c in df.columns])
    weight_arr = weight_arr / weight_arr.sum()  # normalize for missing holdings
    port = (df.values * weight_arr).sum(axis=1)
    return pd.Series(port, index=df.index)
