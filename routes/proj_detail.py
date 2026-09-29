import os, time
from flask import request, redirect, render_template_string, make_response
from datetime import datetime, timedelta
import json
from utils import load_json, save_json, today_str, now, now_str, get_standx_data, PROJECTS_FILE, get_all_tasks, is_due_within
from templates import LAYOUT


def _next_month(date_str):
    d = datetime.strptime(date_str, "%Y-%m-%d")
    month = d.month + 1
    year = d.year
    if month > 12:
        month = 1
        year += 1
    last_day = datetime(year, month, 1) - timedelta(days=1)
    target_day = min(d.day, last_day.day)
    return d.replace(year=year, month=month, day=target_day).strftime("%Y-%m-%d")


def proj_detail_page(proj_id):
    data = load_json(PROJECTS_FILE)
    projects = data.get("projects", [])
    all_tasks = data.get("tasks", [])
    proj = next((p for p in projects if p["id"] == proj_id), None)
    if not proj:
        return redirect("/?s=projects")
    today = today_str()
    proj_tasks = [t for t in all_tasks if t.get("project_id") == proj_id]
    desc = proj.get("desc","")
    notes = proj.get("notes","")
    risk = proj.get("risk","")
    tags = proj.get("tags",[])
    chain = proj.get("chain","")
    ptype = proj.get("type","")
    stars = int(proj.get("stars", 3))
    invest = float(proj.get("invest", 0) or 0)
    earn = float(proj.get("earn", 0) or 0)
    gas = float(proj.get("gas_cost", 0) or 0)
    roi = (earn - invest) / max(invest, 1) * 100 if invest > 0 else 0
    wallets = proj.get("wallets", [])
    chain_icon = {"BNB Chain":"🔶","Solana":"☀️","Base":"🔵","Fogo":"🔥","Aptos":"🟣","Miden":"⚪","Sui":"🔷"}.get(chain,"🔗")
    p_tasks_done = [t for t in proj_tasks if t.get("last_done","").startswith(today)]
    done_count = len(p_tasks_done)
    total_count = len(proj_tasks)
    pct = int(done_count / max(total_count,1) * 100) if total_count > 0 else 0
    ot_done = sum(1 for t in proj_tasks if t.get("freq") == "one-time" and t.get("last_done"))
    ot_total = sum(1 for t in proj_tasks if t.get("freq") == "one-time")
    today_proj_tasks = [t for t in proj_tasks if t.get("next_run", "") != "" and t.get("next_run", "") <= today and t.get("freq") in ("daily", "weekly", "monthly") and t.get("last_done", "")[:10] != today]
    today_proj_done = [t for t in proj_tasks if t.get("last_done", "").startswith(today) and t.get("freq") in ("daily", "weekly", "monthly")]
    tags_html = "".join(["<span style='background:rgba(59,130,246,0.15);color:#60a5fa;border-radius:6px;padding:2px 8px;font-size:11px;margin-right:6px'>" + tag + "</span>" for tag in tags])
    risk_color = {"低":"#22c55e","中":"#f59e0b","高":"#ef4444"}.get(risk,"#9ca3af")
    risk_html = "<span style='background:rgba(0,0,0,0.2);color:" + risk_color + ";border-radius:4px;padding:1px 6px;font-size:10px;margin-left:6px'>⚠️ " + risk + "风险</span>" if risk else ""
    stars_html = "<span style='color:#f0b90b;margin-left:8px'>" + "★" * stars + "☆" * (5 - stars) + "</span>"
    roi_color = "#22c55e" if roi >= 0 else "#ef4444"
    desc_html = "<div style='background:var(--bg2);border:1px solid var(--border);border-radius:8px;padding:12px;margin-bottom:12px;font-size:13px;line-height:1.6'>" + desc + "</div>" if desc else ""
    notes_html = "<div style='background:rgba(245,158,11,0.08);border:1px solid rgba(245,158,11,0.2);border-radius:8px;padding:12px;margin-bottom:12px;font-size:12px;line-height:1.7;color:#f0b90b;white-space:pre-wrap'>" + notes + "</div>" if notes else ""
    rows = []
    for t in sorted(proj_tasks, key=lambda x: (x.get("freq",""), x.get("name",""))):
        done = t.get("last_done","").startswith(today)
        freq_map = {"daily":"📅每日","weekly":"📆每周","monthly":"📆每月","one-time":"⭐一次性"}
        freq_label = freq_map.get(t.get("freq"),"")
        last_done = t.get("last_done","")[:10] if t.get("last_done") else "从未"
        next_run = t.get("next_run","")
        task_note = t.get("note","")
        done_cls = "btn-success" if not done else "btn-secondary"
        done_attr = "disabled" if done else ""
        checkbox = "✅" if done else "⬜"
        note_html = "<div style='font-size:10px;color:var(--text3)'>" + task_note + "</div>" if task_note else ""
        rows.append("<tr" + (" style='opacity:0.5'" if done else "") + "><td>" + checkbox + "</td><td>" + t.get("name","") + note_html + "</td><td>" + freq_label + "</td><td>" + last_done + "</td><td>" + next_run + "</td><td><a href='/task/" + t["id"] + "/edit?next=/proj/detail/" + proj_id + "' class='btn btn-sm'>✏️ 编辑</a> <a href='/task/" + t["id"] + "/done?next=/proj/detail/" + proj_id + "' class='btn btn-sm " + done_cls + "' " + done_attr + ">完成</a></td></tr>")
    pending_rows = ""
    for t in today_proj_tasks[:15]:
        freq_map2 = {"daily":"📅 每日","weekly":"📆 每周","monthly":"📆 每月","one-time":"⭐ 一次性"}
        freq_tag = "<span style='font-size:10px;color:var(--text3);margin-left:4px'>" + freq_map2.get(t.get("freq",""),"") + "</span>"
        next_run = t.get("next_run","")
        next_str = " <span style='font-size:10px;color:var(--text3)'>下次:" + next_run + "</span>" if next_run else ""
        task_note = "<div style='font-size:10px;color:var(--text3)'>" + t.get("note","") + "</div>" if t.get("note") else ""
        done_href = "/log-trade/" + t["id"] if t["id"] == "task-ba-001" else "/task/" + t["id"] + "/done?next=/proj/detail/" + proj_id
        pending_rows += "<div class='task-item'><div class='t-name'>" + t.get("name","") + freq_tag + next_str + task_note + "</div><a href='" + done_href + "' class='btn btn-sm btn-success'>✅ 完成</a></div>"
    done_rows = ""
    for t in today_proj_done[:10]:
        task_note = "<div style='font-size:10px;color:var(--text3)'>" + t.get("note","") + "</div>" if t.get("note") else ""
        done_rows += "<div class='task-item' style='opacity:0.6'><div class='t-name done'>" + t.get("name","") + task_note + "</div><span style='font-size:12px;color:#22c55e'>✓ 已完成</span></div>"
    links = proj.get("links", {})
    links_html = ""
    if isinstance(links, dict):
        items = [(n,u) for n,u in links.items() if u]
    else:
        items = [('',u) for u in (links or [])]
    for name, url in items:
        short = url[:50]+"..." if len(url)>50 else url
        display = name + " →" if name else short
        links_html += "<a href='" + url + "' class='link-tag' target='_blank'>" + display + "</a>"
    links_section = "<div class='section'><div class='section-head'>🔗 链接</div><div style='padding:0 16px;display:flex;flex-direction:column;gap:6px'>" + links_html + "</div></div>" if links_html else ""
    # Wallet management with investment tracking (not for BinanceAlpha)
    wallets_html = ""
    total_wallet_invest = 0
    if wallets and proj_id != "505baa0d":
        for w in wallets:
            if isinstance(w, dict):
                addr = w.get("address","")
                note = w.get("note","")
                invest_val = w.get("invest", 0)
                total_wallet_invest += invest_val
            else:
                addr = str(w)
                note = ""
                invest_val = 0
            if len(addr) > 20:
                addr_short = addr[:12] + "..." + addr[-8:]
            else:
                addr_short = addr
            invest_str = " <span style='color:var(--blue)'>$" + str(invest_val) + "</span>" if invest_val else ""
            wallets_html += "<div class='wallet-card' style='background:var(--bg3);padding:10px 12px;border-radius:6px;font-size:12px;margin-bottom:6px'><div style='display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:6px'><div style='font-size:13px;font-weight:600;color:var(--text)'>" + note + "</div><div style='text-align:right'><div style='font-size:14px;font-weight:700;color:var(--blue)'>$" + str(invest_val) + "</div><div style='font-size:10px;color:var(--text3)'>投入</div></div></div><div style='font-family:monospace;font-size:10px;color:var(--text3);word-break:break-all;margin-bottom:8px;background:var(--bg);padding:4px 6px;border-radius:4px'>" + addr + "</div><div style='display:flex;gap:4px'><button type='button' onclick='toggleEdit(this)' class='btn btn-sm' style='padding:3px 8px;font-size:11px'>✏️ 编辑</button><form method='post' action='/proj/" + proj_id + "/wallet/del' style='display:inline'><input type='hidden' name='wallet_addr' value='" + addr.replace("'","&#39;") + "'><button type='submit' class='btn btn-sm btn-danger' style='padding:3px 8px;font-size:11px'>🗑️ 删除</button></form></div><div style='display:none;margin-top:8px;background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:10px' class='wallet-edit-form'><div style='font-size:11px;color:var(--text3);margin-bottom:8px'>✏️ 编辑钱包</div><form method='post' action='/proj/" + proj_id + "/wallet/edit'><input type='hidden' name='wallet_addr' value='" + addr.replace("'","&#39;") + "'><div class='form-group'><label style='font-size:11px;color:var(--text3)'>别名/备注</label><input name='wallet_note' class='form-control' style='font-size:12px' placeholder='例如：MPC1 - Big Five' value='" + note.replace("'","&#39;") + "'></div><div class='form-group'><label style='font-size:11px;color:var(--text3)'>投入金额 ($)</label><input name='wallet_invest' class='form-control' style='font-size:12px' placeholder='0' type='number' step='0.01' min='0' value='" + str(invest_val) + "'></div><div style='margin-top:8px'><button type='submit' class='btn btn-primary btn-sm'>💾 保存</button> <button type='button' onclick='toggleEdit(this)' class='btn btn-sm'>取消</button></div></form><hr style='margin:10px 0;border-color:var(--border)'><div style='font-size:11px;color:var(--text3);margin-bottom:6px'>⚠️ 删除后将无法恢复</div><form method='post' action='/proj/ + proj_id + /wallet/del' style='display:inline'><input type='hidden' name='wallet_addr' value=' + addr + '><input type='hidden' name='wallet_addr_orig' value=' + addr + '><button type='submit' class='btn btn-sm btn-danger' style='padding:3px 8px;font-size:11px'>🗑️ 删除钱包</button></form></div></div>"
        wallets_html += "<div style='border-top:1px solid var(--border);padding-top:8px;margin-top:4px;font-size:12px;color:var(--text2)'>💰 累计投入: <strong style='color:var(--blue)'>$" + str(total_wallet_invest) + "</strong></div>"
    add_wallet_form = ""
    if proj_id != "505baa0d":
        add_wallet_form = "<div style='border-top:1px solid var(--border);padding-top:10px;margin-top:8px'><div style='font-size:11px;color:var(--text3);margin-bottom:6px'>➕ 添加钱包</div><form method='post' action='/proj/" + proj_id + "/wallet/add'><input name='wallet_addr' class='form-control' style='margin-bottom:6px;font-size:12px' placeholder='钱包地址' required><input name='wallet_note' class='form-control' style='margin-bottom:6px;font-size:12px' placeholder='备注（如：Base Boosted 115U）'><div style='display:flex;gap:6px'><input name='wallet_invest' class='form-control' style='margin-bottom:6px;font-size:12px;width:100px' placeholder='投入金额$' type='number' step='0.01' min='0'><button type='submit' class='btn btn-primary btn-sm'>添加</button></div></form></div>"
    wallets_section = ""  # LP项目单独处理
    if proj_id == "xau-lp-001":
        # ===== LP 流动性仓位 =====
        lp_positions = proj.get("lp_positions", [])
        lp_open = [p for p in lp_positions if p.get("status") == "open"]
        lp_closed = [p for p in lp_positions if p.get("status") == "closed"]
        # LP仓位表格
        lp_rows_html = ""
        for p in lp_open:
            pair = p.get("token_pair", "")
            initial = p.get("lp_amount", 0)
            current = p.get("current_balance", 0)
            fees = p.get("fees", 0)
            pnl = (current + fees) - initial
            pnl_color = "#22c55e" if pnl >= 0 else "#ef4444"
            pnl_sign = "+" if pnl >= 0 else ""
            value_est = current  # 简化：LP token面值=本位币数量
            lp_rows_html += f"<tr>"
            lp_rows_html += f"<td style='font-weight:600'>{pair}</td>"
            lp_rows_html += f"<td style='color:var(--blue)'>${initial:.2f}</td>"
            lp_rows_html += f"<td>${current:.2f}</td>"
            lp_rows_html += f"<td>${fees:.2f}</td>"
            lp_rows_html += f"<td style='color:{pnl_color};font-weight:600'>{pnl_sign}${pnl:.2f}</td>"
            # 格式化开仓时间（兼容 date 和 datetime-local）
            raw_date = p.get('open_date', '')
            if 'T' in raw_date:
                display_date = raw_date.replace('T', ' ')
            else:
                display_date = raw_date
            duration_id = 'dur-' + p['id']
            lp_rows_html += f"<td>{display_date}</td>"
            lp_rows_html += f"<td id='{duration_id}' style='color:#e3b341;font-weight:500'>⏳ 计算中...</td>"
            lp_rows_html += f"<td style='color:#22c55e'>🟢 开仓中</td>"
            lp_rows_html += f"<td><form method='post' action='/proj/lp/close-position/{proj_id}' style='display:inline-flex;gap:4px;align-items:center' onclick=\"this.querySelector('input[name=close_balance]').value=this.closest('tr').querySelector('.bal-cell').textContent.replace('$','')\"><input type='hidden' name='pos_id' value='{p['id']}'><input type='hidden' name='open_date' value='{p.get('open_date','')}'><input type='number' step='0.01' name='close_balance' class='form-control' style='width:80px;font-size:11px' placeholder='余额' required><input type='number' step='0.01' name='close_fees' class='form-control' style='width:70px;font-size:11px' placeholder='手续费' value='{fees:.2f}'><input type='datetime-local' name='close_date' class='form-control' style='width:165px;font-size:11px' value='{datetime.now().strftime('%Y-%m-%dT%H:%M')}'><button type='submit' class='btn btn-sm' style='background:#ef4444;color:#fff;font-size:11px;padding:3px 8px'>关闭仓位</button></form></td>"
            lp_rows_html += f"</tr>"
        if not lp_rows_html:
            lp_rows_html = "<tr><td colspan='9' style='text-align:center;color:var(--text3);padding:20px'>暂无开仓仓位，点击下方添加</td></tr>"
        lp_add_form = f"""
        <div style='border-top:1px solid var(--border);padding-top:12px;margin-top:12px'>
            <div style='font-size:11px;color:var(--text3);margin-bottom:8px'>➕ 添加 LP 仓位</div>
            <form method='post' action='/proj/lp/add-position/{proj_id}' style='display:flex;flex-wrap:wrap;gap:6px;align-items:flex-end'>
                <div style='flex:1;min-width:120px'>
                    <label style='font-size:11px;color:var(--text3)'>代币对</label>
                    <input name='token_pair' class='form-control' style='font-size:12px' placeholder='例如：BASED/USDT' required>
                </div>
                <div>
                    <label style='font-size:11px;color:var(--text3)'>初始LP ($)</label>
                    <input name='lp_amount' type='number' step='0.01' class='form-control' style='width:90px;font-size:12px' placeholder='0' required>
                </div>
                <div>
                    <label style='font-size:11px;color:var(--text3)'>待领手续费</label>
                    <input name='fees' type='number' step='0.01' class='form-control' style='width:80px;font-size:12px' placeholder='0' value='0'>
                </div>
                <div>
                    <label style='font-size:11px;color:var(--text3)'>开仓时间</label>
                    <input name='open_date' type='datetime-local' class='form-control' style='width:175px;font-size:12px' value='{datetime.now().strftime('%Y-%m-%dT%H:%M')}'>
                </div>
                <div style='flex:1'>
                    <label style='font-size:11px;color:var(--text3)'>备注</label>
                    <input name='note' class='form-control' style='font-size:12px' placeholder='可选'>
                </div>
                <button type='submit' class='btn btn-primary' style='font-size:12px'>添加仓位</button>
            </form>
        </div>"""
        lp_section = f"""
        <div class='section'>
            <div class='section-head'>💦 LP 仓位 <span style='background:#22c55e;color:#fff;border-radius:10px;padding:1px 7px;font-size:11px'>{len(lp_open)} 开仓中</span></div>
            <div style='overflow-x:auto;padding:12px 16px'>
                <table class='data-table' style='font-size:12px'>
                    <thead><tr><th>代币对</th><th>初始LP</th><th>当前余额</th><th>待领手续费</th><th>盈亏</th><th>开仓时间</th><th>持有时长</th><th>状态</th><th>操作</th></tr></thead>
                    <tbody>{lp_rows_html}</tbody>
                </table>
                {lp_add_form}
            </div>
        </div>"""
        # LP 操作历史 (with filter)
        lp_ops = proj.get("lp_operations", [])
        op_rows = ""
        lp_op_count = len(lp_ops)
        from collections import defaultdict
        date_groups = defaultdict(list)
        for op in lp_ops:
            date_key = op.get('date', '')[:10]
            date_groups[date_key].append(op)
        sorted_dates = sorted(date_groups.keys(), reverse=True)
        for date_key in sorted_dates:
            day_ops = date_groups[date_key]
            day_pnl = sum(o.get('profit', 0) for o in day_ops if o.get('type') == 'close')
            for op in day_ops:
                pnl_val = op.get("profit", 0)
                pnl_color = "#22c55e" if pnl_val >= 0 else "#ef4444"
                pnl_sign = "+" if pnl_val >= 0 else ""
                op_type = op.get("type", "")
                op_type_icons = {"open": ("🟢 开仓", "#22c55e"), "topup": ("💵 追加", "#f59e0b"), "reduce": ("🔽 减仓", "#ef4444"), "claim": ("🟡 认领", "#f59e0b"), "close": ("🔴 关闭", "#ef4444")}
                op_type_icon, op_type_color = op_type_icons.get(op_type, ("⚪ " + op_type, "#9ca3af"))
                op_rows += f"<tr data-optype='{op_type}'>"
                op_rows += f"<td>{op.get('date', '')}</td>"
                op_rows += f"<td style='color:{op_type_color};font-weight:600'>{op_type_icon}</td>"
                op_rows += f"<td style='font-weight:600'>{op.get('token_pair','')}</td>"
                op_rows += f"<td>${op.get('principal',0):.2f}</td>"
                op_rows += f"<td style='color:{pnl_color};font-weight:600'>{pnl_sign}${pnl_val:.2f}</td>"
                op_rows += f"<td style='color:{pnl_color};font-weight:600'>¥{pnl_val * 6.8:.2f}</td>"
                op_rows += f"<td>{op.get('duration','')}</td>"
                op_rows += f"<td style='font-size:11px;color:var(--text3)'>{op.get('note','')}</td>"
                op_rows += f"</tr>"
            # Daily subtotal row (only one per date)
            day_pnl_color = "#22c55e" if day_pnl >= 0 else "#ef4444"
            day_sign = "+" if day_pnl >= 0 else ""
            op_rows += f"<tr style='background:var(--bg3);font-weight:600;border-top:2px solid var(--border)'>"
            op_rows += f"<td colspan='4' style='text-align:right;font-size:11px;color:var(--text2)'>📊 {date_key} 小计</td>"
            op_rows += f"<td style='color:{day_pnl_color}'>{day_sign}${day_pnl:.2f}</td>"
            op_rows += f"<td style='color:{day_pnl_color}'>¥{day_pnl * 6.8:.2f}</td>"
            op_rows += f"<td></td><td></td>"
            op_rows += f"</tr>"
        if not op_rows:
            op_rows = "<tr><td colspan='8' style='text-align:center;color:var(--text3);padding:16px'>暂无操作记录</td></tr>"
        total_invest = sum(op.get("principal",0) for op in lp_ops if op.get("type") in ("open","topup","reduce"))
        total_pnl = sum(op.get('profit',0) for op in lp_ops)
        pnl_cls = '#22c55e' if total_pnl >= 0 else '#ef4444'
        op_summary = f"<div style='display:flex;gap:16px;padding:10px 16px;background:var(--bg3);border-radius:8px;margin-bottom:10px;font-size:12px;flex-wrap:wrap'><div>累计投入: <strong style='color:var(--blue)'>${total_invest:.2f}</strong></div><div>累计收益: <strong style='color:{pnl_cls}'>{'+' if total_pnl>=0 else ''}${total_pnl:.2f}</strong></div><div>操作次数: <strong>{len(lp_ops)}</strong></div></div>"
        filter_btns = f"""
        <div style='padding:0 16px 8px;display:flex;gap:6px'>
            <button class='lp-filter-btn' data-optype='all' onclick="filterLpOps('all',this)" style='padding:4px 12px;border:1px solid var(--border);border-radius:6px;background:var(--blue);color:#fff;font-size:11px;cursor:pointer'>全部</button>
            <button class='lp-filter-btn' data-optype='open' onclick="filterLpOps('open',this)" style='padding:4px 12px;border:1px solid var(--border);border-radius:6px;background:var(--bg3);color:var(--text2);font-size:11px;cursor:pointer'>🟢 开仓</button>
            <button class='lp-filter-btn' data-optype='close' onclick="filterLpOps('close',this)" style='padding:4px 12px;border:1px solid var(--border);border-radius:6px;background:var(--bg3);color:var(--text2);font-size:11px;cursor:pointer'>🔴 关闭</button>
        </div>
        <script>
        function filterLpOps(type, btn) {{
            var rows = document.querySelectorAll('#lp-op-table tbody tr');
            rows.forEach(function(r) {{
                if(type === 'all' || r.getAttribute('data-optype') === type) {{
                    r.style.display = '';
                }} else {{
                    r.style.display = 'none';
                }}
            }});
            document.querySelectorAll('.lp-filter-btn').forEach(function(b) {{
                b.style.background = 'var(--bg3)';
                b.style.color = 'var(--text2)';
            }});
            btn.style.background = 'var(--blue)';
            btn.style.color = '#fff';
        }}
        </script>"""
        op_section = f"""
    <div style='display:flex;gap:16px;align-items:flex-start;margin-bottom:16px'>

      <!-- 左栏：明细表 -->
      <div style='flex:1;min-width:0'>
        <div class='section'>
            <div class='section-head'>📊 LP 操作历史 <span class='badge'>{len(lp_ops)}</span></div>
                        {filter_btns}
            <div style='overflow-x:auto;padding:0 12px 12px'>
                <table id='lp-op-table' class='data-table' style='font-size:11px'>
                    <thead><tr><th>日期</th><th>类型</th><th>代币对</th><th>本金</th><th>收益(USD)</th><th>收益(CNY)</th><th>时长</th><th>备注</th></tr></thead>
                    <tbody>{op_rows}</tbody>
                </table>
            </div>
        </div>
      </div>

      <!-- 右栏：可视化看板 -->
      <div style='width:520px;flex-shrink:0;display:flex;flex-direction:column;gap:14px'>
        <div id='lp-viz-panel'>
          <div style='text-align:center;color:var(--text3);padding:60px 0;font-size:12px'>⏳ 加载可视化组件...</div>
        </div>
      </div>

    </div>

    <script>
    // ── 构建每日盈亏数据 ──
    (function() {{
      var __rawOps = {json.dumps(proj.get('lp_operations',[]))};
      if (!__rawOps.length) return;

      var CNY_RATE = 6.8;
      var dailyPnl = {{}};
      var allDateKeys = [];
      for (var i = 0; i < __rawOps.length; i++) {{
        var op = __rawOps[i];
        var dateKey = op.date.substring(0, 10); // group by date only
        if (op.type === 'close') {{
          dailyPnl[dateKey] = (dailyPnl[dateKey] || 0) + (op.profit || 0);
        }}
        if (allDateKeys.indexOf(dateKey) === -1) allDateKeys.push(dateKey);
      }}
      // Ensure all dates have entry (even zeros)
      for (var i = 0; i < allDateKeys.length; i++) {{
        if (!(allDateKeys[i] in dailyPnl)) dailyPnl[allDateKeys[i]] = 0;
      }}
      // Build daily trade detail map for tooltips
      var dailyTrades = {{}};
      for (var i = 0; i < __rawOps.length; i++) {{
        var op = __rawOps[i];
        var dk = op.date.substring(0, 10);
        if (!dailyTrades[dk]) dailyTrades[dk] = [];
        dailyTrades[dk].push(op);
      }}

      var dates = Object.keys(dailyPnl).sort();
      var values = dates.map(function(d) {{ return dailyPnl[d]; }});

      // Cumulative
      var cum = 0, cumValues = values.map(function(v) {{ cum += v; return +cum.toFixed(2); }});

      // Max abs for heatmap
      var maxAbs = Math.max.apply(null, values.map(Math.abs).concat([1]));

      function fmtCNY(v) {{ return '¥' + (v * CNY_RATE).toFixed(2); }}

      // Stats
      var pnlSum = values.reduce(function(a,b){{return a+b;}},0);
      var gainDays = values.filter(function(v){{return v>0;}}).length;
      var maxGain = -Infinity, maxLoss = Infinity, maxGainDate='', maxLossDate='';
      for (var i=0;i<dates.length;i++) {{
        if (values[i] > maxGain) {{ maxGain = values[i]; maxGainDate = dates[i]; }}
        if (values[i] < maxLoss) {{ maxLoss = values[i]; maxLossDate = dates[i]; }}
      }}
      var vs = (pnlSum>=0?'+':'') + '$' + pnlSum.toFixed(2);

      var panel = document.getElementById('lp-viz-panel');

      // ── 1. Stats cards ──
      var gc = '#22c55e', rc = '#ef4444', bc = '#58a6ff';
      panel.innerHTML = '<div style="display:flex;gap:8px">' +
        '<div class="stat-item"><div class="s-label">总收益</div><div class="s-value" style="font-size:16px;color:'+gc+'">'+vs+'</div><div class="s-sub">'+fmtCNY(pnlSum)+'</div></div>' +
        '<div class="stat-item"><div class="s-label">盈利天数</div><div class="s-value" style="font-size:16px;color:'+gc+'">'+gainDays+'天</div><div class="s-sub">占 '+Math.round(gainDays/dates.length*100)+'%</div></div>' +
        '<div class="stat-item"><div class="s-label">最大日盈利</div><div class="s-value" style="font-size:16px;color:'+gc+'">+$'+maxGain.toFixed(2)+'</div><div class="s-sub">'+maxGainDate+'</div></div>' +
        '<div class="stat-item"><div class="s-label">最大日亏损</div><div class="s-value" style="font-size:16px;color:'+rc+'">-$'+Math.abs(maxLoss).toFixed(2)+'</div><div class="s-sub">'+maxLossDate+'</div></div>' +
      '</div>';

      // ── 2. Cumulative P&L chart ──
      var chart1 = document.createElement('div');
      chart1.className = 'section';
      chart1.innerHTML = '<div class="section-head">📈 总体盈亏曲线</div><div style="padding:12px"><div style="height:160px"><canvas id="cumChart"></canvas></div></div>';
      panel.appendChild(chart1);

      // ── 3. Daily bar chart ──
      var chart2 = document.createElement('div');
      chart2.className = 'section';
      chart2.innerHTML = '<div class="section-head">📊 每日盈亏</div><div style="padding:12px"><div style="height:130px"><canvas id="pnlChart"></canvas></div></div>';
      panel.appendChild(chart2);

      // ── 4. Heatmap calendar ──
      var cal = document.createElement('div');
      cal.className = 'section';
      cal.id = 'heatmapSection';

      // Build heatmap
      var first = new Date(dates[0]), last = new Date(dates[dates.length-1]);
      var start = new Date(first); start.setDate(start.getDate() - ((start.getDay()+6)%7));
      var end = new Date(last); end.setDate(end.getDate() + (6 - end.getDay()));
      var weeks = [], cur = [];
      for (var d = new Date(start); d <= end; d.setDate(d.getDate()+1)) {{
        if (d.getDay() === 1) {{ if(cur.length) weeks.push(cur); cur = []; }}
        cur.push(new Date(d));
      }}
      if (cur.length) weeks.push(cur);

      function ymd(d) {{ return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0'); }}
      function calColor(ds, p) {{
        if (!(ds in dailyPnl)) return 'var(--bg2)';
        var r = Math.abs(p) / maxAbs;
        return p > 0 ? 'rgba(34,197,94,'+(0.1+r*0.9)+')' : p < 0 ? 'rgba(218,54,51,'+(0.1+r*0.9)+')' : 'var(--bg3)';
      }}

      var months = ['','1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月'];
      var calHtml = '<div class="section-head">📅 盈亏热力图</div><div style="padding:12px"><div style="display:flex;gap:2px;margin-bottom:4px;overflow-x:auto">';
      var pm = -1;
      for (var wi = 0; wi < weeks.length; wi++) {{
        var m = weeks[wi][0].getMonth();
        if (m !== pm) calHtml += '<div style="font-size:8px;color:var(--text3);width:116px;text-align:left">'+months[m+1]+'</div>';
        else calHtml += '<div style="width:116px"></div>';
        pm = m;
      }}
      calHtml += '</div><div style="display:flex;gap:2px"><div style="display:flex;flex-direction:column;gap:2px;margin-right:4px">';
      for (var ni=0;ni<7;ni++) calHtml += '<div style="font-size:8px;color:var(--text3);width:16px;text-align:right;padding-right:2px;height:13px;line-height:13px">'+['一','二','三','四','五','六','日'][ni]+'</div>';
      calHtml += '</div>';
      for (var wi = 0; wi < weeks.length; wi++) {{
        calHtml += '<div style="display:flex;flex-direction:column;gap:2px">';
        for (var di = 0; di < weeks[wi].length; di++) {{
          var d = weeks[wi][di], ds = ymd(d), p = dailyPnl[ds] || 0;
          calHtml += '<div style="width:13px;height:13px;border-radius:2px;background:'+calColor(ds,p)+';cursor:pointer;position:relative" title="'+ds+': '+(p>=0?'+':'')+'$'+p.toFixed(2)+'"></div>';
        }}
        calHtml += '</div>';
      }}
      calHtml += '</div></div>';
      cal.innerHTML = calHtml;
      panel.appendChild(cal);

      // ── 5. Stock-style calendar (month view) ──
      var sc = document.createElement('div');
      sc.className = 'section';
      // Group by month
      var monthMap = {{}};
      for (var i = 0; i < __rawOps.length; i++) {{
        var op = __rawOps[i];
        if (op.type !== 'close') continue;
        var m = op.date.substring(0,7);
        if (!monthMap[m]) monthMap[m] = {{}};
        monthMap[m][op.date.substring(0,10)] = (monthMap[m][op.date.substring(0,10)] || 0) + (op.profit || 0);
      }}
      // Also add dates with only opens
      for (var i = 0; i < __rawOps.length; i++) {{
        var op = __rawOps[i], m = op.date.substring(0,7);
        if (!monthMap[m]) monthMap[m] = {{}};
        monthMap[m][op.date.substring(0,10)] = monthMap[m][op.date.substring(0,10)] || 0;
      }}
      var monthsSorted = Object.keys(monthMap).sort().reverse();

      // This month P&L
      var thisMonth = (new Date().getFullYear())+'-'+String(new Date().getMonth()+1).padStart(2,'0');
      var thisMonthPnl = 0;
      if (monthMap[thisMonth]) for (var k in monthMap[thisMonth]) thisMonthPnl += monthMap[thisMonth][k];

      var scHtml = '<div class="section-head">🗓 盈亏日历 <span style="font-size:10px;color:var(--text3);font-weight:400">每日盈亏金额(USD)</span></div><div style="padding:12px">';
      // Summary bar
      scHtml += '<div style="display:flex;gap:16px;margin-bottom:10px;font-size:11px;flex-wrap:wrap">' +
        '<div>本月盈利: <strong style="color:'+(thisMonthPnl>=0?gc:rc)+'">'+(thisMonthPnl>=0?'+':'')+'$'+thisMonthPnl.toFixed(2)+'</strong></div>' +
        '<div>总收益: <strong style="color:'+(pnlSum>=0?gc:rc)+'">'+vs+'</strong></div>' +
      '</div>';

      for (var mi = 0; mi < Math.min(monthsSorted.length, 3); mi++) {{
        var m = monthsSorted[mi];
        var parts = m.split('-');
        var y = parseInt(parts[0]), mo = parseInt(parts[1]);
        var daysInMonth = new Date(y, mo, 0).getDate();
        var firstDow = new Date(m+'-01').getDay();
        var monthLabel = m.replace('-','年')+'月';
        var monthPnl = 0; for (var k in monthMap[m]) monthPnl += monthMap[m][k];
        var mCls = monthPnl >= 0 ? gc : rc;

        scHtml += '<div style="font-size:11px;color:var(--text2);padding:4px 0;text-align:center">'+monthLabel+'  <span style="color:'+mCls+'">'+(monthPnl>=0?'+':'')+'$'+monthPnl.toFixed(2)+'</span></div>';
        scHtml += '<table style="width:100%;border-collapse:collapse;text-align:center;font-size:10px"><tr>';
        for (var dn=0;dn<7;dn++) scHtml += '<th style="font-size:9px;color:var(--text3);padding:2px 0;font-weight:400">'+['一','二','三','四','五','六','日'][dn]+'</th>';
        scHtml += '</tr><tr>';
        for (var i=0;i<(firstDow===0?6:firstDow-1);i++) scHtml += '<td style="border:none"></td>';

        for (var day=1; day<=daysInMonth; day++) {{
          var ds = m+'-'+String(day).padStart(2,'0');
          var pnl = monthMap[m][ds] || 0;
          var hasOp = ds in (monthMap[m] || {{}});
          var bg = !hasOp ? 'transparent' : pnl > 0 ? 'rgba(34,197,94,0.12)' : pnl < 0 ? 'rgba(218,54,51,0.12)' : 'var(--bg3)';
          var tc = pnl > 0 ? gc : pnl < 0 ? rc : 'var(--text3)';
          scHtml += '<td style="background:'+bg+';border:1px solid var(--border);border-radius:3px;padding:2px 0;width:14.28%">';
          scHtml += '<div style="font-size:7px;color:var(--text3)">'+day+'</div>';
          if (hasOp) scHtml += '<div style="font-size:9px;font-weight:600;color:'+tc+'">'+(pnl>=0?'+':'')+'$'+pnl.toFixed(1)+'</div>';
          scHtml += '</td>';
          if (((firstDow===0?day+6:day+firstDow-1) % 7 === 0) && day < daysInMonth) scHtml += '</tr><tr>';
        }}
        scHtml += '</tr></table><div style="height:8px"></div>';
      }}
      scHtml += '</div>';
      sc.innerHTML = scHtml;
      panel.appendChild(sc);

      // ── Build Chart.js charts ──
      // Cumulative P&L line chart
      try {{
        var cumCtx = document.getElementById('cumChart').getContext('2d');
        if (typeof Chart !== 'undefined') {{
          new Chart(cumCtx, {{
            type: 'line',
            data: {{
              labels: dates,
              datasets: [{{
                data: cumValues,
                borderColor: '#22c55e',
                backgroundColor: 'rgba(34,197,94,0.1)',
                fill: true,
                tension: 0.3,
                pointRadius: 3,
                pointBackgroundColor: cumValues.map(function(v){{return v>=0?'#22c55e':'#ef4444';}}),
                pointBorderColor: '#fff',
                pointBorderWidth: 1
              }}]
            }},
            options: {{
              responsive: true, maintainAspectRatio: false,
              plugins: {{ legend: {{ display: false }}, tooltip: {{ callbacks: {{ title: function(items) {{ return items[0].label; }}, label: function(ctx) {{
  var d = dates[ctx.dataIndex];
  var tds = dailyTrades[d] || [];
  var lines = ['累计: '+(ctx.raw>=0?'+':'')+'$'+ctx.raw.toFixed(2)];
  for (var ti = 0; ti < tds.length; ti++) {{
    var td = tds[ti];
    var tm = td.date.substring(11, 16);
    var sg = (td.profit||0) >= 0 ? '+' : '';
    var ic = td.type === 'close' ? '🔴' : td.type === 'open' ? '🟢' : '⚪';
    lines.push('  ' + tm + ' ' + ic + ' ' + (td.token_pair||'') + ' ' + sg + '$' + (td.profit||0).toFixed(2));
  }}
  return lines;
}} }} }} }},
              scales: {{ x: {{ ticks: {{ color:'var(--text3)', font:{{size:9}}, maxTicksLimit:8 }}, grid:{{ color:'var(--border)' }} }}, y: {{ ticks: {{ color:'var(--text3)', font:{{size:9}}, callback: function(v){{return '$'+v;}} }}, grid:{{ color:'var(--border)' }} }} }}
            }}
          }});

          var pnlCtx = document.getElementById('pnlChart').getContext('2d');
          new Chart(pnlCtx, {{
            type: 'bar',
            data: {{
              labels: dates,
              datasets: [{{
                data: values,
                backgroundColor: values.map(function(v){{return v>=0?'rgba(34,197,94,0.7)':'rgba(218,54,51,0.7)';}}),
                borderColor: values.map(function(v){{return v>=0?'#22c55e':'#da3633';}}),
                borderWidth: 1, borderRadius: 4
              }}]
            }},
            options: {{
              responsive: true, maintainAspectRatio: false,
              plugins: {{ legend: {{ display: false }}, tooltip: {{ callbacks: {{ title: function(items) {{ return items[0].label; }}, label: function(ctx) {{
  var d = dates[ctx.dataIndex];
  var tds = dailyTrades[d] || [];
  var lines = [(ctx.raw>=0?'+':'')+'$'+ctx.raw.toFixed(2)];
  for (var ti = 0; ti < tds.length; ti++) {{
    var td = tds[ti];
    var tm = td.date.substring(11, 16);
    var sg = (td.profit||0) >= 0 ? '+' : '';
    var ic = td.type === 'close' ? '🔴' : td.type === 'open' ? '🟢' : '⚪';
    lines.push('  ' + tm + ' ' + ic + ' ' + (td.token_pair||'') + ' ' + sg + '$' + (td.profit||0).toFixed(2));
  }}
  return lines;
}} }} }} }},
              scales: {{ x: {{ ticks: {{ color:'var(--text3)', font:{{size:9}}, maxRotation:45, maxTicksLimit:14 }}, grid:{{ color:'var(--border)' }} }}, y: {{ ticks: {{ color:'var(--text3)', font:{{size:9}}, callback: function(v){{return '$'+v;}} }}, grid:{{ color:'var(--border)' }} }} }}
            }}
          }});
        }}
      }} catch(e) {{ console.log('Chart error:', e); }}
    }})();
    </script>"""
    elif wallets or proj_id != "505baa0d":
        # 原有钱包逻辑
        wallets_html = ""
        total_wallet_invest = 0
        for w in wallets:
            addr = w.get("address", "")[:10] + "..."
            note = w.get("note", "")
            invest = float(w.get("invest", 0) or 0)
            balance = float(w.get("balance", invest))
            pnl = balance - invest
            pnl_str = f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"
            pnl_color = "#22c55e" if pnl >= 0 else "#ef4444"
            total_wallet_invest += invest
            wallets_html += f"<div style='display:flex;justify-content:space-between;align-items:center;padding:6px 0;border-bottom:1px solid var(--border)'><div><div style='font-size:13px'>{note or addr}</div><div style='font-size:11px;color:var(--text3)'>{addr}</div></div><div style='text-align:right'><div style='font-size:13px;font-weight:600'>${balance:.2f}</div><div style='font-size:11px;color:{pnl_color}'>{pnl_str}</div></div></div>"
        add_wallet_form = f"<div style='border-top:1px solid var(--border);padding-top:10px;margin-top:8px'><div style='font-size:11px;color:var(--text3);margin-bottom:6px'>➕ 添加钱包</div><form method='post' action='/proj/{proj_id}/wallet/add'><input name='wallet_addr' class='form-control' style='margin-bottom:6px;font-size:12px' placeholder='钱包地址' required><input name='wallet_note' class='form-control' style='margin-bottom:6px;font-size:12px' placeholder='备注（如：Base Boosted 115U）'><div style='display:flex;gap:6px'><input name='wallet_invest' class='form-control' style='margin-bottom:6px;font-size:12px;width:100px' placeholder='投入金额$' type='number' step='0.01' min='0'><button type='submit' class='btn btn-primary btn-sm'>添加</button></div></form></div>"
        wallets_section = "<div class='section'><div class='section-head'>💼 钱包 <span class='badge'>" + str(len(wallets)) + "</span></div><div style='padding:12px 16px;display:flex;flex-direction:column;gap:6px'>" + (wallets_html + add_wallet_form if wallets else "<div style='font-size:12px;color:var(--text3);margin-bottom:8px'>暂无钱包</div>" + add_wallet_form) + "</div></div>"

    # ── PredictFun 专属模块 ──────────────────────────────────
    predict_section = ""
    if proj_id == "predictfun-001":
        pw_all  = proj.get("predict_wallets", [])
        ps_list = proj.get("predict_strategies", [])

        # ── 数据整理 ────────────────────────────────────────
        all_ops = []   # 扁平化所有仓位
        for w in pw_all:
            for op in (w.get("ops") or []):
                op["_wallet"] = w.get("name","?")
                all_ops.append(op)

        total_capital = sum(float(op.get("amount",0)) for op in all_ops)
        total_pnl     = sum(float(op.get("pnl",0))   for op in all_ops)
        active_count  = sum(1 for op in all_ops if op.get("action")=="挂单")
        settled_count = sum(1 for op in all_ops if op.get("action")=="平仓")

        # ── 策略选项（for form & calc）──────────────────────
        strat_json = json.dumps({s["id"]: s for s in ps_list}, ensure_ascii=False)
        strat_options = "".join(
            f"<option value='{s['id']}'>{s['name']} — {s['desc']}</option>"
            for s in ps_list
        )
        strat_cards = "".join(
            f"""<div class='strat-card' id='strat-card-{s["id"]}' style='cursor:pointer;flex:1;min-width:150px;background:var(--bg3);border:2px solid var(--border);border-radius:10px;padding:10px' onclick=\"selectStrat('{s['id']}',this)\">
                <div style='font-weight:700;font-size:12px;margin-bottom:4px'>{s['name']}</div>
                <div style='font-size:10px;color:var(--text3);line-height:1.4'>{s['desc']}</div>
            </div>"""
            for s in ps_list
        )

        # ── 仓位记录表 ─────────────────────────────────────
        def strat_by_id(sid):
            return next((s for s in ps_list if s["id"]==sid), None)

        def calc_prices(s, mid, amt):
            nb, na, fb, fa = s["near_bid_ratio"], s["near_ask_ratio"], s["far_bid_ratio"], s["far_ask_ratio"]
            tot = nb+na+fb+fa
            return {
                "nb_p": mid*(1-s["near_bid_pct"]), "nb_a": amt*nb/tot,
                "na_p": mid*(1+s["near_ask_pct"]), "na_a": amt*na/tot,
                "fb_p":  mid*(1-s["far_bid_pct"]),  "fb_a": amt*fb/tot,
                "fa_p":  mid*(1+s["far_ask_pct"]),  "fa_a": amt*fa/tot,
            }

        def fmt_p(v): return f"{v:.4f}" if v < 1 else f"{v:.2f}"

        op_rows = ""
        for op in sorted(all_ops, key=lambda x: x.get("date",""), reverse=True):
            sname   = op.get("strategy","?")
            market  = op.get("market","?")
            mid_s   = ""
            note    = op.get("note","")
            # 从note里解析mid: "mid=0.7 | ..."
            mid_val = 0.0
            if "mid=" in note:
                try: mid_val = float(note.split("mid=")[1].split("|")[0].strip())
                except: pass
            if not mid_val:
                try: mid_val = float(note.strip().split("|")[0])
                except: pass

            action  = op.get("action","挂单")
            amt     = float(op.get("amount",0) or 0)
            pnl     = float(op.get("pnl",0)    or 0)
            date    = op.get("date","?")
            wname   = op.get("_wallet","?")
            m_short = market[:38]+"..." if len(market)>38 else market

            s = strat_by_id(sname)
            if s and mid_val:
                p = calc_prices(s, mid_val, amt)
                order_txt = (
                    f"<span style='color:#60a5fa'>Bid{p['nb_p']:.3f}×${p['nb_a']:.0f}</span> | "
                    f"<span style='color:#f87171'>Ask{p['na_p']:.3f}×${p['na_a']:.0f}</span><br>"
                    f"<span style='color:var(--text3);font-size:9px'>远:{p['fb_p']:.3f}/{p['fa_p']:.3f}</span>"
                )
            elif s:
                order_txt = f"<span style='color:var(--text3)'>-</span>"
            else:
                order_txt = f"<span style='color:var(--text3)'>-</span>"

            status_cls  = "badge-green" if action=="平仓" else "badge-blue"
            status_txt  = "✅已结算"   if action=="平仓" else "🟡挂单中"
            pnl_cls     = "#22c55e"    if pnl>0 else ("#ef4444" if pnl<0 else "var(--text2)")
            pnl_txt     = f"<span style='font-weight:700;color:{pnl_cls}'>{pnl:+.1f}</span>" if action=="平仓" else "<span style='color:var(--text3);font-size:10px'>待结算</span>"

            settle_url  = f"/proj/predictfun-001/settle?id={op.get('date','')}-{op.get('market','')[:10]}&next=/proj/detail/predictfun-001"

            op_rows += f"""<tr>
                <td style='font-size:11px;color:var(--text3);white-space:nowrap'>{date}</td>
                <td><div style='font-size:12px;font-weight:600;max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap' title='{market}'>{m_short}</div></td>
                <td style='font-size:11px;color:var(--blue)'>{wname}</td>
                <td style='font-size:11px;color:var(--text2)'>{sname}</td>
                <td style='font-size:12px;font-weight:700;color:var(--blue)'>${amt:.0f}</td>
                <td style='font-size:11px'>{order_txt}</td>
                <td><span class='{status_cls}' style='font-size:10px;padding:1px 6px;border-radius:4px'>{status_txt}</span></td>
                <td style='font-size:12px'>{pnl_txt}</td>
                <td style='font-size:10px;color:var(--text3)'>{note}</td>
                <td>
                    <form method='get' action='/proj/predictfun-001/settle' style='display:inline'>
                        <input type='hidden' name='id' value='{settle_url.split("id=")[1].split("&")[0]}'>
                        <input type='hidden' name='next' value='/proj/detail/predictfun-001'>
                        <input type='number' name='pnl' step='0.01' placeholder='PnL' style='width:55px;font-size:10px;border:1px solid var(--border);border-radius:4px;background:var(--bg3);color:var(--text);padding:2px 4px'>
                        <button type='submit' class='btn btn-sm' style='font-size:10px;padding:2px 6px'>结算</button>
                    </form>
                </td>
            </tr>"""

        if not op_rows:
            op_rows = "<tr><td colspan='10' style='text-align:center;color:var(--text3);padding:20px'>暂无仓位记录，填写下方表单开始挂单</td></tr>"

        # ── 策略表现统计 ────────────────────────────────────
        strat_stats = {}
        for op in all_ops:
            sn = op.get("strategy","?")
            if sn not in strat_stats: strat_stats[sn] = {"count":0,"capital":0.0,"pnl":0.0}
            strat_stats[sn]["count"]   += 1
            strat_stats[sn]["capital"] += float(op.get("amount",0) or 0)
            strat_stats[sn]["pnl"]     += float(op.get("pnl",0)    or 0)

        strat_perf_rows = ""
        for sn, st in sorted(strat_stats.items(), key=lambda x: -x[1]["capital"]):
            pnl_cls = "#22c55e" if st["pnl"]>=0 else "#ef4444"
            strat_perf_rows += f"""<tr>
                <td style='font-size:12px;font-weight:600;color:var(--blue)'>{sn}</td>
                <td style='font-size:12px'>{st['count']} 个仓位</td>
                <td style='font-size:12px;font-weight:700;color:var(--blue)'>${st['capital']:.0f}</td>
                <td style='font-size:12px;color:{pnl_cls};font-weight:700'>{st['pnl']:+.1f}</td>
            </tr>"""

        if not strat_perf_rows:
            strat_perf_rows = "<tr><td colspan='4' style='text-align:center;color:var(--text3)'>暂无数据</td></tr>"

        # ── 完整HTML ───────────────────────────────────────
        predict_section = f"""
<div class='section'>
<style>
.strat-card {{cursor:pointer;flex:1;min-width:150px;background:var(--bg3);border:2px solid var(--border);border-radius:10px;padding:10px;transition:all .15s}}
.strat-card.strat-active {{border-color:#f0b90b;background:rgba(240,185,11,0.12)}}
</style>
<div class='section-head'>🎯 PredictFun 做市系统</div>

<!-- 统计仪表盘 -->
<div style='display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:16px'>
    <div style='background:var(--bg2);border:1px solid var(--border);border-radius:10px;padding:12px;text-align:center'>
        <div style='font-size:10px;color:var(--text3);margin-bottom:4px'>总仓位</div>
        <div style='font-size:24px;font-weight:800;color:var(--blue)'>{len(all_ops)}</div>
    </div>
    <div style='background:var(--bg2);border:1px solid var(--border);border-radius:10px;padding:12px;text-align:center'>
        <div style='font-size:10px;color:var(--text3);margin-bottom:4px'>🟡 挂单中</div>
        <div style='font-size:24px;font-weight:800;color:#f59e0b'>{active_count}</div>
    </div>
    <div style='background:var(--bg2);border:1px solid var(--border);border-radius:10px;padding:12px;text-align:center'>
        <div style='font-size:10px;color:var(--text3);margin-bottom:4px'>总投入资金</div>
        <div style='font-size:24px;font-weight:800;color:var(--blue)'>${total_capital:.0f}</div>
    </div>
    <div style='background:var(--bg2);border:1px solid var(--border);border-radius:10px;padding:12px;text-align:center'>
        <div style='font-size:10px;color:var(--text3);margin-bottom:4px'>累计 PnL</div>
        <div style='font-size:24px;font-weight:800;color:{"#22c55e" if total_pnl>=0 else "#ef4444"}'>{total_pnl:+.1f}</div>
    </div>
</div>

<!-- 策略表现 -->
<div style='margin-bottom:16px'>
    <div style='font-size:12px;font-weight:700;margin-bottom:8px;color:var(--text2)'>📊 策略表现</div>
    <div style='overflow-x:auto'>
    <table class='data-table' style='font-size:11px'>
        <thead><tr><th>策略</th><th>仓位数</th><th>总资金</th><th>PnL</th></tr></thead>
        <tbody>{strat_perf_rows}</tbody>
    </table>
    </div>
</div>

<!-- 仓位记录表 -->
<div style='margin-bottom:16px'>
    <div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:8px'>
        <div style='font-size:12px;font-weight:700;color:var(--text2)'>📋 仓位记录</div>
    </div>
    <div style='overflow-x:auto'>
    <table class='data-table' style='font-size:11px'>
        <thead><tr>
            <th>日期</th><th>Market</th><th>钱包</th><th>策略</th>
            <th>资金</th><th>挂单价格</th><th>状态</th><th>PnL</th>
            <th>备注</th><th>操作</th>
        </tr></thead>
        <tbody>{op_rows}</tbody>
    </table>
    </div>
</div>

<!-- 快速挂单 + 计算器 -->
<div style='display:grid;grid-template-columns:1fr 1fr;gap:12px'>
    <!-- 左侧：挂单表单 -->
    <div style='background:var(--bg2);border:1px solid var(--border);border-radius:12px;padding:16px'>
        <div style='font-size:14px;font-weight:700;margin-bottom:12px'>⚡ 快速挂单</div>
        <form id='pf-form' method='post' action='/proj/predictfun-001/add-op'>
            <div class='form-group' style='margin-bottom:8px'>
                <label style='font-size:11px;color:var(--text3)'>Market 问题</label>
                <input name='market' class='form-control' style='font-size:12px' placeholder='例如：Will BTC hit $70k by June?' required>
            </div>
            <div style='display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px'>
                <div class='form-group'>
                    <label style='font-size:11px;color:var(--text3)'>选择钱包</label>
                    <select name='wallet_name' class='form-control' style='font-size:12px'>
                        {"".join(f"<option value='{w.get('name','')}'>{w.get('name','')} ({w.get('address','')[:10]}...)</option>" for w in pw_all)}
                    </select>
                </div>
                <div class='form-group'>
                    <label style='font-size:11px;color:var(--text3)'>策略</label>
                    <select name='strategy' class='form-control' style='font-size:12px' onchange=\"syncStratFromSelect2(this.value)\">
                        {strat_options}
                    </select>
                </div>
            </div>
            <div style='display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px'>
                <div class='form-group'>
                    <label style='font-size:11px;color:var(--text3)'>Mid 价格</label>
                    <input id='f-mid' name='mid' type='number' step='0.001' min='0' class='form-control' style='font-size:12px' placeholder='例如 0.7' required oninput='calcFromForm()'>
                </div>
                <div class='form-group'>
                    <label style='font-size:11px;color:var(--text3)'>做市资金 ($)</label>
                    <input id='f-amt' name='amount' type='number' step='1' min='1' class='form-control' style='font-size:12px' placeholder='例如 100' required oninput='calcFromForm()'>
                </div>
            </div>
            <div class='form-group' style='margin-bottom:10px'>
                <label style='font-size:11px;color:var(--text3)'>备注（可选）</label>
                <input name='note' class='form-control' style='font-size:12px' placeholder='例如：exotic market | 120天'>
            </div>
            <!-- 挂单预览 -->
            <div id='order-preview' style='background:var(--bg3);border-radius:8px;padding:10px;margin-bottom:10px;font-size:11px;display:none'>
                <div style='color:var(--text3);margin-bottom:6px'>📐 挂单预览</div>
                <div style='display:grid;grid-template-columns:1fr 1fr;gap:4px'>
                    <div>🔵 <span style='color:#60a5fa'>Bid近</span>: <span id='pv-nb' style='font-weight:700'>-</span> ×$<span id='pv-nba'>-</span></div>
                    <div>🔴 <span style='color:#f87171'>Ask近</span>: <span id='pv-na' style='font-weight:700'>-</span> ×$<span id='pv-naa'>-</span></div>
                    <div>🟡 <span style='color:#facc15'>Bid远</span>: <span id='pv-fb' style='font-weight:700'>-</span> ×$<span id='pv-fba'>-</span></div>
                    <div>🟠 <span style='color:#fb923c'>Ask远</span>: <span id='pv-fa' style='font-weight:700'>-</span> ×$<span id='pv-faa'>-</span></div>
                </div>
            </div>
            <button type='submit' class='btn btn-primary' style='width:100%'>🎯 记录挂单</button>
        </form>
    </div>

    <!-- 右侧：计算器 -->
    <div style='background:var(--bg2);border:1px solid var(--border);border-radius:12px;padding:16px'>
        <div style='font-size:14px;font-weight:700;margin-bottom:10px'>🧮 策略计算器</div>
        <div style='font-size:11px;color:var(--text3);margin-bottom:8px'>点击策略卡片切换</div>
        <div style='display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-bottom:12px'>
            {strat_cards}
        </div>
        <div style='display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:12px'>
            <div class='form-group'>
                <label style='font-size:11px;color:var(--text3)'>Mid 价格</label>
                <input id='c-mid' type='number' step='0.001' min='0' class='form-control' style='font-size:12px' placeholder='0.7' value='0.7' oninput='calcPP()'>
            </div>
            <div class='form-group'>
                <label style='font-size:11px;color:var(--text3)'>做市资金 ($)</label>
                <input id='c-amt' type='number' step='1' min='1' class='form-control' style='font-size:12px' placeholder='100' value='100' oninput='calcPP()'>
            </div>
        </div>
        <div id='calc-result' style='background:var(--bg3);border-radius:8px;padding:12px'>
            <div style='display:grid;grid-template-columns:1fr 1fr;gap:6px;text-align:center;margin-bottom:8px'>
                <div>
                    <div style='font-size:9px;color:var(--text3)'>🔵 Bid近</div>
                    <div id='r-nbp' style='font-size:13px;font-weight:800;color:#60a5fa'>-</div>
                    <div id='r-nba' style='font-size:11px;color:var(--text2)'>-</div>
                </div>
                <div>
                    <div style='font-size:9px;color:var(--text3)'>🔴 Ask近</div>
                    <div id='r-nap' style='font-size:13px;font-weight:800;color:#f87171'>-</div>
                    <div id='r-naa' style='font-size:11px;color:var(--text2)'>-</div>
                </div>
                <div>
                    <div style='font-size:9px;color:var(--text3)'>🟡 Bid远</div>
                    <div id='r-fbp' style='font-size:13px;font-weight:800;color:#facc15'>-</div>
                    <div id='r-fba' style='font-size:11px;color:var(--text2)'>-</div>
                </div>
                <div>
                    <div style='font-size:9px;color:var(--text3)'>🟠 Ask远</div>
                    <div id='r-fap' style='font-size:13px;font-weight:800;color:#fb923c'>-</div>
                    <div id='r-faa' style='font-size:11px;color:var(--text2)'>-</div>
                </div>
            </div>
            <div style='font-size:10px;color:var(--text3);text-align:center'>资金分配比: <span id='r-ratio' style='color:var(--blue)'>-</span></div>
        </div>
    </div>
</div>
</div>

<script>
const STRATS = {strat_json};
let activeStrat = ps_list.length > 1 ? ps_list[1]["id"] : ps_list[0]["id"];

function selectStrat(id, el) {{
    activeStrat = id;
    document.querySelectorAll('.strat-card').forEach(c => c.classList.remove('strat-active'));
    if (el) el.classList.add('strat-active');
    // 同步左侧表单的策略下拉
    const sel = document.querySelector('select[name="strategy"]');
    if (sel) sel.value = id;
    if (typeof calcPP === 'function') calcPP();
    if (typeof calcFromForm === 'function') calcFromForm();
}}

function syncStratFromSelect2(id) {{
    activeStrat = id;
    document.querySelectorAll('.strat-card').forEach(c => c.classList.remove('strat-active'));
    let card = document.getElementById('strat-card-' + id);
    if (card) card.classList.add('strat-active');
    if (typeof calcFromForm === 'function') calcFromForm();
}}

// 初始化：默认选中标准策略
(function initStrat() {{
    const def = document.getElementById('strat-card-' + activeStrat);
    if (def) def.classList.add('strat-active');
}})();

function doCalc(mid, amt) {{
    const s = STRATS[activeStrat];
    if (!s || !mid || !amt) return null;
    const nb=s.near_bid_ratio, na=s.near_ask_ratio, fb=s.far_bid_ratio, fa=s.far_ask_ratio;
    const tot = nb+na+fb+fa;
    return {{
        nbp: mid*(1-s.near_bid_pct), nba: amt*nb/tot,
        nap: mid*(1+s.near_ask_pct), naa: amt*na/tot,
        fbp: mid*(1-s.far_bid_pct),  fba: amt*fb/tot,
        fap: mid*(1+s.far_ask_pct),  faa: amt*fa/tot,
        ratio: nb+'/'+na+'/'+fb+'/'+fa,
    }};
}}

function showPreview(r) {{
    if (!r) return;
    document.getElementById('pv-nb').textContent  = r.nbp.toFixed(4);
    document.getElementById('pv-nba').textContent = r.nba.toFixed(0);
    document.getElementById('pv-na').textContent  = r.nap.toFixed(4);
    document.getElementById('pv-naa').textContent = r.naa.toFixed(0);
    document.getElementById('pv-fb').textContent  = r.fbp.toFixed(4);
    document.getElementById('pv-fba').textContent = r.fba.toFixed(0);
    document.getElementById('pv-fa').textContent  = r.fap.toFixed(4);
    document.getElementById('pv-faa').textContent = r.faa.toFixed(0);
    document.getElementById('order-preview').style.display = 'block';
}}

function calcFromForm() {{
    const mid = parseFloat(document.getElementById('f-mid').value) || 0;
    const amt = parseFloat(document.getElementById('f-amt').value) || 0;
    if (mid && amt) showPreview(doCalc(mid, amt));
}}

function calcPP() {{
    const mid = parseFloat(document.getElementById('c-mid').value) || 0;
    const amt = parseFloat(document.getElementById('c-amt').value) || 0;
    const r = doCalc(mid, amt);
    if (!r) return;
    document.getElementById('r-nbp').textContent = r.nbp.toFixed(4);
    document.getElementById('r-nba').textContent = '$'+r.nba.toFixed(0);
    document.getElementById('r-nap').textContent = r.nap.toFixed(4);
    document.getElementById('r-naa').textContent = '$'+r.naa.toFixed(0);
    document.getElementById('r-fbp').textContent = r.fbp.toFixed(4);
    document.getElementById('r-fba').textContent = '$'+r.fba.toFixed(0);
    document.getElementById('r-fap').textContent = r.fap.toFixed(4);
    document.getElementById('r-faa').textContent = '$'+r.faa.toFixed(0);
    document.getElementById('r-ratio').textContent = r.ratio;
}}

// ── LP 持仓时长实时更新 ──
function fmtDuration(startStr) {{
  var now = new Date();
  var start;
  if (startStr.indexOf('T') >= 0) {{
    start = new Date(startStr.replace('T', ' '));
  }} else {{
    start = new Date(startStr);
  }}
  var diff = (now - start) / 1000;
  if (diff < 0) return '👻 未来';
  var days = Math.floor(diff / 86400);
  var hrs = Math.floor((diff % 86400) / 3600);
  var mins = Math.floor((diff % 3600) / 60);
  var parts = [];
  if (days > 0) parts.push(days + '天');
  if (hrs > 0 || days > 0) parts.push(hrs + '时');
  parts.push(mins + '分');
  return '⏳ ' + parts.join('');
}}

function updateDurations() {{
  var cells = document.querySelectorAll('[id^="dur-"]');
  cells.forEach(function(cell) {{
    var row = cell.closest('tr');
    if (!row) return;
    var dateCell = row.cells[5]; // 开仓时间在第6列(0-indexed=5)
    if (!dateCell) return;
    cell.textContent = fmtDuration(dateCell.textContent.trim());
  }});
}}

// Initial update + every 30 seconds
updateDurations();
setInterval(updateDurations, 30000);

// Init
calcPP();

function calcFee() {{
    var before = parseFloat(document.querySelector('input[name="balance_before"]').value) || 0;
    var after = parseFloat(document.querySelector('input[name="balance_after"]').value) || 0;
    var fee = Math.max(0, before - after);
    var display = document.getElementById('fee_display');
    var hidden = document.getElementById('tx_fee_hidden');
    if (display) display.textContent = '磨损: ' + fee.toFixed(2) + ' U';
    if (hidden) hidden.value = fee.toFixed(2);
}}
</script>
"""

    del_url = "/proj/detail/" + proj_id + "/delete"
    edit_url = "/proj/detail/" + proj_id + "/edit"
    content_parts = [
        "<div class='page-header' style='display:block'>",
        "<a href='/?s=projects' class='back-btn'>← 返回项目列表</a>",
        "<div style='display:flex;align-items:center;gap:10px;margin-top:10px;flex-wrap:wrap'>",
        "<div style='font-size:20px;font-weight:700'>" + chain_icon + " " + proj.get("name","") + stars_html + "</div>",
        "<span style='background:rgba(34,197,94,0.15);color:#22c55e;border-radius:6px;padding:2px 8px;font-size:11px'>" + proj.get("status","") + "</span>",
        risk_html,
        "</div>",
    ]
    if tags_html:
        content_parts.append("<div style='display:flex;flex-wrap:wrap;gap:6px;margin-top:10px'>" + tags_html + "</div>")
    if proj_id == "xau-lp-001":
        # LP项目顶部统计（替代通用meta）
        lp_ops = proj.get("lp_operations", [])
        lp_pairs = list(dict.fromkeys(op.get("token_pair","") for op in lp_ops))
        lp_opens = [op for op in lp_ops if op.get("type") == "open"]
        lp_closes = [op for op in lp_ops if op.get("type") == "close"]
        total_pnl = sum(op.get("profit", 0) for op in lp_ops)
        total_op_count = len(lp_opens) + len(lp_closes)
        pnl_cls = "#22c55e" if total_pnl >= 0 else "#ef4444"
        pnl_sign = "+" if total_pnl >= 0 else ""
        content_parts.extend([
            "<div style='display:flex;gap:16px;margin-top:10px;font-size:12px;color:var(--text3);flex-wrap:wrap'>",
            "<span>" + chain + " · 流动性挖矿</span>",
            "<span>累计操作 <strong style='color:var(--text)'>" + str(total_op_count) + " 次</strong></span>",
            "<span>操作币对 <strong style='color:var(--text)'>" + str(len(lp_pairs)) + " 个</strong></span>",
            "<span>累计收益 <strong style='color:" + pnl_cls + "'>" + pnl_sign + "$" + ("%.2f" % total_pnl) + "</strong></span>",
            "</div></div>",
        ])
    else:
        meta_parts = [
            "<div style='display:flex;gap:16px;margin-top:10px;font-size:12px;color:var(--text3);flex-wrap:wrap'>",
            "<span>" + chain + " · " + ptype + "</span>",
            "<span>投入 <strong style='color:var(--text)'>$" + str(int(invest)) + "</strong></span>",
            "<span>收益 <strong style='color:#22c55e'>+$" + str(int(earn)) + "</strong></span>",
            "<span>Gas <strong style='color:var(--text)'>$" + str(int(gas)) + "</strong></span>",
            "<span>ROI <strong style='color:" + roi_color + "'>" + ("+" if roi >= 0 else "") + ("%.1f" % roi) + "%</strong></span>",
            ("<span>💼 " + str(len(wallets)) + "钱包</span>" if proj_id != "505baa0d" else ""),
            "<span>📋 " + str(total_count) + "任务</span>",
            "<span>⭐ " + str(ot_done) + "/" + str(ot_total) + "一次性</span>",
            "</div></div>",
        ]
        content_parts.extend(meta_parts)
    if proj_id != "xau-lp-001":
        content_parts.extend([
        "<div style='margin:12px 0'>",
        "<div style='display:flex;justify-content:space-between;font-size:11px;color:var(--text3);margin-bottom:4px'>",
        "<span>📋 任务完成度</span><span>" + str(done_count) + "/" + str(total_count) + " 今日完成 · " + str(pct) + "%</span>",
        "</div>",
        "<div style='height:8px;background:var(--border);border-radius:4px'>",
        "<div style='height:100%;width:" + str(pct) + "%;background:linear-gradient(90deg,#22c55e,#16a34a);border-radius:4px'></div>",
        "</div></div>",
        ])
    if desc_html:
        content_parts.append(desc_html)
    if notes_html:
        content_parts.append(notes_html)
    # 详细攻略 button
    readme_path = proj.get("readme_path", "")
    if readme_path and os.path.exists(readme_path):
        content_parts.append("<a href='/proj/detail/" + proj_id + "/plan' target='_blank' class='btn' style='display:inline-flex;align-items:center;gap:6px;margin-bottom:12px;text-decoration:none'>📋 详细攻略</a>")
    if proj_id not in ("xau-lp-001", "505baa0d"):
        content_parts.extend([
        "<div style='display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px'>",
        "<div style='background:var(--bg2);border:1px solid var(--border);border-radius:10px;padding:12px'>",
        "<div style='font-size:11px;color:var(--text3);margin-bottom:8px'>🔥 今日待办 <span style='color:#ef4444;font-weight:700;font-size:14px;margin-left:4px'>" + str(len(today_proj_tasks)) + "</span></div>",
        (pending_rows if pending_rows else "<div style='font-size:12px;color:var(--text3)'>✅ 今日任务已全部完成！</div>"),
        "</div>",
        "<div style='background:var(--bg2);border:1px solid var(--border);border-radius:10px;padding:12px'>",
        "<div style='font-size:11px;color:var(--text3);margin-bottom:8px'>✅ 今日已完成 <span style='color:#22c55e;font-weight:700;font-size:14px;margin-left:4px'>" + str(len(today_proj_done)) + "</span></div>",
        (done_rows if done_rows else "<div style='font-size:12px;color:var(--text3)'>暂无完成</div>"),
        "</div>",
        "</div>",
    ])
    if wallets_section and proj_id != "505baa0d":
        content_parts.append(wallets_section)

    # PredictFun 专属模块（策略卡片 + PP计算器）
    if predict_section:
        content_parts.append(predict_section)

    # ── BinanceAlpha 下拉框切换多钱包 ────────────────────────
    alpha_section = ""
    if proj_id == '505baa0d':
        alpha_wallets = proj.get('alpha_wallets', [])
        if not alpha_wallets:
            alpha_wallets = [{'id':'w1','name':'钱包1','target_vol':32800,'target_pts':17,'tx_log':[]}]
            proj['alpha_wallets'] = alpha_wallets
            save_json(PROJECTS_FILE, data)

        wallet_json_str = json.dumps({w['id']: w for w in alpha_wallets}, ensure_ascii=False)
        wallet_options = ''.join("<option value='{}'>{}</option>".format(w['id'], w['name']) for w in alpha_wallets)

        grand_vol = sum(tx.get('vol',0) for w in alpha_wallets for tx in w.get('tx_log',[]))
        grand_fee = sum(tx.get('fee',0) for w in alpha_wallets for tx in w.get('tx_log',[]))
        grand_pts = sum(tx.get('pts',0) for w in alpha_wallets for tx in w.get('tx_log',[]))
        today_str = datetime.now().strftime('%Y-%m-%d')
        default_target = alpha_wallets[0].get('target_vol', 32800)

        recent_dates = sorted({tx.get('date','') for w in alpha_wallets for tx in w.get('tx_log',[])}, reverse=True)[:7]
        day_badges_html = ''
        for d in recent_dates:
            dv = sum(tx.get('vol',0) for w in alpha_wallets for tx in w.get('tx_log',[]) if tx.get('date','')==d)
            ok = dv >= 32800
            bg = 'rgba(34,197,94,0.15)' if ok else 'rgba(234,85,67,0.15)'
            fg = '#22c55e' if ok else '#ea5343'
            day_badges_html += "<span style='background:{};border-radius:6px;padding:2px 8px;font-size:11px;font-weight:600;margin-right:4px;color:{}'>{} {}</span>".format(bg, fg, d[-5:], '✅' if ok else '⚠️'+str(int(dv)))
        day_badges_section = ("<div style='font-size:11px;color:var(--text2);margin-bottom:12px'>近7天: " + day_badges_html + "</div>") if day_badges_html else ''

        alpha_section = (
            "<div class='section'>" +
            "<div class='section-head'>📊 BinanceAlpha 多钱包交易记录</div>" +
            "<div style='display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin-bottom:12px'>" +
            "<div style='background:var(--bg2);border:1px solid var(--border);border-radius:10px;padding:10px;text-align:center'><div style='font-size:10px;color:var(--text3)'>钱包数</div><div style='font-size:22px;font-weight:800;color:var(--blue)'>" + str(len(alpha_wallets)) + "</div></div>" +
            "<div style='background:var(--bg2);border:1px solid var(--border);border-radius:10px;padding:10px;text-align:center'><div style='font-size:10px;color:var(--text3)'>累计交易量</div><div style='font-size:22px;font-weight:800;color:var(--blue)'>" + str(int(grand_vol)) + " U</div></div>" +
            "<div style='background:var(--bg2);border:1px solid var(--border);border-radius:10px;padding:10px;text-align:center'><div style='font-size:10px;color:var(--text3)'>累计磨损</div><div style='font-size:22px;font-weight:800;color:var(--red)'>" + "{:.2f}".format(grand_fee) + " U</div></div>" +
            "<div style='background:var(--bg2);border:1px solid var(--border);border-radius:10px;padding:10px;text-align:center'><div style='font-size:10px;color:var(--text3)'>累计积分</div><div style='font-size:22px;font-weight:800;color:#22c55e'>" + str(grand_pts) + "</div></div>" +
            "<div style='background:var(--bg2);border:1px solid var(--border);border-radius:10px;padding:10px;text-align:center'><div style='font-size:10px;color:var(--text3)'>效率</div><div style='font-size:22px;font-weight:800;color:var(--yellow)'>" + "{:.3f}".format(grand_fee/max(grand_pts,1)) + " U/分</div></div>" +
            "</div>" +
            day_badges_section +
            "<div style='background:var(--bg2);border:1px solid var(--border);border-radius:12px;padding:16px;margin-bottom:12px'>" +
            "<div style='display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:14px'>" +
            "<div style='font-size:12px;font-weight:700;white-space:nowrap'>👛 切换钱包</div>" +
            "<select id='wal_sel' onchange='switchWallet(this.value)' style='font-size:13px;border:1px solid var(--border);border-radius:8px;background:var(--bg3);color:var(--text);padding:6px 10px;min-width:140px'>" + wallet_options + "</select>" +
            "<div id='wal_stats' style='font-size:12px;color:var(--text2);margin-left:8px'></div>" +
            "<button onclick='delWallet()' style='margin-left:auto;background:none;border:1px solid var(--red);color:var(--red);cursor:pointer;font-size:12px;padding:4px 8px;border-radius:6px'>🗑 删除钱包</button>" +
            "</div>" +
            "<div style='background:var(--bg3);border-radius:8px;padding:12px;margin-bottom:14px'>" +
            "<div style='font-size:12px;font-weight:700;margin-bottom:8px'>➕ 记录交易</div>" +
            "<form method='post' action='/proj/505baa0d/add-tx' style='display:flex;gap:6px;flex-wrap:wrap;align-items:center'>" +
            "<input type='hidden' id='form_wallet_id' name='wallet_id' value='" + alpha_wallets[0]['id'] + "'>" +
            "<input name='tx_date' type='date' class='form-control' style='font-size:12px;width:130px' value='" + today_str + "' required>" +
            "<input name='tx_vol' type='number' step='1' min='0' class='form-control' style='font-size:12px;width:100px' placeholder='交易量U' required>" +
            "<input name='balance_before' type='number' step='0.01' min='0' class='form-control' style='font-size:12px;width:80px' placeholder='刷前余额U' required oninput='calcFee()'>" +
            "<input name='balance_after' type='number' step='0.01' min='0' class='form-control' style='font-size:12px;width:80px' placeholder='刷后余额U' required oninput='calcFee()'>" +
            "<span id='fee_display' style='font-size:12px;color:var(--red);min-width:60px;text-align:center'></span>" +
            "<input type='hidden' name='tx_fee' id='tx_fee_hidden'>" +
            "<input name='tx_pts' type='number' step='1' min='0' class='form-control' style='font-size:12px;width:60px' placeholder='积分' required>" +
            "<input name='tx_note' type='text' class='form-control' style='font-size:12px;width:130px' placeholder='备注'>" +
            "<button type='submit' class='btn btn-primary'>💾 记录</button></form></div>" +
            "<div><div style='font-size:12px;font-weight:700;margin-bottom:8px'>📋 交易记录</div>" +
            "<div style='overflow-x:auto;max-height:420px;overflow-y:auto'><table class='data-table' style='font-size:11px'>" +
            "<thead style='position:sticky;top:0;z-index:1'><tr><th>日期</th><th>交易量</th><th>磨损</th><th>积分</th><th>达标</th><th>备注</th><th></th></tr></thead>" +
            "<tbody id='tx_body'>" +
            "</tbody></table></div></div></div>" +
            "<div style='background:var(--bg2);border:1px dashed var(--border);border-radius:10px;padding:14px;text-align:center'>" +
            "<div style='font-size:12px;color:var(--text3);margin-bottom:8px'>➕ 添加新钱包</div>" +
            "<form method='post' action='/proj/505baa0d/add-wallet' style='display:flex;gap:6px;justify-content:center;flex-wrap:wrap'>" +
            "<input name='wallet_name' type='text' class='form-control' style='font-size:12px;width:120px' placeholder='钱包名称' required>" +
            "<input name='target_vol' type='number' step='1' class='form-control' style='font-size:12px;width:100px' placeholder='目标量U' value='32800'>" +
            "<input name='target_pts' type='number' step='1' class='form-control' style='font-size:12px;width:70px' placeholder='目标积分' value='17'>" +
            "<button type='submit' class='btn btn-primary'>添加钱包</button></form></div></div>"
        )

                # Load pre-built alpha HTML (regenerate via /tmp/gen_alpha_final.py if needed)
        alpha_html_path = '/tmp/alpha_final.html'
        if os.path.exists(alpha_html_path):
            alpha_section = open(alpha_html_path, 'r', encoding='utf-8').read()
        else:
            alpha_section = '<div style="color:var(--red);padding:20px">Alpha HTML 模板未生成，请联系管理员</div>'
        content_parts.append(alpha_section)


        task["next_due"] = nd
        task["next_run"] = nd
        # Update task note with latest data
        if trading_vol or fee:
            task["note"] = "交易量:" + vol_clean + "U 磨损:" + fee_clean + "U" + (" 积分:" + points if points else "")
        save_json(PROJECTS_FILE, data)
        return redirect("/proj/detail/" + proj_id)

    # GET: show form
    prev_note = task.get("note", "")
    content = (
        "<div class='page-header' style='display:block'>"
        "<a href='/proj/detail/" + proj_id + "' class='back-btn'>← 返回" + proj_name + "</a>"
        "<div style='font-size:20px;font-weight:700;margin-top:10px'>📊 登记交易记录</div>"
        "<div style='font-size:13px;color:var(--text3);margin-top:4px'>" + proj_name + " - " + task.get("name", "") + "</div>"
        "</div>"
        "<div class='section'>"
        "<form method='post'>"
        "<div style='padding:16px'>"
        "<div class='form-group'><label>交易量 (U)</label><input name='trading_vol' class='form-control' placeholder='例如：33000' required></div>"
        "<div class='form-group'><label>磨损/手续费 (U)</label><input name='fee' class='form-control' placeholder='例如：1.7'></div>"
        "<div class='form-group'><label>获得积分</label><input name='points' class='form-control' placeholder='自动计算或手动输入'></div>"
        "<div class='form-group'><label>备注</label><input name='note' class='form-control' placeholder='可选备注'></div>"
        "<div style='margin-top:16px'>"
        "<button type='submit' class='btn btn-primary'>✅ 确认登记</button>"
        " <a href='/proj/detail/" + proj_id + "' class='btn'>取消</a>"
        "</div>"
        "</div>"
        "</form></div>"
    )
    return render_template_string(LAYOUT, section="projects", now=now(), content=content,
        standx_ok=0, standx_total=0, ip_total=0, proj_total=len(projects))



