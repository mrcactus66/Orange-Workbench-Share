"""
交易记录页面
=============
完全复刻 LP 流动性页面结构，文字改为交易记录形式
数据独立存储于 projects_data.json 的 trade-tx-001 项目下
"""
import os, json, time
import urllib.parse
from flask import request, redirect, render_template_string, make_response, jsonify
from datetime import datetime, timedelta
from collections import defaultdict
from utils import load_json, save_json, today_str, now_str

TRADE_PROJ_ID = "trade-tx-001"
TRADE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "projects_web", "data", "trade_log_data.json")


def _trade_data():
    data = load_json(TRADE_FILE)
    project = data.get("project", {}) if isinstance(data, dict) else {}
    if not project:
        project = {"id": TRADE_PROJ_ID, "name": "交易记录", "trade_positions": [], "trade_operations": [], "invest": "0", "earn": "0"}
    return project


def _save_trade(project):
    save_json(TRADE_FILE, {"project": project})


def _trade_redirect(result="", error=""):
    query = urllib.parse.urlencode({key: value for key, value in {"trade_result": result, "trade_error": error}.items() if value})
    return redirect("/trade-log" + ("?" + query if query else ""))

def _ensure_project():
    """保留旧调用点；交易记录已独立存储，绝不写入项目数据。"""
    return None

def _get_trade_project():
    return _trade_data()

