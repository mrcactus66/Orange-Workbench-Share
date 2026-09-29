import os
from flask import request, redirect, render_template_string, make_response
from datetime import datetime, timedelta
import json
from utils import load_json, save_json, today_str, now, now_str, get_standx_data, PROJECTS_FILE, get_all_tasks, is_due_within
from templates import LAYOUT

def _next_month(date_str):
    """计算下个月的日期（处理月末天数不同问题）"""
    d = datetime.strptime(date_str, "%Y-%m-%d")
    month = d.month + 1
    year = d.year
    if month > 12:
        month = 1
        year += 1
    last_day_of_month = datetime(year, month, 1) - timedelta(days=1)
    target_day = min(d.day, last_day_of_month.day)
    return d.replace(year=year, month=month, day=target_day).strftime("%Y-%m-%d")


def task_done(task_id):
    data = load_json(PROJECTS_FILE)
    all_tasks = data.get("tasks", [])
    task = next((t for t in all_tasks if t["id"] == task_id), None)
    if task:
        today = today_str()
        task["last_done"] = today
        freq = task.get("freq", "daily")
        if freq == "daily":
            d = datetime.strptime(today, "%Y-%m-%d")
            nd = (d + timedelta(days=1)).strftime("%Y-%m-%d")
        elif freq == "weekly":
            d = datetime.strptime(today, "%Y-%m-%d")
            nd = (d + timedelta(weeks=1)).strftime("%Y-%m-%d")
        elif freq == "monthly":
            nd = _next_month(today)
        elif freq == "one-time":
            nd = ""
        else:
            nd = (datetime.strptime(today, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
        task["next_due"] = nd
        task["next_run"] = nd
        save_json(PROJECTS_FILE, data)
    return redirect(request.args.get("next", "/?s=projects"))

def task_edit(task_id):
    data = load_json(PROJECTS_FILE)
    all_tasks = data.get("tasks", [])
    task = next((t for t in all_tasks if t["id"] == task_id), None)
    if not task:
        return "Task not found", 404
    if request.method == "POST":
        task["name"] = request.form.get("name", task.get("name", ""))
        task["freq"] = request.form.get("freq", task.get("freq", "daily"))
        task["note"] = request.form.get("note", task.get("note", ""))
        today = today_str()
        if task["freq"] == "daily":
            d = datetime.strptime(today, "%Y-%m-%d")
            task["next_due"] = (d + timedelta(days=1)).strftime("%Y-%m-%d")
            task["next_run"] = task["next_due"]
        elif task["freq"] == "weekly":
            d = datetime.strptime(today, "%Y-%m-%d")
            task["next_due"] = (d + timedelta(weeks=1)).strftime("%Y-%m-%d")
            task["next_run"] = task["next_due"]
        elif task["freq"] == "monthly":
            d = datetime.strptime(today, "%Y-%m-%d")
            month = d.month + 1
            year = d.year
            if month > 12:
                month = 1
                year += 1
            last_day = datetime(year, month, 1) - timedelta(days=1)
            target_day = min(d.day, last_day.day)
            task["next_due"] = d.replace(year=year, month=month, day=target_day).strftime("%Y-%m-%d")
            task["next_run"] = task["next_due"]
        save_json(PROJECTS_FILE, data)
        return redirect(request.args.get("next", "/?s=projects"))
    freq_options = [
        ("daily", "📅 每日"),
        ("weekly", "📆 每周"),
        ("monthly", "📆 每月"),
        ("one-time", "⭐ 一次性")
    ]
    freq_html = ""
    for val, label in freq_options:
        sel = "selected" if task.get("freq") == val else ""
        freq_html += f"<option value='{val}' {sel}>{label}</option>"
    edit_form = f"""
    <div style='max-width:500px;margin:30px auto;background:var(--bg2);border:1px solid var(--border);border-radius:10px;padding:24px'>
        <h2 style='font-size:18px;margin-bottom:20px'>✏️ 编辑任务</h2>
        <form method='post'>
            <div style='margin-bottom:16px'>
                <label style='display:block;font-size:12px;color:var(--text2);margin-bottom:6px'>任务名称</label>
                <input name='name' value='{task.get("name","")}' class='form-control' style='font-size:14px;padding:8px 12px' required>
            </div>
            <div style='margin-bottom:16px'>
                <label style='display:block;font-size:12px;color:var(--text2);margin-bottom:6px'>执行频率</label>
                <select name='freq' class='form-control' style='font-size:14px;padding:8px 12px'>
                    {freq_html}
                </select>
            </div>
            <div style='margin-bottom:20px'>
                <label style='display:block;font-size:12px;color:var(--text2);margin-bottom:6px'>备注</label>
                <textarea name='note' class='form-control' style='font-size:14px;padding:8px 12px;height:80px'>{task.get("note","")}</textarea>
            </div>
            <div style='display:flex;gap:10px'>
                <button type='submit' class='btn btn-primary' style='padding:8px 20px;font-size:14px'>💾 保存</button>
                <a href='{request.args.get("next", "/?s=projects")}' class='btn' style='padding:8px 20px;font-size:14px'>取消</a>
            </div>
        </form>
    </div>
    """
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset='utf-8'>
        <title>编辑任务</title>
        <style>
            body{{background:#0d1117;color:#e6edf3;font-family:-apple-system,sans-serif;padding:20px}}
            .form-control{{width:100%;padding:7px 10px;background:#161b22;border:1px solid #30363d;border-radius:6px;color:#e6edf3;font-size:13px;box-sizing:border-box}}
            .form-control:focus{{outline:none;border-color:#58a6ff}}
            .btn{{display:inline-block;padding:5px 12px;background:#21262d;border:1px solid #30363d;border-radius:6px;color:#e6edf3;font-size:12px;cursor:pointer;text-decoration:none}}
            .btn-primary{{background:#238636;color:#fff;border-color:#238636}}
            .btn-primary:hover{{background:#2ea043}}
            select.form-control{{appearance:auto}}
        </style>
    </head>
    <body>
        <a href='{request.args.get("next", "/?s=projects")}' style='color:#58a6ff;font-size:13px'>← 返回</a>
        {edit_form}
    </body>
    </html>
    """