def proj_wallet_add(proj_id):
    data = load_json(PROJECTS_FILE)
    projects = data.get("projects", [])
    proj = next((p for p in projects if p["id"] == proj_id), None)
    if not proj:
        return redirect("/?s=projects")
    wallet_addr = request.form.get("wallet_addr", "").strip()
    wallet_note = request.form.get("wallet_note", "").strip()
    wallet_invest = request.form.get("wallet_invest", "").strip()
    if wallet_addr:
        # Ensure wallets is a list of dicts
        if "wallets" not in proj:
            proj["wallets"] = []
        # Convert old string format to dict if needed
        new_wallet = {
            "address": wallet_addr,
            "note": wallet_note,
            "invest": float(wallet_invest) if wallet_invest and wallet_invest.replace(".","",1).isdigit() else 0
        }
        proj["wallets"].append(new_wallet)
        # Update project invest total
        def w_invest(w): return w.get("invest", 0) if isinstance(w, dict) else 0
        all_invest = sum(w_invest(w) for w in proj["wallets"])
        proj["invest"] = str(all_invest)
        save_json(PROJECTS_FILE, data)
    return redirect("/proj/detail/" + proj_id)


def proj_wallet_edit(proj_id):
    data = load_json(PROJECTS_FILE)
    projects = data.get("projects", [])
    proj = next((p for p in projects if p["id"] == proj_id), None)
    if not proj:
        return redirect("/?s=projects")
    wallet_addr = request.form.get("wallet_addr", "").strip()
    wallet_note = request.form.get("wallet_note", "").strip()
    wallet_invest = request.form.get("wallet_invest", "").strip()
    if wallet_addr and "wallets" in proj:
        def w_addr(w): return w.get("address","") if isinstance(w,dict) else str(w)
        for w in proj["wallets"]:
            if w_addr(w) == wallet_addr:
                if isinstance(w, dict):
                    w["note"] = wallet_note
                    w["invest"] = float(wallet_invest) if wallet_invest and wallet_invest.replace(".","",1).isdigit() else 0
                break
        all_invest = sum(w.get("invest",0) if isinstance(w,dict) else 0 for w in proj["wallets"])
        proj["invest"] = str(all_invest)
        save_json(PROJECTS_FILE, data)
    return redirect("/proj/detail/" + proj_id)

