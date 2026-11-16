"""Offline preparation and project handoff helpers for BossAndCompany."""
import argparse
import copy
import hashlib
import json
import os
import re
import secrets
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import render

SKILL = Path(__file__).resolve().parents[1]
SKILL_VERSION = 2
BEGIN = "<!-- BossAndCompany:begin -->"
END = "<!-- BossAndCompany:end -->"
PLATFORMS = {"codex": "AGENTS.md", "claude-code": "CLAUDE.md", "workbuddy": ".codebuddy/CODEBUDDY.md", "deepseek": "DEEPSEEK_CONTEXT.md"}
SKILL_DIRS = {"codex": ".agents/skills", "claude-code": ".claude/skills", "workbuddy": ".codebuddy/skills"}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def repo(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_.-]+", value):
        raise ValueError("Invalid repository name")
    return value


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,100}", value):
        raise ValueError("Invalid event/task identifier")
    return value


def config_check(config):
    if not isinstance(config, dict):
        raise ValueError("Config must be an object")
    if config.get("schema_version") != render.SCHEMA_VERSION:
        raise ValueError("Unsupported or missing config schema_version")
    render.validate({"schema_version": render.SCHEMA_VERSION, "owner": config.get("owner"), "facts": [], "projects": []})
    mappings = config.get("repositories")
    if not isinstance(mappings, dict):
        raise ValueError("Repository mappings required")
    for key in ("boss", "company", "profile", "website"):
        if repo(mappings.get(key)).split("/")[0].lower() != config["owner"].lower():
            raise ValueError("Repository owner does not match configured owner")
    if len({r.lower() for r in mappings.values()}) != len(mappings):
        raise ValueError("Company repositories must be distinct")
    if mappings["profile"].lower() != f'{config["owner"]}/{config["owner"]}'.lower():
        raise ValueError("Profile repository must be owner/owner")
    platforms = config.get("platforms", list(PLATFORMS))
    if not isinstance(platforms, list) or not platforms or any(p not in PLATFORMS for p in platforms):
        raise ValueError("Unknown or empty platforms")
    if not isinstance(config.get("decisions", {}), dict):
        raise ValueError("Decisions must be an object")


def plan(config, inventory, profile):
    config_check(config)
    render.validate(profile)
    if profile["owner"] != config["owner"]:
        raise ValueError("Profile and config owner differ")
    if not isinstance(inventory, dict) or inventory.get("schema_version") != render.SCHEMA_VERSION:
        raise ValueError("Unsupported or missing inventory schema_version")
    repos = inventory.get("repositories")
    if not isinstance(repos, list):
        raise ValueError("Inventory repositories must be an array")
    found = {}
    for item in repos:
        name = repo(item.get("full_name"))
        if name.lower() in found or item.get("visibility") not in ("public", "private"):
            raise ValueError("Duplicate repository or unknown visibility in inventory")
        found[name.lower()] = item
    actions, questions, blockers = [], [], []
    decisions = config.get("decisions", {})
    for kind, name in config["repositories"].items():
        if kind not in ("boss", "company", "profile", "website"):
            continue
        existing = found.get(name.lower())
        visibility = "private" if kind in ("boss", "company") else "public"
        if existing and existing["visibility"] != visibility:
            blockers.append({"repository": name, "reason": "visibility-mismatch", "expected": visibility})
        action = "reuse" if existing else "create"
        if kind == "profile":
            present = existing is not None and existing.get("profile_readme_exists") is not False
            choice = decisions.get("profile_readme")
            if present and choice not in ("keep", "replace"):
                questions.append({"id": "profile_readme", "default": "keep", "question": "检测到已有 GitHub 主页 README，是否重新生成并覆盖？"})
            elif present:
                action = choice
            elif choice not in (None, "create", "keep", "replace"):
                raise ValueError("Invalid profile decision")
        if kind == "website":
            choice = decisions.get("website")
            if existing and choice not in ("reuse", "new"):
                questions.append({"id": "website", "default": "reuse", "question": "检测到已有个人网站，是否复用现有网站及部署？"})
            elif existing and choice == "new":
                blockers.append({"repository": name, "reason": "new-website-needs-unused-repository-name"})
            elif choice not in (None, "create", "reuse", "new"):
                raise ValueError("Invalid website decision")
        actions.append({"kind": kind, "repository": name, "action": action, "visibility": visibility})

    # The normalized profile is the canonical project registry. Inventory is discovery input.
    canonical = {}
    for project in profile["projects"]:
        name = repo(project["repository"])
        if name.split("/")[0].lower() != config["owner"].lower():
            raise ValueError("Project owner does not match configured owner")
        if name.lower() in canonical:
            raise ValueError("Duplicate canonical project repository")
        canonical[name.lower()] = project["slug"]
        existing = found.get(name.lower())
        visibility = existing["visibility"] if existing else "private"
        actions.append({"kind": "project", "slug": project["slug"], "repository": name,
                        "action": "register" if existing else "create", "visibility": visibility})
    discovered = inventory.get("projects", [])
    if not isinstance(discovered, list):
        raise ValueError("Inventory projects must be an array")
    for item in discovered:
        name = repo(item.get("full_name"))
        if name.lower() not in canonical:
            blockers.append({"repository": name, "reason": "project-profile-missing",
                             "detail": "Add the discovered project to the normalized profile before generation"})
    return {"schema_version": render.SCHEMA_VERSION, "questions": questions, "blockers": blockers,
            "actions": actions, "remote_writes": False}


