import base64
import time
import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend
from config import KALSHI_HOST, KALSHI_API_KEY_ID, KALSHI_PRIVATE_KEY

CRYPTO_SERIES = ["KXBTC", "KXETH", "KXSOL", "KXDOGE", "KXXRP"]
CACHE_TTL = 60
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


def _fetch_series(series_ticker: str) -> list:
    markets = []
    cursor = None
    path = "/trade-api/v2/markets"

    while True:
        params = {"limit": 200, "status": "open", "series_ticker": series_ticker}
        if cursor:
            params["cursor"] = cursor

        try:
            resp = requests.get(f"{KALSHI_HOST}/markets", params=params, timeout=15)
            if not resp.ok:
                print(f"[Markets] {series_ticker} error {resp.status_code}: {resp.text[:200]}")
                break
            data = resp.json()
        except Exception as e:
            print(f"[Markets] {series_ticker} fetch error: {e}")
            break

        batch = data.get("markets", [])
        markets.extend(batch)
        cursor = data.get("cursor")
        if not cursor or not batch:
            break

        time.sleep(0.3)  # respect rate limits

    return markets


def fetch_markets(force=False):
    now = time.time()
    if not force and _cache["markets"] and now - _cache["fetched_at"] < CACHE_TTL:
        return _cache["markets"]

    all_markets = []
    for series in CRYPTO_SERIES:
        batch = _fetch_series(series)
        all_markets.extend(normalize_market(m) for m in batch)
        print(f"[Markets] {series}: {len(batch)} markets")
        time.sleep(0.5)

    _cache["markets"] = all_markets
    _cache["fetched_at"] = time.time()
    print(f"[Markets] Total crypto markets: {len(all_markets)}")
    return all_markets


def _cents_to_dollars(val) -> float | None:
    """Kalshi prices can be in cents (int) or already fractional (float < 1)."""
    if val is None:
        return None
    v = float(val)
    # If the value is > 1 it's in cents (e.g. 30 → $0.30)
    return v / 100.0 if v > 1 else v


def normalize_price(market: dict, base: str) -> float:
    for field_name in (f"{base}_dollars", base):
        val = market.get(field_name)
        if val is not None:
            return _cents_to_dollars(val)
    return None


def normalize_market(m: dict) -> dict:
    """Return a clean dict with guaranteed price keys for the strategy layer."""
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
