from markets import fetch_markets
from strategies.quant_crypto import find_opportunities
from trader import execute_arb
from config import MAX_OPEN_POSITIONS

traded_tickers = set()


def run_scan():
    markets = fetch_markets()

    if not markets:
        print("[Scanner] No markets returned.")
        return

    # Quick sanity check on first market
    sample = markets[0]
    print(f"[Scanner] Sample: ticker={sample.get('ticker')} "
          f"yes_ask={sample.get('yes_ask')} strike={sample.get('floor_strike')} "
          f"type={sample.get('strike_type')} close={sample.get('close_time','')[:10]}")

    opportunities = find_opportunities(markets)

    if not opportunities:
        print("[Scanner] No trade opportunities this scan.")
        return

    print(f"[Scanner] {len(opportunities)} opportunity(s), taking top {MAX_OPEN_POSITIONS}:")
    traded = 0

    for opp in opportunities:
        if traded >= MAX_OPEN_POSITIONS:
            break
        if opp.ticker in traded_tickers:
            continue

        success = execute_arb(opp)
        if success:
            traded_tickers.add(opp.ticker)
            traded += 1

    if traded == 0:
        print("[Scanner] All top opportunities already have open positions.")