def trade_log_page():
    proj = _get_trade_project()
    if not proj:
        proj = {
            "id": TRADE_PROJ_ID,
            "name": "交易记录",
            "trade_positions": [],
            "trade_operations": [],
            "invest": "0",
            "earn": "0"
        }

    today = today_str()

    # ── 仓位数据 ──────────────────────────────────────────
    trade_positions = proj.get("trade_positions", [])
    trade_ops = proj.get("trade_operations", [])

    # ── 开仓中仓位表 ──────────────────────────────────────
    open_pos = [p for p in trade_positions if p.get("status") == "open"]
    closed_pos = [p for p in trade_positions if p.get("status") == "closed"]

    pos_rows_html = ""
    for p in open_pos:
        pair = p.get("token_pair", "")
        direction = p.get("direction", "做多")
        dir_icon = "🟢 做多" if direction == "做多" else "🔴 做空"
        dir_color = "#22c55e" if direction == "做多" else "#ef4444"
        initial = p.get("trade_amount", 0)
        current = p.get("current_balance", initial)
        fees = p.get("fees", 0)
        pnl = (current + fees) - initial
        pnl_color = "#22c55e" if pnl >= 0 else "#ef4444"
        pnl_sign = "+" if pnl >= 0 else ""
        pos_rows_html += f"<tr>"
        pos_rows_html += f"<td style='font-weight:600'>{pair}</td>"
        pos_rows_html += f"<td style='color:{dir_color};font-weight:600'>{dir_icon}</td>"
        pos_rows_html += f"<td style='color:var(--blue)'>${initial:.2f}</td>"
        pos_rows_html += f"<td>${current:.2f}</td>"
        pos_rows_html += f"<td>${fees:.2f}</td>"
        pos_rows_html += f"<td style='color:{pnl_color};font-weight:600'>{pnl_sign}${pnl:.2f}</td>"
        pos_rows_html += f"<td>{p.get('open_date','')}</td>"
        pos_rows_html += f"<td style='color:#22c55e'>🟢 持仓中</td>"
        pos_rows_html += f"""<td>
            <form method='post' action='/trade-log/close' style='display:inline-flex;gap:4px;align-items:center'>
                <input type='hidden' name='pos_id' value='{p['id']}'>
                <input type='hidden' name='open_date' value='{p.get('open_date','')}'>
                <input type='number' step='0.01' name='close_balance' class='form-control' style='width:80px;font-size:11px' placeholder='平仓金额' required>
                <input type='number' step='0.01' name='close_fees' class='form-control' style='width:70px;font-size:11px' placeholder='手续费' value='0'>
                <input type='date' name='close_date' class='form-control' style='width:120px;font-size:11px' value='{today}'>
                <button type='submit' class='btn btn-sm' style='background:#ef4444;color:#fff;font-size:11px;padding:3px 8px'>平仓</button>
            </form>
        </td>"""
        pos_rows_html += f"</tr>"

    if not pos_rows_html:
        pos_rows_html = "<tr><td colspan='9' class='empty'>暂无持仓记录</td></tr>"

    add_pos_form = f"""
    <div id='trade-add-form' class='trade-modal-panel' style='border-top:1px solid var(--border);padding:18px;margin-top:12px'>
        <div><div class='modal-title'>新增交易</div><div class='modal-subtitle'>记录交易方向、金额和开仓信息</div></div>
        <form method='post' action='/trade-log/add' style='display:flex;flex-wrap:wrap;gap:6px;align-items:flex-end'>
            <div style='flex:1;min-width:120px'>
                <label style='font-size:11px;color:var(--text3)'>交易对</label>
                <input name='token_pair' class='form-control' style='font-size:12px' placeholder='例如：BTC/USDT' required>
            </div>
            <div>
                <label style='font-size:11px;color:var(--text3)'>方向</label>
                <select name='direction' class='form-control' style='width:80px;font-size:12px'>
                    <option value='做多'>🟢 做多</option>
                    <option value='做空'>🔴 做空</option>
                </select>
            </div>
            <div>
                <label style='font-size:11px;color:var(--text3)'>金额 ($)</label>
                <input name='trade_amount' type='number' step='0.01' class='form-control' style='width:90px;font-size:12px' placeholder='0' required>
            </div>
            <div>
                <label style='font-size:11px;color:var(--text3)'>入场价</label>
                <input name='entry_price' type='number' step='0.0001' class='form-control' style='width:90px;font-size:12px' placeholder='0'>
            </div>
            <div>
                <label style='font-size:11px;color:var(--text3)'>手续费</label>
                <input name='fees' type='number' step='0.01' class='form-control' style='width:80px;font-size:12px' placeholder='0' value='0'>
            </div>
            <div>
                <label style='font-size:11px;color:var(--text3)'>开仓日期</label>
                <input name='open_date' type='date' class='form-control' style='width:130px;font-size:12px' value='{today}'>
            </div>
            <div style='flex:1'>
                <label style='font-size:11px;color:var(--text3)'>备注</label>
                <input name='note' class='form-control' style='font-size:12px' placeholder='可选'>
            </div>
            <button type='submit' class='btn btn-primary' style='font-size:12px'>添加记录</button><button type='button' class='btn' onclick='toggleTradeAdd()'>取消</button>
        </form>
    </div>"""

    pos_section = f"""
    <div class='section trade-positions'>
        <div class='section-head'><span>当前持仓 <span class='count-badge'>{len(open_pos)}</span></span><span class='pill success'><span class='status-dot'></span>{len(open_pos)} 持仓中</span></div>
        <div style='overflow-x:auto;padding:12px 16px'>
            <table class='data-table' style='font-size:12px'>
                <thead><tr><th>交易对</th><th>方向</th><th>本金</th><th>当前余额</th><th>手续费</th><th>盈亏</th><th>开仓日期</th><th>状态</th><th>操作</th></tr></thead>
                <tbody>{pos_rows_html}</tbody>
            </table>
            {add_pos_form}
        </div>
    </div>"""

    # ── 交易操作历史 ──────────────────────────────────────
    op_rows = ""
    tx_count = len(trade_ops)
    date_groups = defaultdict(list)
    for op in trade_ops:
        date_groups[op.get('date', '')].append(op)
    sorted_dates = sorted(date_groups.keys(), reverse=True)

    for date in sorted_dates:
        day_ops = date_groups[date]
        day_pnl = sum(o.get('profit', 0) for o in day_ops if o.get('type') == 'close')
        for op in day_ops:
            pnl_val = op.get("profit", 0)
            pnl_color = "#22c55e" if pnl_val >= 0 else "#ef4444"
            pnl_sign = "+" if pnl_val >= 0 else ""
            op_type = op.get("type", "")
            if op_type == "open":
                dir = op.get("direction", "做多")
                op_type_icon = "🟢 买入" if dir == "做多" else "🔴 做空"
            elif op_type == "close":
                dir = op.get("direction", "做多")
                op_type_icon = "🔴 卖出" if dir == "做多" else "🟢 买入"
            else:
                op_type_icon = op_type
            op_type_color = "#22c55e" if op_type == "open" else "#ef4444"
            op_rows += f"<tr data-optype='{op_type}'>"
            op_rows += f"<td>{date}</td>"
            op_rows += f"<td style='color:{op_type_color};font-weight:600'>{op_type_icon}</td>"
            op_rows += f"<td style='font-weight:600'>{op.get('token_pair','')}</td>"
            op_rows += f"<td>${op.get('principal',0):.2f}</td>"
            op_rows += f"<td style='color:{pnl_color};font-weight:600'>{pnl_sign}${pnl_val:.2f}</td>"
            op_rows += f"<td style='color:{pnl_color};font-weight:600'>¥{pnl_val * 6.66:.2f}</td>"
            op_rows += f"<td>{op.get('duration','')}</td>"
            op_rows += f"<td style='font-size:11px;color:var(--text3)'>{op.get('note','')}</td>"
            op_rows += f"</tr>"
        # Daily subtotal
        day_pnl_color = "#22c55e" if day_pnl >= 0 else "#ef4444"
        day_sign = "+" if day_pnl >= 0 else ""
        op_rows += f"<tr style='background:var(--bg3);font-weight:600;border-top:2px solid var(--border)'>"
        op_rows += f"<td colspan='4' style='text-align:right;font-size:11px;color:var(--text2)'>📊 {date} 小计</td>"
        op_rows += f"<td style='color:{day_pnl_color}'>{day_sign}${day_pnl:.2f}</td>"
        op_rows += f"<td style='color:{day_pnl_color}'>¥{day_pnl * 6.66:.2f}</td>"
        op_rows += f"<td></td><td></td>"
        op_rows += f"</tr>"

    if not op_rows:
        op_rows = "<tr><td colspan='8' style='text-align:center;color:var(--text3);padding:16px'>暂无交易记录</td></tr>"

    total_invest = sum(op.get('principal',0) for op in trade_ops if op.get('type') in ('open','topup'))
    total_pnl = sum(op.get('profit',0) for op in trade_ops)
    pnl_cls = '#22c55e' if total_pnl >= 0 else '#ef4444'
    op_summary = f"<div style='display:flex;gap:16px;padding:10px 16px;background:var(--bg3);border-radius:8px;margin-bottom:10px;font-size:12px;flex-wrap:wrap'><div>累计投入: <strong style='color:var(--blue)'>${total_invest:.2f}</strong></div><div>累计盈亏: <strong style='color:{pnl_cls}'>{'+' if total_pnl>=0 else ''}${total_pnl:.2f}</strong></div><div>交易次数: <strong>{len(trade_ops)}</strong></div></div>"

    filter_btns = f"""
    <div class='trade-filter-bar'>
        <button class='tx-filter-btn active' data-opttype='all' onclick="filterTxOps('all',this)">全部</button>
        <button class='tx-filter-btn' data-opttype='open' onclick="filterTxOps('open',this)">买入 / 开仓</button>
        <button class='tx-filter-btn' data-opttype='close' onclick="filterTxOps('close',this)">卖出 / 平仓</button>
    </div>
    <script>
    function filterTxOps(type, btn) {{
        var rows = document.querySelectorAll('#tx-op-table tbody tr');
        rows.forEach(function(r) {{
            if(type === 'all' || r.getAttribute('data-optype') === type) {{
                r.style.display = '';
            }} else {{
                r.style.display = 'none';
            }}
        }});
        document.querySelectorAll('.tx-filter-btn').forEach(function(b) {{ b.classList.remove('active'); }});
        btn.classList.add('active');
    }}
    </script>"""

    # ── 右侧看板（图表 + 统计）─────────────────────────────
    crypt_exchanges = ["Bybit", "Binance", "OKX", "HTX", "Gate", "Bitget"]
    viz_html = _build_trade_viz(trade_ops, total_invest, total_pnl)

    op_section = f"""
    <div class='trade-layout'>

      <!-- 左栏：明细表 -->
      <div class='trade-history-column'>
        <div class='section'>
            <div class='section-head'>交易记录明细 <span class='badge'>{len(trade_ops)}</span></div>
            {filter_btns}
            <div style='overflow-x:auto;padding:0 12px 12px'>
                <table id='tx-op-table' class='data-table' style='font-size:11px'>
                    <thead><tr><th>日期</th><th>类型</th><th>交易对</th><th>本金</th><th>盈亏(USD)</th><th>盈亏(CNY)</th><th>时长</th><th>备注</th></tr></thead>
                    <tbody>{op_rows}</tbody>
                </table>
            </div>
        </div>
      </div>

      <!-- 右栏：可视化看板 -->
      <div class='trade-analytics-column'>
        <div id='tx-viz-panel'>
          <div style='text-align:center;color:var(--text3);padding:60px 0;font-size:12px'>⏳ 加载可视化组件...</div>
        </div>
      </div>

    </div>

    <script>
    // ── 构建每日盈亏数据 ──
    (function() {{
      var __rawOps = {json.dumps(trade_ops)};
      if (!__rawOps.length) {{
        document.getElementById('tx-viz-panel').innerHTML = "<div style='text-align:center;padding:60px 20px'><div style='font-size:32px;margin-bottom:12px'>📊</div><div style='font-size:14px;color:var(--text3)'>暂无交易数据</div><div style='font-size:12px;color:var(--text3);margin-top:6px'>\u6dfb\u52a0\u7b2c\u4e00\u7b14\u4ea4\u6613\u8bb0\u5f55\u540e\uff0c\u56fe\u8868\u5c06\u81ea\u52a8\u5c55\u793a</div></div>";
        return;
      }}

      var CNY_RATE = 6.66;
      var dailyPnl = {{}};
      var allDates = [];
      for (var i = 0; i < __rawOps.length; i++) {{
        var op = __rawOps[i];
        if (op.type === 'close') {{
          dailyPnl[op.date] = (dailyPnl[op.date] || 0) + (op.profit || 0);
        }}
        if (allDates.indexOf(op.date) === -1) allDates.push(op.date);
      }}
      for (var i = 0; i < allDates.length; i++) {{
        if (!(allDates[i] in dailyPnl)) dailyPnl[allDates[i]] = 0;
      }}
      var dates = Object.keys(dailyPnl).sort();
      var values = dates.map(function(d) {{ return dailyPnl[d]; }});

      // Cumulative
      var cum = 0, cumValues = values.map(function(v) {{ cum += v; return +cum.toFixed(2); }});

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

      var panel = document.getElementById('tx-viz-panel');
      var gc = '#22c55e', rc = '#ef4444', bc = '#58a6ff';
      panel.innerHTML = '<div style="display:flex;gap:8px">' +
        '<div class="stat-item"><div class="s-label">总盈亏</div><div class="s-value" style="font-size:16px;color:'+gc+'">'+vs+'</div><div class="s-sub">'+fmtCNY(pnlSum)+'</div></div>' +
        '<div class="stat-item"><div class="s-label">盈利天数</div><div class="s-value" style="font-size:16px;color:'+gc+'">'+gainDays+'天</div><div class="s-sub">占 '+Math.round(gainDays/dates.length*100)+'%</div></div>' +
        '<div class="stat-item"><div class="s-label">最大日盈利</div><div class="s-value" style="font-size:16px;color:'+gc+'">+$'+maxGain.toFixed(2)+'</div><div class="s-sub">'+maxGainDate+'</div></div>' +
        '<div class="stat-item"><div class="s-label">最大日亏损</div><div class="s-value" style="font-size:16px;color:'+rc+'">-$'+Math.abs(maxLoss).toFixed(2)+'</div><div class="s-sub">'+maxLossDate+'</div></div>' +
      '</div>';

      // Chart 1: Cumulative
      var chart1 = document.createElement('div');
      chart1.className = 'section';
      chart1.innerHTML = '<div class="section-head">📈 累计盈亏曲线</div><div style="padding:12px"><div style="height:160px"><canvas id="txCumChart"></canvas></div></div>';
      panel.appendChild(chart1);

      // Chart 2: Daily bar
      var chart2 = document.createElement('div');
      chart2.className = 'section';
      chart2.innerHTML = '<div class="section-head">📊 每日盈亏</div><div style="padding:12px"><div style="height:130px"><canvas id="txPnlChart"></canvas></div></div>';
      panel.appendChild(chart2);

      // Heatmap
      var cal = document.createElement('div');
      cal.className = 'section';
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

      // Monthly calendar
      var sc = document.createElement('div');
      sc.className = 'section';
      var monthMap = {{}};
      for (var i = 0; i < __rawOps.length; i++) {{
        var op = __rawOps[i];
        if (op.type !== 'close') continue;
        var m = op.date.substring(0,7);
        if (!monthMap[m]) monthMap[m] = {{}};
        monthMap[m][op.date.substring(0,10)] = (monthMap[m][op.date.substring(0,10)] || 0) + (op.profit || 0);
      }}
      for (var i = 0; i < __rawOps.length; i++) {{
        var op = __rawOps[i], m = op.date.substring(0,7);
        if (!monthMap[m]) monthMap[m] = {{}};
        monthMap[m][op.date.substring(0,10)] = monthMap[m][op.date.substring(0,10)] || 0;
      }}
      var monthsSorted = Object.keys(monthMap).sort().reverse();
      var thisMonth = (new Date().getFullYear())+'-'+String(new Date().getMonth()+1).padStart(2,'0');
      var thisMonthPnl = 0;
      if (monthMap[thisMonth]) for (var k in monthMap[thisMonth]) thisMonthPnl += monthMap[thisMonth][k];

      var scHtml = '<div class="section-head">🗓 盈亏日历 <span style="font-size:10px;color:var(--text3);font-weight:400">每日盈亏金额(USD)</span></div><div style="padding:12px">';
      scHtml += '<div style="display:flex;gap:16px;margin-bottom:10px;font-size:11px;flex-wrap:wrap">' +
        '<div>本月盈亏: <strong style="color:'+(thisMonthPnl>=0?gc:rc)+'">'+(thisMonthPnl>=0?'+':'')+'$'+thisMonthPnl.toFixed(2)+'</strong></div>' +
        '<div>总盈亏: <strong style="color:'+(pnlSum>=0?gc:rc)+'">'+vs+'</strong></div>' +
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

      // Build Chart.js charts
      try {{
        var cumCtx = document.getElementById('txCumChart').getContext('2d');
        var chartText = getComputedStyle(document.body).getPropertyValue('--text3').trim();
        var chartGrid = document.body.classList.contains('theme-dark') ? 'rgba(128,145,160,.18)' : 'rgba(91,119,139,.16)';
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
              plugins: {{ legend: {{ display: false }}, tooltip: {{ callbacks: {{ label: function(ctx) {{ return '累计: '+(ctx.raw>=0?'+':'')+'$'+ctx.raw.toFixed(2)+'  ('+fmtCNY(ctx.raw)+')'; }} }} }} }},
              scales: {{ x: {{ ticks: {{ color:chartText, font:{{size:9}}, maxTicksLimit:8 }}, grid:{{ color:chartGrid }} }}, y: {{ ticks: {{ color:chartText, font:{{size:9}}, callback: function(v){{return '$'+v;}} }}, grid:{{ color:chartGrid }} }} }}
            }}
          }});

          var pnlCtx = document.getElementById('txPnlChart').getContext('2d');
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
              plugins: {{ legend: {{ display: false }}, tooltip: {{ callbacks: {{ label: function(ctx) {{ return (ctx.raw>=0?'+':'')+'$'+ctx.raw.toFixed(2)+'  ('+fmtCNY(ctx.raw)+')'; }} }} }} }},
              scales: {{ x: {{ ticks: {{ color:chartText, font:{{size:9}}, maxRotation:45, maxTicksLimit:14 }}, grid:{{ color:chartGrid }} }}, y: {{ ticks: {{ color:chartText, font:{{size:9}}, callback: function(v){{return '$'+v;}} }}, grid:{{ color:chartGrid }} }} }}
            }}
          }});
        }}
      }} catch(e) {{ console.log('Chart error:', e); }}
    }})();
    </script>"""

    # ── 顶部页面头 ──────────────────────────────────────
    pnl_sign = "+" if total_pnl >= 0 else ""
    meta_info = f"""<header class='page-header page-header-row'>
        <div class='page-heading'><div class='page-title'>交易记录</div><div class='page-subtitle'>集中记录持仓、平仓结果与已实现盈亏</div></div>
        <div class='page-actions'><span class='pill success'><span class='status-dot'></span>本地账本</span><button class='btn btn-primary' onclick='toggleTradeAdd()'>＋ 新增交易</button></div>
    </header>
    <div class='trade-summary'>
      <div class='stat-item'><div class='s-label'>当前持仓</div><div class='s-value c-blue'>{len(open_pos)}</div><div class='s-sub'>个未平仓记录</div></div>
      <div class='stat-item'><div class='s-label'>交易记录</div><div class='s-value'>{len(trade_ops)}</div><div class='s-sub'>累计操作</div></div>
      <div class='stat-item'><div class='s-label'>累计投入</div><div class='s-value'>${total_invest:,.2f}</div><div class='s-sub'>开仓与加仓</div></div>
      <div class='stat-item'><div class='s-label'>累计盈亏</div><div class='s-value' style='color:{pnl_cls}'>{pnl_sign}${total_pnl:,.2f}</div><div class='s-sub'>¥{total_pnl * 6.66:,.2f} CNY</div></div>
    </div>
    <style>.trade-modal-panel{{display:none;position:fixed!important;z-index:51;left:50%;top:50%;transform:translate(-50%,-50%);width:min(900px,calc(100vw - 32px));background:var(--bg2);border:1px solid var(--border)!important;border-radius:13px;box-shadow:0 24px 70px rgba(0,0,0,.25)}}.trade-modal-panel.visible{{display:block!important}}.trade-modal-backdrop{{display:none;position:fixed;inset:0;z-index:50;background:rgba(8,17,28,.5)}}.trade-modal-backdrop.visible{{display:block}}body.theme-dark .trade-modal-panel{{background:#161b22;border-color:#30363d!important}}</style><div id='trade-modal-backdrop' class='trade-modal-backdrop' onclick='toggleTradeAdd()'></div><script>function toggleTradeAdd(){{var form=document.getElementById('trade-add-form'),back=document.getElementById('trade-modal-backdrop'),visible=form.classList.toggle('visible');back.classList.toggle('visible',visible)}}</script>"""

    content = meta_info + pos_section + op_section

    from templates import LAYOUT
    return render_template_string(LAYOUT, section="trade-log", now=now_str(), content=content)


