import os
from dotenv import load_dotenv

load_dotenv()

KALSHI_HOST = "https://api.elections.kalshi.com/trade-api/v2"

KALSHI_API_KEY_ID = os.getenv("KALSHI_API_KEY_ID", "")

# Private key stored as base64 in GitHub Secrets to preserve newlines
import base64 as _b64
_raw = os.getenv("KALSHI_PRIVATE_KEY_B64", "") or os.getenv("KALSHI_PRIVATE_KEY", "")
KALSHI_PRIVATE_KEY = _b64.b64decode(_raw).decode() if not _raw.startswith("-----") else _raw.replace("\\n", "\n")

BANKROLL           = float(os.getenv("BANKROLL", "100.0"))
MIN_EDGE           = float(os.getenv("MIN_EDGE", "0.04"))     # 4% edge required to trade
MAX_TRADE_USDC     = float(os.getenv("MAX_TRADE_USDC", "25"))
MAX_OPEN_POSITIONS = int(os.getenv("MAX_OPEN_POSITIONS", "8"))
SCAN_INTERVAL      = int(os.getenv("SCAN_INTERVAL", "20"))
DRY_RUN            = os.getenv("DRY_RUN", "true").lower() != "false"

# Kalshi takes ~7% of net profit as a fee on winning contracts.
# Arb is only safe when profit margin covers fees + MIN_EDGE.
KALSHI_FEE_RATE    = 0.07

# Exit thresholds — sell early if position moves enough
TAKE_PROFIT_PCT    = float(os.getenv("TAKE_PROFIT_PCT", "0.40"))  # sell at +40% gain
STOP_LOSS_PCT      = float(os.getenv("STOP_LOSS_PCT",   "-0.40")) # sell at -40% loss