def destination(root, relative):
    root = Path(root).resolve()
    path = root / relative
    if not path.resolve().is_relative_to(root):
        raise ValueError("Destination escapes project through path or symlink")
    for candidate in (path, *path.parents):
        if candidate == root:
            break
        if candidate.is_symlink() or (hasattr(candidate, "is_junction") and candidate.is_junction()):
            raise ValueError("Managed files cannot use symlink or junction paths")
    return path


def write_new(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(content)


def merged_json(path, updates, remove=()):
    """Preserve unknown keys in an existing JSON object while updating managed keys."""
    current = read(path) if path.is_file() else {}
    if not isinstance(current, dict):
        raise ValueError("Managed JSON must be an object")
    for key in remove:
        current.pop(key, None)
    current.update(updates)
    return encoded(current)


def atomic_write(path, content):
    """Replace one file atomically; never leave a partially written managed file."""
    payload = content.encode("utf-8") if isinstance(content, str) else content
    if not isinstance(payload, bytes):
        raise ValueError("Atomic content must be text or bytes")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and path.read_bytes() == payload:
        return
    descriptor, temporary = tempfile.mkstemp(prefix=".boss-and-company-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
        os.replace(temporary, path)
    except OSError:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def workspace_identity(project, explicit=None):
    """One opaque identity per local checkout; multiple harnesses may share it."""
    local_path = destination(project, ".boss-and-company/local.json")
    existing = read(local_path) if local_path.is_file() else {}
    current = existing.get("workspace_id") if isinstance(existing, dict) else None
    if current:
        identifier(current)
        if explicit and identifier(explicit) != current:
            raise ValueError("Existing checkout already has a different workspace identity")
        return current
    if explicit:
        return identifier(explicit)
    return "ws-" + hashlib.sha256(str(Path(project).resolve()).encode("utf-8")).hexdigest()[:12]


def project_mapping(project):
    """Read deterministic repository data and per-checkout gitignored private state."""
    public = read(destination(project, ".boss-and-company/company.json"))
    local_path = destination(project, ".boss-and-company/local.json")
    if not local_path.is_file():
        raise ValueError("Private repository mapping is missing; re-run bind")
    local = read(local_path)
    repositories = local.get("repositories") if isinstance(local, dict) else None
    if not isinstance(public, dict) or not isinstance(repositories, dict):
        raise ValueError("Invalid project company mapping")
    if public.get("skill_version") != SKILL_VERSION or local.get("skill_version") != SKILL_VERSION:
        raise ValueError("Installed skill version conflicts with bound project; upgrade intentionally")
    if public.get("schema_version") != render.SCHEMA_VERSION or local.get("schema_version") != render.SCHEMA_VERSION:
        raise ValueError("Project company mapping uses an unsupported schema version")
    for key in ("boss", "company"):
        repo(repositories.get(key))
    workspace_id = identifier(local.get("workspace_id"))
    return {**public, "repositories": repositories, "workspace_id": workspace_id}


def scaffold(config, profile, output):
    config_check(config)
    if profile.get("owner") != config["owner"]:
        raise ValueError("Profile and config owner differ")
    decisions = config.get("decisions", {})
    if decisions.get("profile_readme") not in ("create", "keep", "replace") or decisions.get("website") not in ("create", "reuse", "new"):
        raise ValueError("Run plan, resolve choices, and save create/keep/replace and create/reuse/new decisions first")
    output = Path(output)
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("Output must be new or empty")
    with tempfile.TemporaryDirectory() as temp:
        render.render(profile, Path(temp) / "rendered")
        rendered = Path(temp) / "rendered"
        output.mkdir(parents=True, exist_ok=True)
        boss = output / "Boss_Passport"
        shutil.copytree(rendered / "private", boss)
        # AI work records belong only in the company repository.
        shutil.rmtree(boss / "ai-notes")
        write_new(boss / "SUMMARY.md", "# Boss 快速上下文\n\n" + "\n".join(f"- {render.md(f['label'])}：{render.md(f['value'])}" for f in profile["facts"] if f.get("category") in ("current-goal", "preference", "constraint") and f["status"] in ("verified", "user-stated")) + "\n\n详细经历和来源见 profile.json。\n")
        company = output / "Company_Workspace"
        portable = {"schema_version": render.SCHEMA_VERSION, "skill_version": SKILL_VERSION, "owner": config["owner"], "repositories": config["repositories"], "decisions": decisions, "platforms": config.get("platforms", list(PLATFORMS)), "multi_workspace": True}
        write_new(company / "company.json", encoded(portable))
        write_new(company / "README.md", "# Company Workspace\n\n项目索引见 projects/，工作区登记见 workspaces/，岗位见 positions/，事件见 events/。实际代码和正式产物保存在项目仓库。project 以 owner/repo 为唯一身份；多个本地 checkout/Harness 只增加独立 workspace 登记，不复制 PROJECT.json。\n\nBoss 档案：" + config["repositories"]["boss"] + "（private）。\n")
        shutil.copyfile(SKILL / "references/work-protocol.md", company / "WORK_PROTOCOL.md")
        duties = {"Coder_Position": "代码实现、审查、测试与技术交接", "Art_Position": "视觉设计、资产规格、真实素材及接入说明", "Planning_Position": "需求、玩法规则、范围、验收条件与变更影响"}
        for name, duty in duties.items():
            write_new(company / f"positions/{name}/POSITION.md", f"# {name}\n\n职责：{duty}。\n\n开始工作读取任务快照与必要的老板目标；交付实际产物链接、完成范围、验证和下一步。事件记录至 events/，不在岗位目录存项目代码。新增岗位可以复制本规范并修改职责，不复制历史评价。\n")
        for project in profile["projects"]:
            # Source links can be absent for projects not uploaded yet.
            record = {"schema_version": render.SCHEMA_VERSION}
            record.update({k: project[k] for k in ("slug", "title", "repository", "state", "status", "source_visibility")})
            record["source"] = project.get("source")
            write_new(company / f"projects/{project['slug']}/PROJECT.json", encoded(record))
            write_new(company / f"projects/{project['slug']}/STATE.md", f"# {render.md(project['title'])}\n\n当前记录：{render.md(project['state'])}\n\n本文件是 owner/repo 的唯一任务快照；多个 Harness 只允许追加独立事件，由明确协调者使用远端 SHA 合并本文件。验证：尚未由初始化脚本执行；以项目真实验证为准。\n")
        if decisions["profile_readme"] != "keep":
            target = output / "Profile"
            target.mkdir()
            shutil.copyfile(rendered / "public/README.md", target / "README.md")
            shutil.copytree(rendered / "public/assets", target / "assets")
            shutil.copytree(rendered / "public/projects", target / "projects") if (rendered / "public/projects").exists() else None
        if decisions["website"] == "reuse":
            write_new(output / "Website_Adaptation/public-profile.json", (rendered / "public/profile.json").read_text(encoding="utf-8"))
            write_new(output / "Website_Adaptation/INSTRUCTIONS.md", "# 复用现有网站\n\n按 public-profile.json 更新原网站内容源、路由和设计。此目录是适配输入，不是可部署的网站，不覆盖原工程。\n")
        else:
            shutil.copytree(rendered / "public", output / "Website/site")
            workflow = output / "Website/.github/workflows/pages.yml"
            workflow.parent.mkdir(parents=True)
            shutil.copyfile(SKILL / "assets/templates/pages.yml", workflow)
        write_new(output / "manifest.json", encoded({"schema_version": render.SCHEMA_VERSION, "skill_version": SKILL_VERSION, "repositories": config["repositories"], "decisions": decisions, "multi_workspace": True, "remote_writes": False, "deployed": False, "note": "Candidate files only; existing repositories need incremental merging and visibility checks."}))
    return {"generated": True, "deployed": False}


def managed(existing, body):
    block = f"{BEGIN}\n{body.rstrip()}\n{END}"
    if BEGIN not in existing and END not in existing:
        return existing + ("\n\n" if existing and not existing.endswith("\n\n") else "") + block + "\n"
    if existing.count(BEGIN) != 1 or existing.count(END) != 1 or existing.index(BEGIN) > existing.index(END):
        raise ValueError("Malformed or duplicate BossAndCompany managed block")
    before, rest = existing.split(BEGIN)
    _, after = rest.split(END)
    return before + block + after


def install_paths(project, platforms):
    files = {}
    for platform in platforms:
        if platform not in SKILL_DIRS:
            continue
        folder = destination(project, SKILL_DIRS[platform] + "/boss-and-company")
        if folder.resolve().is_relative_to(SKILL.resolve()):
            raise ValueError("Cannot install a skill inside its own source")
        for source in SKILL.rglob("*"):
            if source.is_file() and "__pycache__" not in source.parts and source.suffix != ".pyc":
                target = destination(project, str(folder.relative_to(project) / source.relative_to(SKILL)))
                if target.exists() and target.read_bytes() != source.read_bytes():
                    raise ValueError("Existing installed skill differs; preserve it and resolve version before installation")
                files[target] = source.read_bytes()
    return files


def bind(project, config, project_repo, install=False, workspace_id=None):
    config_check(config)
    repo(project_repo)
    project = Path(project).resolve()
    if not project.is_dir():
        raise ValueError("Project directory does not exist")
    platforms = config.get("platforms", list(PLATFORMS))
    company_json = destination(project, ".boss-and-company/company.json")
    local_json = destination(project, ".boss-and-company/local.json")
    if company_json.is_file():
        existing = read(company_json)
        if not isinstance(existing, dict) or existing.get("skill_version") != SKILL_VERSION:
            raise ValueError("Bound project uses a different skill version; upgrade intentionally")
    resolved_workspace_id = workspace_identity(project, workspace_id)
    # This file is identical across every checkout of the same repository.
    coordination = {"schema_version": render.SCHEMA_VERSION, "skill_version": SKILL_VERSION,
                    "owner": config["owner"], "project": project_repo, "platforms": platforms,
                    "multi_workspace": True, "workspace_registry": "private-company-space/workspaces"}
    # This file is per-checkout and must never be committed.
    private_mapping = {"schema_version": render.SCHEMA_VERSION, "skill_version": SKILL_VERSION,
                       "workspace_id": resolved_workspace_id, "workspace_root": str(project),
                       "repositories": {k: config["repositories"][k] for k in ("boss", "company")}}
    body = ("## BossAndCompany 默认工作约定\n\n本项目：" + project_repo + "\n"
            "项目身份是 owner/repo；同一仓库可被多个本地 checkout/AI Harness 管理。仓库级 company.json 与规则区块在所有工作区应完全一致，不得写入本地路径或工作区专属字段。\n"
            "每个 checkout 的 workspace_id、私有仓库映射与绝对路径只保存在 gitignored 的 local.json；outbox、receipts、local.json 不随项目提交。\n"
            "开始时读取 company.json 与 local.json，加载 BossAndCompany skill 和当前任务快照；按需读取 Boss 的目标/偏好，不加载所有私人历史。\n"
            "事件必须带 workspace_id 与 harness，ID 以 workspace_id 为前缀；不同 Harness 分别追加独立事件，由明确协调者使用远端 SHA 维护唯一任务快照。\n"
            "运行 `company.py workspace --project <目录>` 生成本 checkout 的不可变登记，再由 `sync.py` 上传到 private 公司空间 workspaces/。\n"
            "关键决定、交接、阻塞及阶段完成时追加独立事件；实际代码、设计与正式决定留在项目。事件先写 outbox/，同步回读一致后再写回执；离线或权限不足时保留 pending。\n"
            "不要伪造验证、人类验收或其他 AI 的工作；用户最新指令及宿主权限优先。DeepSeek 等环境按实际宿主加载技能和工具；无工具时仅整理上下文与待办。")
    changes = {}
    for platform in platforms:
        path = destination(project, PLATFORMS[platform])
        previous = path.read_text(encoding="utf-8") if path.exists() else ""
        changes[path] = managed(previous, body).encode("utf-8")
    path = destination(project, ".gitignore")
    previous = path.read_text(encoding="utf-8") if path.exists() else ""
    changes[path] = managed(previous, "/.boss-and-company/outbox/\n/.boss-and-company/receipts/\n/.boss-and-company/local.json").encode("utf-8")
    changes[company_json] = encoded(coordination).encode("utf-8")
    changes[local_json] = merged_json(local_json, private_mapping, remove=("harness",)).encode("utf-8")
    copies = install_paths(project, platforms) if install else {}
    # Validate all files before the first mutation, including conflicting skill installs.
    for target, content in {**changes, **copies}.items():
        if target.exists() and target not in changes and target.read_bytes() != content:
            raise ValueError("Existing installed skill differs; preserve it and resolve version before installation")
    for target, content in {**changes, **copies}.items():
        atomic_write(target, content)
    return {"bound": True, "workspace_id": resolved_workspace_id, "platforms": platforms,
            "skills_installed": install, "private_mapping_ignored": True,
            "registered_remotely": False}


def validate_event(record, workspace_id=None):
    if not isinstance(record, dict):
        raise ValueError("Event must be an object")
    if record.get("schema_version") != render.SCHEMA_VERSION:
        raise ValueError("Unsupported or missing event schema_version")
    workspace = identifier(record.get("workspace_id"))
    identifier(record.get("harness"))
    if workspace_id and workspace != identifier(workspace_id):
        raise ValueError("Event belongs to a different local workspace")
    event_id = identifier(record.get("id"))
    if not event_id.startswith(workspace + "-"):
        raise ValueError("Event ID must be prefixed by its workspace identity")
    recorded_at = record.get("recorded_at")
    if not isinstance(recorded_at, str):
        raise ValueError("Event requires recorded_at")
    try:
        timestamp = datetime.fromisoformat(recorded_at.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("Event recorded_at must be ISO 8601") from None
    if timestamp.tzinfo is None:
        raise ValueError("Event recorded_at must include a timezone")
    identifier(record.get("task_id"))
    repo(record.get("project"))
    for key in ("role", "actor", "summary", "next"):
        if not isinstance(record.get(key), str) or not record[key].strip():
            raise ValueError(f"Event requires {key}")
    if record.get("kind") not in ("registered", "decision", "handoff", "blocked", "milestone"):
        raise ValueError("Unknown event kind")
    if not isinstance(record.get("artifacts"), list) or not all(isinstance(a, str) for a in record["artifacts"]):
        raise ValueError("Artifacts must be a text array")
    verification = record.get("verification")
    if not isinstance(verification, dict) or verification.get("status") not in ("not-run", "partial", "passed", "failed") or not isinstance(verification.get("detail"), str):
        raise ValueError("Explicit verification status and detail required")


def prepare_event(project, record, harness=None):
    """Attach the checkout identity and generate a globally unique event ID."""
    if not isinstance(record, dict):
        raise ValueError("Event must be an object")
    mapping = project_mapping(Path(project).resolve())
    workspace = mapping["workspace_id"]
    prepared = copy.deepcopy(record)
    prepared["schema_version"] = render.SCHEMA_VERSION
    prepared["workspace_id"] = workspace
    prepared["harness"] = identifier(harness or prepared.get("harness") or "unknown")
    prepared.setdefault("recorded_at", datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"))
    if "id" not in prepared:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        prepared["id"] = f"{workspace}-{stamp}-{secrets.token_hex(4)}"
    validate_event(prepared, workspace)
    return prepared


def workspace(project):
    """Create an immutable, path-free descriptor for this local checkout."""
    project = Path(project).resolve()
    mapping = project_mapping(project)
    ignores = destination(project, ".gitignore")
    if not ignores.is_file() or "/.boss-and-company/outbox/" not in ignores.read_text(encoding="utf-8"):
        raise ValueError("Bind project first to protect private files")
    descriptor = {"schema_version": render.SCHEMA_VERSION, "workspace_id": mapping["workspace_id"],
                  "project": mapping["project"],
                  "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
                  "note": "Opaque checkout identity; absolute paths and credentials stay local."}
    path = destination(project, f".boss-and-company/outbox/workspaces/{descriptor['workspace_id']}.json")
    if path.is_file():
        existing = read(path)
        if not isinstance(existing, dict) or existing.get("workspace_id") != descriptor["workspace_id"] or existing.get("project") != descriptor["project"]:
            raise ValueError("Workspace descriptor conflict; preserve the existing identity")
        return {"workspace_id": descriptor["workspace_id"], "status": "pending", "remote_writes": False}
    atomic_write(path, encoded(descriptor))
    return {"workspace_id": descriptor["workspace_id"], "status": "pending", "remote_writes": False}


def receipt_data(event_id, record, remote_url, mapping):
    identifier(event_id)
    validate_event(record, mapping["workspace_id"])
    if event_id != record["id"]:
        raise ValueError("Receipt ID does not match the event")
    render.safe_url(remote_url)
    prefix = f"https://github.com/{mapping['repositories']['company']}/blob/"
    if not remote_url.startswith(prefix) or not remote_url.endswith(f"/events/{event_id}.json"):
        raise ValueError("Receipt URL must identify the configured company event file")
    return {"schema_version": render.SCHEMA_VERSION, "id": event_id, "remote_url": remote_url,
            "sha256": hashlib.sha256(encoded(record).encode("utf-8")).hexdigest()}


def receipt_status(project, record, mapping):
    path = destination(project, f".boss-and-company/receipts/{record['id']}.json")
    if not path.is_file():
        return "pending"
    stored = read(path)
    if not isinstance(stored, dict) or not isinstance(stored.get("remote_url"), str):
        raise ValueError("Corrupt event receipt")
    expected = receipt_data(record["id"], record, stored["remote_url"], mapping)
    if stored != expected:
        raise ValueError("Receipt does not match the local event")
    return "synced"


def event(project, record, harness=None):
    project = Path(project).resolve()
    mapping = project_mapping(project)
    record = prepare_event(project, record, harness)
    if record["project"].lower() != mapping["project"].lower():
        raise ValueError("Event belongs to a different project")
    ignores = destination(project, ".gitignore")
    protected = ("/.boss-and-company/outbox/", "/.boss-and-company/receipts/", "/.boss-and-company/local.json")
    if not ignores.is_file() or any(entry not in ignores.read_text(encoding="utf-8") for entry in protected):
        raise ValueError("Bind project first to protect private files")
    path = destination(project, f".boss-and-company/outbox/{record['id']}.json")
    payload = encoded(record)
    if path.exists():
        if path.read_text(encoding="utf-8") != payload:
            raise ValueError("Event ID conflict; existing record preserved")
    else:
        try:
            write_new(path, payload)
        except FileExistsError:
            if path.read_text(encoding="utf-8") != payload:
                raise ValueError("Concurrent event ID conflict")
    status = receipt_status(project, record, mapping)
    return {"id": record["id"], "workspace_id": record["workspace_id"], "harness": record["harness"],
            "status": status, "remote_writes": False}


def acknowledge(project, event_id, remote_url):
    identifier(event_id)
    project = Path(project).resolve()
    record = read(destination(project, f".boss-and-company/outbox/{event_id}.json"))
    mapping = project_mapping(project)
    expected = receipt_data(event_id, record, remote_url, mapping)
    path = destination(project, f".boss-and-company/receipts/{event_id}.json")
    if path.exists():
        if read(path) != expected:
            raise ValueError("Receipt conflict")
    else:
        atomic_write(path, encoded(expected))
    return {"id": event_id, "status": "synced", "verification": "caller-confirmed-remote-readback"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--config", required=True)
    p.add_argument("--inventory", required=True)
    p.add_argument("--profile", required=True)
    p = sub.add_parser("scaffold")
    p.add_argument("--config", required=True)
    p.add_argument("--profile", required=True)
    p.add_argument("--output", required=True)
    p = sub.add_parser("bind")
    p.add_argument("--config", required=True)
    p.add_argument("--project", required=True)
    p.add_argument("--repo", required=True)
    p.add_argument("--workspace-id")
    p.add_argument("--install-skills", action="store_true")
    p = sub.add_parser("workspace")
    p.add_argument("--project", required=True)
    p = sub.add_parser("event")
    p.add_argument("--project", required=True)
    p.add_argument("--record", required=True)
    p.add_argument("--harness")
    p = sub.add_parser("acknowledge")
    p.add_argument("--project", required=True)
    p.add_argument("--id", required=True)
    p.add_argument("--remote-url", required=True)
    args = parser.parse_args()
    try:
        if args.command == "plan":
            result = plan(read(args.config), read(args.inventory), read(args.profile))
        elif args.command == "scaffold":
            result = scaffold(read(args.config), read(args.profile), args.output)
        elif args.command == "bind":
            result = bind(args.project, read(args.config), args.repo, args.install_skills, args.workspace_id)
        elif args.command == "workspace":
            result = workspace(args.project)
        elif args.command == "event":
            result = event(args.project, read(args.record), args.harness)
        elif args.command == "acknowledge":
            result = acknowledge(args.project, args.id, args.remote_url)
        else:
            raise ValueError("Unknown command")
    except (ValueError, OSError, KeyError, TypeError, AttributeError) as error:
        if isinstance(error, json.JSONDecodeError):
            message = f"Invalid JSON at line {error.lineno}"
        else:
            message = str(error) if type(error) is ValueError else type(error).__name__
        parser.exit(1, message + "\n")
    print(encoded(result), end="")


if __name__ == "__main__":
    main()
