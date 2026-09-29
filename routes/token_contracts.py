#!/usr/bin/env python3
"""常用代币合约管理"""
import os, json, time
from flask import request, render_template_string, make_response
from utils import load_json, save_json, now_str
from templates import LAYOUT

DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "token_contracts.json")

CHAINS = ["BSC", "ETH", "SOL", "Base", "Aptos", "Sui", "Fogo", "Arbitrum", "Polygon", "Avalanche", "RHOC"]

DEFAULT_CATEGORIES = [
    {"name": "股票代币", "tokens": []},
    {"name": "公链币", "tokens": []},
    {"name": "MEME币", "tokens": []},
    {"name": "DeFi币", "tokens": []},
    {"name": "AI代币", "tokens": []},
    {"name": "其他", "tokens": []}
]


def _load():
    data = load_json(DATA_FILE)
    if not data or "categories" not in data:
        return {"categories": DEFAULT_CATEGORIES}
    return data

def _save(data):
    save_json(DATA_FILE, data)

def token_contracts_page():
    data = _load()
    categories = data.get("categories", [])
    chains_options = "".join(f"<option value='{c}'>{c}</option>" for c in CHAINS)
    
    CAT_COLORS = ["#58a6ff", "#f0b90b", "#ff7b72", "#3fb950", "#d2a8ff", "#ffa657", "#79c0ff", "#ffc107", "#7ee787", "#ffa0a0"]
    cat_cards = ""
    for ci, cat in enumerate(categories):
        name = cat.get("name", "")
        tokens = cat.get("tokens", [])
        color = CAT_COLORS[ci % len(CAT_COLORS)]
        token_list = ""
        for ti, tok in enumerate(tokens):
            tname = tok.get("name", "")
            addr = tok.get("address", "")
            chain = tok.get("chain", "BSC")
            token_list += f"""<div class='tok-item' data-name='{tname.lower()}' data-addr='{addr.lower()}' data-chain='{chain}'>
                <div class='tok-left'><span class='tok-name'>{tname}</span><span class='chain-tag'>{chain}</span><span class='tok-price' data-price=''>—</span></div>
                <div class='tok-addr-full' onclick="copyAddr('{addr}')" title='点击复制'>{addr}</div>
                <div class='tok-ops'>
                    <button class='btn btn-sm' style='font-size:9px;padding:1px 5px;background:transparent;border:none;color:#f85149;cursor:pointer' onclick="delToken({ci},{ti})" title='删除'>✕</button>
                </div>
            </div>"""
        
        if not token_list:
            token_list = "<div style='text-align:center;color:var(--text3);padding:12px;font-size:11px'>暂无代币</div>"
        
        cat_cards += f"""
        <div class='cat-card{' is-empty' if not tokens else ''}'>
            <div class='cat-head'>
                <span class='cat-title'><span id='cat-name-{ci}'>{name}</span> <span class='badge'>{len(tokens)}</span></span>
                <div style='display:flex;gap:4px'>
                    <button class='btn btn-sm' onclick="renameCategory({ci})" title='重命名'>编辑</button>
                    <button class='btn btn-sm' onclick="showAddForm({ci})" title='添加代币'>＋</button>
                    <button class='btn btn-sm btn-danger' onclick="delCategory({ci})" title='删除分类'>×</button>
                </div>
            </div>
            <div class='cat-body'>
                {token_list}
            </div>
            <div id='add-form-{ci}' style='display:none;border-top:1px solid var(--border);padding:8px 10px'>
                <form method='post' action='/token-contracts/add'>
                    <input type='hidden' name='cat_idx' value='{ci}'>
                    <div class='form-group' style='margin-bottom:6px'>
                        <input name='tok_name' class='form-control' style='font-size:11px' placeholder='名称' required>
                    </div>
                    <div class='form-group' style='margin-bottom:6px'>
                        <input name='tok_address' class='form-control tok-addr-input' style='font-size:11px;font-family:monospace' placeholder='🔍 粘贴合约地址自动补全' required>
                    </div>
                    <div class='form-group' style='margin-bottom:6px'>
                        <select name='tok_chain' class='form-control' style='font-size:11px'>
                            {chains_options}
                        </select>
                    </div>
                    <div style='display:flex;gap:4px'>
                        <button type='submit' class='btn btn-primary btn-sm' style='font-size:10px;padding:2px 8px'>✅ 保存</button>
                        <button type='button' class='btn btn-sm' style='font-size:10px;padding:2px 8px' onclick="document.getElementById('add-form-{ci}').style.display='none'">取消</button>
                    </div>
                </form>
            </div>
        </div>"""
    
    def_chain_opts = "".join(f"<option value='{c}' {'selected' if c=='BSC' else ''}>{c}</option>" for c in CHAINS)
    
    content = f"""
    <header class='page-header page-header-row'>
        <div class='page-heading'><div class='page-title'>常用代币合约</div><div class='page-subtitle'>按分类和链管理常用合约地址，点击地址即可复制</div></div>
        <div class='page-actions'><button class='btn' type='button' onclick='showCategoryManager()'>分类管理</button><button class='btn btn-primary' type='button' onclick='showAllAddForm()'>＋ 添加代币</button></div>
    </header>

    <div class='token-toolbar'>
        <input id='token-search' class='form-control' placeholder='搜索代币名称或地址'>
        <select id='token-chain-filter' class='form-control'><option value=''>全部链</option>{''.join(f"<option value='{chain}'>{chain}</option>" for chain in CHAINS)}</select>
        <span id='token-filter-count' class='pill info'></span>
    </div>

    <div id='quick-add-form' style='display:none;background:var(--bg2);border:1px solid var(--border);border-radius:10px;padding:16px;margin-bottom:16px'>
        <form method='post' action='/token-contracts/add'>
            <div class='memo-modal-head'><div><div class='modal-title'>添加代币</div><div class='modal-subtitle'>保存名称、合约地址、链和分类</div></div><button type='button' class='modal-close-button' onclick='hideAllAddForm()'>×</button></div>
            <div class='token-modal-body'>
            <div class='form-row'>
                <div class='form-group'>
                    <label>代币名称</label>
                    <input name='tok_name' class='form-control' style='font-size:12px' placeholder='例如：TSLA' required>
                </div>
                <div class='form-group' style='flex:2'>
                    <label>合约地址</label>
                    <input name='tok_address' class='form-control tok-addr-input' style='font-size:12px;font-family:monospace' placeholder='🔍 粘贴合约地址自动补全' required>
                </div>
                <div class='form-group' style='width:120px'>
                    <label>所属链</label>
                    <select name='tok_chain' class='form-control' style='font-size:12px'>
                        {def_chain_opts}
                    </select>
                </div>
                <div class='form-group' style='width:160px'>
                    <label>分类</label>
                    <select name='cat_idx' class='form-control' style='font-size:12px'>
                        {''.join(f"<option value='{ci}'>{c.get('name','')}</option>" for ci, c in enumerate(categories))}
                    </select>
                </div>
            </div>
            <div style='display:flex;justify-content:flex-end;gap:6px'>
                <button type='submit' class='btn btn-primary'>保存代币</button>
                <button type='button' class='btn btn-sm' onclick="hideAllAddForm()">取消</button>
            </div>
            </div>
        </form>
    </div>

    <div class='cat-grid'>{cat_cards}</div>

    <div id='category-management' class='category-management-modal'>
        <div class='section-head'><span>分类管理</span><button class='modal-close-button' type='button' onclick='hideCategoryManager()'>×</button></div>
        <div class='category-modal-body'>
            <form method='post' action='/token-contracts/add-category' style='display:flex;gap:6px;align-items:flex-end'>
                <div class='form-group' style='margin:0;flex:1'>
                    <label style='font-size:11px;color:var(--text3)'>新增分类名称</label>
                    <input name='cat_name' class='form-control' style='font-size:12px' placeholder='例如：GameFi代币' required>
                </div>
                <button type='submit' class='btn btn-primary'>添加分类</button>
            </form>
        </div>
    </div>

    <style>
    .cat-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}}
    .cat-card{{background:var(--bg2);border:1px solid var(--border);border-radius:10px;overflow:hidden;display:flex;flex-direction:column}}
    .cat-head{{display:flex;justify-content:space-between;align-items:center;padding:8px 10px;border-bottom:1px solid var(--border);flex-shrink:0}}
    .cat-title{{font-size:12px;font-weight:600}}
    .cat-title .badge{{background:currentColor !important;color:var(--bg2) !important}}
    .cat-body{{flex:1;overflow-y:auto;max-height:420px;scrollbar-width:thin}}
    .cat-body::-webkit-scrollbar{{width:4px}}
    .cat-body::-webkit-scrollbar-thumb{{background:var(--border);border-radius:2px}}
    .tok-item{{display:flex;align-items:flex-start;padding:6px 10px;border-bottom:1px solid rgba(48,54,61,0.4);font-size:11px}}
    .tok-item:last-child{{border-bottom:none}}
    .tok-left{{display:flex;align-items:center;gap:4px;min-width:0;flex-shrink:0}}
    .tok-name{{font-weight:600;white-space:nowrap}}
    .tok-addr-full{{flex:1;font-family:monospace;font-size:10px;color:var(--text2);margin:0 6px;word-break:break-all;line-height:1.4;cursor:pointer;transition:color 0.15s}}
    .tok-addr-full:hover{{color:var(--blue);text-decoration:underline}}
    .tok-addr-full:active{{opacity:0.6}}
    .tok-price{{font-size:10px;color:var(--text3);margin-left:4px;white-space:nowrap}}
    .tok-price.loaded{{color:#3fb950;font-weight:600}}
    .tok-ops{{display:flex;gap:2px;flex-shrink:0;padding-top:1px}}
    .chain-tag{{display:inline-block;padding:1px 6px;border-radius:8px;font-size:9px;font-weight:600;background:rgba(88,166,255,0.15);color:#58a6ff;white-space:nowrap}}
    body.theme-dark .chain-tag{{background:rgba(9,105,217,0.1);color:#0969da}}
    .tok-item:hover{{background:rgba(255,255,255,0.03)}}
    #quick-add-form.quick-modal{{display:block!important;position:fixed;z-index:51;left:50%;top:50%;transform:translate(-50%,-50%);width:min(760px,calc(100vw - 32px));margin:0!important;box-shadow:0 24px 70px rgba(0,0,0,.25)}}
    .token-modal-backdrop{{display:none;position:fixed;inset:0;z-index:50;background:rgba(8,17,28,.5)}}.token-modal-backdrop.visible{{display:block}}
    body.theme-dark #quick-add-form.quick-modal{{background:#161b22!important;border-color:#30363d!important}}
    </style>

    <script>
    function showAddForm(ci) {{
        var f = document.getElementById('add-form-'+ci);
        if (f) f.style.display = f.style.display === 'none' ? 'block' : 'none';
    }}
    function showAllAddForm() {{
        var f = document.getElementById('quick-add-form');
        f.classList.add('quick-modal');
        document.getElementById('token-modal-backdrop').classList.add('visible');
    }}
    function hideAllAddForm() {{
        document.getElementById('quick-add-form').classList.remove('quick-modal');
        document.getElementById('token-modal-backdrop').classList.remove('visible');
    }}
    function showCategoryManager() {{
        document.getElementById('category-management').classList.add('visible');
        document.getElementById('token-modal-backdrop').classList.add('visible');
    }}
    function hideCategoryManager() {{
        document.getElementById('category-management').classList.remove('visible');
        document.getElementById('token-modal-backdrop').classList.remove('visible');
    }}
    function closeTokenModals() {{ hideAllAddForm(); hideCategoryManager(); }}
    function filterTokens() {{
        var query = document.getElementById('token-search').value.trim().toLowerCase();
        var chain = document.getElementById('token-chain-filter').value;
        var visible = 0;
        document.querySelectorAll('.cat-card').forEach(function(card) {{
            var cardVisible = false;
            card.querySelectorAll('.tok-item').forEach(function(item) {{
                var matchesText = !query || item.dataset.name.includes(query) || item.dataset.addr.includes(query);
                var matchesChain = !chain || item.dataset.chain === chain;
                item.hidden = !(matchesText && matchesChain);
                if (!item.hidden) {{ cardVisible = true; visible++; }}
            }});
            card.hidden = !cardVisible;
        }});
        document.getElementById('token-filter-count').textContent = visible + ' 个代币';
    }}
    function copyAddr(addr) {{
        // Use textarea fallback (works on HTTP, not just HTTPS)
        var ta = document.createElement('textarea');
        ta.value = addr;
        ta.style.position = 'fixed';
        ta.style.left = '-9999px';
        document.body.appendChild(ta);
        ta.select();
        ta.setSelectionRange(0, 99999);
        try {{
            document.execCommand('copy');
            var tip = document.createElement('div');
            tip.textContent = '✅ 已复制';
            tip.style.cssText = 'position:fixed;top:20px;left:50%;transform:translateX(-50%);background:#238636;color:#fff;padding:8px 20px;border-radius:8px;font-size:13px;z-index:9999;box-shadow:0 4px 12px rgba(0,0,0,0.3)';
            document.body.appendChild(tip);
            setTimeout(function() {{ tip.remove(); }}, 1500);
        }} catch(e) {{
            alert('复制失败，请手动复制');
        }}
        document.body.removeChild(ta);
    }}
    function delToken(ci, ti) {{
        if (!confirm('确定删除该代币？')) return;
        var fd = new FormData();
        fd.append('cat_idx', ci);
        fd.append('tok_idx', ti);
        fetch('/token-contracts/del', {{method:'POST', body:fd}}).then(function(r) {{
            if (r.ok) location.reload();
            else alert('删除失败');
        }});
    }}
    function renameCategory(ci) {{
        var cur = document.getElementById('cat-name-'+ci).textContent;
        var name = prompt('重命名分类：', cur);
        if (!name || name.trim() === '' || name.trim() === cur) return;
        var fd = new FormData();
        fd.append('cat_idx', ci);
        fd.append('cat_name', name.trim());
        fetch('/token-contracts/rename-category', {{method:'POST', body:fd}}).then(function(r) {{
            if (r.ok) location.reload();
            else alert('重命名失败');
        }});
    }}
    function delCategory(ci) {{
        if (!confirm('确定删除整个分类（含其下所有代币）？')) return;
        var fd = new FormData();
        fd.append('cat_idx', ci);
        fetch('/token-contracts/del-category', {{method:'POST', body:fd}}).then(function(r) {{
            if (r.ok) location.reload();
            else alert('删除失败');
        }});
    }}

    // 粘贴合约地址自动补全代币名称
    document.addEventListener('paste', function(e) {{
        var el = e.target;
        if (!el.classList.contains('tok-addr-input')) return;
        setTimeout(function() {{
            var addr = el.value.trim();
            if (!addr || addr.length < 20) return;
            // 显示加载状态
            var origPlaceholder = el.placeholder;
            el.placeholder = '⏳ 查询中...';
            fetch('https://api.dexscreener.com/latest/dex/tokens/' + encodeURIComponent(addr))
                .then(function(r) {{ return r.json(); }})
                .then(function(data) {{
                    var pairs = data.pairs;
                    if (pairs && pairs.length > 0) {{
                        var tok = pairs[0].baseToken;
                        var name = tok.symbol || tok.name || '';
                        var chainId = pairs[0].chainId || '';
                        if (name) {{
                            // 找到对应的名称输入框（父容器内的第一个name输入）
                            var form = el.closest('form');
                            if (form) {{
                                var nameInput = form.querySelector('input[name=tok_name]');
                                if (nameInput && !nameInput.value) {{
                                    nameInput.value = name;
                                    nameInput.style.borderColor = '#3fb950';
                                    setTimeout(function() {{ nameInput.style.borderColor = ''; }}, 2000);
                                }}
                            }}
                            el.style.borderColor = '#3fb950';
                            setTimeout(function() {{ el.style.borderColor = ''; }}, 2000);
                        }}
                    }}
                    el.placeholder = origPlaceholder;
                }})
                .catch(function() {{
                    el.placeholder = origPlaceholder;
                }});
        }}, 100);
    }});

    // 加载页面时通过后端拉取代币价格
    function fetchAllPrices() {{
        var items = document.querySelectorAll('.tok-item[data-addr]');
        items.forEach(function(item) {{
            var priceSpan = item.querySelector('.tok-price');
            if (priceSpan) priceSpan.textContent = '⏳';
        }});
        fetch('/token-contracts/api/prices')
            .then(function(r) {{ return r.json(); }})
            .then(function(prices) {{
                var items = document.querySelectorAll('.tok-item[data-addr]');
                items.forEach(function(item) {{
                    var addr = item.getAttribute('data-addr').toLowerCase();
                    var priceSpan = item.querySelector('.tok-price');
                    if (!priceSpan) return;
                    if (prices[addr]) {{
                        priceSpan.textContent = prices[addr];
                        priceSpan.classList.add('loaded');
                    }} else {{
                        priceSpan.textContent = '—';
                    }}
                }});
            }})
            .catch(function() {{
                document.querySelectorAll('.tok-price').forEach(function(s) {{ s.textContent = '—'; }});
            }});
    }}
    // 页面加载后延时执行
    document.getElementById('token-search').addEventListener('input', filterTokens);
    document.getElementById('token-chain-filter').addEventListener('change', filterTokens);
    filterTokens();
    setTimeout(fetchAllPrices, 300);
    </script><div id='token-modal-backdrop' class='token-modal-backdrop' onclick='closeTokenModals()'></div>
    """

    return render_template_string(LAYOUT, section="token-contracts", now=now_str(), content=content)