# ── API 操作 ─────────────────────────────────────────────

def trade_add():
    """添加交易记录（开仓）"""
    proj = _trade_data()

    pair = request.form.get("token_pair", "").strip()
    direction = request.form.get("direction", "做多")
    market_type = "contract" if request.form.get("market_type") == "contract" else "spot"
    try:
        leverage = max(1.0, float(request.form.get("leverage", 1) or 1)) if market_type == "contract" else 1.0
        amt = float(request.form.get("trade_amount", 0) or 0)
        fees = float(request.form.get("fees", 0) or 0)
        entry_value = float(request.form.get("entry_price", 0) or 0)
    except (TypeError, ValueError):
        return redirect("/trade-log")
    entry_price = request.form.get("entry_price", "")
    open_date = request.form.get("open_date", today_str())
    note = request.form.get("note", "").strip()

    if not pair or amt <= 0 or entry_value <= 0:
        return redirect("/trade-log")

    pos_id = str(time.time_ns())
    if entry_price:
        note = f"入场价={entry_price}" + (" | " + note if note else "")

    # Add position
    positions = proj.get("trade_positions", [])
    positions.append({
        "id": pos_id,
        "token_pair": pair,
        "direction": direction,
        "market_type": market_type,
        "leverage": leverage,
        "quantity": amt * leverage / entry_value,
        "trade_amount": amt,
        "current_balance": amt,
        "fees": fees,
        "entry_price": entry_price,
        "open_date": open_date,
        "status": "open",
        "note": note
    })
    proj["trade_positions"] = positions

    # Add operation record
    ops = proj.get("trade_operations", [])
    ops.append({
        "id": pos_id,
        "type": "open",
        "date": open_date,
        "token_pair": pair,
        "direction": direction,
        "market_type": market_type,
        "leverage": leverage,
        "quantity": amt * leverage / entry_value,
        "principal": amt,
        "unit_price": entry_value,
        "profit": 0,
        "fees": fees,
        "duration": "",
        "note": note
    })
    proj["trade_operations"] = ops

    # Update invest
    total_trade = sum(float(position.get("trade_amount") or 0) for position in positions if position.get("status") == "open")
    proj["invest"] = str(total_trade)
    proj["updated"] = now_str()

    _save_trade(proj)
    return _trade_redirect(result="added")


