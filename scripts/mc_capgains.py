"""Capital gains tax modeling for German equity ETF withdrawals.

Average-cost method for basis tracking (close approximation to FIFO):
- Each contribution increases basis €1-for-€1
- Each withdrawal reduces basis proportional to fraction of wealth withdrawn
- Realized gain at sale = withdraw_eur - basis_proportional_chunk
- Tax = realized_gain × (1 - Teilfreistellung 30%) × Abgeltungsteuer 26.375%
- Subtract Vorabpauschale already paid (avoids double-taxation per § 19 InvStG)
"""
from __future__ import annotations

import numpy as np


TEILFREISTELLUNG_EQUITY = 0.30
ABGELTUNGSTEUER = 0.26375  # KapESt 25% + SolZ 5.5%


def compute_realized_gain_tax(
    withdraw_eur: np.ndarray,    # (P,) — amount withdrawn this event
    wealth_before: np.ndarray,    # (P,) — wealth right before withdrawal
    basis_before: np.ndarray,     # (P,) — cost basis before withdrawal
    vorab_paid_offset: np.ndarray | None = None,  # (P,) — Vorab already paid against this slice
) -> np.ndarray:
    """Compute Abgeltungsteuer on the realized portion of a withdrawal.

    Returns (P,) tax amounts to deduct from withdrawals (or end-state wealth at lump-sum sale).
    """
    P = withdraw_eur.shape[0]
    # Fraction of wealth being liquidated
    withdraw_frac = np.minimum(withdraw_eur / np.maximum(wealth_before, 1e-9), 1.0)
    # Basis chunk being liquidated (average-cost)
    basis_chunk = basis_before * withdraw_frac
    # Realized gain
    gain = withdraw_eur - basis_chunk
    gain = np.maximum(gain, 0)  # losses don't trigger refund here

    tax_before_offset = gain * (1 - TEILFREISTELLUNG_EQUITY) * ABGELTUNGSTEUER

    if vorab_paid_offset is not None:
        # Vorab credit applies (reduces sale-time tax). Don't go negative.
        tax = np.maximum(tax_before_offset - vorab_paid_offset, 0)
    else:
        tax = tax_before_offset

    return tax


def apply_lump_sum_sale_tax(
    wealth: np.ndarray,
    basis: np.ndarray,
    cumulative_vorab_paid: np.ndarray | None,
    sale_day: int,
) -> np.ndarray:
    """At sale_day, apply Abgeltungsteuer on full realized gain. Returns net wealth.

    wealth, basis are (P, T+1). cumulative_vorab_paid is (P,) total Vorab paid.
    Returns wealth modified in-place: tax deducted on and after sale_day.
    """
    wealth_at = wealth[:, sale_day]
    basis_at = basis[:, sale_day]
    full_withdraw = wealth_at.copy()
    tax = compute_realized_gain_tax(full_withdraw, wealth_at, basis_at, cumulative_vorab_paid)
    wealth = wealth.copy()
    wealth[:, sale_day:] -= tax[:, np.newaxis]
    return wealth


def estimate_vorab_paid_during_phase(
    wealth: np.ndarray,
    horizon_years: float,
    basiszins: float = 0.0234,
    freibetrag_eur: float = 1000.0,
    until_day: int | None = None,
) -> np.ndarray:
    """Estimate cumulative Vorabpauschale paid per path by `until_day`.

    Mirrors mc_tax.apply_vorabpauschale but accumulates only, doesn't modify wealth.
    """
    P, T1 = wealth.shape
    if until_day is None:
        until_day = T1 - 1
    days_per_year = (T1 - 1) / horizon_years
    cum = np.zeros(P, dtype=np.float64)
    for yr in range(1, int(horizon_years) + 1):
        idx_start = int((yr - 1) * days_per_year)
        idx_end = int(yr * days_per_year)
        if idx_end > until_day:
            break
        nav_start = wealth[:, idx_start]
        nav_end = wealth[:, idx_end]
        deemed = nav_start * basiszins * 0.7
        actual = np.maximum(nav_end - nav_start, 0)
        taxable_gain = np.minimum(deemed, actual) * (1 - TEILFREISTELLUNG_EQUITY)
        taxable_gain = np.maximum(taxable_gain - freibetrag_eur, 0)
        cum += taxable_gain * ABGELTUNGSTEUER
    return cum


if __name__ == "__main__":
    # Sanity test
    P = 1000
    wealth_before = np.full(P, 50000.0)
    basis_before = np.full(P, 30000.0)  # €30k contributions, €20k gain
    withdraw_eur = np.full(P, 50000.0)  # withdraw all
    tax = compute_realized_gain_tax(withdraw_eur, wealth_before, basis_before)
    expected = 20000 * 0.70 * 0.26375
    print(f"Lump-sum sale: gain €20k → tax = €{tax.mean():.0f}  (expected €{expected:.0f})")
