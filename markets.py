import base64
import time
import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend
from config import KALSHI_HOST, KALSHI_API_KEY_ID, KALSHI_PRIVATE_KEY

_cache = {"markets": [], "fetched_at": 0}
CACHE_TTL = 60


def _sign(method: str, path: str) -> dict:
    timestamp = str(int(time.time() * 1000))
    message = (timestamp + method.upper() + path).encode("utf-8")

    print(f"[Auth] Key ID: {KALSHI_API_KEY_ID[:8]}..." if KALSHI_API_KEY_ID else "[Auth] ERROR: No Key ID set")
    print(f"[Auth] Key loaded: {bool(KALSHI_PRIVATE_KEY)} | First line: {KALSHI_PRIVATE_KEY.splitlines()[0] if KALSHI_PRIVATE_KEY else 'EMPTY'}")
    print(f"[Auth] Signing: {timestamp[:6]}... + {method.upper()} + {path}")

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


def fetch_markets(force=False):
    now = time.time()
    if not force and _cache["markets"] and now - _cache["fetched_at"] < CACHE_TTL:
        return _cache["markets"]

    all_markets = []
    cursor = None
    path_base = "/trade-api/v2/markets"

    while True:
        params = {"limit": 1000, "status": "open"}
        if cursor:
            params["cursor"] = cursor

        try:
            resp = requests.get(
                f"{KALSHI_HOST}/markets",
                params=params,
                headers=auth_headers("GET", path_base),
                timeout=15,
            )
            if not resp.ok:
                print(f"[Markets] HTTP {resp.status_code}: {resp.text[:500]}")
                break
            data = resp.json()
        except Exception as e:
            print(f"[Markets] Error type: {type(e).__name__}")
            print(f"[Markets] Error: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"[Markets] Response body: {e.response.text[:500]}")
            break

        batch = data.get("markets", [])
        all_markets.extend(batch)
        cursor = data.get("cursor")
        if not cursor or not batch:
            break

    _cache["markets"] = all_markets
    _cache["fetched_at"] = time.time()
    print(f"[Markets] Loaded {len(all_markets)} open markets")
    return all_markets


def yes_ask(market):
    return market.get("yes_ask")

def no_ask(market):
    return market.get("no_ask")
