import os
from flask import request, redirect, render_template_string, make_response
from datetime import datetime, timedelta
import json
from utils import load_json, save_json, today_str, now, now_str, get_standx_data, PROJECTS_FILE, get_all_tasks, is_due_within
from templates import LAYOUT

def proj_plan_page(proj_id):
    data = load_json(PROJECTS_FILE)
    projects = data.get("projects", [])
    proj = next((p for p in projects if p["id"] == proj_id), None)
    if not proj:
        return redirect("/?s=projects")
    readme_path = proj.get("readme_path", "")
    plan_html = ""
    if readme_path and os.path.exists(readme_path):
        try:
            with open(readme_path, "r", encoding="utf-8") as f:
                readme_content = f.read()
            lines = readme_content.split("\n")
            in_table = False
            html_lines = []
            for line in lines:
                line = line.rstrip()
                if line.startswith("|") and "---" not in line:
                    if not in_table:
                        html_lines.append("<div style='overflow-x:auto;margin-bottom:16px'><table style='width:100%;border-collapse:collapse;font-size:13px;border-radius:8px;overflow:hidden'>")
                        in_table = True
                    cells = [c.strip() for c in line.split("|")[1:-1]]
                    if cells and cells[0]:
                        is_header = any(c for c in cells)
                        tag = "th" if in_table is False else "td"
                        row_bg = "background:var(--bg2);font-weight:600" if not in_table else ""
                        html_lines.append("<tr>" + "".join(f"<td style='padding:8px 12px;border:1px solid var(--border);{row_bg}'>" + c + "</td>" for c in cells) + "</tr>")
                        in_table = True
                else:
                    if in_table:
                        html_lines.append("</table></div>")
                        in_table = False
                    if line.startswith("# "):
                        html_lines.append(f"<h1 style='font-size:22px;font-weight:700;margin:20px 0 12px 0;color:var(--text);border-bottom:1px solid var(--border);padding-bottom:8px'>" + line[2:] + "</h1>")
                    elif line.startswith("## "):
                        html_lines.append(f"<h2 style='font-size:17px;font-weight:700;margin:18px 0 10px 0;color:var(--text)'>" + line[3:] + "</h2>")
                    elif line.startswith("### "):
                        html_lines.append(f"<h3 style='font-size:14px;font-weight:700;margin:14px 0 8px 0;color:var(--text)'>" + line[4:] + "</h3>")
                    elif line.startswith("- **"):
                        # bold list item
                        parts = line[3:].split("**", 1)
                        if len(parts) > 1:
                            bold_end = parts[1].find("**", 1)
                            if bold_end > 0:
                                bold_text = parts[1][:bold_end]
                                rest = parts[1][bold_end+2:]
                                html_lines.append(f"<li style='margin:6px 0 6px 20px;color:var(--text2);line-height:1.7'><strong style='color:var(--text)'>" + bold_text + "</strong>" + rest + "</li>")
                            else:
                                html_lines.append(f"<li style='margin:6px 0 6px 20px;color:var(--text2);line-height:1.7'>" + line[3:] + "</li>")
                        else:
                            html_lines.append(f"<li style='margin:6px 0 6px 20px;color:var(--text2);line-height:1.7'>" + line[3:] + "</li>")
                    elif line.startswith("- "):
                        html_lines.append(f"<li style='margin:6px 0 6px 20px;color:var(--text2);line-height:1.7'>" + line[2:] + "</li>")
                    elif line.startswith("> "):
                        html_lines.append(f"<blockquote style='border-left:3px solid var(--blue);padding:8px 14px;margin:10px 0;color:var(--text2);font-size:13px;background:var(--bg2);border-radius:4px;line-height:1.6'>" + line[2:] + "</blockquote>")
                    elif line.strip():
                        html_lines.append(f"<p style='margin:8px 0;line-height:1.7;color:var(--text2);font-size:14px'>" + line + "</p>")
            if in_table:
                html_lines.append("</table></div>")
            plan_html = "\n".join(html_lines)
        except Exception as e:
            plan_html = f"<div style='color:#ef4444;padding:20px'>加载失败: {e}</div>"
    else:
        plan_html = "<div style='padding:40px;text-align:center;color:var(--text3);font-size:14px'>暂无详细攻略文档</div>"
    chain_icon = {"BNB Chain":"🔶","Solana":"☀️","Base":"🔵","Fogo":"🔥","Aptos":"🟣","Miden":"⚪","Sui":"🔷"}.get(proj.get("chain",""),"🔗")
    return render_template_string(LAYOUT, title=chain_icon + " " + proj.get("name","") + " — 详细攻略", content="<div class='page-header' style='display:block'><a href='/proj/detail/" + proj_id + "' class='back-btn'>← 返回项目详情</a><div style='margin-top:10px;font-size:22px;font-weight:700'>📋 " + proj.get("name","") + " — 详细攻略</div></div><div style='margin-top:16px'>" + plan_html + "</div>")

