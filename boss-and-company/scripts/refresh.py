"""Read-only refresh of the latest Boss passport and Company_Workspace state.

Every Harness calls this when it attaches to a GitHub-backed project. Results go
ONLY into the gitignored `.boss-and-company/cache/` directory of that checkout:
nothing is pushed, nothing public is written, and no credential is stored. On
any failure the previous cache is preserved and marked stale instead of being
silently replaced or reported as success.
"""
import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import automation
import company
import sync

BOSS_SUMMARY = "SUMMARY.md"
COMPANY_CONFIG = "company.json"
COMPANY_README = "README.md"
PROJECTS_DIR = "projects"
EVENTS_DIR = "events"
WORKSPACES_DIR = "workspaces"
POSITIONS_DIR = "positions"
# Remote directory names become local cache paths; reject anything unexpected.
SAFE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,120}")


def safe_name(value):
    return isinstance(value, str) and ".." not in value and SAFE_NAME.fullmatch(value) is not None


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def default_branch(runner, repository):
    data = sync.gh_json(runner, [f"repos/{repository}", "--jq", "{private:.private,default_branch:.default_branch}"])
    if not isinstance(data, dict) or data.get("private") is not True:
        raise sync.SyncError(f"{repository} must be private before its state is cached locally")
    branch = data.get("default_branch")
    if not isinstance(branch, str) or not branch:
        raise sync.SyncError(f"{repository} has no default branch")
    return branch


def read_optional(runner, repository, path, branch):
    remote = sync.get_remote_file(runner, repository, path, branch)
    return remote[0] if remote is not None else None


def list_directory(runner, repository, path, branch):
    endpoint = f"repos/{repository}/contents/{quote(path, safe='/.-_')}"
    try:
        data = sync.gh_json(runner, [endpoint, "-f", f"ref={branch}"])
    except sync.SyncError:
        return []
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict) and isinstance(item.get("name"), str)]


def remote_sha(runner, repository, branch):
    """`gh api --jq .sha` emits plain text, not a JSON string."""
    try:
        _, body = sync.gh(runner, [f"repos/{repository}/commits/{quote(branch, safe='/.-_')}", "--jq", ".sha"])
        value = (body or "").strip().strip('"')
        return value if re.fullmatch(r"[0-9a-f]{40}", value) else None
    except sync.SyncError:
        return None


def pull(runner, boss_repo, company_repo, event_limit=20, project_limit=40):
    """Fetch a bounded, read-only snapshot. Returns (files, meta)."""
    boss_branch = default_branch(runner, boss_repo)
    company_branch = default_branch(runner, company_repo)
    files = {}

    def take(key, repository, path, branch):
        payload = read_optional(runner, repository, path, branch)
        if payload is not None:
            files[key] = payload

    take("boss/automation.json", boss_repo, automation.BOSS_FILE, boss_branch)
    take("boss/SUMMARY.md", boss_repo, BOSS_SUMMARY, boss_branch)
    take("company/company.json", company_repo, COMPANY_CONFIG, company_branch)
    take("company/README.md", company_repo, COMPANY_README, company_branch)

    slugs = sorted(item["name"] for item in list_directory(runner, company_repo, PROJECTS_DIR, company_branch)
                   if item.get("type") == "dir" and safe_name(item["name"]))[:project_limit]
    for slug in slugs:
        take(f"company/projects/{slug}/STATE.md", company_repo, f"{PROJECTS_DIR}/{slug}/STATE.md", company_branch)
        take(f"company/projects/{slug}/PROJECT.json", company_repo, f"{PROJECTS_DIR}/{slug}/PROJECT.json", company_branch)

    events = sorted((item["name"] for item in list_directory(runner, company_repo, EVENTS_DIR, company_branch)
                     if item.get("type") == "file" and item["name"].endswith(".json")
                     and safe_name(item["name"])), reverse=True)[:event_limit]
    for name in events:
        take(f"company/events/{name}", company_repo, f"{EVENTS_DIR}/{name}", company_branch)

    workspaces = [item["name"] for item in list_directory(runner, company_repo, WORKSPACES_DIR, company_branch)
                  if item.get("type") == "file" and item["name"].endswith(".json") and safe_name(item["name"])]
    positions = [item["name"] for item in list_directory(runner, company_repo, POSITIONS_DIR, company_branch)
                 if item.get("type") == "dir" and safe_name(item["name"])]
    meta = {
        "refreshed_at": now(),
        "boss_repository": boss_repo,
        "company_repository": company_repo,
        "boss_sha": remote_sha(runner, boss_repo, boss_branch),
        "company_sha": remote_sha(runner, company_repo, company_branch),
        "project_count": len(slugs),
        "event_count": len(events),
        "workspace_count": len(workspaces),
        "position_count": len(positions),
        "files": sorted(files),
        "stale": False,
    }
    return files, meta