def proj_wallet_del(proj_id):
    data = load_json(PROJECTS_FILE)
    projects = data.get("projects", [])
    proj = next((p for p in projects if p["id"] == proj_id), None)
    if not proj:
        return redirect("/?s=projects")
    wallet_addr = request.form.get("wallet_addr", "").strip()
    if wallet_addr and "wallets" in proj:
        proj["wallets"] = [w for w in proj["wallets"] if (w.get("address","") if isinstance(w,dict) else str(w)) != wallet_addr]
        def w_invest(w): return w.get("invest", 0) if isinstance(w, dict) else 0
        all_invest = sum(w_invest(w) for w in proj["wallets"])
        proj["invest"] = str(all_invest)
        save_json(PROJECTS_FILE, data)
    return redirect("/proj/detail/" + proj_id)

def proj_wallet_balance(proj_id):
    data = load_json(PROJECTS_FILE)
    projects = data.get("projects", [])
    proj = next((p for p in projects if p["id"] == proj_id), None)
    if not proj:
        return redirect("/dashboard")
    wallet_addr = request.form.get("wallet_addr", "").strip()
    balance_str = request.form.get("balance", "").strip()
    if wallet_addr and balance_str:
        try:
            new_balance = float(balance_str)
        except:
            new_balance = 0.0
        for w in proj.get("wallets", []):
            if isinstance(w, dict) and w.get("address", "") == wallet_addr:
                w["balance"] = new_balance
                break
        save_json(PROJECTS_FILE, data)
    return redirect("/dashboard")

