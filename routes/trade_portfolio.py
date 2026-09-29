"""Aggregation and moving-average accounting for trading positions."""
from __future__ import annotations

from datetime import datetime

from routes.market_prices import normalize_symbol


def number(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def position_market(position):
    return "contract" if position.get("market_type") == "contract" else "spot"


def position_leverage(position):
    return max(1.0, number(position.get("leverage", 1))) if position_market(position) == "contract" else 1.0


def position_quantity(position):
    explicit = number(position.get("quantity"))
    if explicit > 0:
        return explicit
    entry = number(position.get("entry_price"))
    principal = number(position.get("trade_amount"))
    return principal * position_leverage(position) / entry if entry > 0 and principal > 0 else 0.0


def group_key(position):
    symbol = normalize_symbol(position.get("token_pair"))
    market = position_market(position)
    direction = "short" if position.get("direction") == "做空" else "long"
    leverage = f"{position_leverage(position):g}" if market == "contract" else "1"
    return f"{symbol}|{market}|{direction}|{leverage}"


def aggregate_positions(positions):
    """Return display positions without changing the individual ledger lots."""
    grouped = {}
    for position in positions:
        if position.get("status") != "open":
            continue
        quantity = position_quantity(position)
        principal = number(position.get("trade_amount"))
        if quantity <= 0 or principal <= 0:
            continue
        key = group_key(position)
        item = grouped.setdefault(key, {
            "id": key,
            "group_id": key,
            "token_pair": normalize_symbol(position.get("token_pair")) or str(position.get("token_pair", "")),
            "direction": position.get("direction", "做多"),
            "market_type": position_market(position),
            "leverage": position_leverage(position),
            "trade_amount": 0.0,
            "current_balance": 0.0,
            "fees": 0.0,
            "quantity": 0.0,
            "notional_cost": 0.0,
            "lot_count": 0,
            "lot_ids": [],
            "open_date": str(position.get("open_date", "")),
            "status": "open",
        })
        item["trade_amount"] += principal
        item["current_balance"] += number(position.get("current_balance", principal))
        item["fees"] += number(position.get("fees"))
        item["quantity"] += quantity
        item["notional_cost"] += principal * position_leverage(position)
        item["lot_count"] += 1
        item["lot_ids"].append(str(position.get("id", "")))
        opened = str(position.get("open_date", ""))
        if opened and (not item["open_date"] or opened < item["open_date"]):
            item["open_date"] = opened
    for item in grouped.values():
        item["entry_price"] = item["notional_cost"] / item["quantity"] if item["quantity"] else 0.0
    return sorted(grouped.values(), key=lambda item: (item["market_type"], item["token_pair"], item["direction"]))


def lots_for_group(positions, key):
    return [position for position in positions if position.get("status") == "open" and group_key(position) == key]


def apply_sale(positions, key, quantity, unit_price, fees=0.0, close_date=""):
    """Reduce all lots proportionally so the pooled average cost remains stable."""
    lots = lots_for_group(positions, key)
    total_quantity = sum(position_quantity(position) for position in lots)
    if not lots or quantity <= 0 or unit_price <= 0:
        raise ValueError("卖出数量和单价必须大于 0")
    if quantity > total_quantity + max(1e-12, total_quantity * 1e-9):
        raise ValueError("卖出数量不能超过当前持仓数量")
    quantity = min(quantity, total_quantity)
    aggregate = aggregate_positions(lots)[0]
    average_entry = number(aggregate.get("entry_price"))
    direction = -1.0 if aggregate.get("direction") == "做空" else 1.0
    allocated_open_fees = 0.0
    remaining_ratio = max(0.0, (total_quantity - quantity) / total_quantity)
    for lot in lots:
        original_fee = number(lot.get("fees"))
        allocated_open_fees += original_fee * (1 - remaining_ratio)
        lot["quantity"] = position_quantity(lot) * remaining_ratio
        lot["trade_amount"] = number(lot.get("trade_amount")) * remaining_ratio
        lot["current_balance"] = number(lot.get("current_balance", lot.get("trade_amount"))) * remaining_ratio
        lot["fees"] = original_fee * remaining_ratio
        if remaining_ratio <= 1e-12:
            lot["status"] = "closed"
            lot["close_date"] = close_date
    gross_profit = (unit_price - average_entry) * quantity * direction
    profit = gross_profit - allocated_open_fees - fees
    released_principal = number(aggregate.get("trade_amount")) * (quantity / total_quantity)
    return {
        "group": aggregate,
        "quantity": quantity,
        "unit_price": unit_price,
        "average_entry": average_entry,
        "released_principal": released_principal,
        "proceeds": quantity * unit_price,
        "profit": profit,
        "fees": fees,
        "fully_closed": remaining_ratio <= 1e-12,
    }


def holding_duration(open_date, close_date):
    try:
        start = datetime.fromisoformat(str(open_date)[:10])
        end = datetime.fromisoformat(str(close_date)[:10])
        return f"{max(0, (end - start).days)}天"
    except (TypeError, ValueError):
        return ""
