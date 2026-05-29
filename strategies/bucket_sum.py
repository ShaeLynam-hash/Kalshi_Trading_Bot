"""
Bucket Sum Arbitrage — Kalshi
==============================
Kalshi price range markets split an asset price into non-overlapping buckets.
Exactly ONE bucket resolves YES at expiry — so the sum of all YES prices MUST
equal $1.00.

If the sum of all yes_ask prices < $1, buy YES on every bucket and collect
a guaranteed $1 payout regardless of where the price lands.

Example:
  KXBTC event with 40 buckets, each priced at $0.023 ask
  Total cost = 40 × $0.023 = $0.92 → guaranteed $1.00 payout → 8.7% profit
"""

from dataclasses import dataclass
from markets import yes_ask
from config import MIN_EDGE, MAX_TRADE_USDC


@dataclass
class BucketArbOpportunity:
    event_ticker: str
    markets:      list
    total_cost:   float   # sum of all yes_ask prices
    guaranteed_edge: float
    contracts:    int

    def describe(self):
        return (
            f"[Arb] {self.event_ticker}: "
            f"{len(self.markets)} buckets | "
            f"cost=${self.total_cost:.4f} | "
            f"edge={self.guaranteed_edge:.1%} | "
            f"{self.contracts} contracts each"
        )

    def legs(self):
        return [
            {
                "ticker": m["ticker"],
                "side":   "yes",
                "price":  yes_ask(m),
                "count":  self.contracts,
                "label":  f"YES {m['ticker']} @ {yes_ask(m):.3f}",
            }
            for m in self.markets
        ]


def find_opportunities(markets: list) -> list:
    # Group by event_ticker
    events: dict[str, list] = {}
    for m in markets:
        event = m.get("event_ticker", "")
        if not event:
            continue
        ya = yes_ask(m)
        if ya is None or ya <= 0.001 or ya >= 0.999:
            continue
        events.setdefault(event, []).append(m)

    opportunities = []

    for event, buckets in events.items():
        if len(buckets) < 3:
            continue

        total_cost = sum(yes_ask(m) for m in buckets)

        if total_cost >= 1.0:
            continue

        edge = (1.0 - total_cost) / total_cost
        if edge < MIN_EDGE:
            continue

        # Size: spend MAX_TRADE_USDC across all legs
        avg_price = total_cost / len(buckets)
        contracts = max(1, int(MAX_TRADE_USDC / (avg_price * len(buckets))))

        opportunities.append(BucketArbOpportunity(
            event_ticker=event,
            markets=buckets,
            total_cost=total_cost,
            guaranteed_edge=edge,
            contracts=contracts,
        ))

    total_markets = len(markets)
    passed_filter = sum(1 for m in markets if yes_ask(m) is not None and 0.001 < (yes_ask(m) or 0) < 0.999)
    print(f"[Strategy] {total_markets} markets | {passed_filter} passed price filter | {len(events)} events | {len(opportunities)} opportunities")

    opportunities.sort(key=lambda o: o.guaranteed_edge, reverse=True)
    return opportunities
