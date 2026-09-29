import os
from flask import request, redirect, render_template_string, make_response
from datetime import datetime, timedelta
import json
from utils import load_json, save_json, today_str, now, now_str, get_standx_data, PROJECTS_FILE, get_all_tasks, is_due_within
from templates import LAYOUT

def proj_add_page():
    if request.method == "POST":
        import uuid
        data = load_json(PROJECTS_FILE)
        projects = data.get("projects", [])
        new_proj = {
            "id": request.form.get("id") or str(uuid.uuid4())[:8],
            "name": request.form.get("name",""),
            "status": request.form.get("status","进行中"),
            "chain": request.form.get("chain",""),
            "type": request.form.get("type",""),
            "invest": float(request.form.get("invest","0") or 0),
            "gas_cost": float(request.form.get("gas_cost","0") or 0),
            "earn": 0,
            "tasks": [],
            "wallets": [],
            "links": {},
            "created": today_str(),
            "next_renew": request.form.get("next_renew",""),
            "stars": 3
        }
        projects.append(new_proj)
        data["projects"] = projects
        save_json(PROJECTS_FILE, data)
        return redirect(f"/proj/detail/{new_proj['id']}")
    content = (
        "<div class='page-header'><a href='/' class='back-btn'>← 返回</a><div class='page-title'>➕ 新增项目</div></div>"
        "<div class='section'><form method='post'><div class='form-group'><label>项目ID</label><input name='id' class='form-control' placeholder='留空自动生成'></div>"
        "<div class='form-group'><label>项目名称</label><input name='name' class='form-control' required></div>"
        "<div class='form-row'><div class='form-group'><label>状态</label><select name='status' class='form-control'><option value='进行中'>进行中</option><option value='准备中'>准备中</option><option value='已完成'>已完成</option></select></div>"
        "<div class='form-group'><label>链</label><input name='chain' class='form-control' placeholder='如BNB Chain/Solana/Base'></div>"
        "<div class='form-group'><label>类型</label><input name='type' class='form-control'></div></div>"
        "<div class='form-row'><div class='form-group'><label>投入(U)</label><input name='invest' type='number' step='0.01' value='0' class='form-control'></div>"
        "<div class='form-group'><label>Gas成本</label><input name='gas_cost' type='number' step='0.01' value='0' class='form-control'></div></div>"
        "<div class='form-group'><label>下次重要日期</label><input name='next_renew' type='date' class='form-control'></div>"
        "<button type='submit' class='btn btn-primary'>✅ 创建项目</button> <a href='/' class='btn'>取消</a></form></div>"
    )
    return render_template_string(LAYOUT, section="projects", now=now(), content=content,
        standx_ok=0, standx_total=0, ip_total=0, proj_total=0)

# ============ 报表系统 ============

def build_daily_report():
    """从 projects_data.json 生成日报文本"""
    data = load_json(PROJECTS_FILE)
    projects = data.get("projects", [])
    tasks = data.get("tasks", [])
    today = today_str()
    today_short = today[5:]  # MM-DD

    # 统计
    active = [p for p in projects if p.get("status") == "进行中"]
    total_invest = sum(float(p.get("invest", 0) or 0) for p in projects)
    total_earn = sum(float(p.get("earn", 0) or 0) for p in projects)
    total_gas = sum(float(p.get("gas_cost", 0) or 0) for p in projects)
    roi = ((total_earn - total_gas) / total_invest * 100) if total_invest > 0 else 0

    # 今日完成的任务
    today_tasks = [t for t in tasks if t.get("last_done", "").startswith(today)]
    # 即将到期的任务（未来3天）
    upcoming = []
    try:
        td = datetime.strptime(today, "%Y-%m-%d")
        for t in tasks:
            nd = t.get("next_due", "")
            if nd:
                dd = datetime.strptime(nd, "%Y-%m-%d")
                if 0 <= (dd - td).days <= 3:
                    upcoming.append((t, (dd - td).days))
    except:
        pass

    lines = []
    lines.append(f"📊 【Orange | 区块日记日报】{today}")
    lines.append(f"🔥 项目总览：{len(active)}/{len(projects)} 进行中 | 总投入 ${total_invest:.0f} | 总收益 +${total_earn:.0f} | Gas ${total_gas:.0f} | ROI {'+' if roi>=0 else ''}{roi:.1f}%")
    lines.append("")
    lines.append("💰 重点项目状态")
    for p in active:
        inv = float(p.get("invest", 0) or 0)
        earn = float(p.get("earn", 0) or 0)
        gas_c = float(p.get("gas_cost", 0) or 0)
        p_roi = ((earn - gas_c) / inv * 100) if inv > 0 else 0
        wallets = len(p.get("wallets", []))
        lp_ops = len(p.get("lp_operations", []))
        lp_pnl = sum(op.get("profit", 0) for op in p.get("lp_operations", []))
        # LP项目特殊显示
        if p["id"] == "xau-lp-001":
            lp_pairs = list(dict.fromkeys(op.get("token_pair", "") for op in p.get("lp_operations", [])))
            lp_opens = len([o for o in p.get("lp_operations", []) if o.get("type") == "open"])
            lp_closes = len([o for o in p.get("lp_operations", []) if o.get("type") == "close"])
            status_line = f"投入${inv:.0f} | LP操作{lp_opens+lp_closes}次 | 币对{len(lp_pairs)}个 | 累计收益{'+' if lp_pnl>=0 else ''}${lp_pnl:.2f} | ROI {'+' if p_roi>=0 else ''}{p_roi:.1f}%"
        else:
            status_line = f"投入${inv:.0f} | 收益+${earn:.0f} | ROI {'+' if p_roi>=0 else ''}{p_roi:.1f}%" + (f" | {wallets}钱包" if wallets else "")
        lines.append(f"• {p.get('name','?')}（{p.get('chain','?')}）{status_line}")

    if today_tasks:
        lines.append("")
        lines.append(f"✅ 今日完成 {len(today_tasks)} 项任务")
        for t in today_tasks[:10]:
            proj_name = next((p.get("name","?") for p in projects if p["id"] == t.get("project_id")), "?")
            lines.append(f"  ✓ {proj_name}: {t.get('name','')}")

    if upcoming:
        lines.append("")
        lines.append(f"⏰ 即将到期（未来3天）")
        for t, days in upcoming[:8]:
            proj_name = next((p.get("name","?") for p in projects if p["id"] == t.get("project_id")), "?")
            tag = "今天" if days == 0 else f"{days}天后"
            lines.append(f"  • [{tag}] {proj_name}: {t.get('name','')}")

    lines.append("")
    lines.append(f"🕐 生成于 {datetime.now().strftime('%H:%M')}")
    return "\n".join(lines)


