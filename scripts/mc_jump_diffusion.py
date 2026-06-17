"""Jump-diffusion overlay: add Poisson crash events to existing return paths.

Models tail risk via discrete jumps:
- λ = 3 crashes per year (Poisson arrival)
- Jump magnitude ~ N(-3%, 1.5%)
- Applied multiplicatively to entire portfolio return on jump days

Used as an overlay on bootstrap paths to test "what if dotcom-like crashes happen
more often than the post-2014 sample suggests."
"""
from __future__ import annotations

import numpy as np

TRADING_DAYS_PER_YEAR = 252


def apply_jump_overlay(
    daily_paths: np.ndarray,
    seed: int,
    jumps_per_year: float = 3.0,
    jump_mean: float = -0.03,
    jump_std: float = 0.015,
) -> np.ndarray:
    """Add Poisson-arrival jumps to paths.

    Args:
        daily_paths: (n_paths, horizon_days, n_assets) base returns
        jumps_per_year: λ for Poisson process
        jump_mean: mean jump return (negative = crash)
        jump_std: std of jump return

    Returns: paths_with_jumps, same shape, dtype float32
    """
    P, T, A = daily_paths.shape
    daily_intensity = jumps_per_year / TRADING_DAYS_PER_YEAR  # ~0.012/day
    rng = np.random.default_rng(seed)

    # Poisson jump indicator per (path, day)
    jump_mask = rng.random((P, T)) < daily_intensity  # (P, T)
    # Jump magnitudes
    jump_mag = rng.normal(jump_mean, jump_std, size=(P, T)).astype(np.float32)
    jump_mag = jump_mag * jump_mask  # zero out non-jump days

    # Apply additive jump to all assets simultaneously (systemic shock)
    # (1 + base_return) * (1 + jump) - 1 = base + jump + base*jump ≈ base + jump for small magnitudes
    out = daily_paths.copy()
    out += jump_mag[:, :, np.newaxis]
    return out


if __name__ == "__main__":
    rng = np.random.default_rng(42)
    fake = rng.normal(0.0005, 0.012, (5000, 3780, 5)).astype(np.float32)
    print(f"Base paths: mean daily {fake.mean():+.5f}, std {fake.std():.5f}")

    jumped = apply_jump_overlay(fake, seed=42)
    print(f"With jumps: mean daily {jumped.mean():+.5f}, std {jumped.std():.5f}")

    # Compute median max DD on equal-weight portfolio
    port = fake.mean(axis=2)
    wealth = 21302 * np.cumprod(1 + port, axis=1)
    peak = np.maximum.accumulate(wealth, axis=1)
    dd = (wealth / peak) - 1
    print(f"Base median max DD: {np.median(dd.min(axis=1))*100:+.1f}%")

    port_j = jumped.mean(axis=2)
    wealth_j = 21302 * np.cumprod(1 + port_j, axis=1)
    peak_j = np.maximum.accumulate(wealth_j, axis=1)
    dd_j = (wealth_j / peak_j) - 1
    print(f"Jump median max DD: {np.median(dd_j.min(axis=1))*100:+.1f}%")
    print(f"Delta: {(np.median(dd_j.min(axis=1)) - np.median(dd.min(axis=1)))*100:+.2f} percentage points")
