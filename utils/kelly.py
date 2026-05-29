"""
Kelly criterion position sizing.

Full Kelly: f* = (p·b - (1-p)) / b
Half Kelly used for safety on small accounts.

Where:
  p = probability of winning
  b = net odds (profit per $1 risked)
    e.g. buying YES at 0.30 → b = 0.70/0.30 = 2.33
"""
from config import BANKROLL, MAX_TRADE_USDC


def kelly_size(prob_win: float, ask_price: float, half_kelly: bool = True) -> float:
    """
    Returns dollar amount to bet.
    ask_price: cost per contract in dollars (e.g. 0.30)
    """
    if ask_price <= 0 or ask_price >= 1 or prob_win <= 0:
        return 0.0

    b = (1.0 - ask_price) / ask_price   # net odds
    f = (prob_win * b - (1.0 - prob_win)) / b

    if f <= 0:
        return 0.0

    if half_kelly:
        f *= 0.5

    bet = f * BANKROLL
    return min(bet, MAX_TRADE_USDC)
