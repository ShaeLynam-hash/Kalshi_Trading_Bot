import base64
import time
import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend
from config import KALSHI_HOST, KALSHI_API_KEY_ID, KALSHI_PRIVATE_KEY

CACHE_TTL  = 60
MAX_PAGES  = 60     # 60 × 200 = up to 12,000 markets
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


def fetch_markets(force=False):
    now = time.time()
    if not force and _cache["markets"] and now - _cache["fetched_at"] < CACHE_TTL:
        return _cache["markets"]

    all_markets = []
    cursor = None

    for page in range(MAX_PAGES):
        params = {"limit": 200, "status": "open"}
        if cursor:
            params["cursor"] = cursor

        try:
            resp = requests.get(f"{KALSHI_HOST}/markets", params=params, timeout=15)
            if not resp.ok:
                print(f"[Markets] error {resp.status_code}: {resp.text[:200]}")
                break
            data = resp.json()
        except Exception as e:
            print(f"[Markets] fetch error: {e}")
            break

        batch = data.get("markets", [])
        all_markets.extend(normalize_market(m) for m in batch)
        cursor = data.get("cursor")

        if not cursor or not batch:
            break

        time.sleep(0.25)

    _cache["markets"] = all_markets
    _cache["fetched_at"] = time.time()
    print(f"[Markets] Fetched {len(all_markets)} open markets")
    return all_markets
