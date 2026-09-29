from html import escape

from flask import render_template_string

from templates import LAYOUT
from utils import PROJECTS_FILE, load_json, now


def _number(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _money(value):
    value = _number(value)
    return f"${value:,.0f}" if value == int(value) else f"${value:,.2f}"


def projects_page():
    data = load_json(PROJECTS_FILE)
    projects = data.get("projects", [])
    tasks = data.get("tasks", [])
    upcoming = [project for project in projects if project.get("status") == "准备中"]
    active = [project for project in projects if project.get("status") != "准备中"]

    def make_card(project):
        project_id = str(project.get("id", ""))
        project_tasks = [task for task in tasks if task.get("project_id") == project_id]
        wallets = [wallet for wallet in project.get("wallets", []) if isinstance(wallet, dict)]
        invested = sum(_number(wallet.get("invest")) for wallet in wallets)
        balance = sum(_number(wallet.get("balance", wallet.get("invest"))) for wallet in wallets)
        invested = invested or _number(project.get("invest"))
        roi = (balance - invested) / invested * 100 if invested else 0
        risk = str(project.get("risk", ""))
        risk_class = {"低": "low", "中": "medium", "高": "high"}.get(risk, "")
        status = "准备中" if project.get("status") == "准备中" else "进行中"
        status_class = "warning" if status == "准备中" else "success"
        target = "/lp" if project_id == "xau-lp-001" else f"/proj/detail/{project_id}"
        tags = [str(tag) for tag in project.get("tags", [])[:2]]
        meta = [str(project.get("chain", "")).strip(), str(project.get("type", "")).strip(), *tags]
        meta_html = "".join(f"<span class='pill info'>{escape(item)}</span>" for item in meta if item)

        links = project.get("links", {})
        link_items = [(name, url) for name, url in links.items() if url][:2] if isinstance(links, dict) else []
        links_html = "".join(
            f"<a href='{escape(str(url), quote=True)}' target='_blank' onclick='event.stopPropagation()'>{escape(str(name or '打开链接'))}</a>"
            for name, url in link_items if isinstance(url, str)
        )
        risk_html = f"<span class='project-risk {risk_class}'>风险 {escape(risk)}</span>" if risk else ""
        roi_token = "green" if roi >= 0 else "red"
        search_text = escape(" ".join(meta + [str(project.get("name", ""))]).lower(), quote=True)
        return f"""
        <article class='project-card' data-search='{search_text}' onclick="location.href='{escape(target, quote=True)}'">
          <div class='project-card-top'>
            <div style='min-width:0'><div class='project-name'>{escape(str(project.get('name', '未命名项目')))}</div><div class='project-meta'>{meta_html}</div></div>
            <span class='pill {status_class}'><span class='status-dot'></span>{status}</span>
          </div>
          <div class='project-kpis'>
            <div class='project-kpi'><label>钱包</label><b>{len(wallets)}</b></div>
            <div class='project-kpi'><label>任务</label><b>{len(project_tasks)}</b></div>
            <div class='project-kpi'><label>投入</label><b>{_money(invested)}</b></div>
            <div class='project-kpi'><label>估算 ROI</label><b style='color:var(--{roi_token})'>{roi:+.1f}%</b></div>
          </div>
          <div class='project-links'>{links_html}<span style='margin-left:auto'>{risk_html}</span></div>
        </article>"""

    total_invest = sum(_number(project.get("invest")) for project in projects)
    total_earn = sum(_number(project.get("earn")) for project in projects)
    total_gas = sum(_number(project.get("gas_cost")) for project in projects)
    total_wallets = sum(len(project.get("wallets", [])) for project in projects)
    net_earn = total_earn - total_gas
    net_token = "green" if net_earn >= 0 else "red"

    stats = f"""
    <div class='stats-bar'>
      <div class='stat-item'><div class='s-label'>进行中</div><div class='s-value c-blue'>{len(active)}</div><div class='s-sub'>个项目</div></div>
      <div class='stat-item'><div class='s-label'>准备中</div><div class='s-value'>{len(upcoming)}</div><div class='s-sub'>个项目</div></div>
      <div class='stat-item'><div class='s-label'>累计钱包</div><div class='s-value'>{total_wallets}</div><div class='s-sub'>个钱包</div></div>
      <div class='stat-item'><div class='s-label'>累计投入</div><div class='s-value'>{_money(total_invest)}</div><div class='s-sub'>记录投入</div></div>
      <div class='stat-item'><div class='s-label'>净收益</div><div class='s-value c-{net_token}'>{'+' if net_earn >= 0 else ''}{_money(net_earn)}</div><div class='s-sub'>已扣 Gas {_money(total_gas)}</div></div>
    </div>"""

    def render_section(title, items, empty_text):
        cards = "".join(make_card(project) for project in items)
        empty = f"<div class='empty-state' style='grid-column:1/-1'><strong>{empty_text}</strong></div>"
        return f"""
        <section class='section'>
          <div class='section-head project-section-header'><span>{title}<span class='count-badge'>{len(items)}</span></span></div>
          <div class='project-grid'>{cards or empty}</div>
        </section>"""

    content = f"""
    <header class='page-header page-header-row'>
      <div class='page-heading'><div class='page-title'>项目管理</div><div class='page-subtitle'>集中查看项目进度、资金投入与执行入口</div></div>
      <div class='page-actions'><input id='proj-search' class='form-control' placeholder='搜索项目、链或标签'><a href='/proj/add' class='btn btn-primary'>＋ 新建项目</a></div>
    </header>
    {stats}
    {render_section('进行中的项目', active, '暂无进行中的项目')}
    {render_section('准备与观察', upcoming, '暂无准备中的项目') if upcoming else ''}
    <script>
    (function(){{
      var search=document.getElementById('proj-search');
      search.addEventListener('input',function(){{
        var query=search.value.trim().toLowerCase();
        document.querySelectorAll('.project-card').forEach(function(card){{card.hidden=Boolean(query&&!card.dataset.search.includes(query))}});
      }});
    }})();
    </script>"""
    return render_template_string(LAYOUT, section="projects", now=now(), content=content,
                                  standx_ok=0, standx_total=0, ip_total=0, proj_total=len(projects))
