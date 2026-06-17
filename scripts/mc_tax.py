"""German tax modeling for accumulating ETFs/funds.

Vorabpauschale (advance lump-sum): annual deemed gain taxed even when no distribution.
- Computed as: NAV_start_of_year × Basiszins × 0.7 (the "70%" cap on deemed gain)
- Capped at actual annual price appreciation
- Then × Teilfreistellung (30% partial exemption for equity ETFs)
- Then × KapESt 26.375% (incl. SolZ; ignoring Kirchensteuer)

This is an APPROXIMATION — exact rules vary slightly. Used to show ballpark
tax-drag impact on terminal wealth.
"""
from __future__ import annotations

import numpy as np


KAPEST_RATE = 0.26375  # KapESt 25% + 5.5% SolZ
TEILFREISTELLUNG_EQUITY = 0.30  # 30% exemption for equity ETFs


def apply_vorabpauschale(
    wealth: np.ndarray,
    starting_eur: float,
    basiszins_per_year: float = 0.0234,
    freibetrag_eur: float = 1000.0,
    horizon_years: float = 15.0,
) -> np.ndarray:
    """Approximate Vorabpauschale by deducting tax at each year-end on deemed gain.

    Deemed gain = NAV_jan × basiszins × 0.7
    Actual gain = NAV_dec - NAV_jan (per path)
    Lesser of the two is taxed × (1 - Teilfreistellung) × KapESt
    Freibetrag of €1,000 sheltered first.

    Returns wealth array net of cumulative tax deductions.
    """
    P, T1 = wealth.shape
    days_per_year = (T1 - 1) / horizon_years
    out = wealth.copy().astype(np.float64)
    tax_cumulative = np.zeros(P)

    for yr in range(1, int(horizon_years) + 1):
        idx_start = int((yr - 1) * days_per_year)
        idx_end = int(yr * days_per_year)
        if idx_end >= T1:
            idx_end = T1 - 1
        nav_start = out[:, idx_start]
        nav_end = out[:, idx_end]
        deemed = nav_start * basiszins_per_year * 0.7
        actual = np.maximum(nav_end - nav_start, 0)
        taxable_gain = np.minimum(deemed, actual)
        taxable_gain *= (1 - TEILFREISTELLUNG_EQUITY)
        # Apply Freibetrag (annual €1k allowance)
        taxable_gain = np.maximum(taxable_gain - freibetrag_eur, 0)
        tax = taxable_gain * KAPEST_RATE
        # Deduct from wealth at year-end
        out[:, idx_end:] -= tax[:, np.newaxis]
        tax_cumulative += tax

    return out