def trade_adjust_position():
    """Record an additional buy or a partial/full sale against an aggregated holding."""
    from routes.trade_portfolio import apply_sale, holding_duration, lots_for_group, number

    project = _trade_data()
    positions = project.get("trade_positions", [])
    operations = project.get("trade_operations", [])
    group_id = request.form.get("group_id", "")
    action = request.form.get("action", "")
    trade_date = request.form.get("trade_date", today_str())
    note = request.form.get("note", "").strip()
    try:
        quantity = float(request.form.get("quantity", 0) or 0)
        unit_price = float(request.form.get("unit_price", 0) or 0)
        fees = max(0.0, float(request.form.get("fees", 0) or 0))
    except (TypeError, ValueError):
        return _trade_redirect(error="数量、单价或手续费格式不正确")
    if quantity <= 0 or unit_price <= 0:
        return _trade_redirect(error="数量和单价必须大于 0")
    lots = lots_for_group(positions, group_id)
    if not lots:
        return _trade_redirect(error="未找到对应的活跃持仓")
    reference = lots[0]
    market_type = "contract" if reference.get("market_type") == "contract" else "spot"
    leverage = max(1.0, number(reference.get("leverage", 1))) if market_type == "contract" else 1.0
    pair = reference.get("token_pair", "")
    direction = reference.get("direction", "做多")
    operation_id = str(time.time_ns())

    if action == "buy":
        principal = quantity * unit_price / leverage
        positions.append({
            "id": operation_id,
            "token_pair": pair,
            "direction": direction,
            "market_type": market_type,
            "leverage": leverage,
            "quantity": quantity,
            "trade_amount": principal,
            "current_balance": principal,
            "fees": fees,
            "entry_price": unit_price,
            "open_date": trade_date,
            "status": "open",
            "note": note,
        })
        operations.append({
            "id": operation_id,
            "type": "buy",
            "date": trade_date,
            "token_pair": pair,
            "direction": direction,
            "market_type": market_type,
            "leverage": leverage,
            "quantity": quantity,
            "unit_price": unit_price,
            "principal": principal,
            "profit": 0,
            "fees": fees,
            "duration": "",
            "note": note or f"买入 {quantity:g} @ ${unit_price:g}",
        })
        result = "bought"
    elif action == "sell":
        try:
            sale = apply_sale(positions, group_id, quantity, unit_price, fees, trade_date)
        except ValueError as error:
            return _trade_redirect(error=str(error))
        group = sale["group"]
        operations.append({
            "id": operation_id,
            "type": "sell",
            "date": trade_date,
            "token_pair": pair,
            "direction": direction,
            "market_type": market_type,
            "leverage": leverage,
            "quantity": sale["quantity"],
            "unit_price": unit_price,
            "average_entry": sale["average_entry"],
            "principal": sale["released_principal"],
            "proceeds": sale["proceeds"],
            "profit": sale["profit"],
            "fees": fees,
            "duration": holding_duration(group.get("open_date"), trade_date),
            "note": note or f"卖出 {sale['quantity']:g} @ ${unit_price:g}",
        })
        result = "closed" if sale["fully_closed"] else "sold"
    else:
        return _trade_redirect(error="不支持的持仓操作")

    project["trade_positions"] = positions
    project["trade_operations"] = operations
    project["invest"] = str(sum(number(position.get("trade_amount")) for position in positions if position.get("status") == "open"))
    project["earn"] = str(sum(number(operation.get("profit")) for operation in operations if operation.get("type") in ("sell", "close")))
    project["updated"] = now_str()
    _save_trade(project)
    return _trade_redirect(result=result)


