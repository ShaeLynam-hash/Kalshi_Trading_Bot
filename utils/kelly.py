"""
Kelly criterion position sizing.

Full Kelly: f* = (p·b - (1-p)) / b
Quarter Kelly used — prediction market models have real uncertainty,
so we use 0.25x Kelly to protect the bankroll from model error.
"""
from config import MAX_TRADE_USDC


def kelly_size(prob_win: float, ask_price: float, bankroll: float, kelly_fraction: float = 0.25) -> float:
    if ask_price <= 0 or ask_price >= 1 or prob_win <= 0 or bankroll <= 0:
        return 0.0

    b = (1.0 - ask_price) / ask_price
    f = (prob_win * b - (1.0 - prob_win)) / b

    if f <= 0:
        return 0.0

    bet = f * kelly_fraction * bankroll
    return min(bet, MAX_TRADE_USDC)