def dashboard_income():
    data = load_json(PROJECTS_FILE)
    source = request.form.get("source", "").strip()
    amount_str = request.form.get("amount", "").strip()
    proj_id = request.form.get("proj_id", "").strip()
    note = request.form.get("note", "").strip()
    try:
        amount = float(amount_str)
    except:
        amount = 0.0
    if amount > 0 and source:
        if "income_log" not in data:
            data["income_log"] = []
        income_entry = {"source": source, "amount": amount, "proj_id": proj_id, "note": note}
        data["income_log"].insert(0, income_entry)
        # Also track per-project extra earn
        if "extra_earn" not in data:
            data["extra_earn"] = {}
        if proj_id and proj_id != "__other__":
            data["extra_earn"][proj_id] = data["extra_earn"].get(proj_id, 0) + amount
        elif proj_id == "__other__":
            data["extra_earn"]["__other__"] = data["extra_earn"].get("__other__", 0) + amount
        save_json(PROJECTS_FILE, data)
    return redirect("/dashboard")

# ── PredictFun 仓位操作 ─────────────────────────────────

def predictfun_add_op():
    """处理快速挂单表单"""
    from flask import request, redirect
    market     = request.form.get("market","").strip()
    wallet_name= request.form.get("wallet_name","").strip()
    strategy   = request.form.get("strategy","").strip()
    mid        = request.form.get("mid","").strip()
    amount     = request.form.get("amount","").strip()
    note       = request.form.get("note","").strip()

    if not market or not amount:
        return redirect("/proj/detail/predictfun-001")

    try:
        data = load_json(PROJECTS_FILE)
        from datetime import date
        today = date.today().isoformat()

        # 找到对应钱包
        for proj in data.get("projects",[]):
            if proj.get("id") != "predictfun-001": continue
            pw_list = proj.get("predict_wallets",[])
            for w in pw_list:
                if w.get("name","") == wallet_name:
                    ops = w.get("ops") or []
                    # 构建note（含mid和策略）
                    note_full = f"mid={mid} | {strategy}" + (f" | {note}" if note else "")
                    ops.append({
                        "date":      today,
                        "market":    market,
                        "action":    "挂单",
                        "strategy":  strategy,
                        "amount":    float(amount),
                        "pnl":       0,
                        "note":      note_full,
                    })
                    w["ops"] = ops
                    save_json(PROJECTS_FILE, data)
                    break
            break
    except Exception as e:
        print(f"predictfun_add_op error: {e}")

    return redirect("/proj/detail/predictfun-001")


def predictfun_settle():
    """结算/平仓一个仓位"""
    from flask import request, redirect
    op_id   = request.args.get("id","").strip()
    pnl_val = request.args.get("pnl","0").strip()
    action  = request.args.get("action","settle")

    try:
        data = load_json(PROJECTS_FILE)
        for proj in data.get("projects",[]):
            if proj.get("id") != "predictfun-001": continue
            for w in proj.get("predict_wallets",[]):
                ops = w.get("ops") or []
                for op in ops:
                    key = op.get("date","") + "-" + op.get("market","")[:10]
                    if key == op_id:
                        op["action"] = "平仓"
                        try: op["pnl"] = float(pnl_val)
                        except: pass
                        w["ops"] = ops
                        save_json(PROJECTS_FILE, data)
                        break
            break
    except Exception as e:
        print(f"predictfun_settle error: {e}")

    nxt = request.args.get("next","/proj/detail/predictfun-001")
    return redirect(nxt)


# ── BinanceAlpha 多钱包交易操作 ─────────────────────────────────

def alpha_add_tx():
    """添加交易记录"""
    from flask import request, redirect
    wallet_id = request.form.get("wallet_id","").strip()
    tx_date   = request.form.get("tx_date","").strip()
    tx_vol    = request.form.get("tx_vol","").strip()
    tx_fee   = request.form.get("tx_fee","").strip()
    tx_pts    = request.form.get("tx_pts","").strip()
    tx_note   = request.form.get("tx_note","").strip()
    balance_before = request.form.get("balance_before","").strip()
    balance_after  = request.form.get("balance_after","").strip()

    # 如果 JS 自动计算的 tx_fee 为空，手动计算磨损 = 刷前余额 - 刷后余额
    if not tx_fee and balance_before and balance_after:
        try:
            tx_fee = str(max(0.0, float(balance_before) - float(balance_after)))
        except:
            pass

    if not wallet_id or not tx_date or not tx_vol:
        return redirect("/proj/detail/505baa0d")

    try:
        data = load_json(PROJECTS_FILE)
        for proj in data.get("projects",[]):
            if proj.get("id") != "505baa0d": continue
            alpha_wallets = proj.get("alpha_wallets",[])
            for w in alpha_wallets:
                if w.get("id","") == wallet_id:
                    tx_log = w.get("tx_log") or []
                    tx_log.append({
                        "date": tx_date,
                        "vol":  int(float(tx_vol)),
                        "fee":  float(tx_fee),
                        "pts":  int(float(tx_pts)),
                        "note": tx_note,
                    })
                    w["tx_log"] = tx_log
                    save_json(PROJECTS_FILE, data)
                    break
            break
    except Exception as e:
        print(f"alpha_add_tx error: {e}")

    return redirect("/proj/detail/505baa0d")


def alpha_del_tx():
    """删除一条交易记录"""
    from flask import request, redirect
    wallet_id = request.form.get("wallet_id","").strip()
    tx_date   = request.form.get("tx_date","").strip()

    try:
        data = load_json(PROJECTS_FILE)
        for proj in data.get("projects",[]):
            if proj.get("id") != "505baa0d": continue
            for w in proj.get("alpha_wallets",[]):
                if w.get("id","") == wallet_id:
                    tx_log = w.get("tx_log") or []
                    w["tx_log"] = [t for t in tx_log if t.get("date","") != tx_date]
                    save_json(PROJECTS_FILE, data)
                    break
            break
    except Exception as e:
        print(f"alpha_del_tx error: {e}")

    return redirect("/proj/detail/505baa0d")


def alpha_add_wallet():
    """添加新钱包"""
    from flask import request, redirect
    wallet_name = request.form.get("wallet_name","").strip()
    target_vol  = request.form.get("target_vol","32800").strip()
    target_pts  = request.form.get("target_pts","17").strip()

    if not wallet_name:
        return redirect("/proj/detail/505baa0d")

    try:
        data = load_json(PROJECTS_FILE)
        for proj in data.get("projects",[]):
            if proj.get("id") != "505baa0d": continue
            alpha_wallets = proj.get("alpha_wallets",[])
            new_id = "w" + str(int(time.time()*1000) % 100000)
            alpha_wallets.append({
                "id":         new_id,
                "name":      wallet_name,
                "target_vol": int(float(target_vol)),
                "target_pts": int(float(target_pts)),
                "tx_log":    [],
            })
            proj["alpha_wallets"] = alpha_wallets
            save_json(PROJECTS_FILE, data)
            break
    except Exception as e:
        print(f"alpha_add_wallet error: {e}")

    return redirect("/proj/detail/505baa0d")


def dashboard_income_del():
    data = load_json(PROJECTS_FILE)
    idx_str = request.form.get("idx", "").strip()
    try:
        idx = int(idx_str)
        income_log = data.get("income_log", [])
        if 0 <= idx < len(income_log):
            entry = income_log.pop(idx)
            # Decrement extra_earn
            proj_id = entry.get("proj_id", "")
            amount = float(entry.get("amount", 0))
            if proj_id and proj_id != "__other__":
                data["extra_earn"][proj_id] = max(0, data["extra_earn"].get(proj_id, 0) - amount)
            elif proj_id == "__other__":
                data["extra_earn"]["__other__"] = max(0, data["extra_earn"].get("__other__", 0) - amount)
            save_json(PROJECTS_FILE, data)
    except:
        pass
    return redirect("/dashboard")
    # ── BinanceAlpha 下拉框切换多钱包 ────────────────────────
    # Load pre-built alpha HTML (regenerate via /tmp/gen_alpha_final.py)
    alpha_html_path = '/tmp/alpha_final.html'
    if os.path.exists(alpha_html_path):
        alpha_section = open(alpha_html_path, 'r', encoding='utf-8').read()
    else:
        alpha_section = '<div style="color:var(--red);padding:20px">Alpha HTML 模板未生成</div>'
    content_parts.append(alpha_section)
redirect, render_template_string, make_response
from datetime import datetime, timedelta
import json
from utils import load_json, save_json, today_str, now, now_str, get_standx_data, PROJECTS_FILE, get_all_tasks, is_due_within
from templates import LAYOUT


def _next_month(date_str):
    d = datetime.strptime(date_str, "%Y-%m-%d")
    month = d.month + 1
    year = d.year
    if month > 12:
        month = 1
        year += 1
    last_day = datetime(year, month, 1) - timedelta(days=1)
    target_day = min(d.day, last_day.day)
    return d.replace(year=year, month=month, day=target_day).strftime("%Y-%m-%d")


