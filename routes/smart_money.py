"""聪明钱地址库：本地分类管理与可选的 DeBank 资产同步。"""
from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from flask import redirect, render_template, render_template_string, request

from templates import LAYOUT
from utils import load_json, now_str, save_json


DATA_FILE = Path(__file__).resolve().parents[1] / "data" / "smart_wallets.json"

STRATEGIES = ["MEME", "LP", "DeFi", "套利", "NFT", "稳定币"]
CHAINS = ["Ethereum", "BSC", "Base", "Arbitrum", "Optimism", "Polygon", "Avalanche", "X Layer", "Solana"]
CAPITAL_TIERS = [
    ("unknown", "待评估"),
    ("under_10k", "<$10K"),
    ("10k_100k", "$10K–$100K"),
    ("100k_1m", "$100K–$1M"),
    ("over_1m", ">$1M"),
]
PRIORITIES = [("core", "重点跟踪"), ("watch", "持续观察"), ("normal", "普通记录"), ("paused", "暂停观察")]
ACTIVITIES = [("high", "高频"), ("medium", "中频"), ("low", "低频"), ("unknown", "待评估")]

EXPLORERS = {
    "Ethereum": "https://etherscan.io/address/",
    "BSC": "https://bscscan.com/address/",
    "Base": "https://basescan.org/address/",
    "Arbitrum": "https://arbiscan.io/address/",
    "Optimism": "https://optimistic.etherscan.io/address/",
    "Polygon": "https://polygonscan.com/address/",
    "Avalanche": "https://snowscan.xyz/address/",
    "X Layer": "https://www.oklink.com/x-layer/address/",
    "Solana": "https://solscan.io/account/",
}

DEBANK_CHAIN_NAMES = {
    "eth": "Ethereum", "bsc": "BSC", "base": "Base", "arb": "Arbitrum",
    "op": "Optimism", "matic": "Polygon", "avax": "Avalanche", "xlayer": "X Layer",
}

EVM_ADDRESS = re.compile(r"^0x[a-fA-F0-9]{40}$")
SOL_ADDRESS = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")


def _load():
    data = load_json(str(DATA_FILE))
    return data if isinstance(data.get("wallets"), list) else {"wallets": []}


def _save(data):
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    save_json(str(DATA_FILE), data)


def _clean_address(value):
    address = str(value or "").strip()
    return address.lower() if EVM_ADDRESS.fullmatch(address) else address


def _address_kind(address):
    if EVM_ADDRESS.fullmatch(address):
        return "EVM"
    if SOL_ADDRESS.fullmatch(address):
        return "Solana"
    return ""


def _safe_url(value):
    url = str(value or "").strip()
    return url if url.startswith(("https://", "http://")) else ""


def _float(value):
    try:
        return max(0.0, float(value or 0))
    except (TypeError, ValueError):
        return 0.0


def _capital_tier(value):
    if value >= 1_000_000:
        return "over_1m"
    if value >= 100_000:
        return "100k_1m"
    if value >= 10_000:
        return "10k_100k"
    if value > 0:
        return "under_10k"
    return "unknown"


def _redirect(message="", kind="success"):
    query = urlencode({"notice": message, "kind": kind}) if message else ""
    return redirect("/smart-money" + ("?" + query if query else ""))


def smart_money_page():
    data = _load()
    wallets = sorted(
        data["wallets"],
        key=lambda item: (
            {"core": 0, "watch": 1, "normal": 2, "paused": 3}.get(item.get("priority"), 2),
            -_float(item.get("estimated_assets")),
            str(item.get("name", "")).lower(),
        ),
    )
    total_assets = sum(_float(item.get("estimated_assets")) for item in wallets)
    stats = {
        "total": len(wallets),
        "core": sum(item.get("priority") == "core" for item in wallets),
        "meme": sum("MEME" in item.get("strategies", []) for item in wallets),
        "lp": sum("LP" in item.get("strategies", []) for item in wallets),
        "multi_chain": sum(len(item.get("chains", [])) > 1 for item in wallets),
        "assets": total_assets,
    }
    content = render_template(
        "smart_money.html",
        wallets=wallets,
        wallets_json=json.dumps(wallets, ensure_ascii=False).replace("<", "\\u003c"),
        stats=stats,
        strategies=STRATEGIES,
        chains=CHAINS,
        capital_tiers=CAPITAL_TIERS,
        capital_labels=dict(CAPITAL_TIERS),
        priorities=PRIORITIES,
        priority_labels=dict(PRIORITIES),
        activities=ACTIVITIES,
        activity_labels=dict(ACTIVITIES),
        explorer_urls=EXPLORERS,
        notice=request.args.get("notice", ""),
        notice_kind=request.args.get("kind", "success"),
        debank_enabled=bool(os.environ.get("DEBANK_ACCESS_KEY", "").strip()),
    )
    return render_template_string(LAYOUT, section="smart-money", now=now_str(), content=content)


