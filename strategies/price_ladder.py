"""
Price Ladder Arbitrage — all Kalshi threshold markets.

For any ordered set of markets (BTC > 90k, BTC > 95k, BTC > 100k), the
probability of the lower threshold MUST be >= the higher threshold.

If the market prices this backwards (higher threshold priced MORE than lower):
  Buy YES(lower threshold) + Buy NO(higher threshold)
  → Always collect at least $1 since exactly one of these always pays out.
  → Cost must be < $1 × (1 - fee) to lock in guaranteed profit.

Works on crypto, interest rates, CPI, any numeric threshold market.
"""
import re
from dataclasses import dataclass
from typing import Optional
from config import MIN_EDGE, MAX_TRADE_USDC, KALSHI_FEE_RATE

THRESHOLD_RE = re.compile(r"[\$€£¥]?\s*([\d,]+(?:\.\d+)?)\s*([kKmM]?)\b")
ABOVE_RE     = re.compile(
    r"\b(?:above|exceed(?:s)?|over|reach(?:es)?|hit[s]?|surpass(?:es)?|"
    r"top[s]?|higher than|at least|or more|greater than|at or above)\b",
    re.IGNORECASE,
)


def _parse_threshold(text: str) -> Optional[float]:
    """Extract the largest numeric threshold from a market title/subtitle."""
    best = None
    for m in THRESHOLD_RE.finditer(text):
        try:
            value = float(m.group(1).replace(",", ""))
            suffix = m.group(2).lower()
            if suffix == "k":
                value *= 1_000
            elif suffix == "m":
                value *= 1_000_000
            if best is None or value > best:
                best = value
        except ValueError:
            continue
    return best


def _is_threshold_above_market(market: dict) -> bool:
    text = f"{market.get('title', '')} {market.get('subtitle', '')} {market.get('ticker', '')}"
    return bool(ABOVE_RE.search(text)) and _parse_threshold(text) is not None


@dataclass
class LadderOpportunity:
    event_ticker:     str
    lower_market:     dict
    higher_market:    dict
    lower_threshold:  float
    higher_threshold: float
    lower_yes_ask:    float
    higher_no_ask:    float
    guaranteed_edge:  float
    contracts:        int

    def describe(self) -> str:
        return (
            f"[Ladder] {self.event_ticker}: "
            f"threshold {self.lower_threshold:,.0f}(YES@{self.lower_yes_ask:.3f}) + "
            f"{self.higher_threshold:,.0f}(NO@{self.higher_no_ask:.3f}) | "
            f"cost={self.lower_yes_ask + self.higher_no_ask:.3f} | "
            f"edge={self.guaranteed_edge:.1%} | "
            f"{self.contracts} contracts each"
        )

    def legs(self) -> list:
        return [
            {
                "ticker": self.lower_market["ticker"],
                "side":   "yes",
                "price":  self.lower_yes_ask,
                "count":  self.contracts,
                "label":  f"YES {self.lower_threshold:,.0f} @ {self.lower_yes_ask:.3f}",
            },
            {
                "ticker": self.higher_market["ticker"],
                "side":   "no",
                "price":  self.higher_no_ask,
                "count":  self.contracts,
                "label":  f"NO  {self.higher_threshold:,.0f} @ {self.higher_no_ask:.3f}",
            },
        ]


def find_opportunities(markets: list) -> list:
    groups: dict[str, list] = {}

    for m in markets:
        if not _is_threshold_above_market(m):
            continue

        text = f"{m.get('title', '')} {m.get('subtitle', '')}"
        threshold = _parse_threshold(text)
        if threshold is None:
            # Fall back to floor_strike field (Kalshi sets this on crypto markets)
            fs = m.get("floor_strike")
            if fs is not None:
                try:
                    threshold = float(fs)
                except (TypeError, ValueError):
                    continue
            else:
                continue

        ya = m.get("yes_ask")
        na = m.get("no_ask")
        if ya is None or na is None:
            continue
        if not (0.01 <= ya <= 0.99) or not (0.01 <= na <= 0.99):
            continue

        event = m.get("event_ticker") or m.get("series_ticker") or m.get("ticker", "")
        groups.setdefault(event, []).append((threshold, m, ya, na))

    opportunities = []
    # Minimum cost threshold: must clear fees + MIN_EDGE
    max_cost = (1.0 - KALSHI_FEE_RATE) - MIN_EDGE

    for event, entries in groups.items():
        if len(entries) < 2:
            continue

        entries.sort(key=lambda x: x[0])  # ascending threshold

        for i in range(len(entries) - 1):
            lower_thresh,  lower_mkt,  lower_ya,  _          = entries[i]
            higher_thresh, higher_mkt, higher_ya, higher_na  = entries[i + 1]

            # Only act when the price ladder is INVERTED (market mispricing)
            if higher_ya <= lower_ya:
                continue

            total_cost = lower_ya + higher_na
            if total_cost >= max_cost:
                continue

            # Net profit after fee on the winning leg
            net_payout = 1.0 * (1.0 - KALSHI_FEE_RATE)
            edge = (net_payout - total_cost) / total_cost
            if edge < MIN_EDGE:
                continue

            max_price = max(lower_ya, higher_na)
            contracts = max(1, int(MAX_TRADE_USDC / max_price))

            opportunities.append(LadderOpportunity(
                event_ticker=event,
                lower_market=lower_mkt,
                higher_market=higher_mkt,
                lower_threshold=lower_thresh,
                higher_threshold=higher_thresh,
                lower_yes_ask=lower_ya,
                higher_no_ask=higher_na,
                guaranteed_edge=edge,
                contracts=contracts,
            ))

    opportunities.sort(key=lambda o: o.guaranteed_edge, reverse=True)
    return opportunities