def build_weekly_report():
    """从 projects_data.json 生成周报文本"""
    data = load_json(PROJECTS_FILE)
    projects = data.get("projects", [])
    tasks = data.get("tasks", [])
    today = today_str()
    # 过去7天
    try:
        td = datetime.strptime(today, "%Y-%m-%d")
        week_ago = (td - timedelta(days=7)).strftime("%Y-%m-%d")
    except:
        week_ago = today

    active = [p for p in projects if p.get("status") == "进行中"]
    total_invest = sum(float(p.get("invest", 0) or 0) for p in projects)
    total_earn = sum(float(p.get("earn", 0) or 0) for p in projects)
    total_gas = sum(float(p.get("gas_cost", 0) or 0) for p in projects)
    roi = ((total_earn - total_gas) / total_invest * 100) if total_invest > 0 else 0

    # 本周完成任务
    week_tasks = [t for t in tasks if t.get("last_done", "") >= week_ago]
    daily_tasks = [t for t in week_tasks if t.get("freq") == "daily"]
    one_time_tasks = [t for t in week_tasks if t.get("freq") == "one-time"]

    lines = []
    lines.append(f"📊 【Orange | 区块日记周报】{week_ago} ~ {today}")
    lines.append(f"🔥 本周概况：{len(active)} 个项目进行中 | 总投入 ${total_invest:.0f} | 累计收益 +${total_earn:.0f} | Gas ${total_gas:.0f} | 综合ROI {'+' if roi>=0 else ''}{roi:.1f}%")
    lines.append(f"📋 本周任务：完成 {len(week_tasks)} 项（日常 {len(daily_tasks)} | 一次性 {len(one_time_tasks)}）")
    lines.append("")
    lines.append("💰 各项目本周状态")
    for p in active:
        inv = float(p.get("invest", 0) or 0)
        earn = float(p.get("earn", 0) or 0)
        gas_c = float(p.get("gas_cost", 0) or 0)
        p_roi = ((earn - gas_c) / inv * 100) if inv > 0 else 0
        wallets = len(p.get("wallets", []))
        lp_ops = len(p.get("lp_operations", []))
        lp_pnl = sum(op.get("profit", 0) for op in p.get("lp_operations", []))
        proj_tasks = [t for t in tasks if t.get("project_id") == p["id"]]
        proj_week_tasks = [t for t in proj_tasks if t.get("last_done", "") >= week_ago]
        if p["id"] == "xau-lp-001":
            lp_pairs = list(dict.fromkeys(op.get("token_pair", "") for op in p.get("lp_operations", [])))
            lp_opens = len([o for o in p.get("lp_operations", []) if o.get("type") == "open"])
            lp_closes = len([o for o in p.get("lp_operations", []) if o.get("type") == "close"])
            status_line = f"投入${inv:.0f} | LP{lp_opens+lp_closes}次/{len(lp_pairs)}币对 | 累计收益{'+' if lp_pnl>=0 else ''}${lp_pnl:.2f}"
        else:
            status_line = f"投入${inv:.0f} | 收益+${earn:.0f} | ROI {'+' if p_roi>=0 else ''}{p_roi:.1f}%" + (f" | {wallets}钱包" if wallets else "")
        lines.append(f"• {p.get('name','?')}（{p.get('chain','?')}）{status_line}")
        if proj_week_tasks:
            for t in proj_week_tasks[:3]:
                lines.append(f"  ✓ {t.get('name','')}")

    lines.append("")
    lines.append(f"🕐 生成于 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    return "\n".join(lines)