def proj_detail_page(proj_id):
    data = load_json(PROJECTS_FILE)
    projects = data.get("projects", [])
    all_tasks = data.get("tasks", [])
    proj = next((p for p in projects if p["id"] == proj_id), None)
    if not proj:
        return redirect("/?s=projects")
    today = today_str()
    proj_tasks = [t for t in all_tasks if t.get("project_id") == proj_id]
    desc = proj.get("desc","")
    notes = proj.get("notes","")
    risk = proj.get("risk","")
    tags = proj.get("tags",[])
    chain = proj.get("chain","")
    ptype = proj.get("type","")
    stars = int(proj.get("stars", 3))
    invest = float(proj.get("invest", 0) or 0)
    earn = float(proj.get("earn", 0) or 0)
    gas = float(proj.get("gas_cost", 0) or 0)
    roi = (earn - invest) / max(invest, 1) * 100 if invest > 0 else 0
    wallets = proj.get("wallets", [])
    chain_icon = {"BNB Chain":"🔶","Solana":"☀️","Base":"🔵","Fogo":"🔥","Aptos":"🟣","Miden":"⚪","Sui":"🔷"}.get(chain,"🔗")
    p_tasks_done = [t for t in proj_tasks if t.get("last_done","").startswith(today)]
    done_count = len(p_tasks_done)
    total_count = len(proj_tasks)
    pct = int(done_count / max(total_count,1) * 100) if total_count > 0 else 0
    ot_done = sum(1 for t in proj_tasks if t.get("freq") == "one-time" and t.get("last_done"))
    ot_total = sum(1 for t in proj_tasks if t.get("freq") == "one-time")
    today_proj_tasks = [t for t in proj_tasks if t.get("next_run", "") != "" and t.get("next_run", "") <= today and t.get("freq") in ("daily", "weekly", "monthly") and t.get("last_done", "")[:10] != today]
    today_proj_done = [t for t in proj_tasks if t.get("last_done", "").startswith(today) and t.get("freq") in ("daily", "weekly", "monthly")]
    tags_html = "".join(["<span style='background:rgba(59,130,246,0.15);color:#60a5fa;border-radius:6px;padding:2px 8px;font-size:11px;margin-right:6px'>" + tag + "</span>" for tag in tags])
    risk_color = {"低":"#22c55e","中":"#f59e0b","高":"#ef4444"}.get(risk,"#9ca3af")
    risk_html = "<span style='background:rgba(0,0,0,0.2);color:" + risk_color + ";border-radius:4px;padding:1px 6px;font-size:10px;margin-left:6px'>⚠️ " + risk + "风险</span>" if risk else ""
    stars_html = "<span style='color:#f0b90b;margin-left:8px'>" + "★" * stars + "☆" * (5 - stars) + "</span>"
    roi_color = "#22c55e" if roi >= 0 else "#ef4444"
    desc_html = "<div style='background:var(--bg2);border:1px solid var(--border);border-radius:8px;padding:12px;margin-bottom:12px;font-size:13px;line-height:1.6'>" + desc + "</div>" if desc else ""
    notes_html = "<div style='background:rgba(245,158,11,0.08);border:1px solid rgba(245,158,11,0.2);border-radius:8px;padding:12px;margin-bottom:12px;font-size:12px;line-height:1.7;color:#f0b90b;white-space:pre-wrap'>" + notes + "</div>" if notes else ""
    rows = []
    for t in sorted(proj_tasks, key=lambda x: (x.get("freq",""), x.get("name",""))):
        done = t.get("last_done","").startswith(today)
        freq_map = {"daily":"📅每日","weekly":"📆每周","monthly":"📆每月","one-time":"⭐一次性"}
        freq_label = freq_map.get(t.get("freq"),"")
        last_done = t.get("last_done","")[:10] if t.get("last_done") else "从未"
        next_run = t.get("next_run","")
        task_note = t.get("note","")
        done_cls = "btn-success" if not done else "btn-secondary"
        done_attr = "disabled" if done else ""
        checkbox = "✅" if done else "⬜"
        note_html = "<div style='font-size:10px;color:var(--text3)'>" + task_note + "</div>" if task_note else ""
        rows.append("<tr" + (" style='opacity:0.5'" if done else "") + "><td>" + checkbox + "</td><td>" + t.get("name","") + note_html + "</td><td>" + freq_label + "</td><td>" + last_done + "</td><td>" + next_run + "</td><td><a href='/task/" + t["id"] + "/edit?next=/proj/detail/" + proj_id + "' class='btn btn-sm'>✏️ 编辑</a> <a href='/task/" + t["id"] + "/done?next=/proj/detail/" + proj_id + "' class='btn btn-sm " + done_cls + "' " + done_attr + ">完成</a></td></tr>")
    pending_rows = ""
    for t in today_proj_tasks[:15]:
        freq_map2 = {"daily":"📅 每日","weekly":"📆 每周","monthly":"📆 每月","one-time":"⭐ 一次性"}
        freq_tag = "<span style='font-size:10px;color:var(--text3);margin-left:4px'>" + freq_map2.get(t.get("freq",""),"") + "</span>"
        next_run = t.get("next_run","")
        next_str = " <span style='font-size:10px;color:var(--text3)'>下次:" + next_run + "</span>" if next_run else ""
        task_note = "<div style='font-size:10px;color:var(--text3)'>" + t.get("note","") + "</div>" if t.get("note") else ""
        done_href = "/log-trade/" + t["id"] if t["id"] == "task-ba-001" else "/task/" + t["id"] + "/done?next=/proj/detail/" + proj_id
        pending_rows += "<div class='task-item'><div class='t-name'>" + t.get("name","") + freq_tag + next_str + task_note + "</div><a href='" + done_href + "' class='btn btn-sm btn-success'>✅ 完成</a></div>"
    done_rows = ""
    for t in today_proj_done[:10]:
        task_note = "<div style='font-size:10px;color:var(--text3)'>" + t.get("note","") + "</div>" if t.get("note") else ""
        done_rows += "<div class='task-item' style='opacity:0.6'><div class='t-name done'>" + t.get("name","") + task_note + "</div><span style='font-size:12px;color:#22c55e'>✓ 已完成</span></div>"
    links = proj.get("links", {})
    links_html = ""
    if isinstance(links, dict):
        items = [(n,u) for n,u in links.items() if u]
    else:
        items = [('',u) for u in (links or [])]
    for name, url in items:
        short = url[:50]+"..." if len(url)>50 else url
        display = name + " →" if name else short
        links_html += "<a href='" + url + "' class='link-tag' target='_blank'>" + display + "</a>"
    links_section = "<div class='section'><div class='section-head'>🔗 链接</div><div style='padding:0 16px;display:flex;flex-direction:column;gap:6px'>" + links_html + "</div></div>" if links_html else ""
    # Wallet management with investment tracking (not for BinanceAlpha)
    wallets_html = ""
    total_wallet_invest = 0
    if wallets and proj_id != "505baa0d":
        for w in wallets:
            if isinstance(w, dict):
                addr = w.get("address","")
                note = w.get("note","")
                invest_val = w.get("invest", 0)
                total_wallet_invest += invest_val
            else:
                addr = str(w)
                note = ""
                invest_val = 0
            if len(addr) > 20:
                addr_short = addr[:12] + "..." + addr[-8:]
            else:
                addr_short = addr
            invest_str = " <span style='color:var(--blue)'>$" + str(invest_val) + "</span>" if invest_val else ""
            wallets_html += "<div class='wallet-card' style='background:var(--bg3);padding:10px 12px;border-radius:6px;font-size:12px;margin-bottom:6px'><div style='display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:6px'><div style='font-size:13px;font-weight:600;color:var(--text)'>" + note + "</div><div style='text-align:right'><div style='font-size:14px;font-weight:700;color:var(--blue)'>$" + str(invest_val) + "</div><div style='font-size:10px;color:var(--text3)'>投入</div></div></div><div style='font-family:monospace;font-size:10px;color:var(--text3);word-break:break-all;margin-bottom:8px;background:var(--bg);padding:4px 6px;border-radius:4px'>" + addr + "</div><div style='display:flex;gap:4px'><button type='button' onclick='toggleEdit(this)' class='btn btn-sm' style='padding:3px 8px;font-size:11px'>✏️ 编辑</button><form method='post' action='/proj/" + proj_id + "/wallet/del' style='display:inline'><input type='hidden' name='wallet_addr' value='" + addr.replace("'","&#39;") + "'><button type='submit' class='btn btn-sm btn-danger' style='padding:3px 8px;font-size:11px'>🗑️ 删除</button></form></div><div style='display:none;margin-top:8px;background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:10px' class='wallet-edit-form'><div style='font-size:11px;color:var(--text3);margin-bottom:8px'>✏️ 编辑钱包</div><form method='post' action='/proj/" + proj_id + "/wallet/edit'><input type='hidden' name='wallet_addr' value='" + addr.replace("'","&#39;") + "'><div class='form-group'><label style='font-size:11px;color:var(--text3)'>别名/备注</label><input name='wallet_note' class='form-control' style='font-size:12px' placeholder='例如：MPC1 - Big Five' value='" + note.replace("'","&#39;") + "'></div><div class='form-group'><label style='font-size:11px;color:var(--text3)'>投入金额 ($)</label><input name='wallet_invest' class='form-control' style='font-size:12px' placeholder='0' type='number' step='0.01' min='0' value='" + str(invest_val) + "'></div><div style='margin-top:8px'><button type='submit' class='btn btn-primary btn-sm'>💾 保存</button> <button type='button' onclick='toggleEdit(this)' class='btn btn-sm'>取消</button></div></form><hr style='margin:10px 0;border-color:var(--border)'><div style='font-size:11px;color:var(--text3);margin-bottom:6px'>⚠️ 删除后将无法恢复</div><form method='post' action='/proj/ + proj_id + /wallet/del' style='display:inline'><input type='hidden' name='wallet_addr' value=' + addr + '><input type='hidden' name='wallet_addr_orig' value=' + addr + '><button type='submit' class='btn btn-sm btn-danger' style='padding:3px 8px;font-size:11px'>🗑️ 删除钱包</button></form></div></div>"
        wallets_html += "<div style='border-top:1px solid var(--border);padding-top:8px;margin-top:4px;font-size:12px;color:var(--text2)'>💰 累计投入: <strong style='color:var(--blue)'>$" + str(total_wallet_invest) + "</strong></div>"
    add_wallet_form = ""
    if proj_id != "505baa0d":
        add_wallet_form = "<div style='border-top:1px solid var(--border);padding-top:10px;margin-top:8px'><div style='font-size:11px;color:var(--text3);margin-bottom:6px'>➕ 添加钱包</div><form method='post' action='/proj/" + proj_id + "/wallet/add'><input name='wallet_addr' class='form-control' style='margin-bottom:6px;font-size:12px' placeholder='钱包地址' required><input name='wallet_note' class='form-control' style='margin-bottom:6px;font-size:12px' placeholder='备注（如：Base Boosted 115U）'><div style='display:flex;gap:6px'><input name='wallet_invest' class='form-control' style='margin-bottom:6px;font-size:12px;width:100px' placeholder='投入金额$' type='number' step='0.01' min='0'><button type='submit' class='btn btn-primary btn-sm'>添加</button></div></form></div>"
    wallets_section = ""  # LP项目单独处理
    if proj_id == "xau-lp-001":
        # ===== LP 流动性仓位 =====
        lp_positions = proj.get("lp_positions", [])
        lp_open = [p for p in lp_positions if p.get("status") == "open"]
        lp_closed = [p for p in lp_positions if p.get("status") == "closed"]
        # LP仓位表格
        lp_rows_html = ""
        for p in lp_open:
            pair = p.get("token_pair", "")
            initial = p.get("lp_amount", 0)
            top_ups = p.get("top_ups", [])
            total_invested = initial + sum(t.get("amount", 0) for t in top_ups)
            current = p.get("current_balance", 0)
            fees = p.get("fees", 0)
            claimed_fees = p.get("claimed_fees", 0)
            pnl = (current + claimed_fees) - total_invested
            pnl_color = "#22c55e" if pnl >= 0 else "#ef4444"
            pnl_sign = "+" if pnl >= 0 else ""
            value_est = current  # 简化：LP token面值=本位币数量
            # 追加记录展示（小字显示）
            topup_details = ""
            pos_id_attr = p['id']
            if top_ups:
                detail_items = []
                for t in top_ups:
                    amt = t.get("amount", 0)
                    prefix = "+" if amt >= 0 else ""
                    color = "#ef4444" if amt < 0 else "var(--text3)"
                    detail_items.append("<div style='font-size:9px;color:{}'>  {}{:.2f} @ {}{}</div>".format(
                        color, prefix, t.get("amount",0), t.get("date",""),
                        " (" + t.get("note","") + ")" if t.get("note") else ""))
                topup_details = "<div style='margin-top:2px'>{}</div>".format("".join(detail_items))
            # 有追加时在代币对旁标出
            # 区分追加和减仓
            add_count = sum(1 for t in top_ups if t.get("amount", 0) > 0)
            red_count = sum(1 for t in top_ups if t.get("amount", 0) < 0)
            badge_parts = []
            if add_count:
                badge_parts.append("<span style='background:rgba(245,158,11,0.2);color:#f59e0b;border-radius:8px;padding:0 5px;font-size:9px'>{}次追加</span>".format(add_count))
            if red_count:
                badge_parts.append("<span style='background:rgba(239,68,68,0.2);color:#ef4444;border-radius:8px;padding:0 5px;font-size:9px'>{}次减仓</span>".format(red_count))
            topup_badge = " " + " ".join(badge_parts) if badge_parts else ""
            lp_rows_html += f"<tr>"
            lp_rows_html += f"<td style='font-weight:600'>{pair}{topup_badge}{topup_details}</td>"
            lp_rows_html += f"<td style='color:var(--blue)'>${initial:.2f}</td>"
            lp_rows_html += f"<td style='color:var(--blue)'>${total_invested:.2f}</td>"
            lp_rows_html += f"<td style='font-weight:600'>"
            lp_rows_html += f"<span id='bal-display-{pos_id_attr}'>${current:.2f}</span>"
            lp_rows_html += f" <button class='btn btn-sm' style='background:none;border:none;color:#60a5fa;font-size:11px;padding:0 2px;cursor:pointer' onclick=\"var d=document.getElementById('bal-display-{pos_id_attr}');var e=document.getElementById('bal-edit-{pos_id_attr}');var s=document.getElementById('bal-save-{pos_id_attr}');var c=document.getElementById('bal-cancel-{pos_id_attr}');d.style.display='none';e.style.display='inline-block';s.style.display='inline-block';c.style.display='inline-block';e.focus()\">✏️</button>"
            lp_rows_html += f"<input id='bal-edit-{pos_id_attr}' type='number' step='0.01' style='display:none;width:65px;font-size:11px;border:1px solid var(--blue);border-radius:4px;background:var(--bg3);color:var(--text);padding:2px 4px' value='{current:.2f}'>"
            lp_rows_html += f"<button id='bal-save-{pos_id_attr}' class='btn btn-sm' style='display:none;font-size:10px;padding:1px 6px;background:#22c55e;color:#fff' onclick=\"var val=document.getElementById('bal-edit-{pos_id_attr}').value;var fd=new FormData();fd.append('pos_id','{pos_id_attr}');fd.append('balance',val);fetch('/proj/lp/update-balance/{proj_id}',{{method:'POST',body:fd}}).then(function(r){{if(r.ok)location.reload();else alert('保存失败')}});\">💾</button>"
            lp_rows_html += f"<button id='bal-cancel-{pos_id_attr}' class='btn btn-sm' style='display:none;font-size:10px;padding:1px 6px' onclick=\"document.getElementById('bal-display-{pos_id_attr}').style.display='';document.getElementById('bal-edit-{pos_id_attr}').style.display='none';this.style.display='none';document.getElementById('bal-save-{pos_id_attr}').style.display='none'\">✕</button>"
            lp_rows_html += f"</td>"
            lp_rows_html += f"<td>${fees:.2f}</td>"
            lp_rows_html += f"<td style='color:var(--blue)'>${claimed_fees:.2f}</td>"
            pnl_pct = (pnl / total_invested * 100) if total_invested > 0 else 0
            pnl_pct_sign = "+" if pnl_pct >= 0 else ""
            lp_rows_html += f"<td style='color:{pnl_color};font-weight:600'>{pnl_sign}${pnl:.2f} ({pnl_pct_sign}{pnl_pct:.2f}%)</td>"
            # 格式化开仓时间
            raw_date = p.get('open_date', '')
            if 'T' in raw_date:
                display_date = raw_date.replace('T', ' ')
            else:
                display_date = raw_date
            duration_id = 'dur-' + p['id']
            lp_rows_html += f"<td>{display_date}</td>"
            lp_rows_html += f"<td id='{duration_id}' style='color:#e3b341;font-weight:500'>⏳ 计算中...</td>"
            lp_rows_html += f"<td style='color:#22c55e'>🟢 开仓中</td>"
            lp_rows_html += f"<td style='white-space:nowrap'>"
            # 追加按钮（弹出内联表单）
            lp_rows_html += f"<button class='btn btn-sm' style='background:#f59e0b;color:#fff;font-size:10px;padding:2px 6px;cursor:pointer' onclick=\"var f=document.getElementById('topup-form-{pos_id_attr}');f.style.display=f.style.display=='none'?'flex':'none'\">💵 追加</button> "
            lp_rows_html += f"<form method='post' action='/proj/lp/claim-fees/{proj_id}' style='display:inline-flex;gap:3px;align-items:center'>"
            lp_rows_html += f"<input type='hidden' name='pos_id' value='{p['id']}'>"
            lp_rows_html += f"<input type='number' step='0.01' name='claim_amount' class='form-control' style='width:45px;font-size:10px' placeholder='金额' required>"
            lp_rows_html += f"<button type='submit' class='btn btn-sm' style='background:#22c55e;color:#fff;font-size:10px;padding:2px 6px'>认领</button>"
            lp_rows_html += f"</form> "
            lp_rows_html += f"<form method='post' action='/proj/lp/close-position/{proj_id}' style='display:inline-flex;gap:3px;align-items:center'><input type='hidden' name='pos_id' value='{p['id']}'><input type='hidden' name='open_date' value='{p.get('open_date','')}'><input type='number' step='0.01' name='close_balance' class='form-control' style='width:65px;font-size:10px' placeholder='余额' required><input type='number' step='0.01' name='close_fees' class='form-control' style='width:55px;font-size:10px' placeholder='手续费' value='{fees:.2f}'><input type='datetime-local' name='close_date' class='form-control' style='width:145px;font-size:10px' value='{datetime.now().strftime('%Y-%m-%dT%H:%M')}'><button type='submit' class='btn btn-sm' style='background:#ef4444;color:#fff;font-size:10px;padding:2px 6px'>关闭</button></form></td>"
            lp_rows_html += f"</tr>"
            # 追加资金表单（隐藏行）
            lp_rows_html += f"<tr id='topup-form-{pos_id_attr}' style='display:none;background:rgba(245,158,11,0.05)'><td colspan='11' style='padding:8px 16px'>"
            lp_rows_html += f"<form method='post' action='/proj/lp/topup-position/{proj_id}' style='display:flex;gap:6px;align-items:center;flex-wrap:wrap'>"
            lp_rows_html += f"<input type='hidden' name='pos_id' value='{p['id']}'>"
            lp_rows_html += f"<span style='font-size:11px;color:#f59e0b;font-weight:600'>💵 追加资金</span>"
            lp_rows_html += f"<input type='number' step='0.01' name='topup_amount' class='form-control' style='width:80px;font-size:11px' placeholder='金额$' required>"
            lp_rows_html += f"<input type='datetime-local' name='topup_date' class='form-control' style='width:165px;font-size:11px' value='{datetime.now().strftime('%Y-%m-%dT%H:%M')}'>"
            lp_rows_html += f"<input name='topup_note' class='form-control' style='flex:1;min-width:80px;font-size:11px' placeholder='备注（可选）'>"
            lp_rows_html += f"<button type='submit' class='btn btn-sm' style='background:#f59e0b;color:#fff;font-size:11px;padding:3px 10px'>确认操作</button>"
            lp_rows_html += f"<button type='button' class='btn btn-sm' style='font-size:11px' onclick=\"document.getElementById('topup-form-{pos_id_attr}').style.display='none'\">取消</button>"
            lp_rows_html += f"</form></td></tr>"
        if not lp_rows_html:
            lp_rows_html = "<tr><td colspan='10' style='text-align:center;color:var(--text3);padding:20px'>暂无开仓仓位，点击下方添加</td></tr>"
        lp_add_form = f"""
        <div style='border-top:1px solid var(--border);padding-top:12px;margin-top:12px'>
            <div style='font-size:11px;color:var(--text3);margin-bottom:8px'>➕ 添加 LP 仓位</div>
            <form method='post' action='/proj/lp/add-position/{proj_id}' style='display:flex;flex-wrap:wrap;gap:6px;align-items:flex-end'>
                <div style='flex:1;min-width:120px'>
                    <label style='font-size:11px;color:var(--text3)'>代币对</label>
                    <input name='token_pair' class='form-control' style='font-size:12px' placeholder='例如：BASED/USDT' required>
                </div>
                <div>
                    <label style='font-size:11px;color:var(--text3)'>初始LP ($)</label>
                    <input name='lp_amount' type='number' step='0.01' class='form-control' style='width:90px;font-size:12px' placeholder='0' required>
                </div>
                <div>
                    <label style='font-size:11px;color:var(--text3)'>待领手续费</label>
                    <input name='fees' type='number' step='0.01' class='form-control' style='width:80px;font-size:12px' placeholder='0' value='0'>
                </div>
                <div>
                    <label style='font-size:11px;color:var(--text3)'>开仓时间</label>
                    <input name='open_date' type='datetime-local' class='form-control' style='width:175px;font-size:12px' value='{datetime.now().strftime('%Y-%m-%dT%H:%M')}'>
                </div>
                <div style='flex:1'>
                    <label style='font-size:11px;color:var(--text3)'>备注</label>
                    <input name='note' class='form-control' style='font-size:12px' placeholder='可选'>
                </div>
                <button type='submit' class='btn btn-primary' style='font-size:12px'>添加仓位</button>
            </form>
        </div>"""
        lp_add_form = f"""
        <div style='border-top:1px solid var(--border);padding-top:12px;margin-top:12px'>
            <div style='font-size:11px;color:var(--text3);margin-bottom:8px'>➕ 添加 LP 仓位</div>
            <form method='post' action='/proj/lp/add-position/{proj_id}' style='display:flex;flex-wrap:wrap;gap:6px;align-items:flex-end'>
                <div style='flex:1;min-width:120px'>
                    <label style='font-size:11px;color:var(--text3)'>代币对</label>
                    <input name='token_pair' class='form-control' style='font-size:12px' placeholder='例如：BASED/USDT' required>
                </div>
                <div>
                    <label style='font-size:11px;color:var(--text3)'>初始LP ($)</label>
                    <input name='lp_amount' type='number' step='0.01' class='form-control' style='width:90px;font-size:12px' placeholder='0' required>
                </div>
                <div>
                    <label style='font-size:11px;color:var(--text3)'>待领手续费</label>
                    <input name='fees' type='number' step='0.01' class='form-control' style='width:80px;font-size:12px' placeholder='0' value='0'>
                </div>
                <div>
                    <label style='font-size:11px;color:var(--text3)'>开仓时间</label>
                    <input name='open_date' type='datetime-local' class='form-control' style='width:175px;font-size:12px' value='{datetime.now().strftime('%Y-%m-%dT%H:%M')}'>
                </div>
                <div style='flex:1'>
                    <label style='font-size:11px;color:var(--text3)'>备注</label>
                    <input name='note' class='form-control' style='font-size:12px' placeholder='可选'>
                </div>
                <button type='submit' class='btn btn-primary' style='font-size:12px'>添加仓位</button>
            </form>
        </div>"""
        lp_section = f"""
        <div class='section'>
            <div class='section-head'>💦 LP 仓位 <span style='background:#22c55e;color:#fff;border-radius:10px;padding:1px 7px;font-size:11px'>{len(lp_open)} 开仓中</span></div>
            <div style='overflow-x:auto;padding:12px 16px'>
                <table class='data-table' style='font-size:12px'>
                    <thead><tr><th>代币对</th><th>初始LP</th><th>总投入</th><th>当前仓位价值</th><th>待领手续费</th><th>已认领手续费</th><th>浮动盈亏</th><th>开仓时间</th><th>持有时长</th><th>状态</th><th>操作</th></tr></thead>
                    <tbody>{lp_rows_html}</tbody>
                </table>
                {lp_add_form}
            </div>
        </div>"""
        # LP 操作历史 (with filter, collapsible per day)
        lp_ops = proj.get("lp_operations", [])
        op_rows = ""
        lp_op_count = len(lp_ops)
        from collections import defaultdict
        date_groups = defaultdict(list)
        for op in lp_ops:
            date_key = op.get('date', '')[:10]
            date_groups[date_key].append(op)
        sorted_dates = sorted(date_groups.keys(), reverse=True)
        for date_key in sorted_dates:
            day_ops = date_groups[date_key]
            day_pnl = sum(o.get('profit', 0) for o in day_ops if o.get('type') == 'close')
            day_pnl_color = "#22c55e" if day_pnl >= 0 else "#ef4444"
            day_sign = "+" if day_pnl >= 0 else ""
            op_rows += f"<tbody class='day-group'>"
            # Toggle header: subtotal row (always visible, click to expand)
            op_rows += f"<tr class='day-toggle' onclick='toggleDay(this)' style='background:var(--bg3);font-weight:600;border-top:2px solid var(--border);cursor:pointer'>"
            op_rows += f"<td style='font-weight:600;color:var(--text);font-size:12px'>📊 <span class='tog-icon' style='display:inline-block;width:14px;margin-right:2px;font-size:10px'>▶</span>{date_key} 小计 ({len(day_ops)}笔)</td>"
            op_rows += f"<td></td><td></td><td></td>"
            op_rows += f"<td style='color:{day_pnl_color}'>{day_sign}${day_pnl:.2f}</td>"
            op_rows += f"<td style='color:{day_pnl_color}'>¥{day_pnl * 6.8:.2f}</td>"
            op_rows += f"<td></td><td></td>"
            op_rows += f"</tr>"
            # Detail rows (hidden by default)
            for op in day_ops:
                pnl_val = op.get("profit", 0)
                pnl_color = "#22c55e" if pnl_val >= 0 else "#ef4444"
                pnl_sign = "+" if pnl_val >= 0 else ""
                op_type = op.get("type", "")
                op_type_map = {"open": ("🟢 开仓", "#22c55e"), "topup": ("💵 追加", "#f59e0b"), "reduce": ("🔽 减仓", "#ef4444"), "claim": ("🟡 认领", "#f59e0b"), "close": ("🔴 关闭", "#ef4444")}
                op_type_icon, op_type_color = op_type_map.get(op_type, ("⚪ " + op_type, "#9ca3af"))
                pnl_extra = " (计入浮动盈亏)" if op_type == "claim" else ""
                op_rows += f"<tr class='day-detail' data-optype='{op_type}' style='display:none'>"
                op_rows += f"<td>{op.get('date', '')}</td>"
                op_rows += f"<td style='color:{op_type_color};font-weight:600'>{op_type_icon}</td>"
                op_rows += f"<td style='font-weight:600'>{op.get('token_pair','')}</td>"
                princ = op.get('principal', 0)
                princ_color = '#ef4444' if princ < 0 else 'var(--text)'
                op_rows += f"<td style='color:{princ_color}'>${princ:.2f}</td>"
                op_rows += f"<td style='color:{pnl_color};font-weight:600'>{pnl_sign}${pnl_val:.2f}{pnl_extra}</td>"
                op_rows += f"<td style='color:{pnl_color};font-weight:600'>¥{pnl_val * 6.8:.2f}</td>"
                op_rows += f"<td>{op.get('duration','')}</td>"
                op_rows += f"<td style='font-size:11px;color:var(--text3)'>{op.get('note','')}</td>"
                op_rows += f"</tr>"
            op_rows += f"</tbody>"
        if not op_rows:
            op_rows = "<tbody><tr><td colspan='8' style='text-align:center;color:var(--text3);padding:16px'>暂无操作记录</td></tr></tbody>"
        total_invest = sum(op.get('principal',0) for op in lp_ops if op.get('type') in ('open','topup','reduce'))
        total_pnl = sum(op.get('profit',0) for op in lp_ops)
        pnl_cls = '#22c55e' if total_pnl >= 0 else '#ef4444'
        op_summary = f"<div style='display:flex;gap:16px;padding:10px 16px;background:var(--bg3);border-radius:8px;margin-bottom:10px;font-size:12px;flex-wrap:wrap'><div>累计投入: <strong style='color:var(--blue)'>${total_invest:.2f}</strong></div><div>累计收益: <strong style='color:{pnl_cls}'>{'+' if total_pnl>=0 else ''}${total_pnl:.2f}</strong></div><div>操作次数: <strong>{len(lp_ops)}</strong></div></div>"
        filter_btns = f"""

        <div style='padding:0 16px 8px;display:flex;gap:6px'>
            <button class='lp-filter-btn' data-optype='all' onclick="filterLpOps('all',this)" style='padding:4px 12px;border:1px solid var(--border);border-radius:6px;background:var(--blue);color:#fff;font-size:11px;cursor:pointer'>全部</button>
            <button class='lp-filter-btn' data-optype='open' onclick="filterLpOps('open',this)" style='padding:4px 12px;border:1px solid var(--border);border-radius:6px;background:var(--bg3);color:var(--text2);font-size:11px;cursor:pointer'>🟢 开仓</button>
            <button class='lp-filter-btn' data-optype='claim' onclick="filterLpOps('claim',this)" style='padding:4px 12px;border:1px solid var(--border);border-radius:6px;background:var(--bg3);color:var(--text2);font-size:11px;cursor:pointer'>🟡 认领</button>
            <button class='lp-filter-btn' data-optype='topup' onclick="filterLpOps('topup',this)" style='padding:4px 12px;border:1px solid var(--border);border-radius:6px;background:var(--bg3);color:var(--text2);font-size:11px;cursor:pointer'>💵 追加</button>
            <button class='lp-filter-btn' data-optype='reduce' onclick="filterLpOps('reduce',this)" style='padding:4px 12px;border:1px solid var(--border);border-radius:6px;background:var(--bg3);color:var(--text2);font-size:11px;cursor:pointer'>🔽 减仓</button>
            <button class='lp-filter-btn' data-optype='close' onclick="filterLpOps('close',this)" style='padding:4px 12px;border:1px solid var(--border);border-radius:6px;background:var(--bg3);color:var(--text2);font-size:11px;cursor:pointer'>🔴 关闭</button>
        </div>
        <script>
        function toggleDay(el) {{
            var group = el.closest('.day-group');
            if (!group) return;
            var details = group.querySelectorAll('.day-detail');
            if (!details.length) return;
            var icon = el.querySelector('.tog-icon');
            var isNowHidden = details[0].style.display === 'none';
            details.forEach(function(d) {{
                d.style.display = isNowHidden ? 'table-row' : 'none';
            }});
            if (icon) icon.textContent = isNowHidden ? '▼' : '▶';
        }}
        function filterLpOps(type, btn) {{
            var groups = document.querySelectorAll('#lp-op-table .day-group');
            groups.forEach(function(g) {{
                var details = g.querySelectorAll('.day-detail');
                var hasMatch = false;
                details.forEach(function(d) {{
                    if(type === 'all' || d.getAttribute('data-optype') === type) {{
                        d.style.display = 'table-row';
                        hasMatch = true;
                    }} else {{
                        d.style.display = 'none';
                    }}
                }});
                // Show group only if it has matching rows
                g.style.display = hasMatch ? '' : 'none';
                // Update toggle icon
                var toggle = g.querySelector('.day-toggle');
                var icon = toggle && toggle.querySelector('.tog-icon');
                if (icon) {{ icon.textContent = (type === 'all') ? '▶' : (hasMatch ? '▼' : '▶'); }}
            }});
            document.querySelectorAll('.lp-filter-btn').forEach(function(b) {{
                b.style.background = 'var(--bg3)';
                b.style.color = 'var(--text2)';
            }});
            btn.style.background = 'var(--blue)';
            btn.style.color = '#fff';
        }}
        </script>"""
        op_section = f"""
    <div style='display:flex;gap:16px;align-items:flex-start;margin-bottom:16px'>

      <!-- 左栏：明细表 -->
      <div style='flex:1;min-width:0'>
        <div class='section'>
            <div class='section-head'>📊 LP 操作历史 <span class='badge'>{len(lp_ops)}</span></div>
                        {filter_btns}
            <div style='overflow-x:auto;overflow-y:auto;max-height:840px;padding:0 12px 12px'>
                <table id='lp-op-table' class='data-table' style='font-size:11px'>
                    <thead><tr><th>日期</th><th>类型</th><th>代币对</th><th>本金</th><th>收益(USD)</th><th>收益(CNY)</th><th>时长</th><th>备注</th></tr></thead>
                    <tbody>{op_rows}</tbody>
                </table>
            </div>
        </div>
      </div>

      <!-- 右栏：可视化看板 -->
      <div style='width:520px;flex-shrink:0;display:flex;flex-direction:column;gap:14px'>
        <div id='lp-viz-panel'>
          <div style='text-align:center;color:var(--text3);padding:60px 0;font-size:12px'>⏳ 加载可视化组件...</div>
        </div>
      </div>

    </div>

    <script>
    // ── 构建每日盈亏数据 ──
    (function() {{
      var __rawOps = {json.dumps(proj.get('lp_operations',[]))};
      if (!__rawOps.length) return;

      var CNY_RATE = 6.8;
      var dailyPnl = {{}};
      var allDateKeys = [];
      for (var i = 0; i < __rawOps.length; i++) {{
        var op = __rawOps[i];
        var dateKey = op.date.substring(0, 10); // group by date only
        if (op.type === 'close') {{
          dailyPnl[dateKey] = (dailyPnl[dateKey] || 0) + (op.profit || 0);
        }}
        if (allDateKeys.indexOf(dateKey) === -1) allDateKeys.push(dateKey);
      }}
      // Ensure all dates have entry (even zeros)
      for (var i = 0; i < allDateKeys.length; i++) {{
        if (!(allDateKeys[i] in dailyPnl)) dailyPnl[allDateKeys[i]] = 0;
      }}
      // Build daily trade detail map for tooltips
      var dailyTrades = {{}};
      for (var i = 0; i < __rawOps.length; i++) {{
        var op = __rawOps[i];
        var dk = op.date.substring(0, 10);
        if (!dailyTrades[dk]) dailyTrades[dk] = [];
        dailyTrades[dk].push(op);
      }}

      var dates = Object.keys(dailyPnl).sort();
      var values = dates.map(function(d) {{ return dailyPnl[d]; }});

      // Cumulative
      var cum = 0, cumValues = values.map(function(v) {{ cum += v; return +cum.toFixed(2); }});

      // Max abs for heatmap
      var maxAbs = Math.max.apply(null, values.map(Math.abs).concat([1]));

      function fmtCNY(v) {{ return '¥' + (v * CNY_RATE).toFixed(2); }}

      // Stats
      var pnlSum = values.reduce(function(a,b){{return a+b;}},0);
      var gainDays = values.filter(function(v){{return v>0;}}).length;
      var maxGain = -Infinity, maxLoss = Infinity, maxGainDate='', maxLossDate='';
      for (var i=0;i<dates.length;i++) {{
        if (values[i] > maxGain) {{ maxGain = values[i]; maxGainDate = dates[i]; }}
        if (values[i] < maxLoss) {{ maxLoss = values[i]; maxLossDate = dates[i]; }}
      }}
      var vs = (pnlSum>=0?'+':'') + '$' + pnlSum.toFixed(2);

      var panel = document.getElementById('lp-viz-panel');

      // ── 1. Stats cards ──
      var gc = '#22c55e', rc = '#ef4444', bc = '#58a6ff';
      panel.innerHTML = '<div style="display:flex;gap:8px">' +
        '<div class="stat-item"><div class="s-label">总收益</div><div class="s-value" style="font-size:16px;color:'+gc+'">'+vs+'</div><div class="s-sub">'+fmtCNY(pnlSum)+'</div></div>' +
        '<div class="stat-item"><div class="s-label">盈利天数</div><div class="s-value" style="font-size:16px;color:'+gc+'">'+gainDays+'天</div><div class="s-sub">占 '+Math.round(gainDays/dates.length*100)+'%</div></div>' +
        '<div class="stat-item"><div class="s-label">最大日盈利</div><div class="s-value" style="font-size:16px;color:'+gc+'">+$'+maxGain.toFixed(2)+'</div><div class="s-sub">'+maxGainDate+'</div></div>' +
        '<div class="stat-item"><div class="s-label">最大日亏损</div><div class="s-value" style="font-size:16px;color:'+rc+'">-$'+Math.abs(maxLoss).toFixed(2)+'</div><div class="s-sub">'+maxLossDate+'</div></div>' +
      '</div>';

      // ── 2. Cumulative P&L chart ──
      var chart1 = document.createElement('div');
      chart1.className = 'section';
      chart1.innerHTML = '<div class="section-head">📈 总体盈亏曲线</div><div style="padding:12px"><div style="height:160px"><canvas id="cumChart"></canvas></div></div>';
      panel.appendChild(chart1);

      // ── 3. Daily bar chart ──
      var chart2 = document.createElement('div');
      chart2.className = 'section';
      chart2.innerHTML = '<div class="section-head">📊 每日盈亏</div><div style="padding:12px"><div style="height:130px"><canvas id="pnlChart"></canvas></div></div>';
      panel.appendChild(chart2);

      // ── 4. Heatmap calendar ──
      var cal = document.createElement('div');
      cal.className = 'section';
      cal.id = 'heatmapSection';

      // Build heatmap
      var first = new Date(dates[0]), last = new Date(dates[dates.length-1]);
      var start = new Date(first); start.setDate(start.getDate() - ((start.getDay()+6)%7));
      var end = new Date(last); end.setDate(end.getDate() + (6 - end.getDay()));
      var weeks = [], cur = [];
      for (var d = new Date(start); d <= end; d.setDate(d.getDate()+1)) {{
        if (d.getDay() === 1) {{ if(cur.length) weeks.push(cur); cur = []; }}
        cur.push(new Date(d));
      }}
      if (cur.length) weeks.push(cur);

      function ymd(d) {{ return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0'); }}
      function calColor(ds, p) {{
        if (!(ds in dailyPnl)) return 'var(--bg2)';
        var r = Math.abs(p) / maxAbs;
        return p > 0 ? 'rgba(34,197,94,'+(0.1+r*0.9)+')' : p < 0 ? 'rgba(218,54,51,'+(0.1+r*0.9)+')' : 'var(--bg3)';
      }}

      var months = ['','1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月'];
      var calHtml = '<div class="section-head">📅 盈亏热力图</div><div style="padding:12px"><div style="display:flex;gap:2px;margin-bottom:4px;overflow-x:auto">';
      var pm = -1;
      for (var wi = 0; wi < weeks.length; wi++) {{
        var m = weeks[wi][0].getMonth();
        if (m !== pm) calHtml += '<div style="font-size:8px;color:var(--text3);width:116px;text-align:left">'+months[m+1]+'</div>';
        else calHtml += '<div style="width:116px"></div>';
        pm = m;
      }}
      calHtml += '</div><div style="display:flex;gap:2px"><div style="display:flex;flex-direction:column;gap:2px;margin-right:4px">';
      for (var ni=0;ni<7;ni++) calHtml += '<div style="font-size:8px;color:var(--text3);width:16px;text-align:right;padding-right:2px;height:13px;line-height:13px">'+['一','二','三','四','五','六','日'][ni]+'</div>';
      calHtml += '</div>';
      for (var wi = 0; wi < weeks.length; wi++) {{
        calHtml += '<div style="display:flex;flex-direction:column;gap:2px">';
        for (var di = 0; di < weeks[wi].length; di++) {{
          var d = weeks[wi][di], ds = ymd(d), p = dailyPnl[ds] || 0;
          calHtml += '<div style="width:13px;height:13px;border-radius:2px;background:'+calColor(ds,p)+';cursor:pointer;position:relative" title="'+ds+': '+(p>=0?'+':'')+'$'+p.toFixed(2)+'"></div>';
        }}
        calHtml += '</div>';
      }}
      calHtml += '</div></div>';
      cal.innerHTML = calHtml;
      panel.appendChild(cal);

      // ── 5. Stock-style calendar (month view) ──
      var sc = document.createElement('div');
      sc.className = 'section';
      // Group by month
      var monthMap = {{}};
      for (var i = 0; i < __rawOps.length; i++) {{
        var op = __rawOps[i];
        if (op.type !== 'close') continue;
        var m = op.date.substring(0,7);
        if (!monthMap[m]) monthMap[m] = {{}};
        monthMap[m][op.date.substring(0,10)] = (monthMap[m][op.date.substring(0,10)] || 0) + (op.profit || 0);
      }}
      // Also add dates with only opens
      for (var i = 0; i < __rawOps.length; i++) {{
        var op = __rawOps[i], m = op.date.substring(0,7);
        if (!monthMap[m]) monthMap[m] = {{}};
        monthMap[m][op.date.substring(0,10)] = monthMap[m][op.date.substring(0,10)] || 0;
      }}
      var monthsSorted = Object.keys(monthMap).sort().reverse();

      // This month P&L
      var thisMonth = (new Date().getFullYear())+'-'+String(new Date().getMonth()+1).padStart(2,'0');
      var thisMonthPnl = 0;
      if (monthMap[thisMonth]) for (var k in monthMap[thisMonth]) thisMonthPnl += monthMap[thisMonth][k];

      var scHtml = '<div class="section-head">🗓 盈亏日历 <span style="font-size:10px;color:var(--text3);font-weight:400">每日盈亏金额(USD)</span></div><div style="padding:12px">';
      // Summary bar
      scHtml += '<div style="display:flex;gap:16px;margin-bottom:10px;font-size:11px;flex-wrap:wrap">' +
        '<div>本月盈利: <strong style="color:'+(thisMonthPnl>=0?gc:rc)+'">'+(thisMonthPnl>=0?'+':'')+'$'+thisMonthPnl.toFixed(2)+'</strong></div>' +
        '<div>总收益: <strong style="color:'+(pnlSum>=0?gc:rc)+'">'+vs+'</strong></div>' +
      '</div>';

      for (var mi = 0; mi < Math.min(monthsSorted.length, 3); mi++) {{
        var m = monthsSorted[mi];
        var parts = m.split('-');
        var y = parseInt(parts[0]), mo = parseInt(parts[1]);
        var daysInMonth = new Date(y, mo, 0).getDate();
        var firstDow = new Date(m+'-01').getDay();
        var monthLabel = m.replace('-','年')+'月';
        var monthPnl = 0; for (var k in monthMap[m]) monthPnl += monthMap[m][k];
        var mCls = monthPnl >= 0 ? gc : rc;

        scHtml += '<div style="font-size:11px;color:var(--text2);padding:4px 0;text-align:center">'+monthLabel+'  <span style="color:'+mCls+'">'+(monthPnl>=0?'+':'')+'$'+monthPnl.toFixed(2)+'</span></div>';
        scHtml += '<table style="width:100%;border-collapse:collapse;text-align:center;font-size:10px"><tr>';
        for (var dn=0;dn<7;dn++) scHtml += '<th style="font-size:9px;color:var(--text3);padding:2px 0;font-weight:400">'+['一','二','三','四','五','六','日'][dn]+'</th>';
        scHtml += '</tr><tr>';
        for (var i=0;i<(firstDow===0?6:firstDow-1);i++) scHtml += '<td style="border:none"></td>';

        for (var day=1; day<=daysInMonth; day++) {{
          var ds = m+'-'+String(day).padStart(2,'0');
          var pnl = monthMap[m][ds] || 0;
          var hasOp = ds in (monthMap[m] || {{}});
          var bg = !hasOp ? 'transparent' : pnl > 0 ? 'rgba(34,197,94,0.12)' : pnl < 0 ? 'rgba(218,54,51,0.12)' : 'var(--bg3)';
          var tc = pnl > 0 ? gc : pnl < 0 ? rc : 'var(--text3)';
          scHtml += '<td style="background:'+bg+';border:1px solid var(--border);border-radius:3px;padding:2px 0;width:14.28%">';
          scHtml += '<div style="font-size:7px;color:var(--text3)">'+day+'</div>';
          if (hasOp) scHtml += '<div style="font-size:9px;font-weight:600;color:'+tc+'">'+(pnl>=0?'+':'')+'$'+pnl.toFixed(1)+'</div>';
          scHtml += '</td>';
          if (((firstDow===0?day+6:day+firstDow-1) % 7 === 0) && day < daysInMonth) scHtml += '</tr><tr>';
        }}
        scHtml += '</tr></table><div style="height:8px"></div>';
      }}
      scHtml += '</div>';
      sc.innerHTML = scHtml;
      panel.appendChild(sc);

      // ── Build Chart.js charts ──
      // Cumulative P&L line chart
      try {{
        var cumCtx = document.getElementById('cumChart').getContext('2d');
        if (typeof Chart !== 'undefined') {{
          new Chart(cumCtx, {{
            type: 'line',
            data: {{
              labels: dates,
              datasets: [{{
                data: cumValues,
                borderColor: '#22c55e',
                backgroundColor: 'rgba(34,197,94,0.1)',
                fill: true,
                tension: 0.3,
                pointRadius: 3,
                pointBackgroundColor: cumValues.map(function(v){{return v>=0?'#22c55e':'#ef4444';}}),
                pointBorderColor: '#fff',
                pointBorderWidth: 1
              }}]
            }},
            options: {{
              responsive: true, maintainAspectRatio: false,
              plugins: {{ legend: {{ display: false }}, tooltip: {{ callbacks: {{ title: function(items) {{ return items[0].label; }}, label: function(ctx) {{
  var d = dates[ctx.dataIndex];
  var tds = dailyTrades[d] || [];
  var lines = ['累计: '+(ctx.raw>=0?'+':'')+'$'+ctx.raw.toFixed(2)];
  for (var ti = 0; ti < tds.length; ti++) {{
    var td = tds[ti];
    var tm = td.date.substring(11, 16);
    var sg = (td.profit||0) >= 0 ? '+' : '';
    var ic = td.type === 'close' ? '🔴' : td.type === 'open' ? '🟢' : '⚪';
    lines.push('  ' + tm + ' ' + ic + ' ' + (td.token_pair||'') + ' ' + sg + '$' + (td.profit||0).toFixed(2));
  }}
  return lines;
}} }} }} }},
              scales: {{ x: {{ ticks: {{ color:'var(--text3)', font:{{size:9}}, maxTicksLimit:8 }}, grid:{{ color:'var(--border)' }} }}, y: {{ ticks: {{ color:'var(--text3)', font:{{size:9}}, callback: function(v){{return '$'+v;}} }}, grid:{{ color:'var(--border)' }} }} }}
            }}
          }});

          var pnlCtx = document.getElementById('pnlChart').getContext('2d');
          new Chart(pnlCtx, {{
            type: 'bar',
            data: {{
              labels: dates,
              datasets: [{{
                data: values,
                backgroundColor: values.map(function(v){{return v>=0?'rgba(34,197,94,0.7)':'rgba(218,54,51,0.7)';}}),
                borderColor: values.map(function(v){{return v>=0?'#22c55e':'#da3633';}}),
                borderWidth: 1, borderRadius: 4
              }}]
            }},
            options: {{
              responsive: true, maintainAspectRatio: false,
              plugins: {{ legend: {{ display: false }}, tooltip: {{ callbacks: {{ title: function(items) {{ return items[0].label; }}, label: function(ctx) {{
  var d = dates[ctx.dataIndex];
  var tds = dailyTrades[d] || [];
  var lines = [(ctx.raw>=0?'+':'')+'$'+ctx.raw.toFixed(2)];
  for (var ti = 0; ti < tds.length; ti++) {{
    var td = tds[ti];
    var tm = td.date.substring(11, 16);
    var sg = (td.profit||0) >= 0 ? '+' : '';
    var ic = td.type === 'close' ? '🔴' : td.type === 'open' ? '🟢' : '⚪';
    lines.push('  ' + tm + ' ' + ic + ' ' + (td.token_pair||'') + ' ' + sg + '$' + (td.profit||0).toFixed(2));
  }}
  return lines;
}} }} }} }},
              scales: {{ x: {{ ticks: {{ color:'var(--text3)', font:{{size:9}}, maxRotation:45, maxTicksLimit:14 }}, grid:{{ color:'var(--border)' }} }}, y: {{ ticks: {{ color:'var(--text3)', font:{{size:9}}, callback: function(v){{return '$'+v;}} }}, grid:{{ color:'var(--border)' }} }} }}
            }}
          }});
        }}
      }} catch(e) {{ console.log('Chart error:', e); }}
    }})();
    </script>"""
    elif wallets or proj_id != "505baa0d":
        # 原有钱包逻辑
        wallets_html = ""
        total_wallet_invest = 0
        for w in wallets:
            addr = w.get("address", "")[:10] + "..."
            note = w.get("note", "")
            invest = float(w.get("invest", 0) or 0)
            balance = float(w.get("balance", invest))
            pnl = balance - invest
            pnl_str = f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"
            pnl_color = "#22c55e" if pnl >= 0 else "#ef4444"
            total_wallet_invest += invest
            wallets_html += f"<div style='display:flex;justify-content:space-between;align-items:center;padding:6px 0;border-bottom:1px solid var(--border)'><div><div style='font-size:13px'>{note or addr}</div><div style='font-size:11px;color:var(--text3)'>{addr}</div></div><div style='text-align:right'><div style='font-size:13px;font-weight:600'>${balance:.2f}</div><div style='font-size:11px;color:{pnl_color}'>{pnl_str}</div></div></div>"
        add_wallet_form = f"<div style='border-top:1px solid var(--border);padding-top:10px;margin-top:8px'><div style='font-size:11px;color:var(--text3);margin-bottom:6px'>➕ 添加钱包</div><form method='post' action='/proj/{proj_id}/wallet/add'><input name='wallet_addr' class='form-control' style='margin-bottom:6px;font-size:12px' placeholder='钱包地址' required><input name='wallet_note' class='form-control' style='margin-bottom:6px;font-size:12px' placeholder='备注（如：Base Boosted 115U）'><div style='display:flex;gap:6px'><input name='wallet_invest' class='form-control' style='margin-bottom:6px;font-size:12px;width:100px' placeholder='投入金额$' type='number' step='0.01' min='0'><button type='submit' class='btn btn-primary btn-sm'>添加</button></div></form></div>"
        wallets_section = "<div class='section'><div class='section-head'>💼 钱包 <span class='badge'>" + str(len(wallets)) + "</span></div><div style='padding:12px 16px;display:flex;flex-direction:column;gap:6px'>" + (wallets_html + add_wallet_form if wallets else "<div style='font-size:12px;color:var(--text3);margin-bottom:8px'>暂无钱包</div>" + add_wallet_form) + "</div></div>"

    # ── PredictFun 专属模块 ──────────────────────────────────
    predict_section = ""
    if proj_id == "predictfun-001":
        pw_all  = proj.get("predict_wallets", [])
        ps_list = proj.get("predict_strategies", [])

        # ── 数据整理 ────────────────────────────────────────
        all_ops = []   # 扁平化所有仓位
        for w in pw_all:
            for op in (w.get("ops") or []):
                op["_wallet"] = w.get("name","?")
                all_ops.append(op)

        total_capital = sum(float(op.get("amount",0)) for op in all_ops)
        total_pnl     = sum(float(op.get("pnl",0))   for op in all_ops)
        active_count  = sum(1 for op in all_ops if op.get("action")=="挂单")
        settled_count = sum(1 for op in all_ops if op.get("action")=="平仓")

        # ── 策略选项（for form & calc）──────────────────────
        strat_json = json.dumps({s["id"]: s for s in ps_list}, ensure_ascii=False)
        strat_options = "".join(
            f"<option value='{s['id']}'>{s['name']} — {s['desc']}</option>"
            for s in ps_list
        )
        strat_cards = "".join(
            f"""<div class='strat-card' id='strat-card-{s["id"]}' style='cursor:pointer;flex:1;min-width:150px;background:var(--bg3);border:2px solid var(--border);border-radius:10px;padding:10px' onclick=\"selectStrat('{s['id']}',this)\">
                <div style='font-weight:700;font-size:12px;margin-bottom:4px'>{s['name']}</div>
                <div style='font-size:10px;color:var(--text3);line-height:1.4'>{s['desc']}</div>
            </div>"""
            for s in ps_list
        )

        # ── 仓位记录表 ─────────────────────────────────────
        def strat_by_id(sid):
            return next((s for s in ps_list if s["id"]==sid), None)

        def calc_prices(s, mid, amt):
            nb, na, fb, fa = s["near_bid_ratio"], s["near_ask_ratio"], s["far_bid_ratio"], s["far_ask_ratio"]
            tot = nb+na+fb+fa
            return {
                "nb_p": mid*(1-s["near_bid_pct"]), "nb_a": amt*nb/tot,
                "na_p": mid*(1+s["near_ask_pct"]), "na_a": amt*na/tot,
                "fb_p":  mid*(1-s["far_bid_pct"]),  "fb_a": amt*fb/tot,
                "fa_p":  mid*(1+s["far_ask_pct"]),  "fa_a": amt*fa/tot,
            }

        def fmt_p(v): return f"{v:.4f}" if v < 1 else f"{v:.2f}"

        op_rows = ""
        for op in sorted(all_ops, key=lambda x: x.get("date",""), reverse=True):
            sname   = op.get("strategy","?")
            market  = op.get("market","?")
            mid_s   = ""
            note    = op.get("note","")
            # 从note里解析mid: "mid=0.7 | ..."
            mid_val = 0.0
            if "mid=" in note:
                try: mid_val = float(note.split("mid=")[1].split("|")[0].strip())
                except: pass
            if not mid_val:
                try: mid_val = float(note.strip().split("|")[0])
                except: pass

            action  = op.get("action","挂单")
            amt     = float(op.get("amount",0) or 0)
            pnl     = float(op.get("pnl",0)    or 0)
            date    = op.get("date","?")
            wname   = op.get("_wallet","?")
            m_short = market[:38]+"..." if len(market)>38 else market

            s = strat_by_id(sname)
            if s and mid_val:
                p = calc_prices(s, mid_val, amt)
                order_txt = (
                    f"<span style='color:#60a5fa'>Bid{p['nb_p']:.3f}×${p['nb_a']:.0f}</span> | "
                    f"<span style='color:#f87171'>Ask{p['na_p']:.3f}×${p['na_a']:.0f}</span><br>"
                    f"<span style='color:var(--text3);font-size:9px'>远:{p['fb_p']:.3f}/{p['fa_p']:.3f}</span>"
                )
            elif s:
                order_txt = f"<span style='color:var(--text3)'>-</span>"
            else:
                order_txt = f"<span style='color:var(--text3)'>-</span>"

            status_cls  = "badge-green" if action=="平仓" else "badge-blue"
            status_txt  = "✅已结算"   if action=="平仓" else "🟡挂单中"
            pnl_cls     = "#22c55e"    if pnl>0 else ("#ef4444" if pnl<0 else "var(--text2)")
            pnl_txt     = f"<span style='font-weight:700;color:{pnl_cls}'>{pnl:+.1f}</span>" if action=="平仓" else "<span style='color:var(--text3);font-size:10px'>待结算</span>"

            settle_url  = f"/proj/predictfun-001/settle?id={op.get('date','')}-{op.get('market','')[:10]}&next=/proj/detail/predictfun-001"

            op_rows += f"""<tr>
                <td style='font-size:11px;color:var(--text3);white-space:nowrap'>{date}</td>
                <td><div style='font-size:12px;font-weight:600;max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap' title='{market}'>{m_short}</div></td>
                <td style='font-size:11px;color:var(--blue)'>{wname}</td>
                <td style='font-size:11px;color:var(--text2)'>{sname}</td>
                <td style='font-size:12px;font-weight:700;color:var(--blue)'>${amt:.0f}</td>
                <td style='font-size:11px'>{order_txt}</td>
                <td><span class='{status_cls}' style='font-size:10px;padding:1px 6px;border-radius:4px'>{status_txt}</span></td>
                <td style='font-size:12px'>{pnl_txt}</td>
                <td style='font-size:10px;color:var(--text3)'>{note}</td>
                <td>
                    <form method='get' action='/proj/predictfun-001/settle' style='display:inline'>
                        <input type='hidden' name='id' value='{settle_url.split("id=")[1].split("&")[0]}'>
                        <input type='hidden' name='next' value='/proj/detail/predictfun-001'>
                        <input type='number' name='pnl' step='0.01' placeholder='PnL' style='width:55px;font-size:10px;border:1px solid var(--border);border-radius:4px;background:var(--bg3);color:var(--text);padding:2px 4px'>
                        <button type='submit' class='btn btn-sm' style='font-size:10px;padding:2px 6px'>结算</button>
                    </form>
                </td>
            </tr>"""

        if not op_rows:
            op_rows = "<tr><td colspan='10' style='text-align:center;color:var(--text3);padding:20px'>暂无仓位记录，填写下方表单开始挂单</td></tr>"

        # ── 策略表现统计 ────────────────────────────────────
        strat_stats = {}
        for op in all_ops:
            sn = op.get("strategy","?")
            if sn not in strat_stats: strat_stats[sn] = {"count":0,"capital":0.0,"pnl":0.0}
            strat_stats[sn]["count"]   += 1
            strat_stats[sn]["capital"] += float(op.get("amount",0) or 0)
            strat_stats[sn]["pnl"]     += float(op.get("pnl",0)    or 0)

        strat_perf_rows = ""
        for sn, st in sorted(strat_stats.items(), key=lambda x: -x[1]["capital"]):
            pnl_cls = "#22c55e" if st["pnl"]>=0 else "#ef4444"
            strat_perf_rows += f"""<tr>
                <td style='font-size:12px;font-weight:600;color:var(--blue)'>{sn}</td>
                <td style='font-size:12px'>{st['count']} 个仓位</td>
                <td style='font-size:12px;font-weight:700;color:var(--blue)'>${st['capital']:.0f}</td>
                <td style='font-size:12px;color:{pnl_cls};font-weight:700'>{st['pnl']:+.1f}</td>
            </tr>"""

        if not strat_perf_rows:
            strat_perf_rows = "<tr><td colspan='4' style='text-align:center;color:var(--text3)'>暂无数据</td></tr>"

        # ── 完整HTML ───────────────────────────────────────
        predict_section = f"""
<div class='section'>
<style>
.strat-card {{cursor:pointer;flex:1;min-width:150px;background:var(--bg3);border:2px solid var(--border);border-radius:10px;padding:10px;transition:all .15s}}
.strat-card.strat-active {{border-color:#f0b90b;background:rgba(240,185,11,0.12)}}
</style>
<div class='section-head'>🎯 PredictFun 做市系统</div>

<!-- 统计仪表盘 -->
<div style='display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:16px'>
    <div style='background:var(--bg2);border:1px solid var(--border);border-radius:10px;padding:12px;text-align:center'>
        <div style='font-size:10px;color:var(--text3);margin-bottom:4px'>总仓位</div>
        <div style='font-size:24px;font-weight:800;color:var(--blue)'>{len(all_ops)}</div>
    </div>
    <div style='background:var(--bg2);border:1px solid var(--border);border-radius:10px;padding:12px;text-align:center'>
        <div style='font-size:10px;color:var(--text3);margin-bottom:4px'>🟡 挂单中</div>
        <div style='font-size:24px;font-weight:800;color:#f59e0b'>{active_count}</div>
    </div>
    <div style='background:var(--bg2);border:1px solid var(--border);border-radius:10px;padding:12px;text-align:center'>
        <div style='font-size:10px;color:var(--text3);margin-bottom:4px'>总投入资金</div>
        <div style='font-size:24px;font-weight:800;color:var(--blue)'>${total_capital:.0f}</div>
    </div>
    <div style='background:var(--bg2);border:1px solid var(--border);border-radius:10px;padding:12px;text-align:center'>
        <div style='font-size:10px;color:var(--text3);margin-bottom:4px'>累计 PnL</div>
        <div style='font-size:24px;font-weight:800;color:{"#22c55e" if total_pnl>=0 else "#ef4444"}'>{total_pnl:+.1f}</div>
    </div>
</div>

<!-- 策略表现 -->
<div style='margin-bottom:16px'>
    <div style='font-size:12px;font-weight:700;margin-bottom:8px;color:var(--text2)'>📊 策略表现</div>
    <div style='overflow-x:auto'>
    <table class='data-table' style='font-size:11px'>
        <thead><tr><th>策略</th><th>仓位数</th><th>总资金</th><th>PnL</th></tr></thead>
        <tbody>{strat_perf_rows}</tbody>
    </table>
    </div>
</div>

<!-- 仓位记录表 -->
<div style='margin-bottom:16px'>
    <div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:8px'>
        <div style='font-size:12px;font-weight:700;color:var(--text2)'>📋 仓位记录</div>
    </div>
    <div style='overflow-x:auto'>
    <table class='data-table' style='font-size:11px'>
        <thead><tr>
            <th>日期</th><th>Market</th><th>钱包</th><th>策略</th>
            <th>资金</th><th>挂单价格</th><th>状态</th><th>PnL</th>
            <th>备注</th><th>操作</th>
        </tr></thead>
        <tbody>{op_rows}</tbody>
    </table>
    </div>
</div>

<!-- 快速挂单 + 计算器 -->
<div style='display:grid;grid-template-columns:1fr 1fr;gap:12px'>
    <!-- 左侧：挂单表单 -->
    <div style='background:var(--bg2);border:1px solid var(--border);border-radius:12px;padding:16px'>
        <div style='font-size:14px;font-weight:700;margin-bottom:12px'>⚡ 快速挂单</div>
        <form id='pf-form' method='post' action='/proj/predictfun-001/add-op'>
            <div class='form-group' style='margin-bottom:8px'>
                <label style='font-size:11px;color:var(--text3)'>Market 问题</label>
                <input name='market' class='form-control' style='font-size:12px' placeholder='例如：Will BTC hit $70k by June?' required>
            </div>
            <div style='display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px'>
                <div class='form-group'>
                    <label style='font-size:11px;color:var(--text3)'>选择钱包</label>
                    <select name='wallet_name' class='form-control' style='font-size:12px'>
                        {"".join(f"<option value='{w.get('name','')}'>{w.get('name','')} ({w.get('address','')[:10]}...)</option>" for w in pw_all)}
                    </select>
                </div>
                <div class='form-group'>
                    <label style='font-size:11px;color:var(--text3)'>策略</label>
                    <select name='strategy' class='form-control' style='font-size:12px' onchange=\"syncStratFromSelect2(this.value)\">
                        {strat_options}
                    </select>
                </div>
            </div>
            <div style='display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px'>
                <div class='form-group'>
                    <label style='font-size:11px;color:var(--text3)'>Mid 价格</label>
                    <input id='f-mid' name='mid' type='number' step='0.001' min='0' class='form-control' style='font-size:12px' placeholder='例如 0.7' required oninput='calcFromForm()'>
                </div>
                <div class='form-group'>
                    <label style='font-size:11px;color:var(--text3)'>做市资金 ($)</label>
                    <input id='f-amt' name='amount' type='number' step='1' min='1' class='form-control' style='font-size:12px' placeholder='例如 100' required oninput='calcFromForm()'>
                </div>
            </div>
            <div class='form-group' style='margin-bottom:10px'>
                <label style='font-size:11px;color:var(--text3)'>备注（可选）</label>
                <input name='note' class='form-control' style='font-size:12px' placeholder='例如：exotic market | 120天'>
            </div>
            <!-- 挂单预览 -->
            <div id='order-preview' style='background:var(--bg3);border-radius:8px;padding:10px;margin-bottom:10px;font-size:11px;display:none'>
                <div style='color:var(--text3);margin-bottom:6px'>📐 挂单预览</div>
                <div style='display:grid;grid-template-columns:1fr 1fr;gap:4px'>
                    <div>🔵 <span style='color:#60a5fa'>Bid近</span>: <span id='pv-nb' style='font-weight:700'>-</span> ×$<span id='pv-nba'>-</span></div>
                    <div>🔴 <span style='color:#f87171'>Ask近</span>: <span id='pv-na' style='font-weight:700'>-</span> ×$<span id='pv-naa'>-</span></div>
                    <div>🟡 <span style='color:#facc15'>Bid远</span>: <span id='pv-fb' style='font-weight:700'>-</span> ×$<span id='pv-fba'>-</span></div>
                    <div>🟠 <span style='color:#fb923c'>Ask远</span>: <span id='pv-fa' style='font-weight:700'>-</span> ×$<span id='pv-faa'>-</span></div>
                </div>
            </div>
            <button type='submit' class='btn btn-primary' style='width:100%'>🎯 记录挂单</button>
        </form>
    </div>

    <!-- 右侧：计算器 -->
    <div style='background:var(--bg2);border:1px solid var(--border);border-radius:12px;padding:16px'>
        <div style='font-size:14px;font-weight:700;margin-bottom:10px'>🧮 策略计算器</div>
        <div style='font-size:11px;color:var(--text3);margin-bottom:8px'>点击策略卡片切换</div>
        <div style='display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-bottom:12px'>
            {strat_cards}
        </div>
        <div style='display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:12px'>
            <div class='form-group'>
                <label style='font-size:11px;color:var(--text3)'>Mid 价格</label>
                <input id='c-mid' type='number' step='0.001' min='0' class='form-control' style='font-size:12px' placeholder='0.7' value='0.7' oninput='calcPP()'>
            </div>
            <div class='form-group'>
                <label style='font-size:11px;color:var(--text3)'>做市资金 ($)</label>
                <input id='c-amt' type='number' step='1' min='1' class='form-control' style='font-size:12px' placeholder='100' value='100' oninput='calcPP()'>
            </div>
        </div>
        <div id='calc-result' style='background:var(--bg3);border-radius:8px;padding:12px'>
            <div style='display:grid;grid-template-columns:1fr 1fr;gap:6px;text-align:center;margin-bottom:8px'>
                <div>
                    <div style='font-size:9px;color:var(--text3)'>🔵 Bid近</div>
                    <div id='r-nbp' style='font-size:13px;font-weight:800;color:#60a5fa'>-</div>
                    <div id='r-nba' style='font-size:11px;color:var(--text2)'>-</div>
                </div>
                <div>
                    <div style='font-size:9px;color:var(--text3)'>🔴 Ask近</div>
                    <div id='r-nap' style='font-size:13px;font-weight:800;color:#f87171'>-</div>
                    <div id='r-naa' style='font-size:11px;color:var(--text2)'>-</div>
                </div>
                <div>
                    <div style='font-size:9px;color:var(--text3)'>🟡 Bid远</div>
                    <div id='r-fbp' style='font-size:13px;font-weight:800;color:#facc15'>-</div>
                    <div id='r-fba' style='font-size:11px;color:var(--text2)'>-</div>
                </div>
                <div>
                    <div style='font-size:9px;color:var(--text3)'>🟠 Ask远</div>
                    <div id='r-fap' style='font-size:13px;font-weight:800;color:#fb923c'>-</div>
                    <div id='r-faa' style='font-size:11px;color:var(--text2)'>-</div>
                </div>
            </div>
            <div style='font-size:10px;color:var(--text3);text-align:center'>资金分配比: <span id='r-ratio' style='color:var(--blue)'>-</span></div>
        </div>
    </div>
</div>
</div>

<script>
const STRATS = {strat_json};
let activeStrat = ps_list.length > 1 ? ps_list[1]["id"] : ps_list[0]["id"];

function selectStrat(id, el) {{
    activeStrat = id;
    document.querySelectorAll('.strat-card').forEach(c => c.classList.remove('strat-active'));
    if (el) el.classList.add('strat-active');
    // 同步左侧表单的策略下拉
    const sel = document.querySelector('select[name="strategy"]');
    if (sel) sel.value = id;
    if (typeof calcPP === 'function') calcPP();
    if (typeof calcFromForm === 'function') calcFromForm();
}}

function syncStratFromSelect2(id) {{
    activeStrat = id;
    document.querySelectorAll('.strat-card').forEach(c => c.classList.remove('strat-active'));
    let card = document.getElementById('strat-card-' + id);
    if (card) card.classList.add('strat-active');
    if (typeof calcFromForm === 'function') calcFromForm();
}}

// 初始化：默认选中标准策略
(function initStrat() {{
    const def = document.getElementById('strat-card-' + activeStrat);
    if (def) def.classList.add('strat-active');
}})();

function doCalc(mid, amt) {{
    const s = STRATS[activeStrat];
    if (!s || !mid || !amt) return null;
    const nb=s.near_bid_ratio, na=s.near_ask_ratio, fb=s.far_bid_ratio, fa=s.far_ask_ratio;
    const tot = nb+na+fb+fa;
    return {{
        nbp: mid*(1-s.near_bid_pct), nba: amt*nb/tot,
        nap: mid*(1+s.near_ask_pct), naa: amt*na/tot,
        fbp: mid*(1-s.far_bid_pct),  fba: amt*fb/tot,
        fap: mid*(1+s.far_ask_pct),  faa: amt*fa/tot,
        ratio: nb+'/'+na+'/'+fb+'/'+fa,
    }};
}}

function showPreview(r) {{
    if (!r) return;
    document.getElementById('pv-nb').textContent  = r.nbp.toFixed(4);
    document.getElementById('pv-nba').textContent = r.nba.toFixed(0);
    document.getElementById('pv-na').textContent  = r.nap.toFixed(4);
    document.getElementById('pv-naa').textContent = r.naa.toFixed(0);
    document.getElementById('pv-fb').textContent  = r.fbp.toFixed(4);
    document.getElementById('pv-fba').textContent = r.fba.toFixed(0);
    document.getElementById('pv-fa').textContent  = r.fap.toFixed(4);
    document.getElementById('pv-faa').textContent = r.faa.toFixed(0);
    document.getElementById('order-preview').style.display = 'block';
}}

function calcFromForm() {{
    const mid = parseFloat(document.getElementById('f-mid').value) || 0;
    const amt = parseFloat(document.getElementById('f-amt').value) || 0;
    if (mid && amt) showPreview(doCalc(mid, amt));
}}

function calcPP() {{
    const mid = parseFloat(document.getElementById('c-mid').value) || 0;
    const amt = parseFloat(document.getElementById('c-amt').value) || 0;
    const r = doCalc(mid, amt);
    if (!r) return;
    document.getElementById('r-nbp').textContent = r.nbp.toFixed(4);
    document.getElementById('r-nba').textContent = '$'+r.nba.toFixed(0);
    document.getElementById('r-nap').textContent = r.nap.toFixed(4);
    document.getElementById('r-naa').textContent = '$'+r.naa.toFixed(0);
    document.getElementById('r-fbp').textContent = r.fbp.toFixed(4);
    document.getElementById('r-fba').textContent = '$'+r.fba.toFixed(0);
    document.getElementById('r-fap').textContent = r.fap.toFixed(4);
    document.getElementById('r-faa').textContent = '$'+r.faa.toFixed(0);
    document.getElementById('r-ratio').textContent = r.ratio;
}}

// ── LP 持仓时长实时更新 ──
function fmtDuration(startStr) {{
  var now = new Date();
  var start;
  if (startStr.indexOf('T') >= 0) {{
    start = new Date(startStr.replace('T', ' '));
  }} else {{
    start = new Date(startStr);
  }}
  var diff = (now - start) / 1000;
  if (diff < 0) return '👻 未来';
  var days = Math.floor(diff / 86400);
  var hrs = Math.floor((diff % 86400) / 3600);
  var mins = Math.floor((diff % 3600) / 60);
  var parts = [];
  if (days > 0) parts.push(days + '天');
  if (hrs > 0 || days > 0) parts.push(hrs + '时');
  parts.push(mins + '分');
  return '⏳ ' + parts.join('');
}}

function updateDurations() {{
  var cells = document.querySelectorAll('[id^="dur-"]');
  cells.forEach(function(cell) {{
    var row = cell.closest('tr');
    if (!row) return;
    var dateCell = row.cells[7]; // 开仓时间在第8列(0-indexed=7)
    if (!dateCell) return;
    cell.textContent = fmtDuration(dateCell.textContent.trim());
  }});
}}

// Initial update + every 30 seconds
updateDurations();
setInterval(updateDurations, 30000);

// Init
calcPP();

// ── LP 持仓时长实时更新 ──
function fmtDuration(startStr) {{
  var now = new Date();
  var start;
  if (startStr.indexOf('T') >= 0) {{
    start = new Date(startStr.replace('T', ' '));
  }} else {{
    start = new Date(startStr);
  }}
  var diff = (now - start) / 1000;
  if (diff < 0) return '👻 未来';
  var days = Math.floor(diff / 86400);
  var hrs = Math.floor((diff % 86400) / 3600);
  var mins = Math.floor((diff % 3600) / 60);
  var parts = [];
  if (days > 0) parts.push(days + '天');
  if (hrs > 0 || days > 0) parts.push(hrs + '时');
  parts.push(mins + '分');
  return '⏳ ' + parts.join('');
}}

function updateDurations() {{
  var cells = document.querySelectorAll('[id^="dur-"]');
  cells.forEach(function(cell) {{
    var row = cell.closest('tr');
    if (!row) return;
    var dateCell = row.cells[7]; // 开仓时间在第8列(0-indexed=7)
    if (!dateCell) return;
    cell.textContent = fmtDuration(dateCell.textContent.trim());
  }});
}}

// Initial update + every 30 seconds
updateDurations();
setInterval(updateDurations, 30000);

</script>
"""

    del_url = "/proj/detail/" + proj_id + "/delete"
    edit_url = "/proj/detail/" + proj_id + "/edit"
    content_parts = [
        "<div class='page-header' style='display:block'>",
        "<a href='/?s=projects' class='back-btn'>← 返回项目列表</a>",
        "<div style='display:flex;align-items:center;gap:10px;margin-top:10px;flex-wrap:wrap'>",
        "<div style='font-size:20px;font-weight:700'>" + chain_icon + " " + proj.get("name","") + stars_html + "</div>",
        "<span style='background:rgba(34,197,94,0.15);color:#22c55e;border-radius:6px;padding:2px 8px;font-size:11px'>" + proj.get("status","") + "</span>",
        risk_html,
        "</div>",
    ]
    if tags_html:
        content_parts.append("<div style='display:flex;flex-wrap:wrap;gap:6px;margin-top:10px'>" + tags_html + "</div>")
    if proj_id == "xau-lp-001":
        # LP项目顶部统计（替代通用meta）
        lp_ops = proj.get("lp_operations", [])
        lp_pairs = list(dict.fromkeys(op.get("token_pair","") for op in lp_ops))
        lp_opens = [op for op in lp_ops if op.get("type") == "open"]
        lp_closes = [op for op in lp_ops if op.get("type") == "close"]
        total_pnl = sum(op.get("profit", 0) for op in lp_ops)
        total_op_count = len(lp_opens) + len(lp_closes)
        pnl_cls = "#22c55e" if total_pnl >= 0 else "#ef4444"
        pnl_sign = "+" if total_pnl >= 0 else ""
        content_parts.extend([
            "<div style='display:flex;gap:16px;margin-top:10px;font-size:12px;color:var(--text3);flex-wrap:wrap'>",
            "<span>" + chain + " · 流动性挖矿</span>",
            "<span>累计操作 <strong style='color:var(--text)'>" + str(total_op_count) + " 次</strong></span>",
            "<span>操作币对 <strong style='color:var(--text)'>" + str(len(lp_pairs)) + " 个</strong></span>",
            "<span>累计收益 <strong style='color:" + pnl_cls + "'>" + pnl_sign + "$" + ("%.2f" % total_pnl) + "</strong></span>",
            "</div></div>",
        ])
    else:
        meta_parts = [
            "<div style='display:flex;gap:16px;margin-top:10px;font-size:12px;color:var(--text3);flex-wrap:wrap'>",
            "<span>" + chain + " · " + ptype + "</span>",
            "<span>投入 <strong style='color:var(--text)'>$" + str(int(invest)) + "</strong></span>",
            "<span>收益 <strong style='color:#22c55e'>+$" + str(int(earn)) + "</strong></span>",
            "<span>Gas <strong style='color:var(--text)'>$" + str(int(gas)) + "</strong></span>",
            "<span>ROI <strong style='color:" + roi_color + "'>" + ("+" if roi >= 0 else "") + ("%.1f" % roi) + "%</strong></span>",
            ("<span>💼 " + str(len(wallets)) + "钱包</span>" if proj_id != "505baa0d" else ""),
            "<span>📋 " + str(total_count) + "任务</span>",
            "<span>⭐ " + str(ot_done) + "/" + str(ot_total) + "一次性</span>",
            "</div></div>",
        ]
        content_parts.extend(meta_parts)
    if proj_id != "xau-lp-001":
        content_parts.extend([
        "<div style='margin:12px 0'>",
        "<div style='display:flex;justify-content:space-between;font-size:11px;color:var(--text3);margin-bottom:4px'>",
        "<span>📋 任务完成度</span><span>" + str(done_count) + "/" + str(total_count) + " 今日完成 · " + str(pct) + "%</span>",
        "</div>",
        "<div style='height:8px;background:var(--border);border-radius:4px'>",
        "<div style='height:100%;width:" + str(pct) + "%;background:linear-gradient(90deg,#22c55e,#16a34a);border-radius:4px'></div>",
        "</div></div>",
        ])
    if desc_html:
        content_parts.append(desc_html)
    if notes_html:
        content_parts.append(notes_html)
    # 详细攻略 button
    readme_path = proj.get("readme_path", "")
    if readme_path and os.path.exists(readme_path):
        content_parts.append("<a href='/proj/detail/" + proj_id + "/plan' target='_blank' class='btn' style='display:inline-flex;align-items:center;gap:6px;margin-bottom:12px;text-decoration:none'>📋 详细攻略</a>")
    if proj_id not in ("xau-lp-001", "505baa0d"):
        content_parts.extend([
        "<div style='display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px'>",
        "<div style='background:var(--bg2);border:1px solid var(--border);border-radius:10px;padding:12px'>",
        "<div style='font-size:11px;color:var(--text3);margin-bottom:8px'>🔥 今日待办 <span style='color:#ef4444;font-weight:700;font-size:14px;margin-left:4px'>" + str(len(today_proj_tasks)) + "</span></div>",
        (pending_rows if pending_rows else "<div style='font-size:12px;color:var(--text3)'>✅ 今日任务已全部完成！</div>"),
        "</div>",
        "<div style='background:var(--bg2);border:1px solid var(--border);border-radius:10px;padding:12px'>",
        "<div style='font-size:11px;color:var(--text3);margin-bottom:8px'>✅ 今日已完成 <span style='color:#22c55e;font-weight:700;font-size:14px;margin-left:4px'>" + str(len(today_proj_done)) + "</span></div>",
        (done_rows if done_rows else "<div style='font-size:12px;color:var(--text3)'>暂无完成</div>"),
        "</div>",
        "</div>",
    ])
    # 今日待办 + 已完成（非 BinanceAlpha）
    if proj_id not in ("xau-lp-001", "505baa0d"):
        content_parts.extend([
        "<div style='display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px'>",
        "<div style='background:var(--bg2);border:1px solid var(--border);border-radius:10px;padding:12px'>",
        "<div style='font-size:11px;color:var(--text3);margin-bottom:8px'>🔥 今日待办 <span style='color:#ef4444;font-weight:700;font-size:14px;margin-left:4px'>" + str(len(today_proj_tasks)) + "</span></div>",
        (pending_rows if pending_rows else "<div style='font-size:12px;color:var(--text3)'>✅ 今日任务已全部完成！</div>"),
        "</div>",
        "<div style='background:var(--bg2);border:1px solid var(--border);border-radius:10px;padding:12px'>",
        "<div style='font-size:11px;color:var(--text3);margin-bottom:8px'>✅ 今日已完成 <span style='color:#22c55e;font-weight:700;font-size:14px;margin-left:4px'>" + str(len(today_proj_done)) + "</span></div>",
        (done_rows if done_rows else "<div style='font-size:12px;color:var(--text3)'>暂无完成</div>"),
        "</div>",
        "</div>",
    ])
    if wallets_section and proj_id != "505baa0d":
        content_parts.append(wallets_section)

    # PredictFun 专属模块
    if predict_section:
        content_parts.append(predict_section)

    # ── BinanceAlpha 多钱包交易记录 ──────────────────────────
    if proj_id == "505baa0d":
        alpha_wallets = proj.get("alpha_wallets", [])
        if not alpha_wallets:
            alpha_wallets = [{"id":"w1","name":"钱包1","target_vol":32800,"target_pts":17,"tx_log":[]}]
            tx_path = os.environ.get("WORKBENCH_ALPHA_TX_FILE", "").strip()
            if os.path.exists(tx_path):
                with open(tx_path) as f:
                    for line in f:
                        if line.startswith("|") and "日期" not in line and "---" not in line:
                            parts = [p.strip() for p in line.split("|")[1:-1]]
                            if len(parts) >= 4 and parts[0]:
                                try:
                                    vol = int(parts[1].replace(",",""))
                                    fee = float(parts[2])
                                    pts = int(parts[3]) if parts[3].isdigit() else 0
                                    alpha_wallets[0]["tx_log"].append({
                                        "date":parts[0],"vol":vol,"fee":fee,"pts":pts,"note":parts[4] if len(parts)>4 else ""
                                    })
                                except: pass
            proj["alpha_wallets"] = alpha_wallets
            save_json(PROJECTS_FILE, data)

        wallet_blocks = ""
        for w in alpha_wallets:
            wid      = w.get("id","")
            wname    = w.get("name","钱包")
            wtarget  = w.get("target_vol",32800)
            tx_log   = w.get("tx_log",[])
            w_vol    = sum(t.get("vol",0) for t in tx_log)
            w_fee    = sum(t.get("fee",0) for t in tx_log)
            w_pts    = sum(t.get("pts",0) for t in tx_log)

            income_entries = w.get("income_entries", [])
            income_total   = sum(e.get("amount", 0) for e in income_entries)
            w_profit = income_total - w_fee
            inc_rows = ""
            for e in income_entries:
                d = e.get("date", "?")
                a = e.get("amount", 0)
                n = e.get("note", "")
                inc_rows += f"""<tr>
                    <td style='font-size:11px;color:var(--text3)'>{d}</td>
                    <td style='font-size:12px;color:#3fb950;font-weight:600'>+${a:.2f}</td>
                    <td style='font-size:11px;color:var(--text2);max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap' title='{n}'>{n or '—'}</td>
                    <td><form method='post' action='/proj/505baa0d/del-income' style='display:inline'><input type='hidden' name='wallet_id' value='{wid}'><input type='hidden' name='income_date' value='{d}'><button type='submit' class='btn btn-sm' style='font-size:10px;padding:1px 5px;color:var(--red)'>×</button></form></td>
                </tr>"""
            if not inc_rows:
                inc_rows = "<tr><td colspan='4' style='text-align:center;color:var(--text3);font-size:11px'>暂无收入记录</td></tr>"

            tx_rows = ""
            for tx in sorted(tx_log, key=lambda x: x.get("date",""), reverse=True):
                d=tx.get("date","?"); v=tx.get("vol",0); f=tx.get("fee",0); p=tx.get("pts",0); n=tx.get("note","")
                ok = "badge-green" if v>=wtarget else "badge-red"
                day_ok = "✅" if v>=wtarget else f"⚠️{v:,}"
                tx_rows += f"""<tr>
                    <td style='font-size:11px;color:var(--text3)'>{d}</td>
                    <td style='font-size:12px;font-weight:700;color:var(--blue)'>{v:,} U</td>
                    <td style='font-size:12px;color:var(--red)'>{f:.2f}</td>
                    <td style='font-size:12px;color:#22c55e;font-weight:600'>{p}</td>
                    <td><span class='{ok}' style='font-size:10px;padding:1px 6px;border-radius:4px'>{day_ok}</span></td>
                    <td style='font-size:10px;color:var(--text3)'>{n}</td>
                    <td>
                        <form method='post' action='/proj/505baa0d/del-tx' style='display:inline'>
                            <input type='hidden' name='wallet_id' value='{wid}'>
                            <input type='hidden' name='tx_date' value='{d}'>
                            <button type='submit' class='btn btn-sm' style='font-size:10px;padding:1px 5px;color:var(--red)'>×</button>
                        </form>
                    </td>
                </tr>"""
            if not tx_rows:
                tx_rows = "<tr><td colspan='7' style='text-align:center;color:var(--text3)'>暂无记录</td></tr>"

            _today = datetime.now().strftime("%Y-%m-%d")
            wallet_blocks += f"""
            <div style='background:var(--bg2);border:1px solid var(--border);border-radius:12px;margin-bottom:16px'>
                <div style='padding:12px 16px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px'>
                    <div style='display:flex;align-items:center;gap:10px'>
                        <div style='font-size:16px'>👛</div>
                        <div>
                            <div style='font-weight:700;font-size:14px'>{wname}</div>
                            <div style='font-size:10px;color:var(--text3)'>目标: {wtarget:,}U / {w.get('target_pts',17)}分</div>
                        </div>
                    </div>
                    <div style='display:flex;gap:16px;font-size:11px'>
                        <div>量: <strong style='color:var(--blue)'>{w_vol:,} U</strong></div>
                        <div>磨损: <strong style='color:var(--red)'>{w_fee:.2f} U</strong></div>
                        <div>积分: <strong style='color:#22c55e'>{w_pts}</strong></div>
                        <div style='color:#3fb950'>累计已登记收益: <strong>${income_total:.2f}</strong></div>
                        <div style='color:#f59e0b'>累计收益: <strong>${w_profit:+.2f}</strong></div>
                    </div>
                </div>
                <div style='padding:8px 16px;background:var(--bg3);border-bottom:1px solid var(--border)'>
                    <div style='font-size:11px;font-weight:700;color:var(--text2);margin-bottom:6px'>💰 收入明细</div>
                    <table class='data-table' style='font-size:11px'>
                        <thead><tr><th style='width:90px'>日期</th><th style='width:80px'>金额</th><th>来源/备注</th><th style='width:30px'></th></tr></thead>
                        <tbody>{inc_rows}</tbody>
                    </table>
                </div>
                <div style='padding:8px 16px;background:var(--bg3);display:flex;gap:6px;flex-wrap:wrap;align-items:center'>
                    <form method='post' action='/proj/505baa0d/set-wallet-income' style='display:flex;gap:5px;align-items:center;flex-wrap:wrap'>
                        <input type='hidden' name='wallet_id' value='{wid}'>
                        <span style='font-size:10px;color:var(--text3);white-space:nowrap'>日期:</span>
                        <input name='income_date' type='date' value='{_today}'
                            style='padding:3px 6px;background:var(--bg);border:1px solid var(--border);border-radius:4px;color:var(--text);font-size:11px;width:130px'>
                        <span style='font-size:10px;color:var(--text3);white-space:nowrap'>金额 ($):</span>
                        <input name='income_amount' type='number' step='0.01' min='0' placeholder='0.00'
                            style='width:80px;padding:3px 6px;background:var(--bg);border:1px solid var(--border);border-radius:4px;color:var(--text);font-size:11px'>
                        <span style='font-size:10px;color:var(--text3);white-space:nowrap'>来源/备注:</span>
                        <input name='income_note' type='text' placeholder='如: BNX 空投 / TGE 发放'
                            style='width:160px;padding:3px 6px;background:var(--bg);border:1px solid var(--border);border-radius:4px;color:var(--text);font-size:11px'>
                        <button type='submit' style='padding:3px 10px;background:#3fb950;border:none;border-radius:4px;color:#fff;font-size:10px;cursor:pointer'>+ 登记</button>
                    </form>
                </div>
                <div style='padding:10px 16px;background:var(--bg3);border-bottom:1px solid var(--border)'>
                    <form method='post' action='/proj/505baa0d/add-tx' style='display:flex;gap:6px;flex-wrap:wrap;align-items:center'>
                        <input type='hidden' name='wallet_id' value='{wid}'>
                        <input name='tx_date' type='date' class='form-control' style='font-size:11px;width:130px' value='{_today}' required>
                        <input name='tx_vol' type='number' step='1' min='0' class='form-control' style='font-size:11px;width:90px' placeholder='交易量U' required>
                        <input name='balance_before' type='number' step='0.01' min='0' class='form-control' style='font-size:11px;width:75px' placeholder='刷前余额U' required oninput='calcAlphaFee(this)'>
                        <input name='balance_after' type='number' step='0.01' min='0' class='form-control' style='font-size:11px;width:75px' placeholder='刷后余额U' required oninput='calcAlphaFee(this)'>
                        <span id='fee_display2' style='font-size:11px;color:var(--red);min-width:55px;text-align:center'></span>
                        <input type='hidden' name='tx_fee' id='tx_fee_hidden2'>
                        <input name='tx_pts' type='number' step='1' min='0' class='form-control' style='font-size:11px;width:55px' placeholder='积分' required>
                        <input name='tx_note' type='text' class='form-control' style='font-size:11px;width:120px' placeholder='备注'>
                        <button type='submit' class='btn btn-primary btn-sm'>+ 记录</button>
                    </form>
                </div>
                <div style='overflow-x:auto;max-height:420px;overflow-y:auto'>
                <table class='data-table' style='font-size:11px'>
                    <thead style='position:sticky;top:0;z-index:1'><tr><th>日期</th><th>交易量</th><th>磨损</th><th>积分</th><th>达标</th><th>备注</th><th></th></tr></thead>
                    <tbody>{tx_rows}</tbody>
                </table>
                </div>
            </div>"""

        add_wallet_form = f"""<div style='background:var(--bg2);border:1px dashed var(--border);border-radius:10px;padding:14px;text-align:center'>
            <div style='font-size:12px;color:var(--text3);margin-bottom:8px'>添加钱包</div>
            <form method='post' action='/proj/505baa0d/add-wallet' style='display:flex;gap:6px;justify-content:center;flex-wrap:wrap'>
                <input name='wallet_name' type='text' class='form-control' style='font-size:12px;width:120px' placeholder='钱包名称' required>
                <input name='target_vol' type='number' step='1' class='form-control' style='font-size:12px;width:100px' placeholder='目标量U' value='32800'>
                <input name='target_pts' type='number' step='1' class='form-control' style='font-size:12px;width:70px' placeholder='目标积分' value='17'>
                <button type='submit' class='btn btn-primary btn-sm'>➕ 添加钱包</button>
            </form>
        </div>"""

        alpha_section = (
            "<div class='section'>"
            "<div class='section-head'>📊 BinanceAlpha 多钱包交易记录</div>"
            + wallet_blocks
            + add_wallet_form
            + "</div>"
        )
        content_parts.append(alpha_section)


    if proj_id != "xau-lp-001":
        content_parts.extend([
            "<div class='section'>",
            "<div class='section-head'>📋 全部任务 <span class='badge'>" + str(len(proj_tasks)) + "</span></div>",
            "<div style='overflow-x:auto'>",
            "<table class='data-table' style='font-size:12px'>",
            "<thead><tr><th style='width:40px'>状态</th><th>任务 / 备注</th><th style='width:70px'>频率</th><th style='width:90px'>上次完成</th><th style='width:85px'>下次</th><th style='width:70px'>操作</th></tr></thead>",
            "<tbody>" + "".join(rows) + "</tbody>",
            "</table>",
            "</div></div>",
        ])
    if links_section:
        content_parts.append(links_section)
    # LP项目：添加仓位和操作历史（替代钱包和任务区域）
    if proj_id == "xau-lp-001":
        content_parts.append(lp_section)
        content_parts.append(op_section)
    content_parts.extend([
        "<div class='section'>",
        "<a href='" + edit_url + "' class='btn btn-primary'>✏️ 编辑项目</a>",
        " <a href='" + del_url + "' class='btn btn-danger' onclick='return confirm(\u786e\u5b9a\u5220\u9664\u6b64\u9879\u76ee\uff1f)'>🗑️ 删除</a>",
        " <a href='/?s=projects' class='btn'>返回列表</a>",
        "</div>",
    ])
    content = "".join(content_parts)
    # Add wallet edit toggle JS
    edit_js = "<script>function toggleEdit(btn){var card=btn.closest('.wallet-card');if(!card)return;var form=card.querySelector('.wallet-edit-form');if(!form)return;var wasHidden=form.style.display==='none';form.style.display=wasHidden?'block':'none';btn.textContent=wasHidden?'取消':'✏️ 编辑'}\nfunction calcAlphaFee(el){\n  var card=el.closest('.wallet-card')||document;\n  var before=parseFloat(card.querySelector('input[name=\"balance_before\"]').value)||0;\n  var after=parseFloat(card.querySelector('input[name=\"balance_after\"]').value)||0;\n  var fee=Math.max(0,before-after);\n  var display=card.querySelector('.fee_display, #fee_display2');\n  var hidden=card.querySelector('#tx_fee_hidden2');\n  if(display) display.textContent='磨损: '+fee.toFixed(2)+' U';\n  if(hidden) hidden.value=fee.toFixed(2);\n}</script>"
    content += edit_js
    # LP持仓时长定时刷新
    dur_js = '''<script>
function fmtDuration(startStr) {
  var now = new Date();
  var start = startStr.indexOf('T') >= 0 ? new Date(startStr.replace('T', ' ')) : new Date(startStr);
  var diff = (now - start) / 1000;
  if (diff < 0) return '\\u{1F46B} \\u672a\\u6765';
  var days = Math.floor(diff / 86400);
  var hrs = Math.floor((diff % 86400) / 3600);
  var mins = Math.floor((diff % 3600) / 60);
  var parts = [];
  if (days > 0) parts.push(days + '\\u5929');
  if (hrs > 0 || days > 0) parts.push(hrs + '\\u65f6');
  parts.push(mins + '\\u5206');
  return '\\u23F3 ' + parts.join('');
}
function updateDurations() {
  var cells = document.querySelectorAll('[id^="dur-"]');
  cells.forEach(function(cell) {
    var row = cell.closest('tr');
    if (!row) return;
    var dateCell = row.cells[row.cells.length - 4];
    if (!dateCell) return;
    cell.textContent = fmtDuration(dateCell.textContent.trim());
  });
}
updateDurations();
setInterval(updateDurations, 30000);
</script>'''
    content += dur_js
    return render_template_string(LAYOUT, section="projects", now=now(), content=content,
        standx_ok=0, standx_total=0, ip_total=0, proj_total=len(projects))



