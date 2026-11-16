"""User-level automation switches shared by every Harness.

The authoritative switch file is `automation.json` inside the PRIVATE Boss
passport repository. All harnesses read the same file, so a user decision made
once applies everywhere. A checkout may only make the effective settings MORE
conservative through `automation_override` in its gitignored local.json; it can
never escalate a switch that the user turned off.

Defaults follow the user's choice: read-only refresh is ON, every write is OFF.
"""
import json
from pathlib import Path

import company
import render

AUTOMATION_VERSION = 1
BOSS_FILE = "automation.json"
LOCAL_OVERRIDE_KEY = "automation_override"
CACHE_RELATIVE = ".boss-and-company/cache"
SWITCHES = ("auto_refresh", "auto_record", "sync_after_record", "activity_public")
DEFAULTS = {
    "schema_version": render.SCHEMA_VERSION,
    "automation_version": AUTOMATION_VERSION,
    "auto_refresh": True,
    "auto_record": False,
    "sync_after_record": False,
    "activity_public": False,
}
DESCRIPTIONS = {
    "auto_refresh": "接入 GitHub 后只读拉取 Boss 档案与公司空间最新信息到本地私有缓存",
    "auto_record": "代码提交后自动生成事件并写入本地 outbox",
    "sync_after_record": "提交事件生成后自动同步到 private 公司空间",
    "activity_public": "允许生成供个人网站消费的公开活动投影",
}


def validate_remote(data):
    """Accept only well-formed switch files; unknown keys are preserved but ignored."""
    if not isinstance(data, dict):
        raise ValueError("Automation settings must be an object")
    if data.get("schema_version") != render.SCHEMA_VERSION:
        raise ValueError("Unsupported or missing automation schema_version")
    if data.get("automation_version") != AUTOMATION_VERSION:
        raise ValueError("Unsupported automation_version; upgrade the skill intentionally")
    result = dict(DEFAULTS)
    for key in SWITCHES:
        if not isinstance(data.get(key), bool):
            raise ValueError(f"Automation switch {key} must be an explicit boolean")
        result[key] = data[key]
    for key in ("note", "updated_at"):
        if key in data:
            if not isinstance(data[key], str):
                raise ValueError(f"Automation {key} must be text")
            result[key] = data[key]
    return result


def parse_remote(payload):
    """Decode a remote Boss passport switch file."""
    try:
        data = json.loads(payload.decode("utf-8-sig") if isinstance(payload, bytes) else payload)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("Automation settings are not valid UTF-8 JSON") from None
    return validate_remote(data)


def local_override(project):
    path = company.destination(project, ".boss-and-company/local.json")
    if not path.is_file():
        return {}
    data = company.read(path)
    value = data.get(LOCAL_OVERRIDE_KEY) if isinstance(data, dict) else None
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("automation_override must be an object")
    return value


def effective_settings(project, remote=None):
    """Resolve the switches a specific checkout must obey.

    A missing remote file falls back to DEFAULTS (never to "everything on").
    Local overrides can only turn a switch OFF; attempts to turn one ON are
    reported and ignored rather than silently granting write access.
    """
    settings = validate_remote(remote) if remote is not None else dict(DEFAULTS)
    source = "boss-passport" if remote is not None else "defaults"
    override = local_override(project)
    applied, ignored = [], []
    for key, value in override.items():
        if key not in SWITCHES:
            ignored.append({"key": key, "reason": "unknown-switch"})
            continue
        if not isinstance(value, bool):
            raise ValueError(f"Local automation override {key} must be boolean")
        if value is True and settings[key] is False:
            ignored.append({"key": key, "reason": "local-escalation-blocked"})
            continue
        if value is False and settings[key] is True:
            settings[key] = False
            applied.append(key)
    # A dependent switch can never exceed its parent.
    if not settings["auto_record"]:
        settings["sync_after_record"] = False
    return {"schema_version": render.SCHEMA_VERSION, "settings": settings,
            "source": source, "local_overrides_applied": applied,
            "local_overrides_ignored": ignored,
            "descriptions": DESCRIPTIONS}


def cache_guard(project):
    """Private snapshots must never be committed, even on older bound projects."""
    ignores = company.destination(project, ".gitignore")
    if not ignores.is_file():
        raise ValueError("Project .gitignore is missing; bind before refreshing")
    body = ignores.read_text(encoding="utf-8")
    if f"/{CACHE_RELATIVE}/" not in body:
        raise ValueError("Private cache is not gitignored; re-run bind to protect it")
    return company.destination(project, CACHE_RELATIVE)


def switch_template(updated_at=None):
    data = dict(DEFAULTS)
    data["note"] = "用户级开关；所有 Harness 读取同一份。写入类开关默认关闭。"
    if updated_at:
        data["updated_at"] = updated_at
    return data