def smart_money_save():
    data = _load()
    wallet_id = request.form.get("wallet_id", "").strip()
    address = _clean_address(request.form.get("address"))
    address_kind = _address_kind(address)
    if not address_kind:
        return _redirect("地址格式无效，请输入 EVM 或 Solana 钱包地址", "error")

    duplicate = next(
        (item for item in data["wallets"] if item.get("address", "").lower() == address.lower() and item.get("id") != wallet_id),
        None,
    )
    if duplicate:
        return _redirect("该地址已经登记，请直接编辑现有记录", "error")

    current = next((item for item in data["wallets"] if item.get("id") == wallet_id), None)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    estimated_assets = _float(request.form.get("estimated_assets"))
    record = dict(current or {})
    record.update({
        "id": wallet_id or uuid.uuid4().hex[:12],
        "name": request.form.get("name", "").strip() or "未命名钱包",
        "address": address,
        "address_kind": address_kind,
        "estimated_assets": estimated_assets,
        "capital_tier": request.form.get("capital_tier", "unknown") or _capital_tier(estimated_assets),
        "priority": request.form.get("priority", "watch"),
        "activity": request.form.get("activity", "unknown"),
        "strategies": [item for item in request.form.getlist("strategies") if item in STRATEGIES],
        "chains": [item for item in request.form.getlist("chains") if item in CHAINS],
        "tags": [item.strip() for item in request.form.get("tags", "").split(",") if item.strip()][:12],
        "source_url": _safe_url(request.form.get("source_url")),
        "note": request.form.get("note", "").strip(),
        "updated_at": now,
        "added_at": record.get("added_at", now),
        "data_source": record.get("data_source", "manual"),
    })
    if current:
        current.clear()
        current.update(record)
        message = "聪明钱地址已更新"
    else:
        data["wallets"].insert(0, record)
        message = "聪明钱地址已登记"
    _save(data)
    return _redirect(message)


def smart_money_delete():
    data = _load()
    wallet_id = request.form.get("wallet_id", "").strip()
    before = len(data["wallets"])
    data["wallets"] = [item for item in data["wallets"] if item.get("id") != wallet_id]
    if len(data["wallets"]) == before:
        return _redirect("未找到要删除的地址", "error")
    _save(data)
    return _redirect("地址记录已删除")


def smart_money_sync(wallet_id):
    access_key = os.environ.get("DEBANK_ACCESS_KEY", "").strip()
    if not access_key:
        return _redirect("尚未配置 DEBANK_ACCESS_KEY，当前继续使用手工记录", "error")
    data = _load()
    wallet = next((item for item in data["wallets"] if item.get("id") == wallet_id), None)
    if not wallet:
        return _redirect("未找到该地址", "error")
    if wallet.get("address_kind") != "EVM":
        return _redirect("DeBank 资产同步仅适用于 EVM 地址", "error")

    url = "https://pro-openapi.debank.com/v1/user/total_balance?" + urlencode({"id": wallet["address"]})
    try:
        api_request = Request(url, headers={"accept": "application/json", "AccessKey": access_key, "User-Agent": "Orange-Workbench/1.0"})
        with urlopen(api_request, timeout=12) as response:
            result = json.loads(response.read().decode("utf-8"))
        total = _float(result.get("total_usd_value"))
        balances = []
        detected_chains = []
        for chain in result.get("chain_list", []) or []:
            value = _float(chain.get("usd_value"))
            if value <= 0:
                continue
            chain_id = str(chain.get("id", ""))
            name = DEBANK_CHAIN_NAMES.get(chain_id, str(chain.get("name") or chain_id))
            balances.append({"chain": name, "usd": round(value, 2)})
            if name in CHAINS and name not in detected_chains:
                detected_chains.append(name)
        balances.sort(key=lambda item: item["usd"], reverse=True)
        wallet.update({
            "estimated_assets": round(total, 2),
            "capital_tier": _capital_tier(total),
            "chains": detected_chains or wallet.get("chains", []),
            "chain_balances": balances,
            "data_source": "debank",
            "last_synced_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        })
        _save(data)
        return _redirect("DeBank 资产与活跃链已同步")
    except HTTPError as exc:
        return _redirect(f"DeBank 同步失败（HTTP {exc.code}）", "error")
    except (URLError, TimeoutError, json.JSONDecodeError, OSError):
        return _redirect("DeBank 暂时不可用，原有记录未被修改", "error")