def log_trade(task_id):
    """BinanceAlpha 交易记录表单"""
    data = load_json(PROJECTS_FILE)
    all_tasks = data.get("tasks", [])
    task = next((t for t in all_tasks if t["id"] == task_id), None)
    if not task:
        return redirect("/?s=projects")
    proj_id = task.get("project_id", "")
    projects = data.get("projects", [])
    proj = next((p for p in projects if p["id"] == proj_id), None)
    proj_name = proj.get("name", "未知项目") if proj else "未知项目"

    if request.method == "POST":
        trading_vol = request.form.get("trading_vol", "").strip()
        fee = request.form.get("fee", "").strip()
        points = request.form.get("points", "").strip()
        note = request.form.get("note", "").strip()

        # Save to transactions.md
        tx_path = os.environ.get("WORKBENCH_ALPHA_TX_FILE", "").strip()
        today = today_str()
        vol_clean = trading_vol.replace(",", "").replace(",", "")
        fee_clean = fee.replace(",", "").replace(",", "")
        # Append to markdown table
        new_row = "| " + today + " | " + vol_clean + " | " + fee_clean + " | " + (points if points else "-") + " | " + (note if note else "") + " |\n"
        if os.path.exists(tx_path):
            with open(tx_path, "r", encoding="utf-8") as f:
                tx_content = f.read()
            # Find the table and insert before ---
            if "| 日期" in tx_content:
                # Find the line after the table header
                lines = tx_content.split("\n")
                new_lines = []
                for i, line in enumerate(lines):
                    new_lines.append(line)
                    if line.startswith("|------"):
                        new_lines.append(new_row)
                new_tx = "\n".join(new_lines)
            else:
                new_tx = tx_content + "\n" + new_row
            with open(tx_path, "w", encoding="utf-8") as f:
                f.write(new_tx)

        # Update task last_done
        task["last_done"] = today_str()
        freq = task.get("freq", "daily")
        today = today_str()
        if freq == "daily":
            d = datetime.strptime(today, "%Y-%m-%d")
            nd = (d + timedelta(days=1)).strftime("%Y-%m-%d")
        elif freq == "weekly":
            d = datetime.strptime(today, "%Y-%m-%d")
            nd = (d + timedelta(weeks=1)).strftime("%Y-%m-%d")
        elif freq == "monthly":
            nd = _next_month(today)
        else:
            nd = ""
        task["next_due"] = nd
        task["next_run"] = nd
        # Update task note with latest data
        if trading_vol or fee:
            task["note"] = "交易量:" + vol_clean + "U 磨损:" + fee_clean + "U" + (" 积分:" + points if points else "")
        save_json(PROJECTS_FILE, data)
        return redirect("/proj/detail/" + proj_id)

    # GET: show form
    prev_note = task.get("note", "")
    content = (
        "<div class='page-header' style='display:block'>"
        "<a href='/proj/detail/" + proj_id + "' class='back-btn'>← 返回" + proj_name + "</a>"
        "<div style='font-size:20px;font-weight:700;margin-top:10px'>📊 登记交易记录</div>"
        "<div style='font-size:13px;color:var(--text3);margin-top:4px'>" + proj_name + " - " + task.get("name", "") + "</div>"
        "</div>"
        "<div class='section'>"
        "<form method='post'>"
        "<div style='padding:16px'>"
        "<div class='form-group'><label>交易量 (U)</label><input name='trading_vol' class='form-control' placeholder='例如：33000' required></div>"
        "<div class='form-group'><label>磨损/手续费 (U)</label><input name='fee' class='form-control' placeholder='例如：1.7'></div>"
        "<div class='form-group'><label>获得积分</label><input name='points' class='form-control' placeholder='自动计算或手动输入'></div>"
        "<div class='form-group'><label>备注</label><input name='note' class='form-control' placeholder='可选备注'></div>"
        "<div style='margin-top:16px'>"
        "<button type='submit' class='btn btn-primary'>✅ 确认登记</button>"
        " <a href='/proj/detail/" + proj_id + "' class='btn'>取消</a>"
        "</div>"
        "</div>"
        "</form></div>"
    )
    return render_template_string(LAYOUT, section="projects", now=now(), content=content,
        standx_ok=0, standx_total=0, ip_total=0, proj_total=len(projects))



