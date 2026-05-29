import requests
import time
from config import KALSHI_HOST, KALSHI_EMAIL, KALSHI_PASSWORD

_session = {"token": None, "expires_at": 0}
_cache   = {"markets": [], "fetched_at": 0}
CACHE_TTL = 60


def get_token():
    now = time.time()
    if _session["token"] and now < _session["expires_at"]:
        return _session["token"]

    resp = requests.post(
        f"{KALSHI_HOST}/login",
        json={"email": KALSHI_EMAIL, "password": KALSHI_PASSWORD},
        timeout=10,
    )
    resp.raise_for_status()
    token = resp.json()["token"]
    _session["token"] = token
    _session["expires_at"] = now + 3600  # tokens last ~1 hour
    return token


def auth_headers():
    return {"Authorization": f"Bearer {get_token()}"}


def fetch_markets(force=False):
    now = time.time()
    if not force and _cache["markets"] and now - _cache["fetched_at"] < CACHE_TTL:
        return _cache["markets"]

    all_markets = []
    cursor = None

    while True:
        params = {"limit": 1000, "status": "open"}
        if cursor:
            params["cursor"] = cursor

        try:
            resp = requests.get(
                f"{KALSHI_HOST}/markets",
                params=params,
                headers=auth_headers(),
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"[Markets] Fetch error: {e}")
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
    return market.get("yes_ask")   # cents (1–99)


def no_ask(market):
    return market.get("no_ask")    # cents (1–99)
