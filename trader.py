import uuid
import requests
from config import KALSHI_HOST, DRY_RUN
from markets import auth_headers



def place_order(ticker: str, side: str, price_cents: int, count: int, label: str = "") -> bool:
    tag = f"[{'DRY RUN' if DRY_RUN else 'LIVE'}] {label}"

    if DRY_RUN:
        cost = price_cents * count / 100
        print(f"  {tag}: BUY {count} {side.upper()} contracts @ {price_cents}¢ = ${cost:.2f}")
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
        resp.raise_for_status()
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
            price_cents=leg["price"],
            count=leg["count"],
            label=leg["label"],
        )
        if not ok:
            success = False
    return success
