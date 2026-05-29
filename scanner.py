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
from trader import execute_arb, get_open_positions
from config import MAX_OPEN_POSITIONS


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

    # Fetch real open positions from Kalshi so we never double-buy
    open_positions = get_open_positions()

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
    for strategy, opp, edge in all_opps:
        if traded >= MAX_OPEN_POSITIONS:
            break

        # Skip any market we already hold a position in
        ticker = getattr(opp, "ticker", None) or getattr(opp, "event_ticker", "")
        if ticker in open_positions:
            print(f"[Scanner] Skipping {ticker} — already have open position")
            continue

        # Skip bucket/ladder opps if any leg ticker is already held
        leg_tickers = {leg["ticker"] for leg in opp.legs()}
        if leg_tickers & open_positions:
            continue

        print(f"\n[{strategy.upper()}] edge={edge:.1%}")
        success = execute_arb(opp)
        if success:
            open_positions.update(leg_tickers)
            traded += 1

    if traded == 0:
        print("[Scanner] No new positions opened this scan.")
    else:
        print(f"\n[Scanner] Opened {traded} new position(s) this scan.")
