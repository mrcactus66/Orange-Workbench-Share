"""Read-only market pricing and trade valuation helpers."""
from __future__ import annotations

import json
import os
import re
import threading
import time
import urllib.parse
import urllib.request


TOKEN_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "token_contracts.json")
QUOTE_SUFFIXES = ("USDT", "USDC", "BUSD", "USD")
TOKEN_ALIASES = {"CRCLB": ("CRCLB", "CIRCLE")}
COINGECKO_IDS = {
    "BTC": "bitcoin", "ETH": "ethereum", "BNB": "binancecoin", "SOL": "solana",
    "APT": "aptos", "AVAX": "avalanche-2", "SUI": "sui", "XRP": "ripple",
    "DOGE": "dogecoin", "ADA": "cardano", "LINK": "chainlink", "UNI": "uniswap",
    "ARB": "arbitrum", "OP": "optimism", "TON": "the-open-network", "TRX": "tron",
}
_cache = {"expires": 0.0, "quotes": {}}
_last_good = {}
_cache_lock = threading.Lock()


def normalize_symbol(value):
    text = str(value or "").upper().strip()
    first = re.split(r"[\s/\-_:]+", text)[0]
    for suffix in QUOTE_SUFFIXES:
        if first.endswith(suffix) and len(first) > len(suffix):
            return first[: -len(suffix)]
    return re.sub(r"[^A-Z0-9]", "", first)


def calculate_position(position, price):
    """Calculate mark-to-market equity and PnL without mutating the ledger."""
    principal = float(position.get("trade_amount") or 0)
    entry = float(position.get("entry_price") or 0)
    current = float(price or 0)
    fees = float(position.get("fees") or 0)
    market_type = "contract" if position.get("market_type") == "contract" else "spot"
    leverage = max(1.0, float(position.get("leverage") or 1)) if market_type == "contract" else 1.0
    if principal <= 0 or entry <= 0 or current <= 0:
        raise ValueError("本金、入场价和当前价必须大于 0")
    direction = -1.0 if position.get("direction") == "做空" else 1.0
    quantity = float(position.get("quantity") or 0)
    if quantity > 0:
        pnl = (current - entry) * quantity * direction - fees
    else:
        return_rate = (current - entry) / entry * direction
        pnl = principal * leverage * return_rate - fees
    current_value = quantity * current if market_type == "spot" and quantity > 0 else principal + pnl
    return {
        "current_value": current_value,
        "pnl": pnl,
        "pnl_pct": pnl / principal * 100,
        "leverage": leverage,
    }


def _request_json(url, timeout=6):
    req = urllib.request.Request(url, headers={"User-Agent": "Orange-Workbench/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _binance_prices(path, field):
    try:
        payload = _request_json(path)
        if isinstance(payload, dict):
            payload = [payload]
        return {
            str(item.get("symbol", "")).upper(): float(item[field])
            for item in payload
            if item.get("symbol") and item.get(field) and float(item[field]) > 0
        }
    except Exception:
        return {}


def _token_metadata():
    try:
        with open(TOKEN_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, ValueError):
        return {}
    found = {}
    for category in data.get("categories", []):
        for token in category.get("tokens", []):
            name = normalize_symbol(token.get("name"))
            if name and token.get("address"):
                found[name] = token
    return found


def _coingecko_prices(symbols):
    requested = {symbol: COINGECKO_IDS[symbol] for symbol in symbols if symbol in COINGECKO_IDS}
    if not requested:
        return {}
    query = urllib.parse.urlencode({"ids": ",".join(sorted(set(requested.values()))), "vs_currencies": "usd"})
    try:
        payload = _request_json("https://api.coingecko.com/api/v3/simple/price?" + query)
    except Exception:
        return {}
    return {
        symbol + "USDT": float(payload[token_id]["usd"])
        for symbol, token_id in requested.items()
        if token_id in payload and float(payload[token_id].get("usd") or 0) > 0
    }


def _contract_token(symbol, metadata):
    for candidate in TOKEN_ALIASES.get(symbol, (symbol,)):
        token = metadata.get(normalize_symbol(candidate))
        if token:
            return token
    return None


def _dex_price(token):
    address = str(token.get("address") or "").strip()
    if not address:
        return None
    try:
        payload = _request_json(
            "https://api.dexscreener.com/latest/dex/tokens/" + urllib.parse.quote(address),
            timeout=8,
        )
        pairs = [
            pair for pair in (payload.get("pairs") or [])
            if str(pair.get("baseToken", {}).get("address", "")).lower() == address.lower()
            and pair.get("priceUsd")
        ]
        if not pairs:
            return None
        pairs.sort(key=lambda pair: float(pair.get("liquidity", {}).get("usd") or 0), reverse=True)
        price = float(pairs[0]["priceUsd"])
        return price if price > 0 else None
    except Exception:
        return None


def quote_positions(positions, force=False):
    open_positions = [position for position in positions if position.get("status") == "open"]
    cache_key = tuple(sorted(
        (str(position.get("id")), normalize_symbol(position.get("token_pair")), position.get("market_type", "spot"))
        for position in open_positions
    ))
    now = time.time()
    with _cache_lock:
        cached = _cache.get("quotes", {}).get(cache_key)
        if cached and not force and _cache.get("expires", 0) > now:
            return cached

    symbols = {normalize_symbol(position.get("token_pair")) for position in open_positions}
    spot = _binance_prices("https://api.binance.com/api/v3/ticker/price", "price")
    coingecko = _coingecko_prices(symbols)
    needs_contract = any(position.get("market_type") == "contract" for position in open_positions)
    marks = _binance_prices("https://fapi.binance.com/fapi/v1/premiumIndex", "markPrice") if needs_contract else {}
    metadata = _token_metadata()
    results = {}
    for position in open_positions:
        position_id = str(position.get("id", ""))
        symbol = normalize_symbol(position.get("token_pair"))
        market_type = "contract" if position.get("market_type") == "contract" else "spot"
        price = None
        source = ""
        pair_symbol = symbol + "USDT"
        if market_type == "contract" and pair_symbol in marks:
            price, source = marks[pair_symbol], "Binance 合约标记价"
        elif pair_symbol in spot:
            price, source = spot[pair_symbol], "Binance 现货"
        elif pair_symbol in coingecko:
            price, source = coingecko[pair_symbol], "CoinGecko 现货"
        elif pair_symbol in marks:
            price, source = marks[pair_symbol], "Binance 合约标记价"
        else:
            token = _contract_token(symbol, metadata)
            price = _dex_price(token) if token else None
            if price:
                source = "DexScreener · 常用代币合约"
        if not price:
            with _cache_lock:
                previous = _last_good.get(position_id)
            if previous:
                results[position_id] = {
                    **previous,
                    "stale": True,
                    "source": previous.get("source", "行情") + " · 上次成功",
                }
                continue
            results[position_id] = {
                "status": "unavailable", "symbol": symbol,
                "reason": "未匹配到可用行情，请在常用代币合约中登记地址",
            }
            continue
        try:
            valuation = calculate_position(position, price)
        except (TypeError, ValueError) as error:
            results[position_id] = {"status": "invalid", "symbol": symbol, "reason": str(error)}
            continue
        results[position_id] = {
            "status": "ok", "symbol": symbol, "price": price, "source": source,
            "market_type": market_type, "stale": False, **valuation,
        }
        with _cache_lock:
            _last_good[position_id] = dict(results[position_id])
    with _cache_lock:
        _cache["quotes"] = {cache_key: results}
        _cache["expires"] = now + 30
    return results
