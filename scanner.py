"""
Multi-strategy scanner. Runs on every tick (GitHub Actions every 5 min).

Priority order (highest confidence first):
  1. Parity arb   — buy YES + NO when sum < $1 - fee (pure risk-free)
  2. Bucket sum   — buy all YES buckets in an event when sum < $1 - fee (pure risk-free)
  3. Price ladder — inverted threshold prices (risk-free)
  4. Quant model  — log-normal pricing vs market price for crypto markets
"""
from markets import fetch_markets
from strategies.arb_parity   import find_opportunities as parity_opps
from strategies.bucket_sum   import find_opportunities as bucket_opps
from strategies.price_ladder import find_opportunities as ladder_opps
from strategies.quant_crypto import find_opportunities as quant_opps
from trader import execute_arb, get_open_positions, run_exits
from config import MAX_OPEN_POSITIONS

# Max trades per category per scan — forces diversification
MAX_PER_CATEGORY = 3


def run_scan():
    markets = fetch_markets()

    if not markets:
        print("[Scanner] No markets returned.")
        return

    sample = markets[0]
    print(
        f"[Scanner] {len(markets)} markets loaded | "
        f"sample: {sample.get('ticker')} "
        f"yes_ask={sample.get('yes_ask')} no_ask={sample.get('no_ask')}"
    )

    # Check exits first — sell anything that hit take-profit or stop-loss
    run_exits(markets)

    # Fetch real open positions from Kalshi so we never double-buy
    open_positions = get_open_positions()

    # Also track event_tickers we hold — skip the whole event if we're already in it
    open_events = set()
    for m in markets:
        if m.get("ticker") in open_positions:
            ev = m.get("event_ticker") or m.get("series_ticker", "")
            if ev:
                open_events.add(ev)

    # Run all strategies — pure arb first, quant last
    all_opps = []
    all_opps.extend(("parity", o, o.edge)            for o in parity_opps(markets))
    all_opps.extend(("bucket", o, o.guaranteed_edge) for o in bucket_opps(markets))
    all_opps.extend(("ladder", o, o.guaranteed_edge) for o in ladder_opps(markets))
    all_opps.extend(("quant",  o, o.edge)            for o in quant_opps(markets))

    if not all_opps:
        print("[Scanner] No opportunities found this scan.")
        return

    all_opps.sort(key=lambda x: x[2], reverse=True)
    print(f"[Scanner] {len(all_opps)} total opportunities across all strategies")

    traded = 0
    category_counts: dict[str, int] = {}

    for strategy, opp, edge in all_opps:
        if traded >= MAX_OPEN_POSITIONS:
            break

        # Don't over-concentrate in one strategy/category
        if category_counts.get(strategy, 0) >= MAX_PER_CATEGORY:
            continue

        leg_tickers  = {leg["ticker"] for leg in opp.legs()}
        event_ticker = getattr(opp, "event_ticker", "")

        # Skip if we already hold any leg of this trade
        if leg_tickers & open_positions:
            print(f"[Scanner] Skipping {event_ticker} — already have open position")
            continue

        # Skip if we already have ANY position in this event
        if event_ticker and event_ticker in open_events:
            print(f"[Scanner] Skipping {event_ticker} — already in this event")
            continue

        print(f"\n[{strategy.upper()}] edge={edge:.1%}")
        success = execute_arb(opp)
        if success:
            open_positions.update(leg_tickers)
            if event_ticker:
                open_events.add(event_ticker)
            category_counts[strategy] = category_counts.get(strategy, 0) + 1
            traded += 1

    if traded == 0:
        print("[Scanner] No new positions opened this scan.")
    else:
        print(f"\n[Scanner] Opened {traded} new position(s) this scan.")
