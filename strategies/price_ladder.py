"""
Price Ladder Arbitrage — Kalshi
================================
Kalshi groups related markets under the same event_ticker. For example:
  KXBTCD-25DEC31  groups all "BTC price on Dec 31" markets:
    - "Bitcoin above $90,000?"  yes_ask=40
    - "Bitcoin above $100,000?" yes_ask=50  ← IMPOSSIBLE, must be <= 40

Guaranteed arbitrage:
  Buy YES($90k)  @ 40¢  +  Buy NO($100k) @ 50¢  =  90¢ total cost
  Minimum payout: 100¢ → guaranteed +10¢ (~11%) no matter what BTC does.

Kalshi prices are in cents (integers 1–99), not decimals.
"""

import re
from dataclasses import dataclass
from typing import Optional
from markets import yes_ask, no_ask
from config import MIN_EDGE, MAX_TRADE_USDC

THRESHOLD_RE = re.compile(r"\$\s*([\d,]+(?:\.\d+)?)\s*([kKmM]?)")
ABOVE_RE     = re.compile(r"\b(?:above|exceed|over|reach|hit|surpass|top|higher than)\b", re.IGNORECASE)
CRYPTO_RE    = re.compile(r"\b(?:BTC|Bitcoin|ETH|Ethereum|SOL|Solana|DOGE|XRP|BNB)\b", re.IGNORECASE)


def parse_threshold(title: str) -> Optional[float]:
    m = THRESHOLD_RE.search(title)
    if not m:
        return None
    value = float(m.group(1).replace(",", ""))
    suffix = m.group(2).lower()
    if suffix == "k":
        value *= 1_000
    elif suffix == "m":
        value *= 1_000_000
    return value


def is_crypto_above_market(market: dict) -> bool:
    title = market.get("title", "") + " " + market.get("subtitle", "")
    return bool(CRYPTO_RE.search(title)) and bool(ABOVE_RE.search(title))


@dataclass
class ArbOpportunity:
    lower_market:    dict
    higher_market:   dict
    lower_threshold: float
    higher_threshold: float
    lower_yes_ask:   int    # cents
    higher_no_ask:   int    # cents
    guaranteed_edge: float  # e.g. 0.11 = 11% guaranteed profit
    contracts:       int    # number of contracts per leg

    def describe(self):
        title = self.lower_market.get("event_ticker", "?")
        return (
            f"[Arb] {title}: "
            f"${self.lower_threshold:,.0f}(YES@{self.lower_yes_ask}¢) + "
            f"${self.higher_threshold:,.0f}(NO@{self.higher_no_ask}¢) | "
            f"cost={self.lower_yes_ask + self.higher_no_ask}¢ | "
            f"edge={self.guaranteed_edge:.1%} | "
            f"{self.contracts} contracts each"
        )

    def legs(self):
        return [
            {
                "ticker": self.lower_market["ticker"],
                "side":   "yes",
                "price":  self.lower_yes_ask,
                "count":  self.contracts,
                "label":  f"YES ${self.lower_threshold:,.0f} @ {self.lower_yes_ask}¢",
            },
            {
                "ticker": self.higher_market["ticker"],
                "side":   "no",
                "price":  self.higher_no_ask,
                "count":  self.contracts,
                "label":  f"NO  ${self.higher_threshold:,.0f} @ {self.higher_no_ask}¢",
            },
        ]


def find_opportunities(markets: list) -> list:
    # Group eligible markets by event_ticker
    groups: dict[str, list] = {}

    for m in markets:
        if not is_crypto_above_market(m):
            continue
        threshold = parse_threshold(m.get("title", "") + " " + m.get("subtitle", ""))
        if threshold is None:
            continue
        ya = yes_ask(m)
        na = no_ask(m)
        if ya is None or na is None or ya <= 1 or ya >= 99:
            continue

        event = m.get("event_ticker", m.get("ticker", ""))
        groups.setdefault(event, []).append((threshold, m, ya, na))

    opportunities = []

    for event, entries in groups.items():
        if len(entries) < 2:
            continue

        entries.sort(key=lambda x: x[0])  # ascending threshold

        for i in range(len(entries) - 1):
            lower_thresh,  lower_mkt,  lower_ya,  lower_na  = entries[i]
            higher_thresh, higher_mkt, higher_ya, higher_na = entries[i + 1]

            # Arbitrage: higher threshold priced more than lower (mathematically wrong)
            if higher_ya <= lower_ya:
                continue

            total_cost_cents = lower_ya + higher_na  # buy YES(lower) + buy NO(higher)
            if total_cost_cents >= 100:
                continue

            edge = (100 - total_cost_cents) / total_cost_cents
            if edge < MIN_EDGE:
                continue

            # Contracts per leg: spend MAX_TRADE_USDC on each leg
            # Use the more expensive leg to size (conservative)
            max_price_cents = max(lower_ya, higher_na)
            contracts = max(1, int((MAX_TRADE_USDC * 100) / max_price_cents))

            opportunities.append(ArbOpportunity(
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