def build_context(files, meta, settings, mapping):
    """A short, private Markdown brief for the next Agent to read first."""
    lines = [
        "# BossAndCompany 接手上下文（私有缓存）",
        "",
        f"- 刷新时间：{meta['refreshed_at']}",
        f"- 项目身份：`{mapping['project']}`（唯一 owner/repo）",
        f"- 本 checkout：`{mapping['workspace_id']}`；公司空间：`{meta['company_repository']}`（private）",
        f"- 远端版本：Boss `{meta['boss_sha']}` / Company `{meta['company_sha']}`",
        f"- 索引：{meta['project_count']} 个项目、{meta['event_count']} 个近期事件、{meta['workspace_count']} 个工作区登记",
        f"- 主动性：auto_refresh={settings['auto_refresh']}、auto_record={settings['auto_record']}、"
        f"sync_after_record={settings['sync_after_record']}、activity_public={settings['activity_public']}",
        "",
        "> 本文件来自 private 公司空间，仅供本地 Agent 读取；不得提交、不得复制到公开仓库或网站。",
        "",
        "## 当前状态快照",
        "",
    ]
    states = [(key, payload) for key, payload in sorted(files.items())
              if key.startswith("company/projects/") and key.endswith("/STATE.md")]
    if states:
        for key, payload in states:
            slug = key.split("/")[2]
            body = payload.decode("utf-8", "replace").strip().splitlines()
            headline = next((line.lstrip("# ").strip() for line in body if line.strip()), slug)
            lines.append(f"- **{slug}**：{headline}")
    else:
        lines.append("- 远端没有可读的项目状态快照。")
    lines += ["", "## 近期工作事件（仅本地缓存，不公开）", ""]
    events = [payload for key, payload in sorted(files.items(), reverse=True)
              if key.startswith("company/events/")]
    if events:
        for payload in events[:8]:
            try:
                record = json.loads(payload.decode("utf-8-sig"))
                lines.append(f"- {record.get('recorded_at', '?')} · {record.get('harness', '?')} · "
                             f"{record.get('kind', '?')} · {record.get('summary', '')[:120]}")
            except (UnicodeDecodeError, json.JSONDecodeError):
                lines.append("- （事件文件无法解析，已保留原文）")
    else:
        lines.append("- 暂无已同步事件。")
    lines += ["", "## Boss 摘要", ""]
    summary = files.get("boss/SUMMARY.md")
    lines.append(summary.decode("utf-8", "replace").strip() if summary else "- 远端没有 Boss 摘要。")
    lines += ["", "开始工作前再读取 `company/company.json` 与本项目 `.boss-and-company/local.json`；"
              "验证状态和人类验收以项目真实产物为准，不以本缓存自评。", ""]
    return "\n".join(lines)


def mark_stale(cache, reason):
    path = cache / "snapshot.json"
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict):
            return False
        data["stale"] = True
        data["stale_reason"] = reason
        data["stale_at"] = now()
        company.atomic_write(path, company.encoded(data))
        return True
    except (OSError, ValueError, json.JSONDecodeError):
        return False


def refresh(project, runner=sync.default_runner, event_limit=20, project_limit=40):
    project = Path(project).resolve()
    mapping = company.project_mapping(project)
    local = automation.effective_settings(project)
    if not local["settings"]["auto_refresh"]:
        return {"status": "disabled", "reason": "auto_refresh is off locally", "remote_writes": False}

    boss_repo = mapping["repositories"]["boss"]
    company_repo = mapping["repositories"]["company"]
    cache = automation.cache_guard(project)
    try:
        files, meta = pull(runner, boss_repo, company_repo, event_limit, project_limit)
        remote_settings = None
        if "boss/automation.json" in files:
            remote_settings = automation.parse_remote(files["boss/automation.json"])
        resolved = automation.effective_settings(project, remote_settings)
        settings = resolved["settings"]
        if not settings["auto_refresh"]:
            return {"status": "disabled", "reason": "auto_refresh is off in the Boss passport",
                    "source": resolved["source"], "remote_writes": False}
        for relative, payload in files.items():
            company.atomic_write(company.destination(project, f"{automation.CACHE_RELATIVE}/{relative}"), payload)
        company.atomic_write(company.destination(project, f"{automation.CACHE_RELATIVE}/CONTEXT.md"),
                             build_context(files, meta, settings, mapping).encode("utf-8"))
        meta["automation"] = resolved
        company.atomic_write(company.destination(project, f"{automation.CACHE_RELATIVE}/snapshot.json"),
                             company.encoded(meta).encode("utf-8"))
        return {"status": "refreshed", "refreshed_at": meta["refreshed_at"],
                "source": resolved["source"], "files": len(files),
                "projects": meta["project_count"], "events": meta["event_count"],
                "boss_sha": meta["boss_sha"], "company_sha": meta["company_sha"],
                "automation": settings, "remote_writes": False}
    except (sync.SyncError, ValueError, OSError, KeyError, TypeError) as error:
        preserved = mark_stale(cache, str(error))
        return {"status": "stale", "reason": str(error), "previous_cache_preserved": preserved,
                "remote_writes": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--events", type=int, default=20)
    parser.add_argument("--projects", type=int, default=40)
    args = parser.parse_args()
    try:
        result = refresh(args.project, event_limit=args.events, project_limit=args.projects)
    except ValueError as error:
        parser.exit(1, "Refresh cannot run: " + str(error) + "\n")
    print(company.encoded(result), end="")
    if result["status"] == "stale":
        sys.exit(1)


if __name__ == "__main__":
    main()
