from markets import fetch_markets
from strategies.bucket_sum import find_opportunities
from trader import execute_arb
from config import MAX_OPEN_POSITIONS

traded_events = set()


def run_scan():
    markets = fetch_markets()

    # Debug: show sample prices to verify format
    if markets:
        for m in markets[:3]:
            print(f"[Debug] {m.get('ticker')} | yes_ask={m.get('yes_ask')} | no_ask={m.get('no_ask')} | event={m.get('event_ticker')}")

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
