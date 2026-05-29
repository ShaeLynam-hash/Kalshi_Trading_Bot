from markets import fetch_markets
from strategies.price_ladder import find_opportunities
from trader import execute_arb
from config import MAX_OPEN_POSITIONS

open_positions = set()  # track market IDs we've already traded


def run_scan():
    markets = fetch_markets()
    opportunities = find_opportunities(markets)

    if not opportunities:
        print("[Scanner] No arbitrage opportunities found this scan.")
        return

    print(f"[Scanner] Found {len(opportunities)} opportunity(s):")
    traded = 0

    for opp in opportunities:
        if traded >= MAX_OPEN_POSITIONS:
            break

        # Skip if we already have a position in either market
        lower_id  = opp.lower_market.get("id", "")
        higher_id = opp.higher_market.get("id", "")
        if lower_id in open_positions or higher_id in open_positions:
            continue

        success = execute_arb(opp)
        if success:
            open_positions.add(lower_id)
            open_positions.add(higher_id)
            traded += 1

    if traded == 0:
        print("[Scanner] All opportunities already have open positions.")
