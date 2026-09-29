"""LP 数据读写，以及用户主动配置时的外部 JSON 同步。"""
from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from time import sleep

LP_PROJECT_ID = "xau-lp-001"
DEFAULT_SOURCE = ""


def source_path() -> Path | None:
    value = os.getenv("WORKBENCH_LP_SOURCE_FILE", DEFAULT_SOURCE).strip()
    return Path(value).expanduser() if value else None


def _read(path: Path) -> dict | None:
    """处理 WSL 脚本刚好在覆写文件时的短暂不完整状态。"""
    for attempt in range(3):
        try:
            with path.open("r", encoding="utf-8") as file:
                value = json.load(file)
            return value if isinstance(value, dict) else None
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            if attempt < 2:
                sleep(0.12)
    return None


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as file:
        json.dump(data, file, indent=2, ensure_ascii=False)
        temporary = Path(file.name)
    try:
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink(missing_ok=True)


def _project(data: dict) -> dict | None:
    return next((item for item in data.get("projects", []) if item.get("id") == LP_PROJECT_ID), None)


def _record_key(item: dict) -> str:
    record_id = str(item.get("id", "")).strip()
    if record_id:
        return f"id:{record_id}"
    return "legacy:" + "|".join(str(item.get(key, "")) for key in ("type", "date", "token_pair", "principal", "profit"))


def _merge_lp_data(source_data: dict, working_data: dict, touched_position_id: str | None) -> dict:
    """仅合并 LP 项目；其他项目始终保留 WSL 的最新版本。"""
    source_project = _project(source_data)
    working_project = _project(working_data)
    if not working_project:
        return source_data
    if not source_project:
        source_data.setdefault("projects", []).append(working_project)
        return source_data

    source_operations = {_record_key(item): item for item in source_project.get("lp_operations", [])}
    for item in working_project.get("lp_operations", []):
        source_operations.setdefault(_record_key(item), item)
    source_project["lp_operations"] = sorted(
        source_operations.values(), key=lambda item: str(item.get("date", "")), reverse=True
    )

    if touched_position_id:
        updated_position = next(
            (item for item in working_project.get("lp_positions", []) if str(item.get("id")) == str(touched_position_id)),
            None,
        )
        if updated_position:
            source_positions = source_project.setdefault("lp_positions", [])
            index = next((i for i, item in enumerate(source_positions) if str(item.get("id")) == str(touched_position_id)), None)
            if index is None:
                source_positions.insert(0, updated_position)
            else:
                source_positions[index] = updated_position

    source_project["updated"] = max(str(source_project.get("updated", "")), str(working_project.get("updated", "")))
    return source_data


def load_lp_data(local_path: str) -> tuple[dict, str]:
    """返回主源数据；WSL 不可达时才使用本地缓存。"""
    source = source_path()
    source_data = _read(source) if source else None
    if source_data is not None:
        local = Path(local_path)
        cached = _read(local)
        if cached != source_data:
            _write(local, source_data)
        return source_data, "external"
    return _read(Path(local_path)) or {}, "local"


def save_lp_data(working_data: dict, local_path: str, touched_position_id: str | None) -> tuple[dict, str]:
    """将 Windows 的 LP 操作合并至 WSL 最新数据，并更新本地缓存。"""
    source = source_path()
    latest_source = _read(source) if source else None
    if latest_source is not None:
        merged = _merge_lp_data(latest_source, working_data, touched_position_id)
        _write(source, merged)
        _write(Path(local_path), merged)
        return merged, "external"
    _write(Path(local_path), working_data)
    return working_data, "local"