def proj_detail_delete(proj_id):
    data = load_json(PROJECTS_FILE)
    data["projects"] = [p for p in data.get("projects",[]) if p["id"] != proj_id]
    data["tasks"] = [t for t in data.get("tasks",[]) if t.get("project_id") != proj_id]
    save_json(PROJECTS_FILE, data)
    return redirect("/?s=projects")

def proj_detail_edit(proj_id):
    data = load_json(PROJECTS_FILE)
    projects = data.get("projects", [])
    proj = next((p for p in projects if p["id"] == proj_id), None)
    if not proj:
        return redirect("/?s=projects")
    if request.method == "POST":
        proj["name"] = request.form.get("name","")
        proj["status"] = request.form.get("status","")
        proj["chain"] = request.form.get("chain","")
        proj["type"] = request.form.get("type","")
        proj["invest"] = float(request.form.get("invest","0") or 0)
        proj["gas_cost"] = float(request.form.get("gas_cost","0") or 0)
        proj["earn"] = float(request.form.get("earn","0") or 0)
        proj["next_renew"] = request.form.get("next_renew","")
        proj["stars"] = int(request.form.get("stars","3") or 3)
        proj["start_date"] = request.form.get("start_date","")
        proj["links"] = [l for l in request.form.get("links","").split("\n") if l.strip()]
        save_json(PROJECTS_FILE, data)
        return redirect(f"/proj/detail/{proj_id}")
    _links = proj.get("links", [])
    if isinstance(_links, dict):
        links_val = "\n".join(_links.values())
    elif isinstance(_links, list):
        links_val = "\n".join(entry.get("url","") if isinstance(entry,dict) else str(entry) for entry in _links)
    else:
        links_val = str(_links)
    content = (
        "<div class='page-header'><a href='/proj/detail/" + proj_id + "' class='back-btn'>← 返回</a><div class='page-title'>✏️ 编辑项目</div></div>"
        "<div class='section'><form method='post'>"
        "<div class='form-group'><label>项目名称</label><input name='name' value='" + proj.get("name","") + "' class='form-control' required></div>"
        "<div class='form-row'><div class='form-group'><label>状态</label><select name='status' class='form-control'>"
        "<option value='进行中'" + (" selected" if proj.get("status")=="进行中" else "") + ">进行中</option>"
        "<option value='准备中'" + (" selected" if proj.get("status")=="准备中" else "") + ">准备中</option>"
        "<option value='已完成'" + (" selected" if proj.get("status")=="已完成" else "") + ">已完成</option>"
        "</select></div>"
        "<div class='form-group'><label>链</label><input name='chain' value='" + proj.get("chain","") + "' class='form-control'></div>"
        "<div class='form-group'><label>类型</label><input name='type' value='" + proj.get("type","") + "' class='form-control'></div></div>"
        "<div class='form-row'><div class='form-group'><label>投入(U)</label><input name='invest' type='number' step='0.01' value='" + str(proj.get("invest","")) + "' class='form-control'></div>"
        "<div class='form-group'><label>Gas成本</label><input name='gas_cost' type='number' step='0.01' value='" + str(proj.get("gas_cost","")) + "' class='form-control'></div>"
        "<div class='form-group'><label>收益</label><input name='earn' type='number' step='0.01' value='" + str(proj.get("earn","")) + "' class='form-control'></div></div>"
        "<div class='form-row'><div class='form-group'><label>星级</label><input name='stars' type='number' min='1' max='5' value='" + str(proj.get("stars","3")) + "' class='form-control'></div>"
        "<div class='form-group'><label>开始日期</label><input name='start_date' type='date' value='" + proj.get("start_date","") + "' class='form-control'></div>"
        "<div class='form-group'><label>下次重要日期</label><input name='next_renew' type='date' value='" + proj.get("next_renew","") + "' class='form-control'></div></div>"
        "<div class='form-group'><label>链接 (每行一个)</label><textarea name='links' class='form-control' rows='3'>" + links_val + "</textarea></div>"
        "<button type='submit' class='btn btn-primary'>💾 保存</button> <a href='/proj/detail/" + proj_id + "' class='btn'>取消</a>"
        "</form></div>"
    )
    return render_template_string(LAYOUT, section="projects", now=now(), content=content,
        standx_ok=0, standx_total=0, ip_total=0, proj_total=len(projects))
