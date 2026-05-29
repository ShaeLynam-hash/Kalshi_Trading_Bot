"""
Log-normal binary option pricing for Kalshi crypto markets.

For a market "Asset > K at time T":
  P(S_T > K) = N(d1)
  d1 = [ln(S/K) + (σ²/2)·T] / (σ·√T)

Where:
  S = current spot price
  K = strike (threshold)
  T = time to expiry in years
  σ = annualized volatility
  N = cumulative normal distribution
"""
import math


def _norm_cdf(x: float) -> float:
    """Approximation of cumulative standard normal distribution."""
    # Abramowitz & Stegun approximation (error < 7.5e-8)
    t = 1.0 / (1.0 + 0.2316419 * abs(x))
    poly = t * (0.319381530
               + t * (-0.356563782
               + t * (1.781477937
               + t * (-1.821255978
               + t * 1.330274429))))
    pdf = math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)
    cdf = 1.0 - pdf * poly
    return cdf if x >= 0 else 1.0 - cdf


def prob_above(spot: float, strike: float, years_to_expiry: float, annual_vol: float) -> float:
    """P(S_T > strike) under log-normal model."""
    if years_to_expiry <= 0:
        return 1.0 if spot > strike else 0.0
    if spot <= 0 or strike <= 0 or annual_vol <= 0:
        return 0.5

    d1 = (math.log(spot / strike) + 0.5 * annual_vol ** 2 * years_to_expiry) \
         / (annual_vol * math.sqrt(years_to_expiry))
    return _norm_cdf(d1)


def prob_range(spot: float, low: float, high: float,
               years_to_expiry: float, annual_vol: float) -> float:
    """P(low < S_T <= high)."""
    return prob_above(spot, low, years_to_expiry, annual_vol) \
         - prob_above(spot, high, years_to_expiry, annual_vol)