def proj_wallet_add(proj_id):
    data = load_json(PROJECTS_FILE)
    projects = data.get("projects", [])
    proj = next((p for p in projects if p["id"] == proj_id), None)
    if not proj:
        return redirect("/?s=projects")
    wallet_addr = request.form.get("wallet_addr", "").strip()
    wallet_note = request.form.get("wallet_note", "").strip()
    wallet_invest = request.form.get("wallet_invest", "").strip()
    if wallet_addr:
        # Ensure wallets is a list of dicts
        if "wallets" not in proj:
            proj["wallets"] = []
        # Convert old string format to dict if needed
        new_wallet = {
            "address": wallet_addr,
            "note": wallet_note,
            "invest": float(wallet_invest) if wallet_invest and wallet_invest.replace(".","",1).isdigit() else 0
        }
        proj["wallets"].append(new_wallet)
        # Update project invest total
        def w_invest(w): return w.get("invest", 0) if isinstance(w, dict) else 0
        all_invest = sum(w_invest(w) for w in proj["wallets"])
        proj["invest"] = str(all_invest)
        save_json(PROJECTS_FILE, data)
    return redirect("/proj/detail/" + proj_id)


def proj_wallet_edit(proj_id):
    data = load_json(PROJECTS_FILE)
    projects = data.get("projects", [])
    proj = next((p for p in projects if p["id"] == proj_id), None)
    if not proj:
        return redirect("/?s=projects")
    wallet_addr = request.form.get("wallet_addr", "").strip()
    wallet_note = request.form.get("wallet_note", "").strip()
    wallet_invest = request.form.get("wallet_invest", "").strip()
    if wallet_addr and "wallets" in proj:
        def w_addr(w): return w.get("address","") if isinstance(w,dict) else str(w)
        for w in proj["wallets"]:
            if w_addr(w) == wallet_addr:
                if isinstance(w, dict):
                    w["note"] = wallet_note
                    w["invest"] = float(wallet_invest) if wallet_invest and wallet_invest.replace(".","",1).isdigit() else 0
                break
        all_invest = sum(w.get("invest",0) if isinstance(w,dict) else 0 for w in proj["wallets"])
        proj["invest"] = str(all_invest)
        save_json(PROJECTS_FILE, data)
    return redirect("/proj/detail/" + proj_id)

