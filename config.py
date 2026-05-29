import os
from dotenv import load_dotenv

load_dotenv()

KALSHI_HOST = "https://trading-api.kalshi.com/trade-api/v2"

KALSHI_API_KEY_ID   = os.getenv("KALSHI_API_KEY_ID", "")
KALSHI_PRIVATE_KEY  = os.getenv("KALSHI_PRIVATE_KEY", "").replace("\\n", "\n")

MIN_EDGE           = float(os.getenv("MIN_EDGE", "0.04"))     # 4% guaranteed minimum profit
MAX_TRADE_USDC     = float(os.getenv("MAX_TRADE_USDC", "25"))
MAX_OPEN_POSITIONS = int(os.getenv("MAX_OPEN_POSITIONS", "8"))
SCAN_INTERVAL      = int(os.getenv("SCAN_INTERVAL", "20"))
DRY_RUN            = os.getenv("DRY_RUN", "true").lower() != "false"
