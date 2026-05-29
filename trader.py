import uuid
import requests
from config import KALSHI_HOST, DRY_RUN
from markets import auth_headers


def place_order(ticker: str, side: str, price: float, count: int, label: str = "") -> bool:
    tag = f"[{'DRY RUN' if DRY_RUN else 'LIVE'}] {label}"
    price_cents = int(round(price * 100))

    if DRY_RUN:
        print(f"  {tag}: BUY {count} {side.upper()} @ {price:.3f} (${price * count:.2f})")
        return True

    try:
        order_path = "/trade-api/v2/portfolio/orders"
        resp = requests.post(
            f"{KALSHI_HOST}/portfolio/orders",
            json={
                "ticker":          ticker,
                "client_order_id": str(uuid.uuid4()),
                "type":            "limit",
                "action":          "buy",
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
            price=leg["price"],
            count=leg["count"],
            label=leg["label"],
        )
        if not ok:
            success = False
    return success
