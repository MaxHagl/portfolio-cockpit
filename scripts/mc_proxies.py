"""History augmentation via index-proxy regression.

For short-history active funds (BGF since 2022, A3DRHJ since 2022), we extend
the return history pre-2022 using:

    holding_return[t] = beta * proxy_return[t] + alpha/252 + eps[t]
    eps[t] ~ N(0, resid_sigma)   (resampled from native window for fat tails)

This is a deliberately humble augmentation: it grafts on systematic exposure to
historical regimes (2008, 2020) without pretending the active alpha+idio component
is anything but small-sample noise.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd

from mc_data import (
    TRADING_DAYS_PER_YEAR,
    align_returns,
    load_holding,
    load_holdings_meta,
    load_index,
    to_business_day_returns,
)

# Proxy mapping per holding. Strategy: prefer EUR-listed proxies to avoid
# currency-mismatch and timezone-alignment artifacts in the regression.
# - VWCE / SWDA / XDWT: XDWD (Xtrackers MSCI World, Xetra EUR) — same currency, same close time
# - BGF: IXN (iShares Global Tech, NYSE) — best available global tech long-history; USD-listed so
#   we EUR-convert with EUR/USD spot AND apply lag=+1 to absorb the timezone offset
# - A3DRHJ: EEM (iShares MSCI EM, NYSE) — same EUR conversion + lag=-1 (NY close leads BGF NAV)
PROXY = {
    "VWCE":   ("XDWD",  False, 0),   # (proxy_id, eur_convert, lag)
    "SWDA":   ("XDWD",  False, 0),
    "BGF":    ("IXN",   True,  1),
    "XDWT":   ("XDWD",  False, 0),
    "A3DRHJ": ("EEM",   True, -1),
}


@dataclass
class ProxyFit:
    holding_id: str
    proxy_id: str
    alpha_daily: float
    beta: float
    resid_std: float
    r2: float
    n_overlap: int
    overlap_start: str
    overlap_end: str
    native_start: str
    native_end: str


def fit_proxy_regression(target: pd.Series, proxy: pd.Series) -> ProxyFit | None:
    """OLS regression of target on proxy on overlapping dates."""
    df = pd.concat([target, proxy], axis=1, join="inner").dropna()
    df.columns = ["y", "x"]
    if len(df) < 60:
        return None
    x = df["x"].values
    y = df["y"].values
    # OLS: y = alpha + beta * x + eps
    X = np.column_stack([np.ones_like(x), x])
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    alpha_daily, beta = float(coef[0]), float(coef[1])
    y_hat = X @ coef
    resid = y - y_hat
    resid_std = float(resid.std(ddof=2))
    ss_res = float((resid ** 2).sum())
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return ProxyFit(
        holding_id=str(target.name),
        proxy_id=str(proxy.name),
        alpha_daily=alpha_daily,
        beta=beta,
        resid_std=resid_std,
        r2=r2,
        n_overlap=int(len(df)),
        overlap_start=str(df.index.min().date()),
        overlap_end=str(df.index.max().date()),
        native_start=str(target.index.min().date()),
        native_end=str(target.index.max().date()),
    )


def augment_returns(
    native: pd.Series,
    proxy: pd.Series,
    fit: ProxyFit,
    rng: np.random.Generator,
    target_start: pd.Timestamp,
) -> pd.Series:
    """Extend native series backward to target_start using proxy + α + residual sampling.

    Synthesized pre-period: synth[t] = beta * proxy[t] + alpha + sampled_resid[t]
    where sampled_resid is bootstrapped from the native window's residuals
    (preserves fat-tailed residual distribution).
    """
    if proxy.index.min() > target_start:
        target_start = proxy.index.min()  # can't go before proxy history

    # Window to synthesize: from target_start to (native_start - 1 day)
    native_start = native.dropna().index.min()
    pre_window = proxy.loc[
        (proxy.index >= target_start) & (proxy.index < native_start)
    ].dropna()

    if len(pre_window) == 0:
        # Native already covers everything (e.g., VWCE)
        return native

    # Compute native residuals for resampling
    overlap = pd.concat([native, proxy], axis=1, join="inner").dropna()
    overlap.columns = ["y", "x"]
    resid_native = overlap["y"] - (fit.alpha_daily + fit.beta * overlap["x"])

    # Bootstrap residuals
    synth_resid = rng.choice(resid_native.values, size=len(pre_window), replace=True)
    synth = fit.alpha_daily + fit.beta * pre_window.values + synth_resid

    synth_series = pd.Series(synth, index=pre_window.index, name=native.name)
    combined = pd.concat([synth_series, native]).sort_index()
    # Drop dup indices (keep native where overlap)
    combined = combined[~combined.index.duplicated(keep="last")]
    return combined


def _eur_convert(usd_rets: pd.Series, eurusd_rets: pd.Series) -> pd.Series:
    """Convert USD-denominated daily returns to EUR view.

    EUR return ≈ USD return - EURUSD return (where EURUSD = USD per EUR, rising = EUR stronger).
    Approximation: (1+r_usd)/(1+r_eurusd) - 1 ≈ r_usd - r_eurusd for small daily moves.
    """
    aligned_fx = eurusd_rets.reindex(usd_rets.index).fillna(0)
    return (usd_rets - aligned_fx).rename(usd_rets.name)


def build_augmented_matrix(
    target_start: str = "2009-07-01",
    seed: int = 20260617,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, ProxyFit]]:
    """Build 5-asset returns matrices: native (inner-join) and augmented (back to target_start).

    Returns:
        native_df: inner-join native returns (~3.5y where all 5 hold data)
        augmented_df: extended back to target_start using proxy regressions
        Dict of ProxyFit diagnostics per holding
    """
    rng = np.random.default_rng(seed)
    meta = load_holdings_meta()

    eurusd = to_business_day_returns(load_index("EURUSD"))

    native = {}
    proxies_prepared = {}
    proxy_meta = {}
    for h in meta["holdings"]:
        hid = h["id"]
        s = load_holding(hid)
        native[hid] = to_business_day_returns(s)

        proxy_id, eur_convert, lag = PROXY[hid]
        p_raw = to_business_day_returns(load_index(proxy_id))
        if eur_convert:
            p_raw = _eur_convert(p_raw, eurusd)
        if lag != 0:
            p_raw = p_raw.shift(lag).dropna()
        proxies_prepared[hid] = p_raw
        proxy_meta[hid] = {"proxy_id": proxy_id, "eur_convert": eur_convert, "lag": lag}

    fits: dict[str, ProxyFit] = {}
    augmented = {}
    target_ts = pd.Timestamp(target_start)
    for hid, native_rets in native.items():
        proxy_rets = proxies_prepared[hid]
        fit = fit_proxy_regression(native_rets, proxy_rets)
        if fit is None:
            augmented[hid] = native_rets
            continue
        fits[hid] = fit
        augmented[hid] = augment_returns(native_rets, proxy_rets, fit, rng, target_ts)

    # Native inner-join: all 5 holdings have data
    native_df = align_returns(native, how="outer").dropna(how="any")
    # Augmented: extended history
    augmented_df = align_returns(augmented, how="outer").dropna(how="any")

    # Attach proxy meta to fits
    for hid, m in proxy_meta.items():
        if hid in fits:
            # mutate dataclass via __dict__ to record meta
            fits[hid].__dict__.update(m)

    return native_df, augmented_df, fits


if __name__ == "__main__":
    native_df, augmented_df, fits = build_augmented_matrix()
    print(f"Native (inner-join) matrix: {native_df.shape}, "
          f"{native_df.index.min().date()} → {native_df.index.max().date()} "
          f"(~{(native_df.index.max() - native_df.index.min()).days / 365.25:.1f}y)")
    print(f"Augmented matrix:           {augmented_df.shape}, "
          f"{augmented_df.index.min().date()} → {augmented_df.index.max().date()} "
          f"(~{(augmented_df.index.max() - augmented_df.index.min()).days / 365.25:.1f}y)\n")
    print("Proxy regression diagnostics:")
    print(f"{'holding':10s} {'proxy':6s} {'EUR?':4s} {'lag':4s} {'α_ann':>10s} {'β':>6s} {'resid_σ_ann':>12s} {'R²':>6s} {'n':>6s}")
    for hid, f in fits.items():
        alpha_ann = f.alpha_daily * TRADING_DAYS_PER_YEAR
        resid_sigma_ann = f.resid_std * np.sqrt(TRADING_DAYS_PER_YEAR)
        eur = str(getattr(f, "eur_convert", False))[:3]
        lag = getattr(f, "lag", 0)
        print(f"{hid:10s} {f.proxy_id:6s} {eur:4s} {lag:>4d} {alpha_ann:+10.4f} {f.beta:6.3f} {resid_sigma_ann:12.4f} {f.r2:6.3f} {f.n_overlap:6d}")

    print("\nPer-asset augmented stats (μ/σ annualized):")
    for col in augmented_df.columns:
        r = augmented_df[col]
        print(f"  {col:10s} μ_ann={r.mean()*TRADING_DAYS_PER_YEAR:+.3f}  σ_ann={r.std()*np.sqrt(TRADING_DAYS_PER_YEAR):.3f}")

    print("\nCorrelation matrix (augmented):")
    print(augmented_df.corr().round(3))
    print("\nCorrelation matrix (native only):")
    print(native_df.corr().round(3))