def trade_prices_api():
    """Return partial live quotes without writing external values to the ledger."""
    from routes.market_prices import quote_positions
    from routes.trade_portfolio import aggregate_positions
    project = _trade_data()
    force = request.args.get("force") == "1"
    quotes = quote_positions(aggregate_positions(project.get("trade_positions", [])), force=force)
    ok_count = sum(1 for item in quotes.values() if item.get("status") == "ok")
    return jsonify({
        "quotes": quotes,
        "ok_count": ok_count,
        "total": len(quotes),
        "updated_at": now_str(),
    })


def trade_close():
    """平仓"""
    proj = _trade_data()

    pos_id = request.form.get("pos_id", "")
    close_balance = float(request.form.get("close_balance", 0) or 0)
    close_fees = float(request.form.get("close_fees", 0) or 0)
    close_date = request.form.get("close_date", today_str())
    open_date = request.form.get("open_date", "")

    positions = proj.get("trade_positions", [])
    pos = next((p for p in positions if p["id"] == pos_id), None)
    if not pos:
        return redirect("/trade-log")

    initial = pos.get("trade_amount", 0)
    fees_collected = close_fees
    profit = (close_balance + fees_collected) - initial

    # Update position
    pos["status"] = "closed"
    pos["current_balance"] = close_balance
    pos["fees"] = fees_collected
    pos["close_date"] = close_date

    # Calculate duration
    duration = ""
    if open_date and close_date:
        try:
            d1 = datetime.strptime(open_date, "%Y-%m-%d")
            d2 = datetime.strptime(close_date, "%Y-%m-%d")
            diff = (d2 - d1).days
            duration = f"{diff}天" if diff == 1 else f"{diff}天"
        except:
            pass

    # Add close operation
    ops = proj.get("trade_operations", [])
    ops.append({
        "id": pos_id + "-close",
        "type": "close",
        "date": close_date,
        "token_pair": pos.get("token_pair", ""),
        "direction": pos.get("direction", "做多"),
        "market_type": "contract" if pos.get("market_type") == "contract" else "spot",
        "leverage": pos.get("leverage", 1),
        "principal": initial,
        "total_invested": initial,
        "profit": profit,
        "fees": 0,
        "claimed_fees": fees_collected,
        "duration": duration,
        "note": f"平仓盈亏 ${profit:.2f}" + (f" | 手续费 ${close_fees:.2f}" if close_fees else "")
    })
    proj["trade_operations"] = ops

    # Update earn
    total_profit = sum(op.get("profit", 0) for op in ops)
    proj["earn"] = str(max(0, total_profit))
    proj["updated"] = now_str()

    _save_trade(proj)
    return redirect("/trade-log")


def _build_trade_viz(ops, total_invest, total_pnl):
    """生成交易统计看板 HTML（备用，目前 JS 端已处理）"""
    return ""
