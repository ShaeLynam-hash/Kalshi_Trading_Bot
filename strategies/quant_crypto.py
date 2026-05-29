"""
Quant strategy for Kalshi crypto markets.

For each open "greater" market (e.g. BTC > 95000 at close):
  1. Fetch spot price and 30-day historical vol from CoinGecko
  2. Price the binary option with log-normal model: P(S_T > K)
  3. If model_prob > yes_ask + MIN_EDGE → buy YES (market underpriced)
  4. If model_prob < yes_ask - MIN_EDGE → buy NO  (market overpriced)
  5. Size position with half-Kelly criterion
"""
import time
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import List

from config import MIN_EDGE, MAX_TRADE_USDC
from data.feeds import get_spot_price, get_annualized_vol
from quant.model import prob_above
from utils.kelly import kelly_size

ASSET_MAP = {
    "KXBTC":  "BTC",
    "KXETH":  "ETH",
    "KXSOL":  "SOL",
    "KXDOGE": "DOGE",
    "KXXRP":  "XRP",
}


@dataclass
class QuantOpportunity:
    ticker: str
    event_ticker: str
    side: str          # "yes" or "no"
    ask_price: float
    model_prob: float
    edge: float
    dollar_size: float
    label: str

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
    """Parse ISO close_time string and return years until expiry."""
    if not close_time:
        return 0.0
    try:
        if close_time.endswith("Z"):
            close_time = close_time[:-1] + "+00:00"
        dt = datetime.fromisoformat(close_time)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        seconds = (dt - now).total_seconds()
        return max(seconds / (365.25 * 24 * 3600), 0.0)
    except Exception:
        return 0.0


def _asset_from_market(market: dict) -> str:
    # Check series_ticker and ticker both — general fetch may populate either
    for key in ("series_ticker", "ticker", "event_ticker"):
        val = market.get(key, "") or ""
        for prefix, asset in ASSET_MAP.items():
            if val.startswith(prefix):
                return asset
    return None


def find_opportunities(markets: list) -> List[QuantOpportunity]:
    opportunities = []

    # Cache prices/vols per asset so we don't re-fetch for every market
    price_cache = {}
    vol_cache = {}

    crypto_count = 0
    filtered_strike_type = 0
    filtered_no_strike = 0
    filtered_expired = 0
    filtered_no_price = 0
    sample_printed = False

    for market in markets:
        asset = _asset_from_market(market)
        if not asset:
            continue
        crypto_count += 1

        strike_type = market.get("strike_type", "")
        if strike_type != "greater":
            filtered_strike_type += 1
            continue

        strike = market.get("floor_strike")
        if strike is None:
            filtered_no_strike += 1
            continue
        try:
            strike = float(strike)
        except (TypeError, ValueError):
            filtered_no_strike += 1
            continue

        close_time = market.get("close_time", "")
        years = _years_to_expiry(close_time)
        if years <= 0:
            filtered_expired += 1
            continue

        yes_ask = market.get("yes_ask")
        no_ask  = market.get("no_ask")
        if yes_ask is None or no_ask is None:
            filtered_no_price += 1
            continue
        if not (0.01 <= yes_ask <= 0.99):
            filtered_no_price += 1
            continue

        # Print one sample to verify the model is computing correctly
        if not sample_printed:
            sample_printed = True
            if asset not in price_cache:
                price_cache[asset] = get_spot_price(asset)
            if asset not in vol_cache:
                vol_cache[asset] = get_annualized_vol(asset)
            _spot = price_cache.get(asset)
            _vol  = vol_cache.get(asset)
            if _spot and _vol:
                _model = prob_above(_spot, strike, years, _vol)
                print(f"[Quant DEBUG] {asset} spot={_spot} strike={strike} years={years:.4f} vol={_vol:.2f} model={_model:.3f} yes_ask={yes_ask:.3f} edge={_model-yes_ask:+.3f}")

        # Fetch spot and vol (cached per asset)
        if asset not in price_cache:
            spot = get_spot_price(asset)
            if spot is None:
                continue
            price_cache[asset] = spot
        spot = price_cache[asset]

        if asset not in vol_cache:
            vol = get_annualized_vol(asset)
            vol_cache[asset] = vol
        vol = vol_cache[asset]

        model_prob = prob_above(spot, strike, years, vol)

        # YES edge: model says more likely than market prices
        yes_edge = model_prob - yes_ask
        if yes_edge >= MIN_EDGE:
            size = kelly_size(model_prob, yes_ask)
            size = min(size, MAX_TRADE_USDC)
            if size >= 1.0:
                opportunities.append(QuantOpportunity(
                    ticker=market.get("ticker", ""),
                    event_ticker=market.get("event_ticker", market.get("series_ticker", "")),
                    side="yes",
                    ask_price=yes_ask,
                    model_prob=model_prob,
                    edge=yes_edge,
                    dollar_size=size,
                    label=f"{asset} YES>{strike} expires {close_time[:10]}",
                ))

        # NO edge: model says less likely, so NO is underpriced
        no_edge = (1.0 - model_prob) - no_ask
        if no_edge >= MIN_EDGE:
            size = kelly_size(1.0 - model_prob, no_ask)
            size = min(size, MAX_TRADE_USDC)
            if size >= 1.0:
                opportunities.append(QuantOpportunity(
                    ticker=market.get("ticker", ""),
                    event_ticker=market.get("event_ticker", market.get("series_ticker", "")),
                    side="no",
                    ask_price=no_ask,
                    model_prob=1.0 - model_prob,
                    edge=no_edge,
                    dollar_size=size,
                    label=f"{asset} NO>{strike} expires {close_time[:10]}",
                ))

    print(f"[Quant] {crypto_count} crypto | filtered: strike_type={filtered_strike_type} no_strike={filtered_no_strike} expired={filtered_expired} no_price={filtered_no_price}")
    opportunities.sort(key=lambda o: o.edge, reverse=True)
    print(f"[Quant] {crypto_count} crypto markets found → {len(opportunities)} opportunities")
    return opportunities
