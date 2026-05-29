"""
YES+NO Parity Arbitrage — all binary Kalshi markets.

For any binary market: YES resolves to $1 or NO resolves to $1.
If yes_ask + no_ask < 1 - fees, buy both sides and collect guaranteed profit.

This fires when market makers leave the spread so wide that both sides are
cheap — common in illiquid or newly listed markets.

Threshold: yes_ask + no_ask < (1 - fee_rate) - MIN_EDGE
"""
from dataclasses import dataclass
from config import MIN_EDGE, MAX_TRADE_USDC, KALSHI_FEE_RATE


@dataclass
class ParityOpportunity:
    ticker:       str
    event_ticker: str
    yes_ask:      float
    no_ask:       float
    edge:         float
    contracts:    int

    def describe(self) -> str:
        return (
            f"[Parity] {self.ticker}: "
            f"YES@{self.yes_ask:.3f} + NO@{self.no_ask:.3f} = {self.yes_ask + self.no_ask:.3f} | "
            f"edge={self.edge:.1%} | {self.contracts} contracts each"
        )

    def legs(self) -> list:
        return [
            {
                "ticker": self.ticker,
                "side":   "yes",
                "price":  self.yes_ask,
                "count":  self.contracts,
                "label":  f"YES parity @ {self.yes_ask:.3f}",
            },
            {
                "ticker": self.ticker,
                "side":   "no",
                "price":  self.no_ask,
                "count":  self.contracts,
                "label":  f"NO  parity @ {self.no_ask:.3f}",
            },
        ]


def find_opportunities(markets: list) -> list:
    opportunities = []
    # Net payout after fee on the winning side
    net_payout = 1.0 - KALSHI_FEE_RATE
    threshold = net_payout - MIN_EDGE  # e.g. 0.93 - 0.04 = 0.89

    for m in markets:
        ya = m.get("yes_ask")
        na = m.get("no_ask")
        if ya is None or na is None:
            continue
        if not (0.01 <= ya <= 0.99) or not (0.01 <= na <= 0.99):
            continue

        total = ya + na
        if total >= threshold:
            continue

        edge = (net_payout - total) / total
        if edge < MIN_EDGE:
            continue

        # Size by the more expensive leg
        max_price = max(ya, na)
        contracts = max(1, int(MAX_TRADE_USDC / max_price))

        opportunities.append(ParityOpportunity(
            ticker=m.get("ticker", ""),
            event_ticker=m.get("event_ticker", m.get("series_ticker", "")),
            yes_ask=ya,
            no_ask=na,
            edge=edge,
            contracts=contracts,
        ))

    opportunities.sort(key=lambda o: o.edge, reverse=True)
    print(f"[Parity] Checked {len(markets)} markets → {len(opportunities)} opportunities")
    return opportunities
