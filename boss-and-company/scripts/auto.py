"""Single entry point for BossAndCompany automation hooks.

A skill is passive: it cannot run in the background by itself. Hosts trigger
this file from a session-start hook, a git post-commit hook, or from the skill's
own "on load" instructions. Every action first resolves the user-level switches
in the private Boss passport, so enabling a hook never grants write permission
that the user did not give. Failures are reported as data, never as a fake
success, and never block the host's work.
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

import activity
import automation
import company
import refresh
import sync

SUBJECT_LIMIT = 160


def default_git(command, input_data=None):
    return subprocess.run(command, input=input_data, text=True, encoding="utf-8", capture_output=True)


def commit_info(project, git=default_git):
    process = git(["git", "-C", str(Path(project).resolve()), "log", "-1",
                   "--format=%H%n%cI%n%s%n%D"])
    if getattr(process, "returncode", 1) != 0:
        raise ValueError("Cannot read the latest local git commit")
    lines = (getattr(process, "stdout", "") or "").splitlines()
    if len(lines) < 3 or not re.fullmatch(r"[0-9a-f]{40}", lines[0]):
        raise ValueError("Local git commit output is incomplete")
    refs = lines[3] if len(lines) > 3 else ""
    match = re.search(r"HEAD -> ([^,\s]+)", refs)
    return {"sha": lines[0], "committed_at": lines[1],
            "subject": re.sub(r"\s+", " ", lines[2]).strip()[:SUBJECT_LIMIT] or "(no subject)",
            "branch": match[1] if match else "detached"}


def commit_record(mapping, info, harness):
    """Build a PRIVATE, idempotent event from a local commit.

    The event ID and recorded_at both derive from the commit, so replaying the
    hook produces byte-identical content. No diff, code, author email or local
    path is ever included.
    """
    short = info["sha"][:12]
    workspace = mapping["workspace_id"]
    return {
        "schema_version": company.render.SCHEMA_VERSION,
        "id": f"{workspace}-commit-{short}",
        "workspace_id": workspace,
        "harness": harness,
        "recorded_at": info["committed_at"],
        "task_id": f"commit-{short}",
        "project": mapping["project"],
        "role": "Coder_Position",
        "actor": harness,
        "kind": "milestone",
        "summary": info["subject"],
        "artifacts": [],
        "verification": {"status": "not-run",
                         "detail": "由 post-commit hook 依据本地 git commit 生成；验证状态需按实际工作补充。"},
        "next": "读取 Company_Workspace 最新状态后继续；关键决定、验证与人类验收另行记录。",
        "visibility": "private",
        "commit": {"sha": info["sha"], "branch": info["branch"],
                   "committed_at": info["committed_at"]},
    }


def session_start(project, harness="unknown", runner=sync.default_runner):
    try:
        result = refresh.refresh(project, runner=runner)
    except ValueError as error:
        result = {"status": "blocked", "reason": str(error), "remote_writes": False}
    result["action"] = "session-start"
    result["harness"] = harness
    result["blocking"] = False
    return result


def post_commit(project, harness="unknown", runner=sync.default_runner, git=default_git):
    project = Path(project).resolve()
    effective = activity.settings_for(project)
    settings = effective["settings"]
    if not settings["auto_record"]:
        return {"action": "post-commit", "status": "disabled",
                "reason": "auto_record is off; no event was written", "remote_writes": False,
                "blocking": False}
    try:
        mapping = company.project_mapping(project)
        info = commit_info(project, git)
        record = commit_record(mapping, info, harness)
        # company.event checks .gitignore protections and is idempotent by ID.
        written = company.event(project, record, harness)
        result = {"action": "post-commit", "status": "recorded", "id": written["id"],
                  "sha": info["sha"][:12], "visibility": "private",
                  "local_status": written["status"], "remote_writes": False, "blocking": False}
        if settings["sync_after_record"]:
            outcome = sync.sync(project, runner=runner, only=[written["id"]])
            result["sync"] = {"ok": outcome["ok"], "results": outcome["results"]}
            result["remote_writes"] = outcome["ok"]
            result["status"] = "synced" if outcome["ok"] else "sync-failed"
        return result
    except (ValueError, OSError, KeyError, TypeError, sync.SyncError) as error:
        return {"action": "post-commit", "status": "failed", "reason": str(error),
                "remote_writes": False, "blocking": False}


def status(project):
    project = Path(project).resolve()
    effective = activity.settings_for(project)
    cache = company.destination(project, automation.CACHE_RELATIVE)
    snapshot = cache / "snapshot.json"
    data = {}
    if snapshot.is_file():
        try:
            loaded = json.loads(snapshot.read_text(encoding="utf-8-sig"))
            if isinstance(loaded, dict):
                data = {"refreshed_at": loaded.get("refreshed_at"),
                        "stale": loaded.get("stale"), "files": len(loaded.get("files", [])),
                        "company_sha": loaded.get("company_sha")}
        except (OSError, json.JSONDecodeError):
            pass
    return {"action": "status", "source": effective["source"],
            "settings": effective["settings"],
            "descriptions": effective["descriptions"],
            "local_overrides_applied": effective["local_overrides_applied"],
            "local_overrides_ignored": effective["local_overrides_ignored"],
            "cache": data or {"refreshed_at": None, "stale": None, "files": 0},
            "context_path": str(cache / "CONTEXT.md"),
            "remote_writes": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    for name in ("session-start", "post-commit", "status"):
        p = sub.add_parser(name)
        p.add_argument("--project", required=True)
        if name != "status":
            p.add_argument("--harness", default="unknown")
    p = sub.add_parser("activity")
    p.add_argument("--project", required=True)
    p.add_argument("--profile", required=True)
    p.add_argument("--output")
    p.add_argument("--limit", type=int, default=activity.DEFAULT_LIMIT)
    args = parser.parse_args()
    try:
        if args.action == "session-start":
            result = session_start(args.project, args.harness)
        elif args.action == "post-commit":
            result = post_commit(args.project, args.harness)
        elif args.action == "status":
            result = status(args.project)
        else:
            projection, effective = activity.build_activity(args.project, company.read(args.profile), args.limit)
            if not projection["enabled"]:
                result = {"action": "activity", "enabled": False,
                          "reason": "activity_public is off; nothing was written",
                          "written": None, "remote_writes": False}
            else:
                if not args.output:
                    parser.exit(1, "Specify --output; activity never chooses a website path on its own\n")
                output = Path(args.output)
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(company.encoded(projection), encoding="utf-8", newline="\n")
                result = {"action": "activity", "enabled": True, "written": str(output),
                          "items": len(projection["items"]), "source": effective["source"],
                          "remote_writes": False}
    except (ValueError, OSError) as error:
        # Hooks must never break the host session or a successful git commit.
        print(company.encoded({"action": args.action, "status": "failed", "reason": str(error),
                               "blocking": False, "remote_writes": False}), end="")
        return
    print(company.encoded(result), end="")


if __name__ == "__main__":
    main()
