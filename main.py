"""
TideMerge Polymarket Arbitrage Bot
===================================
Strategy: Price Ladder Arbitrage

When Polymarket prices a higher-threshold market MORE than a lower-threshold
market (e.g. "BTC > $100k" @ 50% while "BTC > $90k" @ 40%), the math is
provably wrong. We buy both sides and collect guaranteed profit regardless
of the outcome.

Setup:
  1. cp .env.example .env
  2. Fill in PRIVATE_KEY and optionally POLYMARKET_API_* creds
  3. pip install -r requirements.txt
  4. python main.py            ← runs in DRY_RUN mode (no real orders)
  5. Set DRY_RUN=false in .env when ready to go live
"""

import time
import signal
import sys
from scanner import run_scan
from config import SCAN_INTERVAL, DRY_RUN

running = True


def handle_exit(sig, frame):
    global running
    print("\n[Bot] Shutting down gracefully...")
    running = False


signal.signal(signal.SIGINT, handle_exit)
signal.signal(signal.SIGTERM, handle_exit)


def main():
    mode = "DRY RUN (no real orders)" if DRY_RUN else "LIVE TRADING"
    print(f"""
╔══════════════════════════════════════════════╗
║   TideMerge Polymarket Arbitrage Bot         ║
║   Strategy : Price Ladder Arbitrage          ║
║   Mode     : {mode:<32}║
║   Interval : every {SCAN_INTERVAL}s                        ║
╚══════════════════════════════════════════════╝
""")

    if not DRY_RUN:
        print("⚠️  LIVE MODE — real orders will be placed. Ctrl+C to stop.\n")
        time.sleep(3)

    scan_count = 0
    while running:
        scan_count += 1
        print(f"\n── Scan #{scan_count} ─────────────────────────────────────")
        try:
            run_scan()
        except Exception as e:
            print(f"[Bot] Scan error: {e}")

        if running:
            time.sleep(SCAN_INTERVAL)

    print("[Bot] Stopped.")


if __name__ == "__main__":
    main()
