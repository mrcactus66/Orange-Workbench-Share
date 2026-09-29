import os, json, uuid
from flask import request, redirect, render_template_string
from datetime import datetime
from utils import now
from templates import LAYOUT
from runtime import data_file

MEMOS_FILE = str(data_file("memos_data.json"))

def load_memos():
    try:
        with open(MEMOS_FILE) as f:
            return json.load(f)
    except:
        return {"memos": []}

def save_memos(data):
    with open(MEMOS_FILE, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def memos_page():
    data = load_memos()
    memos = sorted(data.get("memos", []), key=lambda x: x.get("created", ""), reverse=True)

    edit_id = request.args.get("edit", "").strip()
    edit_memo = next((m for m in memos if m.get("id") == edit_id), None)

    # Build square cards grid
    cards = []
    for m in memos:
        cid = m.get("id", "")
        title = m.get("title", "")
        content = m.get("content", "") or ""
        created = m.get("created", "")
        updated = m.get("updated", "")
        content_html = content.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace("\n","<br>")
        time_str = created.split(" ")[0] if created else ""

        # Compact square-ish card
        cards.append(
            "<article class='memo-card' style='background:var(--bg2);border:1px solid var(--border);border-radius:10px;padding:14px;"
            "display:flex;flex-direction:column;gap:6px;min-height:120px;position:relative'>"
            "<div style='font-size:13px;font-weight:600;color:var(--text);word-break:break-word;line-height:1.3'>" + title + "</div>"
            "<div style='font-size:12px;color:var(--text2);line-height:1.5;flex:1;word-break:break-word;overflow:hidden;"
            "display:-webkit-box;-webkit-line-clamp:4;-webkit-box-orient:vertical'>" + content_html + "</div>"
            "<div style='display:flex;justify-content:space-between;align-items:center;margin-top:auto;padding-top:6px'>"
            "<span style='font-size:11px;color:var(--text3)'>" + time_str + "</span>"
            "<div class='memo-actions'>"
            "<a href='/memos?edit=" + cid + "' class='btn btn-sm' style='text-decoration:none'>编辑</a>"
            "<form method='post' action='/memos/del' style='display:inline' onsubmit='return confirm(\"删除？\")'>"
            "<input type='hidden' name='id' value='" + cid + "'>"
            "<button type='submit' class='btn btn-danger btn-sm'>删除</button>"
            "</form></div></div></article>"
        )

    card_html = "\n".join(cards)
    empty_html = (
        "<div class='empty-state' style='grid-column:1/-1'>"
        "<div class='empty-state-icon'>＋</div>"
        "<strong>还没有备忘</strong><p>记录临时想法、待办事项或重要信息</p>"
        "<button id='memo-empty-new' type='button' class='btn btn-primary'>新建第一条备忘</button>"
        "</div>"
    )

    # Edit form
    edit_form_html = ""
    if edit_memo:
        edit_form_html = (
            "<div id='memo-edit' class='memo-modal-panel' style='background:var(--bg2);border:1px solid var(--border)'>"
            "<div class='memo-modal-head'><div><div class='modal-title'>编辑备忘</div><div class='modal-subtitle'>更新标题和正文内容</div></div><button type='button' class='modal-close-button memo-close'>×</button></div>"
            "<form method='post' action='/memos/save' class='memo-modal-body'>"
            "<input type='hidden' name='id' value='" + edit_memo["id"] + "'>"
            "<div class='form-group'><label>标题</label>"
            "<input name='title' class='form-control' value='" + edit_memo.get("title","").replace("'","&#39;") + "' required maxlength='100' style='font-size:13px'>"
            "</div>"
            "<div class='form-group'><label>正文</label>"
            "<textarea name='content' class='form-control' rows='3' style='font-size:13px'>" + (edit_memo.get("content","") or '').replace("<","&lt;").replace(">","&gt;") + "</textarea>"
            "</div>"
            "<div class='memo-modal-footer'><a href='/memos' class='btn'>取消</a><button type='submit' class='btn btn-primary'>保存修改</button>"
            "</div></form></div>"
        )

    # New memo form
    new_form_html = (
        "<div id='memo-new' class='memo-modal-panel' style='background:var(--bg2);border:1px solid var(--border)'>"
        "<div class='memo-modal-head'><div><div class='modal-title'>新建备忘</div><div class='modal-subtitle'>快速记录一条新的信息</div></div><button type='button' class='modal-close-button memo-close'>×</button></div>"
        "<form method='post' action='/memos/save' class='memo-modal-body'>"
        "<input type='hidden' name='id' value=''>"
        "<div class='form-group'><label>标题</label><input name='title' class='form-control' placeholder='输入备忘标题' required maxlength='100'></div>"
        "<div class='form-group'><label>正文</label><textarea name='content' class='form-control' placeholder='输入正文内容（可选）' maxlength='500'></textarea></div>"
        "<div class='memo-modal-footer'><button type='button' class='btn memo-close'>取消</button><button type='submit' class='btn btn-primary'>保存备忘</button></div>"
        "</form></div>"
    )

    content = (
        "<style>"
        ".memo-workbench{display:flex;justify-content:space-between;gap:12px;align-items:center;margin-bottom:12px;padding:14px 16px;background:var(--bg2);border:1px solid var(--border);border-radius:13px}.memo-workbench h1{font-size:20px;margin:0}.memo-workbench p{font-size:11px;color:var(--text3);margin:3px 0 0}.memo-workbench button{background:#087cad;color:#fff;border:1px solid #087cad;border-radius:7px;padding:8px 12px;cursor:pointer;font:inherit;font-size:12px}.memo-workbench input{width:190px;padding:8px 10px;background:var(--bg3);border:1px solid var(--border);border-radius:7px;color:var(--text);font:inherit;font-size:12px}.memos-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:10px}.memo-card{display:flex;flex-direction:column;gap:6px;min-height:130px;transition:border-color .15s,box-shadow .15s}.memo-card:hover{border-color:var(--blue)!important;box-shadow:0 8px 20px rgba(29,78,110,.08);transform:translateY(-1px)}.memo-modal-panel{display:none!important;position:fixed;z-index:51;left:50%;top:50%;transform:translate(-50%,-50%);width:min(580px,calc(100vw - 32px));margin:0!important;box-shadow:0 24px 70px rgba(0,0,0,.25)}.memo-modal-panel.visible{display:block!important}.memo-backdrop{display:none;position:fixed;inset:0;background:rgba(8,17,28,.5);z-index:50}.memo-backdrop.visible{display:block}@media(max-width:640px){.memo-workbench{align-items:flex-start;flex-direction:column}.memo-workbench input{width:100%}}body.theme-dark .memo-workbench{background:#161b22;border-color:#30363d}body.theme-dark .memo-modal-panel{background:#161b22!important;border-color:#30363d!important}"
        "</style>"
        "<div class='memo-workbench workbench-header'><div class='page-heading'><h1 class='page-title'>备忘录</h1><p>" + str(len(memos)) + " 条记录 · 搜索、浏览和快速编辑</p></div><div class='page-actions'><input id='memo-search' class='form-control' placeholder='搜索备忘'><button id='memo-new-button' type='button' class='btn btn-primary'>＋ 新建备忘</button></div></div>"
        + new_form_html + edit_form_html + "<div id='memo-backdrop' class='memo-backdrop'></div>"
        + "<div class='memos-grid'>" + (card_html if cards else empty_html) + "</div>"
        + "<script>(function(){var back=document.getElementById('memo-backdrop'),panels=document.querySelectorAll('.memo-modal-panel');function close(){panels.forEach(function(p){p.classList.remove('visible')});back.classList.remove('visible')}function open(id){var panel=document.getElementById(id);if(panel){panel.classList.add('visible');back.classList.add('visible')}}document.getElementById('memo-new-button').onclick=function(){open('memo-new')};var emptyButton=document.getElementById('memo-empty-new');if(emptyButton)emptyButton.onclick=function(){open('memo-new')};document.querySelectorAll('.memo-close').forEach(function(button){button.onclick=close});back.onclick=close;document.addEventListener('keydown',function(e){if(e.key==='Escape')close()});var search=document.getElementById('memo-search');search.oninput=function(){var q=search.value.toLowerCase();document.querySelectorAll('.memo-card').forEach(function(card){card.style.display=card.textContent.toLowerCase().includes(q)?'':'none'})};if(document.getElementById('memo-edit'))open('memo-edit')})()</script>"
    )

    return render_template_string(LAYOUT, section="memos", now=now(), content=content,
        standx_ok=0, standx_total=0, ip_total=0, proj_total=0)

def memos_save():
    memo_id = request.form.get("id", "").strip()
    title = request.form.get("title", "").strip()
    content = request.form.get("content", "").strip()
    if not title:
        return redirect("/memos")
    data = load_memos()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    if memo_id:
        for m in data.get("memos", []):
            if m.get("id") == memo_id:
                m["title"] = title
                m["content"] = content
                m["updated"] = now_str
                break
    else:
        data.setdefault("memos", []).insert(0, {
            "id": str(uuid.uuid4())[:8],
            "title": title,
            "content": content,
            "created": now_str,
            "updated": now_str
        })
    save_memos(data)
    return redirect("/memos")

def memos_del():
    memo_id = request.form.get("id", "").strip()
    if memo_id:
        data = load_memos()
        data["memos"] = [m for m in data.get("memos", []) if m.get("id") != memo_id]
        save_memos(data)
    return redirect("/memos")
