"""
Single-scan entry point for GitHub Actions.
Runs one full market scan and exits.
"""
from scanner import run_scan

print("=== Polymarket Arbitrage Scan ===")
run_scan()
print("=== Scan complete ===")
