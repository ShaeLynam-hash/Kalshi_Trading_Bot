"""
Free price data from CoinGecko — no API key needed.
"""
import math
import time
import requests

GECKO_IDS = {
    "BTC":  "bitcoin",
    "ETH":  "ethereum",
    "SOL":  "solana",
    "DOGE": "dogecoin",
    "XRP":  "ripple",
}

_price_cache  = {}
_vol_cache    = {}
PRICE_TTL     = 60    # seconds
VOL_TTL       = 3600  # 1 hour


def get_spot_price(asset: str) -> float:
    gecko_id = GECKO_IDS.get(asset.upper())
    if not gecko_id:
        return None

    cached = _price_cache.get(asset)
    if cached and time.time() - cached[1] < PRICE_TTL:
        return cached[0]

    try:
        resp = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": gecko_id, "vs_currencies": "usd"},
            timeout=10,
        )
        price = float(resp.json()[gecko_id]["usd"])
        _price_cache[asset] = (price, time.time())
        return price
    except Exception as e:
        print(f"[Feed] Price fetch error for {asset}: {e}")
        return None


def get_annualized_vol(asset: str, days: int = 30) -> float:
    gecko_id = GECKO_IDS.get(asset.upper())
    if not gecko_id:
        return 0.80  # default high vol

    cached = _vol_cache.get(asset)
    if cached and time.time() - cached[1] < VOL_TTL:
        return cached[0]

    try:
        resp = requests.get(
            f"https://api.coingecko.com/api/v3/coins/{gecko_id}/market_chart",
            params={"vs_currency": "usd", "days": days, "interval": "daily"},
            timeout=15,
        )
        prices = [p[1] for p in resp.json()["prices"]]
        if len(prices) < 2:
            return 0.80

        returns = [math.log(prices[i] / prices[i - 1]) for i in range(1, len(prices))]
        mean    = sum(returns) / len(returns)
        variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
        daily_vol = math.sqrt(variance)
        annual_vol = daily_vol * math.sqrt(365)

        _vol_cache[asset] = (annual_vol, time.time())
        print(f"[Feed] {asset} vol: {annual_vol:.1%} annualized ({days}d history)")
        return annual_vol
    except Exception as e:
        print(f"[Feed] Vol fetch error for {asset}: {e}")
        return 0.80
