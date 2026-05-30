"""
Scanner — runs once per cron tick.

Strategy: crypto quant only.
  - Fetch real Kalshi balance so Kelly sizing is accurate
  - Run take-profit exits first
  - Find high-conviction crypto quant trades (8%+ edge)
  - Max 4 open positions, up to $12 each
  - Skip any market already held to prevent doubling up
"""
from markets import fetch_markets
from strategies.quant_crypto import find_opportunities as quant_opps
from trader import execute_arb, get_open_positions, get_balance, run_exits
from config import MAX_OPEN_POSITIONS, MIN_BALANCE


def run_scan():
    markets = fetch_markets()
    if not markets:
        print("[Scanner] No markets returned.")
        return

    crypto_count = sum(1 for m in markets if any(
        (m.get("series_ticker") or m.get("ticker", "")).startswith(p)
        for p in ("KXBTC", "KXETH", "KXSOL", "KXDOGE", "KXXRP")
    ))
    print(f"[Scanner] {len(markets)} markets | {crypto_count} crypto")

    balance = get_balance()
    if balance < MIN_BALANCE:
        print(f"[Scanner] Balance too low (${balance:.2f}), skipping scan.")
        return

    # Take-profit exits first
    run_exits(markets)

    # Open positions — never double-buy
    open_positions = get_open_positions()
    open_events = set()
    for m in markets:
        if m.get("ticker") in open_positions:
            ev = m.get("event_ticker") or m.get("series_ticker", "")
            if ev:
                open_events.add(ev)

    slots = MAX_OPEN_POSITIONS - len(open_positions)
    if slots <= 0:
        print(f"[Scanner] All {MAX_OPEN_POSITIONS} position slots full.")
        return

    opps = quant_opps(markets, bankroll=balance)
    if not opps:
        print("[Scanner] No opportunities found.")
        return

    print(f"[Scanner] {len(opps)} opportunities | {slots} slots open | balance=${balance:.2f}")

    traded = 0
    for opp in opps:
        if traded >= slots:
            break

        leg_tickers  = {leg["ticker"] for leg in opp.legs()}
        event_ticker = getattr(opp, "event_ticker", "")

        if leg_tickers & open_positions:
            continue
        if event_ticker and event_ticker in open_events:
            continue

        print(f"\n[QUANT] edge={opp.edge:.1%} balance=${balance:.2f}")
        success = execute_arb(opp)
        if success:
            open_positions.update(leg_tickers)
            if event_ticker:
                open_events.add(event_ticker)
            traded += 1

    print(f"\n[Scanner] Opened {traded} new position(s)." if traded else "[Scanner] No new positions this scan.")
