"""运行时路径与平台适配。

所有业务模块只从这里取得项目根目录、数据目录和解释器路径，避免把 WSL
绝对路径散落在页面路由中。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


UNIFIED_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = UNIFIED_DIR
DATA_DIR = UNIFIED_DIR / "data"
MONITOR_DIR = UNIFIED_DIR / "monitor-engine"
PYTHON = sys.executable


def data_file(name: str) -> Path:
    """Return an existing application data file and ensure its parent exists."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR / name


def optional_path_from_env(name: str) -> Path | None:
    value = os.getenv(name, "").strip()
    return Path(value).expanduser() if value else None
