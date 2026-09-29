"""LP 流动性看板：独立的数据展示与记账闭环。"""
from __future__ import annotations

import json
import time
import uuid
from collections import defaultdict
from datetime import datetime
from html import escape

from flask import redirect, render_template_string, request

from lp_sync import load_lp_data, save_lp_data
from templates import LAYOUT
from utils import PROJECTS_FILE

LP_PROJECT_ID = "xau-lp-001"

# LP 仓位的链元数据使用稳定显示名；旧仓位不强制迁移，用户可在列表中补充。
LP_CHAINS = (
    "X Layer",
    "Monad",
    "BNB Smart Chain",
    "Base",
    "Ink",
    "Robinhood Chain",
    "Sui",
    "Solana",
    "ARC",
    "Ethereum",
    "Arbitrum",
    "Optimism",
    "Polygon",
    "Avalanche",
    "Aptos",
    "Fogo",
)

CHAIN_COLORS = {
    "X Layer": "#16181d",
    "Monad": "#8367ff",
    "BNB Smart Chain": "#f0b90b",
    "Base": "#1652f0",
    "Ink": "#7047eb",
    "Robinhood Chain": "#00c805",
    "Sui": "#4da2ff",
    "Solana": "#14dca4",
    "ARC": "#ff5a36",
    "Ethereum": "#627eea",
    "Arbitrum": "#2d8dcc",
    "Optimism": "#ff0420",
    "Polygon": "#8247e5",
    "Avalanche": "#e84142",
    "Aptos": "#111827",
    "Fogo": "#f97316",
}


def _number(value, default=0.0):
    try:
        return float(value or default)
    except (TypeError, ValueError):
        return default


def _project(data):
    return next((item for item in data.get("projects", []) if item.get("id") == LP_PROJECT_ID), None)


def _invested(position):
    return _number(position.get("lp_amount")) + sum(_number(item.get("amount")) for item in position.get("top_ups", []))


