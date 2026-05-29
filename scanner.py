from markets import fetch_markets
from strategies.bucket_sum import find_opportunities
from trader import execute_arb
from config import MAX_OPEN_POSITIONS

traded_events = set()


def run_scan():
    markets = fetch_markets()

    # Debug: check price format and event grouping
    if markets:
        sample = markets[0]
        ya = sample.get("yes_ask")
        na = sample.get("no_ask")
        ev = sample.get("event_ticker", "")
        price_fields = [k for k in sample.keys() if "ask" in k or "bid" in k or "price" in k]
        print(f"[Debug] Price fields available: {price_fields}")
        print(f"[Debug] yes_ask type={type(ya).__name__} has_event={bool(ev)}")
        events = set(m.get("event_ticker") for m in markets if m.get("event_ticker"))
        print(f"[Debug] Unique events: {len(events)}")

    opportunities = find_opportunities(markets)

    if not opportunities:
        print("[Scanner] No arbitrage opportunities found this scan.")
        return

    print(f"[Scanner] Found {len(opportunities)} opportunity(s):")
    traded = 0

    for opp in opportunities:
        if traded >= MAX_OPEN_POSITIONS:
            break
        if opp.event_ticker in traded_events:
            continue

        success = execute_arb(opp)
        if success:
            traded_events.add(opp.event_ticker)
            traded += 1

    if traded == 0:
        print("[Scanner] All opportunities already have open positions.")
