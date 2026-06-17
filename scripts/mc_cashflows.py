"""Cashflow schedule builders for accumulation + decumulation phases.

Produces (T+1,) EUR arrays compatible with simulate_portfolio_wealth's `cashflows` param.
"""
from __future__ import annotations

import numpy as np

TRADING_DAYS_PER_YEAR = 252
DAYS_PER_MONTH = 21  # trading days


def build_dca_schedule(
    monthly_eur: float,
    horizon_days: int,
    salary_growth_annual: float = 0.0,
    broker_fee_per_contribution: float = 0.0,
    start_day: int = 21,
) -> np.ndarray:
    """Build monthly DCA contribution schedule.

    Args:
        monthly_eur: base monthly contribution in EUR
        horizon_days: simulation length
        salary_growth_annual: contribution grows by this rate annually (e.g. 0.03 = +3%/yr)
        broker_fee_per_contribution: fee deducted per execution
        start_day: first contribution at day start_day (default 21 = end of first month)

    Returns:
        (horizon_days + 1,) array of net EUR contributions per day
    """
    cf = np.zeros(horizon_days + 1, dtype=np.float64)
    month = 0
    for day in range(start_day, horizon_days + 1, DAYS_PER_MONTH):
        year_frac = month / 12.0
        contribution = monthly_eur * (1 + salary_growth_annual) ** year_frac
        cf[day] = max(0, contribution - broker_fee_per_contribution)
        month += 1
    return cf


def build_withdrawal_schedule(
    strategy: str,
    horizon_days: int,
    withdrawal_start_day: int,
    monthly_eur: float = 1500.0,
    rule_pct: float = 0.04,
    year15_wealth: float | None = None,
    inflation_path: np.ndarray | None = None,
) -> np.ndarray:
    """Build withdrawal schedule for decumulation phase.

    Args:
        strategy: 'fourPctRule' | 'fixed1500' | 'fixed3000' | 'fixed5000'
        horizon_days: simulation length (typically 30y × 252 = 7560)
        withdrawal_start_day: day index when withdrawals begin (e.g., 15 × 252 = 3780)
        monthly_eur: monthly amount for fixed strategies
        rule_pct: % rule fraction (4% rule = 0.04)
        year15_wealth: wealth at withdrawal_start_day used to compute % rule amount
        inflation_path: optional (horizon_days+1,) deflator for inflation-indexing

    Returns:
        (horizon_days + 1,) array of net negative EUR amounts per day
    """
    cf = np.zeros(horizon_days + 1, dtype=np.float64)

    if strategy == "fourPctRule":
        if year15_wealth is None:
            raise ValueError("year15_wealth required for fourPctRule")
        annual_amount = year15_wealth * rule_pct
        monthly = annual_amount / 12.0
    elif strategy == "fixed1500":
        monthly = 1500.0
    elif strategy == "fixed3000":
        monthly = 3000.0
    elif strategy == "fixed5000":
        monthly = 5000.0
    elif strategy == "fixedCustom":
        monthly = monthly_eur
    else:
        raise ValueError(f"unknown strategy: {strategy}")

    month_idx = 0
    for day in range(withdrawal_start_day, horizon_days + 1, DAYS_PER_MONTH):
        amt = monthly
        if inflation_path is not None and day < len(inflation_path):
            amt = monthly * inflation_path[day]
        cf[day] = -amt
        month_idx += 1
    return cf


# Per-broker Sparplan execution fees (EUR per contribution)
BROKER_FEES = {
    "tradeRepublic":   0.00,
    "vrBayernUnder31": 0.00,
    "ingDiba":         1.50,
    "comdirect":       1.50,
    "scalable":        0.00,
    "consorsbank":     1.50,
}


def combine_cashflows(*flows: np.ndarray) -> np.ndarray:
    """Element-wise sum of cashflow arrays (e.g., contributions + withdrawals)."""
    if not flows:
        raise ValueError("need at least one cashflow array")
    result = np.zeros_like(flows[0])
    for f in flows:
        result += f
    return result


if __name__ == "__main__":
    # Sanity checks
    horizon = 15 * 252
    dca = build_dca_schedule(50.0, horizon)
    print(f"DCA €50/mo × 15y: total contributions = €{dca.sum():.0f}  (expected ~€9,000)")

    dca_grow = build_dca_schedule(50.0, horizon, salary_growth_annual=0.03)
    print(f"DCA €50 grow 3%/yr: total = €{dca_grow.sum():.0f}  (expected ~€11,300)")

    dca_fee = build_dca_schedule(50.0, horizon, broker_fee_per_contribution=1.50)
    print(f"DCA €50 - €1.50 fee × 180: total = €{dca_fee.sum():.0f}  (expected €{180*(50-1.50)})")

    horizon30 = 30 * 252
    wd = build_withdrawal_schedule("fixed1500", horizon30, withdrawal_start_day=15*252)
    print(f"€1500/mo withdrawal years 15-30: total = €{-wd.sum():.0f}  (expected €{1500*12*15:,})")

    wd_4pct = build_withdrawal_schedule("fourPctRule", horizon30,
                                         withdrawal_start_day=15*252, year15_wealth=200000)
    print(f"4% rule on €200k: monthly = €{-wd_4pct[15*252]:.0f}  (expected ~€{200000*0.04/12:.0f})")