def _holding_period(open_date):
    try:
        opened = datetime.fromisoformat(str(open_date).strip().replace("T", " "))
        current = datetime.now(tz=opened.tzinfo) if opened.tzinfo else datetime.now()
        total_minutes = max(0, int((current - opened).total_seconds() // 60))
        days, remaining_minutes = divmod(total_minutes, 24 * 60)
        hours, minutes = divmod(remaining_minutes, 60)
        return f"{days} 天 {hours} 小时 {minutes} 分钟"
    except (TypeError, ValueError):
        return "—"


def _display_datetime(value):
    """将 ISO 日期时间转换为更易读的界面格式，不改变源数据。"""
    text = str(value or "").strip()
    return text.replace("T", " ", 1) if text else "-"


def _pair_suggestions(positions):
    """按最近使用时间返回历史仓位名称，并忽略大小写去重。"""
    ordered = sorted(
        positions,
        key=lambda item: str(item.get("close_date") or item.get("open_date") or ""),
        reverse=True,
    )
    suggestions = []
    seen = set()
    for item in ordered:
        pair = str(item.get("token_pair") or "").strip()
        key = pair.casefold()
        if pair and key not in seen:
            seen.add(key)
            suggestions.append(pair)
    return suggestions


def _chain_options(selected="", include_placeholder=True):
    selected = str(selected or "").strip()
    options = [f"<option value='' disabled{' selected' if not selected else ''}>请选择所属链</option>"] if include_placeholder else []
    for chain in LP_CHAINS:
        options.append(
            f"<option value='{escape(chain)}'{' selected' if chain == selected else ''}>{escape(chain)}</option>"
        )
    return "".join(options)


def _load():
    return load_lp_data(PROJECTS_FILE)


def _save(data, touched_position_id):
    return save_lp_data(data, PROJECTS_FILE, touched_position_id)


def _back(message=""):
    return redirect("/lp" + ("?notice=" + message if message else ""))


def lp_dashboard_page():
    data, data_origin = _load()
    project = _project(data)
    if not project:
        return render_template_string(LAYOUT, section="lp", now=datetime.now().strftime("%Y-%m-%d %H:%M"), content="<div class='empty'>未找到 LP 数据项目。</div>")

    positions = project.get("lp_positions", [])
    open_positions = [item for item in positions if item.get("status") == "open"]
    closed_positions = [item for item in positions if item.get("status") == "closed"]
    current_value = sum(_number(item.get("current_balance"), _invested(item)) for item in open_positions)
    invested = sum(_invested(item) for item in open_positions)
    pending_fees = sum(_number(item.get("fees")) for item in open_positions)
    realized = sum(_number(item.get("profit")) for item in project.get("lp_operations", []) if item.get("type") == "close")
    claimed = sum(_number(item.get("claimed_fees")) for item in positions)
    unrealized = current_value + pending_fees - invested
    pnl_color = "var(--green)" if unrealized >= 0 else "var(--red)"
    notice = escape(request.args.get("notice", ""))
    source_status = "WSL 源数据已同步" if data_origin == "wsl" else "WSL 源数据暂不可达，正在使用本地缓存"

    # 只使用平仓操作的实际 profit 字段计算已实现盈亏图表；不把开仓或追加
    # 当作利润，也不将已包含在平仓结果内的费用重复记入。
    daily_pnl = defaultdict(float)
    for operation in project.get("lp_operations", []):
        if operation.get("type") == "close":
            day = str(operation.get("date", ""))[:10]
            if day:
                daily_pnl[day] += _number(operation.get("profit"))
    chart_series = [{"date": day, "pnl": round(amount, 2)} for day, amount in sorted(daily_pnl.items())]
    chart_payload = json.dumps(chart_series, ensure_ascii=False)
    pair_suggestions_payload = json.dumps(_pair_suggestions(positions), ensure_ascii=False)
    pair_suggestions_payload = pair_suggestions_payload.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    profit_days = sum(1 for item in chart_series if item["pnl"] > 0)
    best_day = max(chart_series, key=lambda item: item["pnl"], default={"date": "-", "pnl": 0})
    worst_day = min(chart_series, key=lambda item: item["pnl"], default={"date": "-", "pnl": 0})

    rows = []
    for item in sorted(open_positions, key=lambda p: p.get("open_date", ""), reverse=True):
        position_id = escape(str(item.get("id", "")))
        pair = escape(str(item.get("token_pair", "未命名仓位")))
        chain = str(item.get("chain") or "").strip()
        chain_color = CHAIN_COLORS.get(chain, "#94a3b8")
        chain_options = _chain_options(chain)
        principal = _invested(item)
        value = _number(item.get("current_balance"), principal)
        fees = _number(item.get("fees"))
        claimed_fees = _number(item.get("claimed_fees"))
        claimed_class = "claimed-fee has-value" if claimed_fees else "claimed-fee"
        pnl = value + fees - principal
        color = "var(--green)" if pnl >= 0 else "var(--red)"
        rows.append(f"""
        <tr data-search='{pair.lower()} {escape(chain.lower())}'>
          <td><strong>{pair}</strong><div class='muted'>{escape(str(item.get('note','')))}</div></td>
          <td><form class='chain-form' method='post' action='/lp/action'><input type='hidden' name='action' value='chain'><input type='hidden' name='id' value='{position_id}'><span class='chain-select-wrap' style='--chain-color:{chain_color}'><select class='chain-select' name='chain' aria-label='修改 {pair} 的所属链' onchange='this.form.submit()'>{chain_options}</select></span></form></td>
          <td>${principal:,.2f}</td><td>${value:,.2f}</td><td>${fees:,.2f}</td><td class='{claimed_class}'>${claimed_fees:,.2f}</td>
          <td style='color:{color};font-weight:700'>{'+' if pnl >= 0 else ''}${pnl:,.2f}</td>
          <td>{escape(_display_datetime(item.get('open_date')))}</td><td>{_holding_period(item.get('open_date'))}</td>
          <td><button class='position-action' type='button' data-id='{position_id}' data-pair='{pair}' data-value='{value:.2f}' data-fees='{fees:.2f}'>管理</button></td>
        </tr>""")

    history = []
    history_months = set()
    history_types = set()
    labels = {"open": "建仓", "topup": "追加", "reduce": "减仓", "claim": "认领费用", "close": "平仓"}
    for item in project.get("lp_operations", []):
        op_type = item.get("type", "")
        if op_type:
            history_types.add(op_type)
        amount = _number(item.get("profit")) if op_type in ("claim", "close") else _number(item.get("principal"))
        realized_pnl = _number(item.get("profit")) if op_type in ("claim", "close") else 0.0
        amount_class = "pnl-positive" if op_type in ("claim", "close") and amount > 0 else "pnl-negative" if op_type in ("claim", "close") and amount < 0 else "pnl-neutral"
        op_date = str(item.get("date", ""))
        op_day, op_month = op_date[:10], op_date[:7]
        if op_month:
            history_months.add(op_month)
        history.append(f"<tr class='op-row op-{escape(op_type)}' data-month='{escape(op_month)}' data-day='{escape(op_day)}' data-type='{escape(op_type)}' data-pnl='{realized_pnl:.8f}'><td>{escape(_display_datetime(op_date))}</td><td><span class='op-tag op-tag-{escape(op_type)}'>{labels.get(op_type, op_type)}</span></td><td>{escape(str(item.get('token_pair','-')))}</td><td><strong class='{amount_class}'>{'+' if amount > 0 and op_type in ('claim', 'close') else ''}${amount:,.2f}</strong></td><td>{escape(str(item.get('note','')))}</td></tr>")
    history_month_options = "".join(f"<option value='{escape(month)}'>{escape(month)}</option>" for month in sorted(history_months, reverse=True))
    type_order = ["open", "topup", "reduce", "claim", "close"]
    ordered_types = [item for item in type_order if item in history_types] + sorted(history_types - set(type_order))
    history_type_options = "".join(f"<option value='{escape(item)}'>{escape(labels.get(item, item))}</option>" for item in ordered_types)

    content = f"""
    <style>
      .lp-console{{color:var(--text)}}.lp-console .muted{{font-size:11px;color:#718096;margin-top:3px}}.lp-head{{display:flex;justify-content:space-between;gap:20px;align-items:flex-end;margin-bottom:18px}}.lp-head h1{{font-size:26px;letter-spacing:.2px;margin:0}}.lp-eyebrow{{color:#1589b3;font-size:11px;letter-spacing:1.2px;text-transform:uppercase;margin-bottom:5px}}.lp-console .btn{{background:#fff;border:1px solid #bcd7e4;color:#196f95}}.lp-grid{{display:grid;grid-template-columns:repeat(5,minmax(145px,1fr));gap:10px;margin-bottom:14px}}.metric,.analytics-card{{background:linear-gradient(135deg,#fff,#f8fcff);border:1px solid #d9e7ef;border-radius:12px;padding:14px 15px;box-shadow:0 5px 18px rgba(29,78,110,.04)}}.metric label,.analytics-card label{{font-size:11px;color:#718096}}.metric b,.analytics-card b{{display:block;font-size:20px;margin-top:5px;letter-spacing:.2px}}.analytics-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:0 0 14px}}.analytics-card{{padding:11px 14px}}.analytics-card b{{font-size:17px}}.charts-grid{{display:grid;grid-template-columns:1.3fr .9fr;gap:14px;margin-bottom:14px}}.chart-panel,.panel{{background:#fff;border:1px solid #d9e7ef;border-radius:13px;overflow:hidden;box-shadow:0 5px 18px rgba(29,78,110,.035)}}.chart-head,.panel-h{{padding:12px 15px;border-bottom:1px solid #e3edf3;font-weight:700;display:flex;justify-content:space-between;align-items:center}}.chart-head span{{color:#718096;font-size:11px;font-weight:400}}.chart-body{{height:245px;padding:12px 14px}}.heatmap-body{{padding:14px}}.heatmap-months{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}}.heat-month{{border:1px solid #e2edf3;border-radius:9px;padding:9px;background:#fbfdff}}.heat-month-title{{font-size:12px;font-weight:700;color:#24536c;margin-bottom:8px}}.heat-weekdays,.heat-calendar{{display:grid;grid-template-columns:repeat(7,1fr);gap:3px}}.heat-weekdays span{{font-size:9px;text-align:center;color:#93a4b3}}.heat-day{{min-height:35px;border-radius:5px;padding:3px;background:#f1f6f9;color:#9aabb8;font-size:9px}}.heat-day.has-pnl{{color:#1f475f;background:#eaf7f5}}.heat-day.positive-2{{background:#c9f0e6;color:#08755f}}.heat-day.positive-3{{background:#9de4d2;color:#075d4d}}.heat-day.negative{{background:#fee7ea;color:#b23a4b}}.heat-pnl{{display:block;font-size:8px;font-weight:700;white-space:nowrap;margin-top:3px}}.lp-layout{{display:grid;grid-template-columns:minmax(0,1fr) 330px;gap:14px}}.table-wrap{{max-height:490px;overflow:auto}}.lp-table{{width:100%;border-collapse:collapse;font-size:12px}}.lp-table th{{position:sticky;top:0;background:#f1f7fa;z-index:1;text-align:left;padding:10px 12px;color:#547085;font-weight:600}}.lp-table td{{padding:11px 12px;border-top:1px solid #e5eef3;vertical-align:top}}.lp-table tr:hover{{background:#f7fbfd}}details summary{{cursor:pointer;color:#087cad;font-weight:600}}.quick-actions{{display:grid;gap:6px;width:210px;margin-top:8px}}.quick-actions form{{display:flex;gap:5px}}.quick-actions input,.add-grid input,.add-grid textarea{{min-width:0;width:100%;padding:7px 8px;background:#fff;border:1px solid #cbdde8;border-radius:6px;color:var(--text);font:inherit}}.lp-console button{{border:1px solid #087cad;border-radius:6px;padding:7px 9px;background:#087cad;color:white;cursor:pointer;white-space:nowrap;font-size:11px}}.lp-console .danger-form button{{background:#c84d60;border-color:#c84d60}}.add-grid{{padding:15px;display:grid;gap:10px}}.add-grid .two{{display:grid;grid-template-columns:1fr 1fr;gap:8px}}.notice{{background:#edf9f5;color:#19735f;border:1px solid #bee8da;border-radius:8px;padding:9px 12px;margin-bottom:14px;font-size:13px}}.op-tag{{background:#e7f4fb;color:#17749a;border-radius:12px;padding:2px 7px;font-size:11px}}@media(max-width:1050px){{.lp-grid{{grid-template-columns:repeat(3,1fr)}}.analytics-grid{{grid-template-columns:repeat(2,1fr)}}.charts-grid,.lp-layout{{grid-template-columns:1fr}}.heatmap-months{{grid-template-columns:repeat(2,1fr)}}}}@media(max-width:650px){{.lp-head{{display:block}}.lp-grid{{grid-template-columns:repeat(2,1fr)}}.heatmap-months{{grid-template-columns:1fr}}}}
    </style>
    <div class='lp-console'><div class='lp-head'><div><div class='lp-eyebrow'>Portfolio Intelligence · Local Ledger</div><h1>LP 流动性</h1><p class='muted'>真实平仓数据驱动 · 估值、费用与仓位操作统一留痕 · {source_status}</p></div><div class='lp-head-actions'><button id='open-add-modal' type='button'>新增仓位</button><button id='open-apy-modal' type='button' class='quiet-action'>APY 计算器</button><button id='open-history-modal' type='button' class='quiet-action'>操作明细</button><button id='open-range-modal' type='button' class='quiet-action' aria-haspopup='dialog'>区间计算器</button></div></div>
    {f"<div class='notice'>{notice}</div>" if notice else ''}
    <section class='summary-grid'><div class='metric'><label>开仓仓位</label><b>{len(open_positions)}</b></div><div class='metric'><label>当前仓位价值</label><b>${current_value:,.2f}</b></div><div class='metric'><label>待领手续费</label><b>${pending_fees:,.2f}</b></div><div class='metric'><label>浮动盈亏</label><b style='color:#179677'>{'+' if unrealized >= 0 else ''}${unrealized:,.2f}</b></div><div class='metric'><label>已实现盈亏</label><b style='color:#1689bd'>${realized:,.2f}</b></div><div class='analytics-card'><label>盈利天数</label><b style='color:#179677'>{profit_days} 天</b><span class='muted'>按日结算</span></div><div class='analytics-card'><label>最大日盈利</label><b style='color:#179677'>+${best_day['pnl']:,.2f}</b><span class='muted'>{best_day['date']}</span></div><div class='analytics-card'><label>最大日亏损</label><b style='color:#c84d60'>${worst_day['pnl']:,.2f}</b><span class='muted'>{worst_day['date']}</span></div><div class='analytics-card'><label>结算交易日</label><b>{len(chart_series)} 天</b><span class='muted'>仅已平仓</span></div></section>
    <section class='charts-grid'><div class='chart-panel'><div class='chart-head'>累计盈亏曲线 <span id='lp-month-total' class='month-total'>当月累计 --</span></div><div class='chart-body'><canvas id='lp-cumulative-chart'></canvas></div></div><div class='chart-panel'><div class='chart-head'>每日盈亏 <span>平仓日汇总 · USD</span></div><div class='chart-body'><canvas id='lp-daily-chart'></canvas></div></div><div class='chart-panel'><div class='chart-head'><strong id='lp-calendar-title'>盈亏日历</strong><span>按日期展示已实现盈亏</span></div><div id='lp-heatmap' class='heatmap-body'></div></div></section>
    <div class='lp-layout'><section class='panel'><div class='panel-h'>活跃仓位 <span class='muted'>{len(open_positions)} 开仓 / {len(closed_positions)} 已关闭</span></div><div style='padding:10px 12px;border-bottom:1px solid var(--border)'><input id='lp-search' class='form-control' placeholder='按代币对或所属链筛选仓位'></div><div class='table-wrap'><table class='lp-table'><thead><tr><th>代币对 / 备注</th><th>所属链</th><th>总投入</th><th>当前价值</th><th>待领费</th><th>已领取费</th><th>浮动盈亏</th><th>开仓时间</th><th>持仓时长</th><th>记账操作</th></tr></thead><tbody id='lp-rows'>{''.join(rows) or "<tr><td colspan='10' class='empty'>暂无开仓仓位</td></tr>"}</tbody></table></div></section>
    <aside class='panel'><div class='panel-h'>新增 LP 仓位</div><form method='post' action='/lp/action' class='add-grid'><input type='hidden' name='action' value='open'><input name='pair' placeholder='代币对，例如 ETH / USDC' required><select name='chain' required>{_chain_options()}</select><div class='two'><input name='amount' type='number' min='0.01' step='0.01' placeholder='初始投入 ($)' required><input name='fees' type='number' min='0' step='0.01' placeholder='初始待领费用'></div><input name='date' type='datetime-local' value='{datetime.now().strftime('%Y-%m-%dT%H:%M')}' required><textarea name='note' rows='3' placeholder='备注（可选）'></textarea><button type='submit'>记录新仓位</button></form><div class='panel-h'>最近操作</div><div class='table-wrap' style='max-height:360px'><table class='lp-table'><tbody>{''.join(history) or "<tr><td class='empty'>暂无历史记录</td></tr>"}</tbody></table></div></aside></div>
    <script>document.getElementById('lp-search').addEventListener('input',function(e){{var q=e.target.value.trim().toLowerCase();document.querySelectorAll('#lp-rows tr[data-search]').forEach(function(r){{r.style.display=!q||r.dataset.search.includes(q)?'':'none';}})}});(function(){{var series={chart_payload};var labels=series.map(function(x){{return x.date;}}),values=series.map(function(x){{return x.pnl;}}),cumulative=[],total=0;values.forEach(function(v){{total+=v;cumulative.push(+total.toFixed(2));}});var common={{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{display:false}},tooltip:{{callbacks:{{label:function(c){{return (c.raw>=0?'+':'')+'$'+Number(c.raw).toFixed(2);}}}}}}}},scales:{{x:{{ticks:{{color:'#91a5bd',maxTicksLimit:8,font:{{size:10}}}},grid:{{color:'rgba(113,153,190,.13)'}}}},y:{{ticks:{{color:'#91a5bd',callback:function(v){{return '$'+v;}}}},grid:{{color:'rgba(113,153,190,.13)'}}}}}}}};if(window.Chart){{new Chart(document.getElementById('lp-cumulative-chart'),{{type:'line',data:{{labels:labels,datasets:[{{data:cumulative,borderColor:'#55e6be',backgroundColor:'rgba(85,230,190,.13)',fill:true,tension:.32,pointRadius:2,pointHoverRadius:5}}]}},options:common}});new Chart(document.getElementById('lp-daily-chart'),{{type:'bar',data:{{labels:labels,datasets:[{{data:values,backgroundColor:values.map(function(v){{return v>=0?'rgba(85,230,190,.75)':'rgba(255,120,144,.75)';}}),borderRadius:4}}]}},options:common}});}}var heat=document.getElementById('lp-heatmap'),max=Math.max.apply(null,values.map(function(v){{return Math.abs(v);}}).concat([1])),map={{}};series.forEach(function(x){{map[x.date]=x.pnl;}});var start=series.length?new Date(series[0].date+'T00:00:00'):new Date(),end=series.length?new Date(series[series.length-1].date+'T00:00:00'):start;start.setDate(start.getDate()-((start.getDay()+6)%7));var grid=document.createElement('div');grid.className='heatmap-grid';for(var d=new Date(start);d<=end;d.setDate(d.getDate()+1)){{var key=d.toISOString().slice(0,10),v=map[key],cell=document.createElement('div');cell.className='heat-cell';if(v!==undefined){{if(v<0)cell.classList.add('heat-loss');else{{var level=Math.max(1,Math.ceil(Math.abs(v)/max*3));cell.classList.add('heat-'+level);}}cell.title=key+'  '+(v>=0?'+':'')+'$'+v.toFixed(2);}}grid.appendChild(cell);}}heat.appendChild(grid);}})();</script></div>"""
    # 日历在主内容之后构建，确保日格明确显示真实日期及当天的已实现盈亏。
    content += f"""<script>(function(){{
      var series={chart_payload}, byDate={{}}, max=1;
      series.forEach(function(item){{byDate[item.date]=item.pnl;max=Math.max(max,Math.abs(item.pnl));}});
      var months=Array.from(new Set(series.map(function(item){{return item.date.slice(0,7);}}))).sort();
      var host=document.getElementById('lp-heatmap'); host.innerHTML='';
      var wrap=document.createElement('div'); wrap.className='heatmap-months';
      months.forEach(function(month){{
        var year=Number(month.slice(0,4)), monthNo=Number(month.slice(5,7));
        var days=new Date(year,monthNo,0).getDate(), first=(new Date(year,monthNo-1,1).getDay()+6)%7;
        var card=document.createElement('section'); card.className='heat-month';
        var html='<div class="heat-weekdays"><span>一</span><span>二</span><span>三</span><span>四</span><span>五</span><span>六</span><span>日</span></div><div class="heat-calendar">';
        for(var blank=0;blank<first;blank++) html+='<div></div>';
        for(var day=1;day<=days;day++){{
          var date=month+'-'+String(day).padStart(2,'0'), pnl=byDate[date], cls='heat-day', text='';
          if(pnl!==undefined){{var ratio=Math.abs(pnl)/max;cls+=' has-pnl '+(pnl<0?'negative':ratio>.6?'positive-3':ratio>.25?'positive-2':'');text='<span class="heat-pnl">'+(pnl>=0?'+':'')+'$'+pnl.toFixed(1)+'</span>';}}
          html+='<div class="'+cls+'" title="'+date+(pnl===undefined?'：无平仓结算':'：'+(pnl>=0?'+':'')+'$'+pnl.toFixed(2))+'"><span>'+day+'</span>'+text+'</div>';
        }}
        card.innerHTML=html+'</div>';wrap.appendChild(card);
      }}); host.appendChild(wrap);
    }})();</script>"""
    content += f"""<style>.month-filter{{display:flex;align-items:center;gap:7px;flex-wrap:wrap;margin:0 0 14px;padding:10px 12px;background:#fff;border:1px solid #d9e7ef;border-radius:12px}}.month-filter strong{{font-size:12px;color:#31576b;margin-right:4px}}.month-filter button{{background:#f3f8fb!important;color:#547085!important;border:1px solid #d8e6ed!important;padding:5px 10px!important}}.month-filter button.active{{background:#087cad!important;color:#fff!important;border-color:#087cad!important}}</style><script>(function(){{
      var series={chart_payload}, months=Array.from(new Set(series.map(function(x){{return x.date.slice(0,7);}}))).sort(), current=months[months.length-1];
      var anchor=document.querySelector('.charts-grid'), filter=document.createElement('div');filter.className='month-filter';filter.innerHTML='<strong>结算月份</strong>';
      months.forEach(function(month){{var button=document.createElement('button');button.type='button';button.dataset.month=month;button.textContent=month;button.onclick=function(){{renderMonth(month);}};filter.appendChild(button);}});anchor.parentNode.insertBefore(filter,anchor);
      function calendar(month,items){{var host=document.getElementById('lp-heatmap'),title=document.getElementById('lp-calendar-title'),byDate={{}},max=1;title.textContent='盈亏日历 · '+month;items.forEach(function(x){{byDate[x.date]=x.pnl;max=Math.max(max,Math.abs(x.pnl));}});var year=Number(month.slice(0,4)),monthNo=Number(month.slice(5,7)),days=new Date(year,monthNo,0).getDate(),first=(new Date(year,monthNo-1,1).getDay()+6)%7,html='<div class="heatmap-months"><section class="heat-month"><div class="heat-weekdays"><span>一</span><span>二</span><span>三</span><span>四</span><span>五</span><span>六</span><span>日</span></div><div class="heat-calendar">';for(var blank=0;blank<first;blank++)html+='<div></div>';for(var day=1;day<=days;day++){{var date=month+'-'+String(day).padStart(2,'0'),pnl=byDate[date],cls='heat-day',text='';if(pnl!==undefined){{var r=Math.abs(pnl)/max;cls+=' has-pnl '+(pnl<0?'negative':r>.6?'positive-3':r>.25?'positive-2':'');text='<span class="heat-pnl">'+(pnl>=0?'+':'')+'$'+pnl.toFixed(1)+'</span>';}}html+='<div class="'+cls+'" title="'+date+(pnl===undefined?'：无平仓结算':'：'+(pnl>=0?'+':'')+'$'+pnl.toFixed(2))+'"><span>'+day+'</span>'+text+'</div>';}}host.innerHTML=html+'</div></section></div>';}}
      function renderMonth(month){{current=month;var items=series.filter(function(x){{return x.date.slice(0,7)===month;}}),labels=items.map(function(x){{return x.date.slice(5);}}),values=items.map(function(x){{return x.pnl;}}),sum=0,cumulative=values.map(function(v){{sum+=v;return +sum.toFixed(2);}});document.querySelectorAll('.month-filter button').forEach(function(b){{b.classList.toggle('active',b.dataset.month===month);}});var line=Chart.getChart('lp-cumulative-chart'),bar=Chart.getChart('lp-daily-chart');line.data.labels=labels;line.data.datasets[0].data=cumulative;line.options.plugins.tooltip.callbacks.title=function(ctx){{return month+'-'+ctx[0].label;}};line.update();bar.data.labels=labels;bar.data.datasets[0].data=values;bar.data.datasets[0].backgroundColor=values.map(function(v){{return v>=0?'rgba(23,150,119,.72)':'rgba(200,77,96,.72)';}});bar.options.plugins.tooltip.callbacks.title=function(ctx){{return month+'-'+ctx[0].label;}};bar.update();document.querySelector('.charts-grid .chart-head').childNodes[0].textContent='月内累计盈亏曲线 ';document.querySelectorAll('.charts-grid .chart-head')[1].childNodes[0].textContent='每日盈亏 · '+month+' ';calendar(month,items);}}
      renderMonth(current);
    }})();</script>"""
    content += f"""
    <style>
      .summary-grid{{display:grid;grid-template-columns:repeat(9,minmax(0,1fr));gap:8px;margin-bottom:10px}}.summary-grid .metric,.summary-grid .analytics-card{{min-width:0;padding:9px 11px;border-radius:10px;box-shadow:none}}.summary-grid label{{font-size:10px;white-space:nowrap}}.summary-grid b{{font-size:16px;margin-top:3px;white-space:nowrap}}.summary-grid .muted{{font-size:9px;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;display:block}}.charts-grid{{grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-bottom:12px}}.charts-grid .chart-body{{height:248px;padding:10px}}.charts-grid .heatmap-body{{height:248px;padding:10px;overflow:hidden}}.charts-grid .heatmap-months{{display:block}}.charts-grid .heat-month{{padding:7px}}.charts-grid .heat-day{{min-height:28px;font-size:8px}}.charts-grid .heat-pnl{{font-size:7px;margin-top:2px}}.lp-layout{{grid-template-columns:1fr}}.lp-layout>aside{{display:none}}.lp-secondary{{margin:0 0 12px}}.lp-secondary .panel-h{{padding:11px 14px}}.add-panel form{{padding:10px 12px}}.add-row{{display:grid;grid-template-columns:1.55fr .85fr .85fr 1.2fr 1.65fr auto;gap:8px;align-items:center}}.add-row input,.add-row textarea{{box-sizing:border-box;min-width:0;width:100%;padding:8px 9px;border:1px solid #cbdde8;border-radius:7px;font:inherit;color:var(--text);background:#fff}}.add-row textarea{{height:36px;resize:vertical}}.add-row button{{height:36px;border:1px solid #087cad;border-radius:7px;background:#087cad;color:#fff;font-weight:600;white-space:nowrap;padding:0 14px;cursor:pointer}}.operation-toolbar{{display:flex;gap:8px;align-items:center;padding:9px 12px;border-bottom:1px solid #e3edf3;background:#fbfdff}}.operation-toolbar label{{font-size:11px;color:#547085;white-space:nowrap}}.operation-toolbar select,.operation-toolbar input{{height:31px;border:1px solid #cbdde8;border-radius:6px;background:#fff;padding:0 8px;color:var(--text);font:inherit;font-size:12px}}.operation-toolbar button{{height:31px;padding:0 10px;border:1px solid #bcd7e4;border-radius:6px;background:#fff;color:#196f95;cursor:pointer;font-size:11px}}.operation-panel .table-wrap{{max-height:480px}}.operation-panel .lp-table td{{padding:9px 12px}}@media(max-width:1180px){{.summary-grid{{grid-template-columns:repeat(5,minmax(0,1fr))}}.charts-grid{{grid-template-columns:repeat(2,minmax(0,1fr))}}.add-row{{grid-template-columns:repeat(3,minmax(0,1fr))}}}}@media(max-width:760px){{.summary-grid,.charts-grid,.add-row{{grid-template-columns:repeat(2,minmax(0,1fr))}}.operation-toolbar{{flex-wrap:wrap}}}}
    </style>
    <section class='panel lp-secondary add-panel'><div class='panel-h'>新增 LP 仓位 <span class='muted'>输入名称可匹配历史仓位</span></div><form method='post' action='/lp/action' class='add-row'><input type='hidden' name='action' value='open'><div class='pair-combobox'><label class='sr-only' for='lp-pair-input'>代币对或仓位名称</label><input id='lp-pair-input' name='pair' placeholder='代币对，例如 ETH / USDC' autocomplete='off' role='combobox' aria-autocomplete='list' aria-controls='lp-pair-suggestions' aria-expanded='false' required><div id='lp-pair-suggestions' class='pair-suggestions' role='listbox' aria-label='历史仓位候选' hidden></div></div><label class='add-chain-field'><span>所属链</span><select name='chain' required>{_chain_options()}</select></label><input name='amount' type='number' min='0.01' step='0.01' placeholder='初始投入 ($)' required><input name='fees' type='number' min='0' step='0.01' placeholder='初始待领费用'><input name='date' type='datetime-local' value='{datetime.now().strftime('%Y-%m-%dT%H:%M')}' required><textarea name='note' placeholder='备注（可选）'></textarea><button type='submit'>记录新仓位</button></form></section>
    <section class='panel lp-secondary operation-panel'><div class='panel-h'>操作明细 <span class='muted'>按日期与操作类型组合筛选</span></div><div class='operation-toolbar'><label for='op-month'>月份</label><select id='op-month'><option value=''>全部月份</option>{history_month_options}</select><label for='op-day'>日期</label><input id='op-day' type='date'><label for='op-type' class='op-type-label'>类型</label><select id='op-type'><option value=''>全部类型</option>{history_type_options}</select><button id='op-filter-clear' type='button'>清除筛选</button><span id='op-count' class='muted'></span></div><div class='table-wrap'><table class='lp-table'><thead><tr><th>操作时间</th><th>类型</th><th>代币对</th><th>金额 / 盈亏</th><th>备注</th></tr></thead><tbody id='lp-history'>{''.join(history) or "<tr><td colspan='5' class='empty'>暂无历史记录</td></tr>"}</tbody></table></div></section>
    <script>(function(){{var month=document.getElementById('op-month'),day=document.getElementById('op-day'),type=document.getElementById('op-type'),clear=document.getElementById('op-filter-clear'),count=document.getElementById('op-count'),rows=Array.from(document.querySelectorAll('#lp-history .op-row'));function apply(){{var visible=0;rows.forEach(function(row){{var show=(!month.value||row.dataset.month===month.value)&&(!day.value||row.dataset.day===day.value)&&(!type.value||row.dataset.type===type.value);row.hidden=!show;if(show)visible++;}});count.textContent='显示 '+visible+' / '+rows.length+' 条';}}month.addEventListener('change',apply);day.addEventListener('change',apply);type.addEventListener('change',apply);clear.addEventListener('click',function(){{month.value='';day.value='';type.value='';apply();}});apply();}})();</script>
    <style>
      .pair-combobox{{position:relative;min-width:0}}.pair-combobox>input{{width:100%}}.pair-suggestions{{position:absolute;z-index:70;top:calc(100% + 6px);left:0;right:0;max-height:224px;overflow:auto;padding:5px;background:var(--bg2);border:1px solid var(--border);border-radius:10px;box-shadow:0 16px 36px rgba(28,51,67,.18);scrollbar-gutter:stable}}.pair-suggestions[hidden]{{display:none}}.pair-option{{display:flex;width:100%;align-items:center;gap:9px;padding:9px 10px;border:0!important;border-radius:7px!important;background:transparent!important;color:var(--text)!important;text-align:left;font:inherit;cursor:pointer}}.pair-option::before{{content:'历史';flex:0 0 auto;padding:2px 5px;border-radius:4px;background:var(--bg3);color:var(--text2);font-size:9px;line-height:1.2}}.pair-option:hover,.pair-option.active{{background:var(--bg3)!important;color:var(--blue)!important}}.pair-option:focus-visible{{outline:2px solid var(--blue);outline-offset:-2px}}.pair-empty{{padding:12px 10px;color:var(--text2);font-size:11px}}.add-panel.modal-open .add-row>.pair-combobox{{grid-column:1/-1}}body.theme-dark .pair-suggestions{{background:#161b22;border-color:#30363d;box-shadow:0 18px 42px rgba(0,0,0,.45)}}body.theme-dark .pair-option::before{{background:#21262d;color:#9eacba}}body.theme-dark .pair-option:hover,body.theme-dark .pair-option.active{{background:#21262d!important;color:#58a6ff!important}}
    </style>
    <script>(function(){{
      var input=document.getElementById('lp-pair-input'),list=document.getElementById('lp-pair-suggestions'),source={pair_suggestions_payload},matches=[],active=-1,composing=false;
      if(!input||!list)return;
      function closeList(){{list.hidden=true;input.setAttribute('aria-expanded','false');input.removeAttribute('aria-activedescendant');active=-1;}}
      function setActive(index){{if(!matches.length)return;active=(index+matches.length)%matches.length;list.querySelectorAll('.pair-option').forEach(function(option,optionIndex){{var selected=optionIndex===active;option.classList.toggle('active',selected);option.setAttribute('aria-selected',selected?'true':'false');if(selected){{input.setAttribute('aria-activedescendant',option.id);option.scrollIntoView({{block:'nearest'}});}}}});}}
      function choose(index){{if(index<0||!matches[index])return;input.value=matches[index];closeList();input.focus();}}
      function render(){{var query=input.value.trim().toLocaleLowerCase();list.replaceChildren();active=-1;if(!query)return closeList();matches=source.filter(function(value){{return value.toLocaleLowerCase().includes(query);}}).sort(function(a,b){{var aPrefix=a.toLocaleLowerCase().startsWith(query)?0:1,bPrefix=b.toLocaleLowerCase().startsWith(query)?0:1;return aPrefix-bPrefix;}}).slice(0,8);if(!matches.length){{var empty=document.createElement('div');empty.className='pair-empty';empty.textContent='没有相似历史仓位，可直接使用当前名称';list.appendChild(empty);}}else{{matches.forEach(function(value,index){{var option=document.createElement('button');option.type='button';option.tabIndex=-1;option.id='lp-pair-option-'+index;option.className='pair-option';option.setAttribute('role','option');option.setAttribute('aria-selected','false');option.textContent=value;option.addEventListener('pointerdown',function(event){{event.preventDefault();}});option.addEventListener('click',function(){{choose(index);}});list.appendChild(option);}});}}list.hidden=false;input.setAttribute('aria-expanded','true');}}
      input.addEventListener('compositionstart',function(){{composing=true;}});input.addEventListener('compositionend',function(){{composing=false;render();}});input.addEventListener('input',function(){{if(!composing)render();}});input.addEventListener('focus',function(){{if(input.value.trim())render();}});
      input.addEventListener('keydown',function(event){{if(event.isComposing||composing)return;if(event.key==='ArrowDown'||event.key==='ArrowUp'){{event.preventDefault();if(list.hidden)render();if(matches.length)setActive(active+(event.key==='ArrowDown'?1:-1));}}else if(event.key==='Enter'&&active>=0&&!list.hidden){{event.preventDefault();choose(active);}}else if(event.key==='Escape'&&!list.hidden){{event.preventDefault();event.stopPropagation();closeList();}}}});
      document.addEventListener('pointerdown',function(event){{if(!event.target.closest('.pair-combobox'))closeList();}});
    }})();</script>
    """
    content += f"""
    <style>
      .month-total{{font-size:10px!important;font-weight:800!important;color:var(--text)!important;white-space:nowrap;flex-shrink:0}}.month-total.positive{{color:var(--green)!important}}.month-total.negative{{color:var(--red)!important}}.charts-grid .chart-panel:first-child .chart-head{{gap:8px;font-size:14px}}
      .op-tag{{font-weight:700;border:1px solid transparent}}.op-tag-open{{background:#e7f0ff;color:#2459c6;border-color:#cbdcff}}.op-tag-topup{{background:#e4f8f2;color:#08755f;border-color:#bcebdd}}.op-tag-reduce{{background:#fff5df;color:#a36500;border-color:#f0d79f}}.op-tag-claim{{background:#f1eaff;color:#7048b8;border-color:#d9c8fb}}.op-tag-close{{background:#e7f6ec;color:#187342;border-color:#bfe4cd}}.pnl-positive{{color:var(--green)}}.pnl-negative{{color:var(--red)}}.pnl-neutral{{color:var(--text2)}}
      .charts-grid .heat-month{{background:#f7fafc;border-color:#dce8ef}}.charts-grid .heat-month-title{{font-size:12px}}.charts-grid .heat-weekdays span{{font-size:10px}}.charts-grid .heat-calendar{{grid-auto-rows:30px}}.charts-grid .heat-day{{height:30px;min-height:0;padding:3px;background:#edf3f7;color:#66798a;font-size:10px;overflow:hidden}}.charts-grid .heat-day.has-pnl{{background:#def4ee;color:#155548}}.charts-grid .heat-day.positive-2{{background:#b9eadc;color:#075d4d}}.charts-grid .heat-day.positive-3{{background:#83d9c5;color:#064d42}}.charts-grid .heat-day.negative{{background:#fde5e9;color:#a72f43}}.charts-grid .heat-pnl{{font-size:10px;font-weight:800;line-height:1.05;margin-top:1px}}
      body.theme-dark .lp-console{{color:var(--text)}}body.theme-dark .metric,body.theme-dark .analytics-card,body.theme-dark .chart-panel,body.theme-dark .panel,body.theme-dark .month-filter{{background:#161b22!important;border-color:#30363d!important;box-shadow:none!important}}body.theme-dark .metric,body.theme-dark .analytics-card,body.theme-dark .chart-head,body.theme-dark .panel-h,body.theme-dark .lp-table td{{color:var(--text)}}body.theme-dark .metric label,body.theme-dark .analytics-card label,body.theme-dark .lp-console .muted,body.theme-dark .chart-head span{{color:var(--text2)!important}}body.theme-dark .chart-head,body.theme-dark .panel-h,body.theme-dark .operation-toolbar{{border-color:#30363d!important}}body.theme-dark .lp-table th{{background:#21262d!important;color:#a9b7c6!important}}body.theme-dark .lp-table td{{border-color:#30363d!important}}body.theme-dark .lp-table tr:hover{{background:#1c222b!important}}body.theme-dark .month-filter button,body.theme-dark .operation-toolbar button{{background:#21262d!important;border-color:#30363d!important;color:#b8c5d1!important}}body.theme-dark .month-filter button.active{{background:#0e7490!important;border-color:#22a6c7!important;color:#fff!important}}body.theme-dark .add-row input,body.theme-dark .add-row textarea,body.theme-dark .operation-toolbar select,body.theme-dark .operation-toolbar input{{background:#0d1117!important;border-color:#30363d!important;color:var(--text)!important}}body.theme-dark .operation-toolbar{{background:#161b22!important}}body.theme-dark .charts-grid .heat-month{{background:#0d1117!important;border-color:#30363d!important}}body.theme-dark .charts-grid .heat-month-title{{color:#c7d6e2!important}}body.theme-dark .charts-grid .heat-weekdays span{{color:#8493a2!important}}body.theme-dark .charts-grid .heat-day{{background:#21262d!important;color:#9cabb8!important}}body.theme-dark .charts-grid .heat-day.has-pnl{{background:#153c38!important;color:#b6eadc!important}}body.theme-dark .charts-grid .heat-day.positive-2{{background:#176453!important;color:#d0f5e9!important}}body.theme-dark .charts-grid .heat-day.positive-3{{background:#1d8069!important;color:#e5fff8!important}}body.theme-dark .charts-grid .heat-day.negative{{background:#592d38!important;color:#ffd8df!important}}body.theme-dark .op-tag-open{{background:#17345f!important;color:#bcd4ff!important;border-color:#2f5b9b!important}}body.theme-dark .op-tag-topup{{background:#153f37!important;color:#b6eadc!important;border-color:#267362!important}}body.theme-dark .op-tag-reduce{{background:#503b18!important;color:#ffe1a0!important;border-color:#8e6e2c!important}}body.theme-dark .op-tag-claim{{background:#352252!important;color:#decaff!important;border-color:#654293!important}}body.theme-dark .op-tag-close{{background:#173e2a!important;color:#bff0cf!important;border-color:#2e7751!important}}
    </style>
    <script>(function(){{
      var series={chart_payload};
      function updateMonthTotal(){{var active=document.querySelector('.month-filter button.active'),target=document.getElementById('lp-month-total');if(!active||!target)return;var month=active.dataset.month,total=series.filter(function(item){{return item.date.slice(0,7)===month;}}).reduce(function(sum,item){{return sum+item.pnl;}},0),cny=total*6.66,sign=total>=0?'+':'-',cnySign=cny>=0?'+':'-',format=function(value){{return Math.abs(value).toLocaleString('zh-CN',{{minimumFractionDigits:2,maximumFractionDigits:2}});}};target.textContent=month+' 累计 '+sign+'$'+format(total)+' · '+cnySign+'¥'+format(cny)+' CNY';target.classList.toggle('positive',total>=0);target.classList.toggle('negative',total<0);}}
      var dailyValueLabels={{id:'lpDailyValueLabels',beforeEvent:function(chart,args){{if(chart.canvas.id==='lp-daily-chart'&&chart.$lockedIndex!==null&&chart.$lockedIndex!==undefined&&(args.event.type==='mousemove'||args.event.type==='mouseout'))return false;}},afterDatasetsDraw:function(chart){{if(window.lpDrawDailyLabels)window.lpDrawDailyLabels(chart);}}}};Chart.register(dailyValueLabels);var dailyChart=Chart.getChart('lp-daily-chart');if(dailyChart){{dailyChart.$lockedIndex=null;var labelCount=dailyChart.data.datasets[0].data.filter(function(raw){{return Number(raw||0)!==0;}}).length,labelAngle=labelCount>20?75:labelCount>10?45:0;dailyChart.options.layout={{padding:{{top:labelAngle===75?46:labelAngle===45?42:18,bottom:labelAngle===75?40:labelAngle===45?38:14}}}};dailyChart.options.plugins.tooltip.callbacks.label=function(context){{var value=Number(context.raw||0),sign=value>=0?'+':'-',cny=value*6.66;return['当日盈亏 '+sign+'$'+Math.abs(value).toFixed(2),'人民币 '+(cny>=0?'+':'-')+'¥'+Math.abs(cny).toLocaleString('zh-CN',{{minimumFractionDigits:2,maximumFractionDigits:2}})+' CNY'];}};dailyChart.options.onClick=function(event,elements,chart){{function clearLocked(){{chart.$lockedIndex=null;chart.setActiveElements([]);chart.tooltip.setActiveElements([],{{x:0,y:0}});chart.update();}}if(!elements.length)return clearLocked();var point=elements[0];if(chart.$lockedIndex===point.index)return clearLocked();chart.$lockedIndex=point.index;var position=point.element.tooltipPosition();chart.setActiveElements([{{datasetIndex:point.datasetIndex,index:point.index}}]);chart.tooltip.setActiveElements([{{datasetIndex:point.datasetIndex,index:point.index}}],position);chart.update();}};dailyChart.update();}}
      function updateChartTheme(){{if(!window.Chart)return;var dark=document.body.classList.contains('theme-dark'),text=dark?'#9eacba':'#718096',grid=dark?'rgba(139,148,158,.18)':'rgba(113,153,190,.13)';['lp-cumulative-chart','lp-daily-chart'].forEach(function(id){{var chart=Chart.getChart(id);if(!chart)return;['x','y'].forEach(function(axis){{chart.options.scales[axis].ticks.color=text;chart.options.scales[axis].grid.color=grid;}});chart.update();}})}}
      document.querySelectorAll('.month-filter button').forEach(function(button){{button.addEventListener('click',function(){{setTimeout(updateMonthTotal,0);}});}});window.addEventListener('themechange',updateChartTheme);updateMonthTotal();updateChartTheme();
    }})();</script>
    """
    content += """
    <style>
      .summary-grid .analytics-card{display:none}.lp-head-actions{display:flex;gap:7px;align-items:center;flex-wrap:wrap}.lp-head-actions .quiet-action{background:transparent;color:var(--text2);border-color:var(--border)}.lp-head-actions .quiet-action:hover{color:var(--blue);border-color:var(--blue)}.position-action{background:transparent!important;color:#087cad!important;border-color:#b9d9e7!important;padding:5px 9px!important}.position-action:hover{background:#eef8fc!important}.add-panel,.operation-panel{display:none!important}body .add-panel.modal-open,body .operation-panel.modal-open{display:block!important}.lp-layout{margin-top:0}.lp-table th:nth-child(4),.lp-table td:nth-child(4),.lp-table th:nth-child(5),.lp-table td:nth-child(5),.lp-table th:nth-child(8),.lp-table td:nth-child(8){white-space:nowrap}.claimed-fee.has-value{color:var(--blue);font-weight:700}
      .lp-modal-backdrop{display:none;position:fixed;inset:0;background:rgba(8,17,28,.54);backdrop-filter:blur(3px);z-index:50}.lp-modal-backdrop.visible{display:block}.lp-secondary.modal-open{display:block!important;position:fixed;z-index:51;left:50%;top:50%;transform:translate(-50%,-50%);width:min(1120px,calc(100vw - 40px));max-height:calc(100vh - 50px);overflow:auto;margin:0!important;box-shadow:0 26px 70px rgba(0,0,0,.26)!important}.add-panel.modal-open{width:min(540px,calc(100vw - 32px))}.add-panel.modal-open .panel-h{padding:14px 16px}.add-panel.modal-open .panel-h .muted{display:block;margin-top:3px;font-weight:400}.add-panel.modal-open .add-row{grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;padding:16px}.add-panel.modal-open .add-row input[name='pair'],.add-panel.modal-open .add-row input[name='date'],.add-panel.modal-open .add-row textarea,.add-panel.modal-open .add-row button{grid-column:1/-1}.add-panel.modal-open .add-row textarea{height:78px;padding-top:9px}.add-panel.modal-open .add-row button{height:38px;width:100%;margin-top:2px}.operation-panel.modal-open .table-wrap{max-height:calc(100vh - 230px)}.modal-close{margin-left:auto!important;width:29px;height:29px;padding:0!important;border-radius:50%!important;background:transparent!important;color:var(--text2)!important;border-color:transparent!important;font-size:18px!important;line-height:1!important}.modal-close:hover{background:var(--bg3)!important;color:var(--text)!important}.modal-position{display:none;position:fixed;z-index:52;left:50%;top:50%;transform:translate(-50%,-50%);width:min(560px,calc(100vw - 40px));padding:0;background:var(--bg2);border:1px solid var(--border);border-radius:14px;box-shadow:0 26px 70px rgba(0,0,0,.28);overflow:hidden}.modal-position.visible{display:block}.modal-position-head{padding:14px 16px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:8px;font-weight:700}.modal-position-body{padding:16px;display:grid;gap:12px}.modal-position-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}.modal-position form{display:flex;gap:8px;align-items:end}.modal-position label{display:grid;gap:5px;flex:1;font-size:11px;color:var(--text2)}.modal-position input{width:100%;padding:8px 9px;border:1px solid var(--border);border-radius:7px;background:var(--bg3);color:var(--text);font:inherit}.modal-position .danger{background:#c84d60!important;border-color:#c84d60!important}.analytics-float{display:none;position:fixed;z-index:52;left:50%;top:50%;transform:translate(-50%,-50%);width:min(720px,calc(100vw - 40px));padding:0;background:var(--bg2);border:1px solid var(--border);border-radius:14px;box-shadow:0 26px 70px rgba(0,0,0,.28);overflow:hidden}.analytics-float.visible{display:block}.analytics-float-head{padding:14px 16px;border-bottom:1px solid var(--border);display:flex;font-weight:700}.analytics-float-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;padding:14px}.analytics-float .analytics-card{display:block!important;background:var(--bg3);border:1px solid var(--border);border-radius:10px;padding:12px}.analytics-float .analytics-card b{font-size:18px}@media(max-width:760px){.lp-head-actions{margin-top:12px}.lp-head-actions .btn{display:none}.modal-position-grid,.analytics-float-grid{grid-template-columns:1fr 1fr}.modal-position form{display:grid;grid-template-columns:1fr auto}.lp-secondary.modal-open{width:calc(100vw - 20px)}.add-panel.modal-open .add-row{grid-template-columns:1fr}.add-panel.modal-open .add-row input[name='amount'],.add-panel.modal-open .add-row input[name='fees']{grid-column:1/-1}}
      body.theme-dark .position-action{color:#58a6ff!important;border-color:#2f5b78!important}body.theme-dark .position-action:hover{background:#172632!important}body.theme-dark .lp-modal-backdrop{background:rgba(0,0,0,.7)}body.theme-dark .modal-position,body.theme-dark .analytics-float{background:#161b22;border-color:#30363d}body.theme-dark .modal-position-head,body.theme-dark .analytics-float-head{border-color:#30363d}body.theme-dark .modal-position input{background:#0d1117;border-color:#30363d;color:#e6edf3}body.theme-dark .analytics-float .analytics-card{background:#21262d;border-color:#30363d}
      .modal-position{width:min(660px,calc(100vw - 32px));border-radius:16px}.modal-position-head{min-height:54px;padding:13px 16px}.modal-position-title{font-size:15px;line-height:1.3}.modal-position-subtitle{display:flex;align-items:center;gap:6px;margin-top:3px;color:var(--text2);font-size:10px;font-weight:500}.position-modal-pair{max-width:460px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--blue);font-weight:700}.modal-position-body{padding:14px;background:var(--bg)}.modal-position-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.manage-card{min-width:0;padding:12px;border:1px solid var(--border);border-radius:11px;background:var(--bg2);box-shadow:0 4px 14px rgba(29,78,110,.035)}.manage-card form{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px;align-items:end}.manage-card label{display:block;min-width:0;color:var(--text);font-size:12px;font-weight:700}.manage-card-label{display:block;margin-bottom:7px}.manage-card input{box-sizing:border-box;height:38px;padding:0 10px;border:1px solid var(--border);border-radius:8px;background:var(--bg3);color:var(--text);font:inherit;font-variant-numeric:tabular-nums}.manage-card input:focus{border-color:var(--blue);outline:2px solid rgba(8,124,173,.14);outline-offset:1px}.manage-card button{height:38px;min-width:94px;padding:0 13px;border:1px solid #087cad;border-radius:8px;background:#087cad;color:#fff;font:inherit;font-size:12px;font-weight:700;cursor:pointer;white-space:nowrap}.manage-card button:hover{background:#076e99;border-color:#076e99}.manage-card button:focus-visible{outline:2px solid var(--blue);outline-offset:2px}.manage-card small{grid-column:1/-1;display:block;min-height:14px;margin:0;color:var(--text2);font-size:10px;line-height:1.4}.manage-card-danger{border-color:rgba(200,77,96,.34);background:rgba(200,77,96,.045)}.manage-card-danger .manage-card-label{color:var(--red)}.manage-card-danger button{background:var(--red);border-color:var(--red)}.manage-card-danger button:hover{filter:brightness(.92)}body.theme-dark .modal-position-body{background:#0d1117}body.theme-dark .manage-card{background:#161b22;border-color:#30363d;box-shadow:none}body.theme-dark .manage-card-danger{background:rgba(248,81,73,.07);border-color:rgba(248,81,73,.32)}body.theme-dark .manage-card input{background:#0d1117;border-color:#3a424c}@media(max-width:600px){.modal-position-grid{grid-template-columns:1fr}.modal-position-body{max-height:calc(100vh - 92px);overflow:auto}.position-modal-pair{max-width:240px}}

    </style>
    <div id='lp-modal-backdrop' class='lp-modal-backdrop'></div><div id='lp-position-modal' class='modal-position' role='dialog' aria-modal='true' aria-labelledby='position-modal-title'></div><section id='lp-apy-modal' class='apy-modal' role='dialog' aria-modal='true' aria-labelledby='apy-modal-title'>
<div class='apy-head'><div><h2 id='apy-modal-title'>收益计算器 <span>APY</span></h2><p>调整参数，即时对比资金增长</p></div><button id='close-apy-modal' type='button' class='modal-close' aria-label='关闭计算器'>×</button></div>
<div class='apy-workspace'><aside class='apy-controls'>
<label for='apy-principal'>投入金额</label><div class='apy-input-wrap'><span>$</span><input id='apy-principal' type='number' min='0' step='any' value='10000' inputmode='decimal'><span>USD</span></div>
<label for='apy-apr'>年化收益率 APR <span class='apy-unit'>%</span></label><div class='apy-input-wrap'><input id='apy-apr' type='number' min='0' step='any' value='60' inputmode='decimal'><span>%</span></div>
<p class='apy-help'>输入未复投年化；复投后的 APY 自动计算。</p>
<label>收益方式</label><div class='apy-segment' aria-label='收益方式'><button type='button' data-mode='simple' aria-pressed='false'>不复投</button><button type='button' data-mode='compound' aria-pressed='true'>复投</button></div>
<label>复投频率</label><div class='apy-segment' aria-label='复投频率'><button type='button' data-frequency='365' aria-pressed='true'>每日</button><button type='button' data-frequency='52' aria-pressed='false'>每周</button><button type='button' data-frequency='12' aria-pressed='false'>每月</button></div>
<label>测算周期</label><div class='apy-periods' aria-label='测算周期'><button type='button' data-period='1' aria-pressed='false'>1 天</button><button type='button' data-period='7' aria-pressed='false'>7 天</button><button type='button' data-period='30' aria-pressed='false'>30 天</button><button type='button' data-period='90' aria-pressed='false'>90 天</button><button type='button' data-period='180' aria-pressed='false'>180 天</button><button type='button' data-period='365' aria-pressed='true'>1 年</button></div>
<div class='apy-rate'><span>复投有效年化 APY</span><strong id='apy-effective'>—</strong></div>
<p id='apy-input-status' class='apy-help' role='status'></p>
</aside><div class='apy-analysis'>
<div class='apy-result-heading'><span id='apy-result-label'>1 年 · 复投后总额</span><span class='apy-live'>实时测算</span></div>
<strong id='apy-year-total' class='apy-total'>—</strong>
<div class='apy-result-stats'><div><span>预计收益</span><b id='apy-year-profit'>—</b></div><div><span>收益率</span><b id='apy-roi'>—</b></div><div><span>复投额外收益</span><b id='apy-extra'>—</b></div></div>
<div class='apy-chart-heading'><strong>资金增长曲线</strong><div><span class='apy-key simple'>不复投</span><span class='apy-key compound'>复投</span></div></div>
<div class='apy-chart-wrap'><canvas id='apy-growth-chart' role='img' aria-label='不复投与复投资金增长对比，横轴为天数，纵轴为美元总额'></canvas></div>
<div class='apy-table-wrap'><table class='apy-table'><thead><tr><th>周期</th><th>不复投收益</th><th>复投收益</th><th id='apy-total-heading'>复投后总额</th></tr></thead><tbody id='apy-results'><tr data-days='1'><td>1 天</td><td class='simple-profit'>—</td><td class='compound-profit'>—</td><td class='compound-total'>—</td></tr><tr data-days='7'><td>7 天</td><td class='simple-profit'>—</td><td class='compound-profit'>—</td><td class='compound-total'>—</td></tr><tr data-days='30'><td>30 天</td><td class='simple-profit'>—</td><td class='compound-profit'>—</td><td class='compound-total'>—</td></tr><tr data-days='90'><td>90 天</td><td class='simple-profit'>—</td><td class='compound-profit'>—</td><td class='compound-total'>—</td></tr><tr data-days='180'><td>180 天</td><td class='simple-profit'>—</td><td class='compound-profit'>—</td><td class='compound-total'>—</td></tr><tr data-days='365'><td>1 年</td><td class='simple-profit'>—</td><td class='compound-profit'>—</td><td class='compound-total'>—</td></tr></tbody></table></div>
</div></div><footer class='apy-note'>按固定 APR、365 天/年估算，未满复投周期按天计息；不含币价波动、无常损失与 Gas。</footer></section><link rel='stylesheet' href='/static/apy-calculator.css?v=2'><script src='/static/apy-calculator.js?v=2'></script><link rel='stylesheet' href='/static/range-calculator.css?v=3'><script src='/static/range-calculator.js?v=3'></script>
    <script>(function(){
      var backdrop=document.getElementById('lp-modal-backdrop'),positionModal=document.getElementById('lp-position-modal'),apyModal=document.getElementById('lp-apy-modal'),openedPanel=null,apyFrequency=365;
      function closeAll(){if(openedPanel)openedPanel.classList.remove('modal-open');openedPanel=null;positionModal.classList.remove('visible');apyModal.classList.remove('visible');backdrop.classList.remove('visible');document.body.style.overflow='';}
      function openPanel(panel){closeAll();openedPanel=panel;panel.classList.add('modal-open');backdrop.classList.add('visible');document.body.style.overflow='hidden';}
      [document.querySelector('.add-panel'),document.querySelector('.operation-panel')].forEach(function(panel){var header=panel.querySelector('.panel-h'),close=document.createElement('button');close.type='button';close.className='modal-close';close.setAttribute('aria-label','关闭');close.textContent='×';close.addEventListener('click',closeAll);header.appendChild(close);});
      document.getElementById('open-add-modal').addEventListener('click',function(){openPanel(document.querySelector('.add-panel'));});document.getElementById('open-history-modal').addEventListener('click',function(){openPanel(document.querySelector('.operation-panel'));});


      document.getElementById('open-apy-modal').addEventListener('click',function(){closeAll();apyModal.classList.add('visible');backdrop.classList.add('visible');document.body.style.overflow='hidden';window.lpApy.open();});document.getElementById('close-apy-modal').addEventListener('click',function(){closeAll();document.getElementById('open-apy-modal').focus();});
      document.querySelectorAll('.position-action').forEach(function(button){button.addEventListener('click',function(){var d=button.dataset;closeAll();positionModal.innerHTML='<div class="modal-position-head"><div><div id="position-modal-title" class="modal-position-title">管理仓位</div><div class="modal-position-subtitle">当前仓位 <span class="position-modal-pair"></span></div></div><button type="button" class="modal-close" aria-label="关闭">×</button></div><div class="modal-position-body"><div class="modal-position-grid"><section class="manage-card"><form method="post" action="/lp/action"><input type="hidden" name="action" value="balance"><input type="hidden" name="id" value="'+d.id+'"><label><span class="manage-card-label">更新当前估值</span><input name="balance" type="number" step="0.01" value="'+d.value+'" required></label><button type="submit">保存估值</button><small>只更新仓位当前价值，不改变投入本金</small></form></section><section class="manage-card"><form method="post" action="/lp/action"><input type="hidden" name="action" value="claim"><input type="hidden" name="id" value="'+d.id+'"><label><span class="manage-card-label">认领手续费</span><input name="amount" type="number" inputmode="decimal" step="0.01" min="0.01" aria-describedby="lp-claim-hint" placeholder="本次到账金额" required></label><button type="submit">记录领取</button><small id="lp-claim-hint">当前待领 $'+d.fees+' · 填写本次实际到账金额</small></form></section><section class="manage-card"><form method="post" action="/lp/action"><input type="hidden" name="action" value="topup"><input type="hidden" name="id" value="'+d.id+'"><label><span class="manage-card-label">调整投入本金</span><input name="amount" type="number" step="0.01" placeholder="增加为正，减少为负" required></label><button type="submit">记录调整</button><small>追加填写正数，减少仓位填写负数</small></form></section><section class="manage-card manage-card-danger"><form method="post" action="/lp/action"><input type="hidden" name="action" value="close"><input type="hidden" name="id" value="'+d.id+'"><label><span class="manage-card-label">关闭仓位</span><input name="balance" type="number" step="0.01" placeholder="最终回收金额" required></label><button class="danger" type="submit">确认平仓</button><small>关闭后将结算并计入已实现盈亏</small></form></section></div></div>';positionModal.querySelector('.position-modal-pair').textContent=d.pair;positionModal.querySelector('.modal-close').addEventListener('click',closeAll);positionModal.classList.add('visible');backdrop.classList.add('visible');document.body.style.overflow='hidden';positionModal.querySelector('input[name="balance"]').focus();});});
      backdrop.addEventListener('click',closeAll);document.addEventListener('keydown',function(event){if(event.key==='Escape')closeAll();});
    })();</script>
    """
    content += """
    <style>
      .operation-toolbar>label,.operation-toolbar>select,.operation-toolbar>input{display:none!important}
      .operation-toolbar>.op-type-label{display:block!important}.operation-toolbar>#op-type{display:block!important;min-width:104px}.operation-toolbar{justify-content:flex-end}
      .op-date-button{margin-right:auto!important;background:var(--bg3)!important;color:var(--text)!important;border-color:var(--border)!important;font-weight:600}
      .op-pnl-summary{font-size:12px;font-weight:700;white-space:nowrap}.op-pnl-summary small{font-size:10px;color:var(--text2);font-weight:600;margin-left:5px}.op-pnl-summary.positive{color:var(--green)}.op-pnl-summary.negative{color:var(--red)}
      .op-date-picker{display:none;position:fixed;z-index:60;left:50%;top:50%;transform:translate(-50%,-50%);width:min(476px,calc(100vw - 28px));padding:0;overflow:hidden;background:var(--bg2);color:var(--text);border:1px solid #d8e5ed;border-radius:18px;box-shadow:0 24px 70px rgba(28,51,67,.22),0 4px 14px rgba(28,51,67,.08)}
      .op-date-picker.visible{display:block;animation:op-picker-in .16s ease-out}@keyframes op-picker-in{from{opacity:0;transform:translate(-50%,-48%) scale(.985)}to{opacity:1;transform:translate(-50%,-50%) scale(1)}}
      .op-picker-head{display:flex;align-items:center;gap:8px;padding:16px 18px 13px;border-bottom:1px solid #e8f0f4;font-size:15px;font-weight:750;letter-spacing:.1px}
      .op-picker-head .modal-close{margin-left:auto!important;width:28px;height:28px;color:var(--text3)!important;background:transparent!important;border:0!important}
      .op-picker-months{display:flex;gap:7px;flex-wrap:wrap;padding:14px 16px 13px;border-bottom:1px solid #edf3f6;background:#fbfdfe}
      .op-picker-months button{height:29px;padding:0 11px!important;border:1px solid #d9e6ed!important;border-radius:999px!important;background:#fff!important;color:#5d7283!important;font-size:11px!important;font-weight:600;box-shadow:none!important;transition:background .15s ease,border-color .15s ease,color .15s ease,transform .15s ease}
      .op-picker-months button:hover{border-color:#9fc7d8!important;color:#087cad!important;transform:translateY(-1px)}
      .op-picker-months button.active{background:#e6f5fb!important;color:#08769d!important;border-color:#9dd0e3!important;box-shadow:inset 0 0 0 1px rgba(8,124,173,.06)!important}
      .op-picker-calendar{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:6px;padding:13px 16px 11px}
      .op-picker-calendar .weekday{display:grid;place-items:center;height:22px;padding:0;font-size:10px;font-weight:600;text-align:center;color:#8da0ae}
      .op-picker-calendar button{height:38px;min-height:38px;padding:0!important;border:1px solid transparent!important;border-radius:9px!important;background:transparent!important;color:#9aabb7!important;font-size:12px!important;font-weight:500;box-shadow:none!important;transition:background .14s ease,border-color .14s ease,color .14s ease,transform .14s ease}
      .op-picker-calendar button:disabled{cursor:default;opacity:.62}
      .op-picker-calendar button.has-data{background:#f2f7fa!important;color:#344f62!important;border-color:#e2ebf0!important;font-weight:650}
      .op-picker-calendar button.has-data:hover{background:#e5f5f3!important;color:#08755f!important;border-color:#b9e0d8!important;transform:translateY(-1px)}
      .op-picker-calendar button.today{position:relative;background:#edf8fc!important;color:#087cad!important;border-color:#8fcbe0!important;box-shadow:inset 0 0 0 1px rgba(8,124,173,.08)!important;font-weight:750}
      .op-picker-calendar button.today::after{content:'';position:absolute;right:5px;top:5px;width:4px;height:4px;border-radius:50%;background:#16a1ce}
      .op-picker-calendar button.selected{background:#087cad!important;color:#fff!important;border-color:#087cad!important;box-shadow:0 5px 12px rgba(8,124,173,.2)!important}
      .op-picker-calendar button.selected::after{background:#fff}
      .op-picker-actions{display:flex;align-items:center;justify-content:flex-end;gap:8px;padding:12px 16px 15px;border-top:1px solid #edf3f6;background:#fbfdfe}
      .op-picker-actions button{height:32px;padding:0 12px!important;border:1px solid #d9e6ed!important;border-radius:8px!important;background:#fff!important;color:#526b7c!important;font-weight:600;box-shadow:none!important}
      .op-picker-actions button[data-action='recent']{margin-right:auto}.op-picker-actions button:hover{border-color:#abcbd9!important;color:#087cad!important}
      .op-picker-actions button.primary{background:#087cad!important;color:#fff!important;border-color:#087cad!important;box-shadow:0 5px 12px rgba(8,124,173,.16)!important}.op-picker-actions button.primary:hover{background:#076f9a!important}
      body.theme-dark .op-date-picker{background:#161b22;border-color:#303b46;box-shadow:0 26px 75px rgba(0,0,0,.48)}
      body.theme-dark .op-picker-head{border-color:#29333d}body.theme-dark .op-picker-months,body.theme-dark .op-picker-actions{background:#12171d;border-color:#29333d}
      body.theme-dark .op-date-button,body.theme-dark .op-picker-months button,body.theme-dark .op-picker-calendar button,body.theme-dark .op-picker-actions button{background:#1d242c!important;border-color:#303b46!important;color:#b8c5d1!important}
      body.theme-dark .op-picker-months button.active{background:#12384a!important;border-color:#276881!important;color:#8ed9f2!important}body.theme-dark .op-picker-calendar button:disabled{background:transparent!important;border-color:transparent!important;color:#667582!important}
      body.theme-dark .op-picker-calendar button.has-data{background:#202a33!important;color:#d3dde5!important}body.theme-dark .op-picker-calendar button.has-data:hover{background:#173e36!important;border-color:#2b6558!important;color:#b6eadc!important}body.theme-dark .op-picker-calendar button.today{background:#12384a!important;border-color:#277a99!important;color:#8ed9f2!important}body.theme-dark .op-picker-calendar button.selected{background:#0e7490!important;border-color:#22a6c7!important;color:#fff!important}
    </style>
    <div id='op-date-picker' class='op-date-picker'></div>
    <script>(function(){
      var toolbar=document.querySelector('.operation-toolbar'),picker=document.getElementById('op-date-picker'),monthSelect=document.getElementById('op-month'),dayInput=document.getElementById('op-day'),typeSelect=document.getElementById('op-type'),clearButton=document.getElementById('op-filter-clear'),count=document.getElementById('op-count'),rows=Array.from(document.querySelectorAll('#lp-history .op-row')),days=Array.from(new Set(rows.map(function(row){return row.dataset.day;}))).filter(Boolean).sort().reverse(),months=Array.from(new Set(rows.map(function(row){return row.dataset.month;}))).filter(Boolean).sort().reverse(),selectedMonth=months[0],dateButton=document.createElement('button'),pnlSummary=document.createElement('span'),activePredicate=function(){return true;},activeLabel='全部记录';
      dateButton.type='button';dateButton.className='op-date-button';pnlSummary.className='op-pnl-summary';toolbar.insertBefore(dateButton,toolbar.firstChild);toolbar.insertBefore(pnlSummary,count);
      function setLabel(label){dateButton.textContent='筛选：'+label;}
      function renderRows(){var shown=0,total=0;rows.forEach(function(row){var visible=activePredicate(row)&&(!typeSelect.value||row.dataset.type===typeSelect.value);row.hidden=!visible;if(visible){shown++;total+=Number(row.dataset.pnl||0);}});count.textContent='显示 '+shown+' / '+rows.length+' 条';setLabel(activeLabel);if(dayInput.value){var cny=total*6.66;pnlSummary.className='op-pnl-summary '+(total>=0?'positive':'negative');pnlSummary.innerHTML='当天已实现盈亏 '+(total>=0?'+':'')+'$'+total.toFixed(2)+'<small>¥'+(cny>=0?'+':'')+cny.toFixed(2)+' CNY</small>';}else{pnlSummary.textContent='';pnlSummary.className='op-pnl-summary';}}
      function showRows(predicate,label){activePredicate=predicate;activeLabel=label;renderRows();}
      function recent(){monthSelect.value='';dayInput.value='';var keep=days.slice(0,2);showRows(function(row){return keep.indexOf(row.dataset.day)!==-1;},'最近 2 天');}
      function chooseMonth(month){monthSelect.value=month;dayInput.value='';showRows(function(row){return row.dataset.month===month;},month+' 全月');picker.classList.remove('visible');}
      function chooseDay(day){monthSelect.value=day.slice(0,7);dayInput.value=day;showRows(function(row){return row.dataset.day===day;},day);picker.classList.remove('visible');}
      function renderPicker(){var nowDate=new Date(),today=nowDate.getFullYear()+'-'+String(nowDate.getMonth()+1).padStart(2,'0')+'-'+String(nowDate.getDate()).padStart(2,'0'),y=Number(selectedMonth.slice(0,4)),m=Number(selectedMonth.slice(5,7)),length=new Date(y,m,0).getDate(),first=(new Date(y,m-1,1).getDay()+6)%7,html='<div class="op-picker-head">选择月份与日期 <button type="button" class="modal-close" aria-label="关闭日期选择">×</button></div><div class="op-picker-months">';months.forEach(function(month){html+='<button type="button" class="'+(month===selectedMonth?'active':'')+'" aria-pressed="'+(month===selectedMonth?'true':'false')+'" data-month="'+month+'">'+month+'</button>';});html+='</div><div class="op-picker-calendar">';['一','二','三','四','五','六','日'].forEach(function(name){html+='<span class="weekday">'+name+'</span>';});for(var blank=0;blank<first;blank++)html+='<span></span>';for(var number=1;number<=length;number++){var day=selectedMonth+'-'+String(number).padStart(2,'0'),has=days.indexOf(day)!==-1,selected=dayInput.value===day,isToday=day===today,classes=(has?'has-data':'')+(selected?' selected':'')+(isToday?' today':'');html+='<button type="button" class="'+classes.trim()+'" aria-label="'+day+(isToday?'，今天':'')+'" '+(isToday?'aria-current="date" ':'')+(has?'data-day="'+day+'"':'disabled')+'>'+number+'</button>';}html+='</div><div class="op-picker-actions"><button type="button" data-action="recent">最近 2 天</button><button type="button" data-action="close">取消</button><button type="button" class="primary" data-action="month">查看整月</button></div>';picker.innerHTML=html;picker.querySelector('.modal-close').addEventListener('click',function(){picker.classList.remove('visible');});picker.querySelectorAll('[data-month]').forEach(function(button){button.addEventListener('click',function(){selectedMonth=button.dataset.month;renderPicker();});});picker.querySelectorAll('[data-day]').forEach(function(button){button.addEventListener('click',function(){chooseDay(button.dataset.day);});});picker.querySelector('[data-action="recent"]').addEventListener('click',function(){recent();picker.classList.remove('visible');});picker.querySelector('[data-action="month"]').addEventListener('click',function(){chooseMonth(selectedMonth);});picker.querySelector('[data-action="close"]').addEventListener('click',function(){picker.classList.remove('visible');});}
      dateButton.addEventListener('click',function(){renderPicker();picker.classList.add('visible');});typeSelect.addEventListener('change',renderRows);clearButton.addEventListener('click',function(){monthSelect.value='';dayInput.value='';typeSelect.value='';showRows(function(){return true;},'全部记录');});recent();
    })();</script>
    <script>(function(){if(!window.Chart)return;var chart=Chart.getChart('lp-daily-chart');if(chart){chart.data.datasets[0].barThickness=16;chart.data.datasets[0].maxBarThickness=18;chart.data.datasets[0].categoryPercentage=.62;chart.update();}})();</script>
    """
    content += f"""
    <script>(function(){{
      var series={chart_payload};
      function renderContinuousMonth(month){{
        var items=series.filter(function(item){{return item.date.slice(0,7)===month;}}),year=Number(month.slice(0,4)),monthNo=Number(month.slice(5,7)),monthLength=new Date(year,monthNo,0).getDate(),byDay={{}};
        items.forEach(function(item){{byDay[Number(item.date.slice(8,10))]=item.pnl;}});
        var known=Object.keys(byDay).map(Number),start=known.length?Math.min.apply(null,known):1,end=known.length?Math.max.apply(null,known):Math.min(7,monthLength);
        if(end-start+1<7){{start=Math.max(1,end-6);end=Math.min(monthLength,start+6);start=Math.max(1,end-6);}}
        var labels=[],values=[],running=0;Object.keys(byDay).forEach(function(day){{if(Number(day)<start)running+=byDay[day];}});
        for(var day=start;day<=end;day++){{labels.push(String(day).padStart(2,'0'));var value=byDay[day]||0;values.push(value);running+=value;}}
        var now=new Date('{datetime.now().strftime("%Y-%m-%d")}T00:00:00'),isCurrentMonth=year===now.getFullYear()&&monthNo===now.getMonth()+1,lastReached=isCurrentMonth?now.getDate():end,cumulative=[],total=0;Object.keys(byDay).forEach(function(day){{if(Number(day)<start)total+=byDay[day];}});values.forEach(function(value,index){{total+=value;var calendarDay=start+index;cumulative.push(calendarDay>lastReached?null:+total.toFixed(2));}});
        var line=Chart.getChart('lp-cumulative-chart'),bar=Chart.getChart('lp-daily-chart');if(!line||!bar)return;bar.$lockedIndex=null;bar.setActiveElements([]);bar.tooltip.setActiveElements([],{{x:0,y:0}});
        line.data.labels=labels;line.data.datasets[0].data=cumulative;line.data.datasets[0].spanGaps=false;line.options.plugins.tooltip.callbacks.title=function(context){{return month+'-'+context[0].label;}};line.update();
        bar.data.labels=labels;bar.data.datasets[0].data=values;bar.data.datasets[0].backgroundColor=values.map(function(value){{return value>0?'rgba(23,150,119,.72)':value<0?'rgba(200,77,96,.72)':'rgba(145,160,175,.24)';}});bar.data.datasets[0].barThickness=14;bar.data.datasets[0].maxBarThickness=16;var labelCount=values.filter(function(value){{return Number(value)!==0;}}).length,labelAngle=labelCount>20?75:labelCount>10?45:0;bar.options.layout={{padding:{{top:labelAngle===75?46:labelAngle===45?42:18,bottom:labelAngle===75?40:labelAngle===45?38:14}}}};bar.options.plugins.tooltip.callbacks.title=function(context){{return month+'-'+context[0].label;}};bar.update();
      }}
      document.querySelectorAll('.month-filter button').forEach(function(button){{button.addEventListener('click',function(){{renderContinuousMonth(button.dataset.month);}});}});
      var initial=document.querySelector('.month-filter button.active');if(initial)renderContinuousMonth(initial.dataset.month);
    }})();</script>
    """
    content += """
    <style>
      .chain-form{margin:0}.chain-select-wrap{position:relative;display:inline-flex;align-items:center;min-width:128px}.chain-select-wrap::before{content:'';position:absolute;z-index:1;left:1px;top:5px;bottom:5px;width:3px;border-radius:3px;background:var(--chain-color);pointer-events:none}.chain-select{box-sizing:border-box;width:100%;height:31px;padding:0 25px 0 12px;border:1px solid color-mix(in srgb,var(--chain-color) 28%,var(--border));border-radius:8px;background:color-mix(in srgb,var(--chain-color) 6%,var(--bg2));color:var(--chain-color);font:inherit;font-size:10px;font-weight:750;cursor:pointer}.chain-select:focus{outline:2px solid color-mix(in srgb,var(--chain-color) 32%,transparent);outline-offset:2px}.chain-select option{color:var(--text);background:var(--bg2)}
      .add-chain-field{display:grid;gap:5px;color:var(--text2);font-size:11px}.add-chain-field select,.add-grid select{box-sizing:border-box;width:100%;height:36px;padding:0 10px;border:1px solid var(--border);border-radius:8px;background:var(--bg2);color:var(--text);font:inherit}.add-panel.modal-open .add-row .add-chain-field{grid-column:1/-1}.add-panel.modal-open .add-row .add-chain-field span{font-weight:650}.lp-table th:nth-child(2),.lp-table td:nth-child(2){min-width:145px;white-space:nowrap}
      body.theme-dark .chain-select{border-color:color-mix(in srgb,var(--chain-color) 45%,#30363d);background:color-mix(in srgb,var(--chain-color) 12%,#161b22);color:color-mix(in srgb,var(--chain-color) 72%,#fff)}body.theme-dark .add-chain-field select,body.theme-dark .add-grid select{background:#0d1117;border-color:#30363d;color:var(--text)}
      @media(max-width:760px){.chain-select-wrap{min-width:116px}}
    </style>
    """
    return render_template_string(LAYOUT, section="lp", now=datetime.now().strftime("%Y-%m-%d %H:%M"), content=content)


def lp_action():
    data, data_origin = _load()
    project = _project(data)
    if not project:
        return _back("未找到 LP 项目")
    action = request.form.get("action", "")
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    positions = project.setdefault("lp_positions", [])
    operations = project.setdefault("lp_operations", [])
    position = next((item for item in positions if str(item.get("id")) == request.form.get("id", "")), None)

    if action == "open":
        amount = _number(request.form.get("amount"))
        pair = request.form.get("pair", "").strip()
        chain = request.form.get("chain", "").strip()
        if not pair or amount <= 0: return _back("请填写有效的代币对和投入金额")
        if chain not in LP_CHAINS: return _back("请选择有效的所属链")
        position = {"id": uuid.uuid4().hex[:12], "token_pair": pair, "chain": chain, "lp_amount": amount, "current_balance": amount, "fees": _number(request.form.get("fees")), "claimed_fees": 0, "open_date": request.form.get("date", now).replace("T", " "), "status": "open", "note": request.form.get("note", "").strip(), "top_ups": []}
        positions.insert(0, position); operations.insert(0, {"id": uuid.uuid4().hex[:12], "type": "open", "date": position["open_date"], "token_pair": pair, "chain": chain, "principal": amount, "profit": 0, "note": position["note"]}); message = "已记录新 LP 仓位"
    elif not position or position.get("status") != "open":
        return _back("未找到可操作的开仓仓位")
    elif action == "balance":
        position["current_balance"] = _number(request.form.get("balance")); message = "当前仓位估值已更新"
    elif action == "chain":
        chain = request.form.get("chain", "").strip()
        if chain not in LP_CHAINS: return _back("请选择有效的所属链")
        position["chain"] = chain; message = f"所属链已更新为 {chain}"
    elif action == "claim":
        amount = round(_number(request.form.get("amount")), 2)
        if amount <= 0: return _back("请输入大于 0 的实际领取金额")
        pending_fees = _number(position.get("fees"))
        position["fees"] = round(max(0.0, pending_fees - amount), 2)
        position["claimed_fees"] = round(_number(position.get("claimed_fees")) + amount, 2)
        operations.insert(0, {"id": uuid.uuid4().hex[:12], "type": "claim", "date": now, "token_pair": position.get("token_pair"), "principal": 0, "profit": amount, "note": "中途认领手续费"}); message = "手续费认领已记录"
    elif action == "topup":
        amount = _number(request.form.get("amount"))
        if not amount: return _back("调整金额不能为零")
        position.setdefault("top_ups", []).append({"amount": amount, "date": now, "note": ""}); position["current_balance"] = _number(position.get("current_balance"), _invested(position)) + amount
        operations.insert(0, {"id": uuid.uuid4().hex[:12], "type": "topup" if amount > 0 else "reduce", "date": now, "token_pair": position.get("token_pair"), "principal": amount, "profit": 0, "note": "追加资金" if amount > 0 else "减少仓位"}); message = "本金调整已记录"
    elif action == "close":
        balance = _number(request.form.get("balance")); total = _invested(position); claimed = _number(position.get("claimed_fees")); fees = _number(position.get("fees")); profit = balance + fees + claimed - total
        position.update({"current_balance": balance, "status": "closed", "close_date": now})
        operations.insert(0, {"id": uuid.uuid4().hex[:12], "type": "close", "date": now, "token_pair": position.get("token_pair"), "principal": total, "total_invested": total, "profit": profit, "fees": fees, "claimed_fees": claimed, "note": "平仓结算"}); message = "仓位已关闭并计入已实现盈亏"
    else:
        return _back("未知操作")
    project["updated"] = now
    _, saved_to = _save(data, position.get("id") if position else None)
    if saved_to != "wsl":
        message += "；WSL 源数据不可达，已暂存本地缓存"
    return _back(message)