def token_add():
    data = _load()
    cat_idx = int(request.form.get("cat_idx", 0))
    name = request.form.get("tok_name", "").strip()
    address = request.form.get("tok_address", "").strip()
    chain = request.form.get("tok_chain", "BSC")
    if not name or not address:
        return redirect_back()
    categories = data.get("categories", [])
    if cat_idx < len(categories):
        categories[cat_idx]["tokens"].append({
            "name": name,
            "address": address,
            "chain": chain
        })
    _save(data)
    return redirect_back()


def api_prices():
    """后端多渠道获取代币价格，返回 {address: price_str}"""
    import urllib.request, urllib.error
    
    def _fmt_price(p):
        if p >= 10000: return f"${p:,.0f}"
        if p >= 1: return f"${p:.2f}"
        if p >= 0.01: return f"${p:.4f}"
        if p >= 0.0001: return f"${p:.6f}"
        return f"${p:.8f}"
    
    # 读取所有代币（带链信息+分类+名称）
    data = _load()
    addr_info = []  # [(address, chain, category, symbol), ...]
    for cat in data.get("categories", []):
        cat_name = cat.get("name", "")
        for tok in cat.get("tokens", []):
            addr = tok.get("address", "").strip()
            chain = tok.get("chain", "BSC")
            symbol = tok.get("name", "").strip().upper()
            if addr and len(addr) >= 20:
                addr_info.append((addr.lower(), chain.upper(), cat_name, symbol))
    
    if not addr_info:
        return json.dumps({})
    
    # 按地址去重（保留第一个链信息）
    seen = set()
    unique = []
    for addr, chain, cat_name, symbol in addr_info:
        if addr not in seen:
            seen.add(addr)
            unique.append((addr, chain, cat_name, symbol))
    
    results = {}
    
    # ── 渠道1（股票代币优先）：币安现货 API ──
    stock_addrs = [(a, s) for a, c, cn, s in unique if cn == "股票代币" and a not in results]
    if stock_addrs:
        for addr, symbol in stock_addrs:
            try:
                symbol_pair = f"{symbol}USDT"
                url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol_pair}"
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                resp = urllib.request.urlopen(req, timeout=8)
                bp = json.loads(resp.read().decode())
                price = bp.get("price")
                if price:
                    p = float(price)
                    if p > 0 and addr not in results:
                        results[addr] = _fmt_price(p)
            except:
                pass
    
    # ── 渠道2（BSC优先）：Binance Alpha 官方 API ──
    try:
        alpha_req = urllib.request.Request(
            "https://www.binance.com/bapi/defi/v1/public/wallet-direct/buw/wallet/cex/alpha/all/token/list",
            headers={"User-Agent": "Mozilla/5.0"}
        )
        alpha_resp = urllib.request.urlopen(alpha_req, timeout=10)
        alpha_raw = json.loads(alpha_resp.read().decode())
        alpha_data = alpha_raw.get("data", []) or []
        alpha_prices = {}
        for item in alpha_data:
            addr = (item.get("contractAddress") or "").lower()
            chain = str(item.get("chainId") or "")
            price = item.get("price")
            if addr and chain == "56" and price and float(price) > 0:
                alpha_prices[addr] = float(price)
        for addr, ch, cn, s in unique:
            if ch == "BSC" and addr in alpha_prices and addr not in results:
                results[addr] = _fmt_price(alpha_prices[addr])
    except:
        pass
    
    # ── 渠道3（BSC补充）：DexScreener（BSC链DEX聚合）──
    bsc_addrs = [a for a, c, cn, s in unique if c == "BSC" and a not in results]
    for addr in bsc_addrs:
        try:
            url = "https://api.dexscreener.com/latest/dex/tokens/" + addr
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            resp = urllib.request.urlopen(req, timeout=8)
            raw = json.loads(resp.read().decode())
            pairs = raw.get("pairs", []) or []
            if pairs:
                base_pairs = [p for p in pairs if p.get("baseToken", {}).get("address", "").lower() == addr and p.get("chainId") == "bsc"]
                if base_pairs:
                    base_pairs.sort(key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0), reverse=True)
                    best = base_pairs[0]
                    price_usd = best.get("priceUsd")
                    if price_usd:
                        p = float(price_usd)
                        if p > 0:
                            results[addr] = _fmt_price(p)
        except:
            pass
    
    # ── 渠道3: DexScreener（跨链，覆盖面最广）──
    remaining = [a for a, c, cn, s in unique if a not in results]
    for addr in remaining:
        try:
            url = "https://api.dexscreener.com/latest/dex/tokens/" + addr
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            resp = urllib.request.urlopen(req, timeout=8)
            raw = json.loads(resp.read().decode())
            pairs = raw.get("pairs", []) or []
            if pairs:
                # 只取该地址作为 baseToken 的交易对（否则查到的priceUsd是配对币的）
                base_pairs = [p for p in pairs if p.get("baseToken", {}).get("address", "").lower() == addr]
                if base_pairs:
                    base_pairs.sort(key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0), reverse=True)
                    best = base_pairs[0]
                    price_usd = best.get("priceUsd")
                    if price_usd:
                        p = float(price_usd)
                        if p > 0:
                            results[addr] = _fmt_price(p)
        except:
            pass
    
    # ── 渠道5: CoinGecko（多链兜底）──
    remaining = [a for a, c, cn, s in unique if a not in results]
    for chain_name in ["binance-smart-chain", "ethereum", "polygon-pos", "arbitrum-one", "optimistic-ethereum", "avalanche"]:
        if not remaining: break
        batch = remaining[:50]
        try:
            addr_param = ",".join(batch)
            url = f"https://api.coingecko.com/api/v3/simple/token_price/{chain_name}?contract_addresses={addr_param}&vs_currencies=usd"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            resp = urllib.request.urlopen(req, timeout=8)
            cg_data = json.loads(resp.read().decode())
            if cg_data:
                for addr_lower, info in cg_data.items():
                    usd_price = info.get("usd")
                    if usd_price and usd_price > 0:
                        results[addr_lower] = _fmt_price(usd_price)
                remaining = [a for a in remaining if a not in results]
        except:
            pass
    
    return json.dumps(results)


def token_del():
    data = _load()
    cat_idx = int(request.form.get("cat_idx", 0))
    tok_idx = int(request.form.get("tok_idx", 0))
    categories = data.get("categories", [])
    if cat_idx < len(categories) and tok_idx < len(categories[cat_idx]["tokens"]):
        categories[cat_idx]["tokens"].pop(tok_idx)
    _save(data)
    return "OK"


def rename_category():
    data = _load()
    cat_idx = int(request.form.get("cat_idx", 0))
    name = request.form.get("cat_name", "").strip()
    categories = data.get("categories", [])
    if 0 <= cat_idx < len(categories) and name:
        categories[cat_idx]["name"] = name
    _save(data)
    return "OK"


def add_category():
    data = _load()
    name = request.form.get("cat_name", "").strip()
    if name:
        data["categories"].append({"name": name, "tokens": []})
    _save(data)
    return redirect_back()


def del_category():
    data = _load()
    cat_idx = int(request.form.get("cat_idx", 0))
    categories = data.get("categories", [])
    if 0 <= cat_idx < len(categories):
        categories.pop(cat_idx)
    _save(data)
    return "OK"


def redirect_back():
    from flask import redirect
    return redirect("/token-contracts")
