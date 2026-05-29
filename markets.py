import base64
import time
import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend
from config import KALSHI_HOST, KALSHI_API_KEY_ID, KALSHI_PRIVATE_KEY

CRYPTO_SERIES = ["KXBTC", "KXETH", "KXSOL", "KXDOGE", "KXXRP"]
CACHE_TTL  = 60
MAX_PAGES  = 60
_cache = {"markets": [], "fetched_at": 0}


def _sign(method: str, path: str) -> dict:
    timestamp = str(int(time.time() * 1000))
    message = (timestamp + method.upper() + path).encode("utf-8")
    private_key = serialization.load_pem_private_key(
        KALSHI_PRIVATE_KEY.encode(),
        password=None,
        backend=default_backend(),
    )
    signature = private_key.sign(
        message,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.DIGEST_LENGTH,
        ),
        hashes.SHA256(),
    )
    return {
        "KALSHI-ACCESS-KEY":       KALSHI_API_KEY_ID,
        "KALSHI-ACCESS-TIMESTAMP": timestamp,
        "KALSHI-ACCESS-SIGNATURE": base64.b64encode(signature).decode(),
        "Content-Type":            "application/json",
    }


def auth_headers(method: str, path: str) -> dict:
    return _sign(method, path)


def _cents_to_dollars(val):
    if val is None:
        return None
    v = float(val)
    return v / 100.0 if v > 1 else v


def normalize_price(market: dict, base: str):
    for field_name in (f"{base}_dollars", base):
        val = market.get(field_name)
        if val is not None:
            return _cents_to_dollars(val)
    return None


def normalize_market(m: dict) -> dict:
    return {
        **m,
        "yes_ask": normalize_price(m, "yes_ask"),
        "no_ask":  normalize_price(m, "no_ask"),
        "yes_bid": normalize_price(m, "yes_bid"),
        "no_bid":  normalize_price(m, "no_bid"),
    }


def yes_ask(market):
    return normalize_price(market, "yes_ask")


def no_ask(market):
    return normalize_price(market, "no_ask")


def _fetch_series(series_ticker: str) -> list:
    """Fetch all markets for a specific series (guaranteed to return crypto markets)."""
    markets = []
    cursor = None
    while True:
        params = {"limit": 200, "status": "open", "series_ticker": series_ticker}
        if cursor:
            params["cursor"] = cursor
        try:
            resp = requests.get(f"{KALSHI_HOST}/markets", params=params, timeout=15)
            if not resp.ok:
                break
            data = resp.json()
        except Exception:
            break
        batch = data.get("markets", [])
        markets.extend(batch)
        cursor = data.get("cursor")
        if not cursor or not batch:
            break
        time.sleep(0.2)
    return markets


def fetch_markets(force=False):
    now = time.time()
    if not force and _cache["markets"] and now - _cache["fetched_at"] < CACHE_TTL:
        return _cache["markets"]

    all_markets = []
    seen_tickers = set()

    # Always fetch crypto series first — these are what the quant model needs
    for series in CRYPTO_SERIES:
        batch = _fetch_series(series)
        for m in batch:
            if m["ticker"] not in seen_tickers:
                all_markets.append(normalize_market(m))
                seen_tickers.add(m["ticker"])
        print(f"[Markets] {series}: {len(batch)} markets")
        time.sleep(0.3)

    # Then fetch all other open markets for arb strategies
    cursor = None
    for page in range(MAX_PAGES):
        params = {"limit": 200, "status": "open"}
        if cursor:
            params["cursor"] = cursor
        try:
            resp = requests.get(f"{KALSHI_HOST}/markets", params=params, timeout=15)
            if not resp.ok:
                break
            data = resp.json()
        except Exception as e:
            print(f"[Markets] fetch error: {e}")
            break
        batch = data.get("markets", [])
        for m in batch:
            if m["ticker"] not in seen_tickers:
                all_markets.append(normalize_market(m))
                seen_tickers.add(m["ticker"])
        cursor = data.get("cursor")
        if not cursor or not batch:
            break
        time.sleep(0.2)

    _cache["markets"] = all_markets
    _cache["fetched_at"] = time.time()
    print(f"[Markets] Total: {len(all_markets)} markets")
    return all_markets
