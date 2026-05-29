import uuid
import requests
from config import KALSHI_HOST, DRY_RUN, TAKE_PROFIT_PCT, STOP_LOSS_PCT
from markets import auth_headers


def get_open_positions() -> set:
    """Return set of tickers where we already have an open position."""
    try:
        path = "/trade-api/v2/portfolio/positions"
        resp = requests.get(
            f"{KALSHI_HOST}/portfolio/positions",
            params={"limit": 200, "settlement_status": "unsettled"},
            headers=auth_headers("GET", path),
            timeout=10,
        )
        if not resp.ok:
            print(f"[Positions] fetch failed {resp.status_code}: {resp.text[:200]}")
            return set()
        positions = resp.json().get("market_positions", [])
        tickers = {p["ticker"] for p in positions if p.get("position", 0) != 0}
        print(f"[Positions] {len(tickers)} open positions")
        return tickers
    except Exception as e:
        print(f"[Positions] error: {e}")
        return set()


def get_positions_with_pnl() -> list:
    """Return full position details including unrealized P&L."""
    try:
        path = "/trade-api/v2/portfolio/positions"
        resp = requests.get(
            f"{KALSHI_HOST}/portfolio/positions",
            params={"limit": 200, "settlement_status": "unsettled"},
            headers=auth_headers("GET", path),
            timeout=10,
        )
        if not resp.ok:
            return []
        return [p for p in resp.json().get("market_positions", []) if p.get("position", 0) != 0]
    except Exception as e:
        print(f"[Positions] P&L fetch error: {e}")
        return []


def place_order(ticker: str, side: str, action: str, price: float, count: int, label: str = "") -> bool:
    mode = "DRY RUN" if DRY_RUN else "LIVE"
    price_cents = int(round(price * 100))
    tag = f"[{mode}] {label}"

    if DRY_RUN:
        print(f"  {tag}: {action.upper()} {count} {side.upper()} @ {price:.3f} (${price * count:.2f})")
        return True

    try:
        order_path = "/trade-api/v2/portfolio/orders"
        resp = requests.post(
            f"{KALSHI_HOST}/portfolio/orders",
            json={
                "ticker":          ticker,
                "client_order_id": str(uuid.uuid4()),
                "type":            "limit",
                "action":          action,
                "side":            side,
                "count":           count,
                f"{side}_price":   price_cents,
            },
            headers=auth_headers("POST", order_path),
            timeout=10,
        )
        if not resp.ok:
            print(f"  {tag}: order FAILED {resp.status_code}: {resp.text[:200]}")
            return False
        order = resp.json().get("order", {})
        print(f"  {tag}: order placed → {order.get('id', '?')} status={order.get('status', '?')}")
        return True
    except Exception as e:
        print(f"  {tag}: order FAILED → {e}")
        return False


def execute_arb(opportunity) -> bool:
    print(f"\n{opportunity.describe()}")
    success = True
    for leg in opportunity.legs():
        ok = place_order(
            ticker=leg["ticker"],
            side=leg["side"],
            action="buy",
            price=leg["price"],
            count=leg["count"],
            label=leg["label"],
        )
        if not ok:
            success = False
    return success


def run_exits(markets: list):
    """Check all open positions and sell if take-profit or stop-loss hit."""
    positions = get_positions_with_pnl()
    if not positions:
        return

    # Build a price lookup from current market data
    market_by_ticker = {m["ticker"]: m for m in markets}

    exits = 0
    for pos in positions:
        ticker   = pos.get("ticker", "")
        count    = pos.get("position", 0)       # positive = long YES, negative = long NO
        exposure = pos.get("market_exposure", 0) # total $ invested
        unreal   = pos.get("unrealized_pnl", None)

        if not ticker or count == 0 or exposure == 0:
            continue

        # If API gives us unrealized_pnl, use it; otherwise skip
        if unreal is None:
            continue

        pnl_pct = unreal / abs(exposure)

        market = market_by_ticker.get(ticker)
        if not market:
            continue

        should_exit = False
        reason = ""

        if pnl_pct >= TAKE_PROFIT_PCT:
            should_exit = True
            reason = f"take profit {pnl_pct:+.1%}"
        elif pnl_pct <= STOP_LOSS_PCT:
            should_exit = True
            reason = f"stop loss {pnl_pct:+.1%}"

        if not should_exit:
            continue

        # Determine side and exit price (use bid — what buyers will pay us)
        if count > 0:
            side       = "yes"
            exit_price = market.get("yes_bid") or market.get("yes_ask", 0.50)
        else:
            side       = "no"
            exit_price = market.get("no_bid") or market.get("no_ask", 0.50)
            count      = abs(count)

        if not exit_price or exit_price <= 0.01:
            continue

        print(f"[Exit] {ticker} {reason} → selling {count} {side.upper()} @ {exit_price:.3f}")
        place_order(
            ticker=ticker,
            side=side,
            action="sell",
            price=exit_price,
            count=count,
            label=f"EXIT {reason}",
        )
        exits += 1

    if exits:
        print(f"[Exit] Closed {exits} position(s) this scan.")
    else:
        print(f"[Exit] {len(positions)} open position(s), none hit exit threshold.")
