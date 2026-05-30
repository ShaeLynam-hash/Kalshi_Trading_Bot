"""
Quant strategy for Kalshi crypto markets.

Handles all three market types:
  - "above" markets: floor_strike set → P(S_T > floor_strike)
  - "below" markets: cap_strike set  → P(S_T < cap_strike) = 1 - P(S_T > cap_strike)
  - "range" markets: both set        → P(floor < S_T < cap)
"""
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import List

from config import MIN_EDGE, MAX_TRADE_USDC
from data.feeds import get_spot_price, get_annualized_vol
from quant.model import prob_above, prob_range
from utils.kelly import kelly_size

ASSET_MAP = {
    "KXBTC":  "BTC",
    "KXETH":  "ETH",
    "KXSOL":  "SOL",
    "KXDOGE": "DOGE",
    "KXXRP":  "XRP",
}

MIN_YEARS = 1 / 8760  # at least 1 hour remaining


@dataclass
class QuantOpportunity:
    ticker:       str
    event_ticker: str
    side:         str
    ask_price:    float
    model_prob:   float
    edge:         float
    dollar_size:  float
    label:        str

    def describe(self) -> str:
        return (
            f"[Quant] {self.ticker} BUY {self.side.upper()} "
            f"ask={self.ask_price:.3f} model={self.model_prob:.3f} "
            f"edge={self.edge:+.3f} size=${self.dollar_size:.2f}"
        )

    def legs(self) -> list:
        count = max(1, int(self.dollar_size / self.ask_price))
        return [{
            "ticker": self.ticker,
            "side":   self.side,
            "price":  self.ask_price,
            "count":  count,
            "label":  self.label,
        }]


def _years_to_expiry(close_time: str) -> float:
    if not close_time:
        return 0.0
    try:
        if close_time.endswith("Z"):
            close_time = close_time[:-1] + "+00:00"
        dt = datetime.fromisoformat(close_time)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        seconds = (dt - datetime.now(timezone.utc)).total_seconds()
        return max(seconds / (365.25 * 24 * 3600), 0.0)
    except Exception:
        return 0.0


def _asset_from_market(market: dict) -> str:
    for key in ("series_ticker", "ticker", "event_ticker"):
        val = market.get(key, "") or ""
        for prefix, asset in ASSET_MAP.items():
            if val.startswith(prefix):
                return asset
    return None


def _market_prob(spot: float, floor_strike, cap_strike, years: float, vol: float) -> float:
    """Return model probability that YES resolves, handling all market types."""
    has_floor = floor_strike is not None
    has_cap   = cap_strike is not None

    if has_floor and has_cap:
        return prob_range(spot, float(floor_strike), float(cap_strike), years, vol)
    elif has_floor:
        return prob_above(spot, float(floor_strike), years, vol)
    elif has_cap:
        return 1.0 - prob_above(spot, float(cap_strike), years, vol)
    return None


def find_opportunities(markets: list, bankroll: float = 50.0) -> List[QuantOpportunity]:
    opportunities = []
    price_cache = {}
    vol_cache   = {}

    crypto_count  = 0
    no_strike     = 0
    expired_count = 0
    no_price      = 0
    sample_logged = False

    for market in markets:
        asset = _asset_from_market(market)
        if not asset:
            continue
        crypto_count += 1

        floor_strike = market.get("floor_strike")
        cap_strike   = market.get("cap_strike")
        if floor_strike is None and cap_strike is None:
            no_strike += 1
            continue

        years = _years_to_expiry(market.get("close_time", ""))
        if years < MIN_YEARS:
            expired_count += 1
            continue

        yes_ask = market.get("yes_ask")
        no_ask  = market.get("no_ask")
        if yes_ask is None or no_ask is None:
            no_price += 1
            continue
        if not (0.01 <= yes_ask <= 0.99):
            no_price += 1
            continue

        if asset not in price_cache:
            spot = get_spot_price(asset)
            if spot is None:
                continue
            price_cache[asset] = spot
        spot = price_cache[asset]

        if asset not in vol_cache:
            vol_cache[asset] = get_annualized_vol(asset)
        vol = vol_cache[asset]

        model_prob = _market_prob(spot, floor_strike, cap_strike, years, vol)
        if model_prob is None:
            continue

        if not sample_logged:
            sample_logged = True
            print(f"[Quant DEBUG] {asset} spot={spot:.0f} floor={floor_strike} cap={cap_strike} "
                  f"years={years:.4f} model={model_prob:.3f} yes_ask={yes_ask:.3f} edge={model_prob-yes_ask:+.3f}")

        yes_edge = model_prob - yes_ask
        if yes_edge >= MIN_EDGE:
            size = min(kelly_size(model_prob, yes_ask, bankroll), MAX_TRADE_USDC)
            if size >= 1.0:
                opportunities.append(QuantOpportunity(
                    ticker=market.get("ticker", ""),
                    event_ticker=market.get("event_ticker", market.get("series_ticker", "")),
                    side="yes",
                    ask_price=yes_ask,
                    model_prob=model_prob,
                    edge=yes_edge,
                    dollar_size=size,
                    label=f"{asset} YES floor={floor_strike} cap={cap_strike}",
                ))

        no_edge = (1.0 - model_prob) - no_ask
        if no_edge >= MIN_EDGE:
            size = min(kelly_size(1.0 - model_prob, no_ask, bankroll), MAX_TRADE_USDC)
            if size >= 1.0:
                opportunities.append(QuantOpportunity(
                    ticker=market.get("ticker", ""),
                    event_ticker=market.get("event_ticker", market.get("series_ticker", "")),
                    side="no",
                    ask_price=no_ask,
                    model_prob=1.0 - model_prob,
                    edge=no_edge,
                    dollar_size=size,
                    label=f"{asset} NO floor={floor_strike} cap={cap_strike}",
                ))

    print(f"[Quant] {crypto_count} crypto | no_strike={no_strike} expired={expired_count} no_price={no_price} → {len(opportunities)} opportunities")
    opportunities.sort(key=lambda o: o.edge, reverse=True)
    return opportunities