def proj_wallet_del(proj_id):
    data = load_json(PROJECTS_FILE)
    projects = data.get("projects", [])
    proj = next((p for p in projects if p["id"] == proj_id), None)
    if not proj:
        return redirect("/?s=projects")
    wallet_addr = request.form.get("wallet_addr", "").strip()
    if wallet_addr and "wallets" in proj:
        proj["wallets"] = [w for w in proj["wallets"] if (w.get("address","") if isinstance(w,dict) else str(w)) != wallet_addr]
        def w_invest(w): return w.get("invest", 0) if isinstance(w, dict) else 0
        all_invest = sum(w_invest(w) for w in proj["wallets"])
        proj["invest"] = str(all_invest)
        save_json(PROJECTS_FILE, data)
    return redirect("/proj/detail/" + proj_id)

def proj_wallet_balance(proj_id):
    data = load_json(PROJECTS_FILE)
    projects = data.get("projects", [])
    proj = next((p for p in projects if p["id"] == proj_id), None)
    if not proj:
        return redirect("/dashboard")
    wallet_addr = request.form.get("wallet_addr", "").strip()
    balance_str = request.form.get("balance", "").strip()
    if wallet_addr and balance_str:
        try:
            new_balance = float(balance_str)
        except:
            new_balance = 0.0
        for w in proj.get("wallets", []):
            if isinstance(w, dict) and w.get("address", "") == wallet_addr:
                w["balance"] = new_balance
                break
        save_json(PROJECTS_FILE, data)
    return redirect("/dashboard")

def dashboard_income():
    data = load_json(PROJECTS_FILE)
    source = request.form.get("source", "").strip()
    amount_str = request.form.get("amount", "").strip()
    proj_id = request.form.get("proj_id", "").strip()
    note = request.form.get("note", "").strip()
    try:
        amount = float(amount_str)
    except:
        amount = 0.0
    if amount > 0 and source:
        if "income_log" not in data:
            data["income_log"] = []
        income_entry = {"source": source, "amount": amount, "proj_id": proj_id, "note": note}
        data["income_log"].insert(0, income_entry)
        # Also track per-project extra earn
        if "extra_earn" not in data:
            data["extra_earn"] = {}
        if proj_id and proj_id != "__other__":
            data["extra_earn"][proj_id] = data["extra_earn"].get(proj_id, 0) + amount
        elif proj_id == "__other__":
            data["extra_earn"]["__other__"] = data["extra_earn"].get("__other__", 0) + amount
        save_json(PROJECTS_FILE, data)
    return redirect("/dashboard")

# ── PredictFun 仓位操作 ─────────────────────────────────

def predictfun_add_op():
    """处理快速挂单表单"""
    from flask import request, redirect
    market     = request.form.get("market","").strip()
    wallet_name= request.form.get("wallet_name","").strip()
    strategy   = request.form.get("strategy","").strip()
    mid        = request.form.get("mid","").strip()
    amount     = request.form.get("amount","").strip()
    note       = request.form.get("note","").strip()

    if not market or not amount:
        return redirect("/proj/detail/predictfun-001")

    try:
        data = load_json(PROJECTS_FILE)
        from datetime import date
        today = date.today().isoformat()

        # 找到对应钱包
        for proj in data.get("projects",[]):
            if proj.get("id") != "predictfun-001": continue
            pw_list = proj.get("predict_wallets",[])
            for w in pw_list:
                if w.get("name","") == wallet_name:
                    ops = w.get("ops") or []
                    # 构建note（含mid和策略）
                    note_full = f"mid={mid} | {strategy}" + (f" | {note}" if note else "")
                    ops.append({
                        "date":      today,
                        "market":    market,
                        "action":    "挂单",
                        "strategy":  strategy,
                        "amount":    float(amount),
                        "pnl":       0,
                        "note":      note_full,
                    })
                    w["ops"] = ops
                    save_json(PROJECTS_FILE, data)
                    break
            break
    except Exception as e:
        print(f"predictfun_add_op error: {e}")

    return redirect("/proj/detail/predictfun-001")


def predictfun_settle():
    """结算/平仓一个仓位"""
    from flask import request, redirect
    op_id   = request.args.get("id","").strip()
    pnl_val = request.args.get("pnl","0").strip()
    action  = request.args.get("action","settle")

    try:
        data = load_json(PROJECTS_FILE)
        for proj in data.get("projects",[]):
            if proj.get("id") != "predictfun-001": continue
            for w in proj.get("predict_wallets",[]):
                ops = w.get("ops") or []
                for op in ops:
                    key = op.get("date","") + "-" + op.get("market","")[:10]
                    if key == op_id:
                        op["action"] = "平仓"
                        try: op["pnl"] = float(pnl_val)
                        except: pass
                        w["ops"] = ops
                        save_json(PROJECTS_FILE, data)
                        break
            break
    except Exception as e:
        print(f"predictfun_settle error: {e}")

    nxt = request.args.get("next","/proj/detail/predictfun-001")
    return redirect(nxt)


# ── BinanceAlpha 多钱包交易操作 ─────────────────────────────────

def alpha_add_tx():
    """添加交易记录"""
    from flask import request, redirect
    wallet_id = request.form.get("wallet_id","").strip()
    tx_date   = request.form.get("tx_date","").strip()
    tx_vol    = request.form.get("tx_vol","").strip()
    tx_fee   = request.form.get("tx_fee","").strip()
    tx_pts    = request.form.get("tx_pts","").strip()
    tx_note   = request.form.get("tx_note","").strip()
    balance_before = request.form.get("balance_before","").strip()
    balance_after  = request.form.get("balance_after","").strip()

    # 如果 JS 自动计算的 tx_fee 为空，手动计算磨损 = 刷前余额 - 刷后余额
    if not tx_fee and balance_before and balance_after:
        try:
            tx_fee = str(max(0.0, float(balance_before) - float(balance_after)))
        except:
            pass

    if not wallet_id or not tx_date or not tx_vol:
        return redirect("/proj/detail/505baa0d")

    try:
        data = load_json(PROJECTS_FILE)
        for proj in data.get("projects",[]):
            if proj.get("id") != "505baa0d": continue
            alpha_wallets = proj.get("alpha_wallets",[])
            for w in alpha_wallets:
                if w.get("id","") == wallet_id:
                    tx_log = w.get("tx_log") or []
                    tx_log.append({
                        "date": tx_date,
                        "vol":  int(float(tx_vol)),
                        "fee":  float(tx_fee),
                        "pts":  int(float(tx_pts)),
                        "note": tx_note,
                    })
                    w["tx_log"] = tx_log
                    save_json(PROJECTS_FILE, data)
                    break
            break
    except Exception as e:
        print(f"alpha_add_tx error: {e}")

    return redirect("/proj/detail/505baa0d")


def alpha_del_tx():
    """删除一条交易记录"""
    from flask import request, redirect
    wallet_id = request.form.get("wallet_id","").strip()
    tx_date   = request.form.get("tx_date","").strip()

    try:
        data = load_json(PROJECTS_FILE)
        for proj in data.get("projects",[]):
            if proj.get("id") != "505baa0d": continue
            for w in proj.get("alpha_wallets",[]):
                if w.get("id","") == wallet_id:
                    tx_log = w.get("tx_log") or []
                    w["tx_log"] = [t for t in tx_log if t.get("date","") != tx_date]
                    save_json(PROJECTS_FILE, data)
                    break
            break
    except Exception as e:
        print(f"alpha_del_tx error: {e}")

    return redirect("/proj/detail/505baa0d")


def alpha_add_wallet():
    """添加新钱包"""
    from flask import request, redirect
    wallet_name = request.form.get("wallet_name","").strip()
    target_vol  = request.form.get("target_vol","32800").strip()
    target_pts  = request.form.get("target_pts","17").strip()

    if not wallet_name:
        return redirect("/proj/detail/505baa0d")

    try:
        data = load_json(PROJECTS_FILE)
        for proj in data.get("projects",[]):
            if proj.get("id") != "505baa0d": continue
            alpha_wallets = proj.get("alpha_wallets",[])
            new_id = "w" + str(int(time.time()*1000) % 100000)
            alpha_wallets.append({
                "id":         new_id,
                "name":      wallet_name,
                "target_vol": int(float(target_vol)),
                "target_pts": int(float(target_pts)),
                "tx_log":    [],
            })
            proj["alpha_wallets"] = alpha_wallets
            save_json(PROJECTS_FILE, data)
            break
    except Exception as e:
        print(f"alpha_add_wallet error: {e}")

    return redirect("/proj/detail/505baa0d")


def dashboard_income_del():
    data = load_json(PROJECTS_FILE)
    idx_str = request.form.get("idx", "").strip()
    try:
        idx = int(idx_str)
        income_log = data.get("income_log", [])
        if 0 <= idx < len(income_log):
            entry = income_log.pop(idx)
            # Decrement extra_earn
            proj_id = entry.get("proj_id", "")
            amount = float(entry.get("amount", 0))
            if proj_id and proj_id != "__other__":
                data["extra_earn"][proj_id] = max(0, data["extra_earn"].get(proj_id, 0) - amount)
            elif proj_id == "__other__":
                data["extra_earn"]["__other__"] = max(0, data["extra_earn"].get("__other__", 0) - amount)
            save_json(PROJECTS_FILE, data)
    except:
        pass
    return redirect("/dashboard")


def alpha_set_wallet_income():
    """为指定 Alpha 钱包新增一笔收入记录"""
    wallet_id  = request.form.get("wallet_id", "").strip()
    income_str = request.form.get("income_amount", "0").strip()
    income_note = request.form.get("income_note", "").strip()
    try:
        income_val = float(income_str) if income_str else 0.0
    except:
        income_val = 0.0
    if not wallet_id or income_val <= 0:
        return redirect("/proj/detail/505baa0d")
    try:
        data = load_json(PROJECTS_FILE)
        for proj in data.get("projects", []):
            if proj.get("id") != "505baa0d":
                continue
            alpha_wallets = proj.get("alpha_wallets", [])
            for w in alpha_wallets:
                if w.get("id") == wallet_id:
                    entries = w.get("income_entries", [])
                    import datetime as _dt
                    entries.insert(0, {
                        "date":  request.form.get("income_date", "") or datetime.now().strftime("%Y-%m-%d"),
                        "amount": income_val,
                        "note":  income_note
                    })
                    w["income_entries"] = entries
                    save_json(PROJECTS_FILE, data)
                    break
            break
    except Exception as e:
        print(f"alpha_set_wallet_income error: {e}")
    return redirect("/proj/detail/505baa0d")


def alpha_del_income():
    """删除指定钱包的一笔收入记录"""
    wallet_id    = request.form.get("wallet_id", "").strip()
    income_date  = request.form.get("income_date", "").strip()
    try:
        data = load_json(PROJECTS_FILE)
        for proj in data.get("projects", []):
            if proj.get("id") != "505baa0d":
                continue
            alpha_wallets = proj.get("alpha_wallets", [])
            for w in alpha_wallets:
                if w.get("id") == wallet_id:
                    entries = w.get("income_entries", [])
                    w["income_entries"] = [e for e in entries if e.get("date", "") != income_date]
                    save_json(PROJECTS_FILE, data)
                    break
            break
    except Exception as e:
        print(f"alpha_del_income error: {e}")
    return redirect("/proj/detail/505baa0d")
