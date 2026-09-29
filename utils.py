# ─────────────────────────────────────────────────────────────
# utils.py — 全局共享工具函数
# ─────────────────────────────────────────────────────────────
import json, subprocess
from datetime import datetime, timedelta
from runtime import data_file, optional_path_from_env, PYTHON

PROJECTS_FILE = str(data_file("projects_data.json"))



def load_json(path):
    try:
        # 数据文件来自 WSL，必须明确 UTF-8；Windows 默认代码页会导致读取失败并被误判为空数据。
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def today_str():
    return datetime.now().strftime("%Y-%m-%d")


def now():
    return datetime.now()

def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def get_all_tasks(projects):
    """从项目列表中提取所有任务"""
    tasks = []
    for p in projects:
        for t in p.get("tasks", []):
            t["proj_id"] = p.get("id", "")
            t["proj_name"] = p.get("name", "")
            tasks.append(t)
    return sorted(tasks, key=lambda x: x.get("due", "9999-12-31"))


def is_due_within(task, days):
    due = task.get("due", "")
    if not due:
        return False
    try:
        diff = (datetime.strptime(due, "%Y-%m-%d").date() - datetime.now().date()).days
        return 0 <= diff <= days
    except:
        return False


def get_standx_data():
    """StandX 钱包状态查询"""
    standx_dir = optional_path_from_env("WORKBENCH_STANDX_DIR")
    if not standx_dir or not (standx_dir / "monitor_only.py").exists():
        return {"total": 0, "ok": 0, "total_wallets": 0, "wallets": [], "available": False}
    try:
        result = subprocess.run(
            [PYTHON, "-c",
             "import sys; sys.path.insert(0,sys.argv[1]); "
             "from monitor_only import get_all_status; print(get_all_status())", str(standx_dir)],
            cwd=str(standx_dir),
            env=None,
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return json.loads(result.stdout.strip())
    except:
        pass
    return {"total": 0, "ok": 0, "total_wallets": 0, "wallets": []}
