"""Synchronize local BossAndCompany events through an already authenticated gh CLI.

The module never stores credentials, prints gh stderr, or treats a sent request as
success. It verifies the company repository is private, writes one immutable file
per event, reads the remote content back, and only then records a receipt.
"""
import argparse
import base64
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

import company


class SyncError(RuntimeError):
    pass


def default_runner(command, input_data=None):
    return subprocess.run(command, input=input_data, text=True, encoding="utf-8", capture_output=True)


def gh(runner, arguments, input_data=None):
    command = ["gh", "api", *arguments]
    try:
        process = runner(command, input_data=input_data)
    except OSError:
        raise SyncError("Cannot execute gh; sign in with an already authenticated GitHub CLI") from None
    output = getattr(process, "stdout", "") or ""
    code = getattr(process, "returncode", 1)
    if "-i" in arguments:
        normalized = output.replace("\r\n", "\n")
        match = re.search(r"^HTTP/\S+\s+(\d{3})", normalized, re.MULTILINE)
        status = int(match[1]) if match else (200 if code == 0 else 500)
        header, _, body = normalized.partition("\n\n")
        if not match:
            body = header
    else:
        status, body = (200 if code == 0 else 500), output
    if 200 <= status < 300 and code == 0:
        return status, body
    if status == 404:
        return status, None
    raise SyncError(f"GitHub API request failed with HTTP {status}")


def gh_json(runner, arguments, input_data=None):
    _, body = gh(runner, arguments, input_data)
    try:
        return json.loads(body)
    except (TypeError, json.JSONDecodeError):
        raise SyncError("GitHub API returned invalid JSON") from None


def repository_metadata(runner, repository):
    data = gh_json(runner, [f"repos/{repository}", "--jq", "{private:.private,default_branch:.default_branch}"])
    if not isinstance(data, dict) or data.get("private") is not True:
        raise SyncError("Company workspace must be private")
    branch = data.get("default_branch")
    if not isinstance(branch, str) or not re.fullmatch(r"[A-Za-z0-9._/-]{1,200}", branch):
        raise SyncError("Company workspace has an unsupported default branch")
    return branch


def remote_path(repository, path):
    return f"repos/{repository}/contents/{quote(path, safe='/.-_')}"


def get_remote_file(runner, repository, path, branch):
    endpoint = remote_path(repository, path)
    status, body = gh(runner, ["-i", "-X", "GET", endpoint, "-f", f"ref={branch}"])
    if status == 404:
        return None
    try:
        data = json.loads(body)
        encoded_content = data["content"]
        if not isinstance(encoded_content, str):
            raise KeyError("content")
        content = base64.b64decode("".join(encoded_content.split()), validate=True)
        html_url = data["html_url"]
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        raise SyncError("Remote file response is incomplete or malformed") from None
    if not isinstance(html_url, str):
        raise SyncError("Remote file response has no HTML URL")
    return content, html_url


def put_remote_file(runner, repository, path, branch, payload, message):
    endpoint = remote_path(repository, path)
    request = {"message": message,
               "content": base64.b64encode(payload).decode("ascii"),
               "branch": branch}
    gh_json(runner, ["-X", "PUT", endpoint, "--input", "-"], json.dumps(request, ensure_ascii=False))


def sync_event(project, record, repository, branch, runner):
    event_id = record["id"]
    remote_name = f"events/{event_id}.json"
    payload = company.encoded(record).encode("utf-8")
    remote = get_remote_file(runner, repository, remote_name, branch)
    if remote is not None:
        content, remote_url = remote
        if content != payload:
            return {"id": event_id, "status": "conflict", "detail": "Remote event with the same ID has different content"}
    else:
        put_remote_file(runner, repository, remote_name, branch, payload, f"Record BossAndCompany event {event_id}")
        remote = get_remote_file(runner, repository, remote_name, branch)
        if remote is None or remote[0] != payload:
            return {"id": event_id, "status": "failed", "detail": "Remote readback did not match the local event"}
        remote_url = remote[1]
    company.acknowledge(project, event_id, remote_url)
    return {"id": event_id, "status": "synced", "verification": "remote-content-readback", "remote_url": remote_url}


def validate_workspace_descriptor(descriptor, mapping):
    if not isinstance(descriptor, dict) or descriptor.get("schema_version") != company.render.SCHEMA_VERSION:
        raise ValueError("Unsupported workspace descriptor")
    if descriptor.get("project", "").lower() != mapping["project"].lower():
        raise ValueError("Workspace descriptor belongs to a different project")
    workspace_id = company.identifier(descriptor.get("workspace_id"))
    if any(key in descriptor for key in ("workspace_root", "path", "harness")):
        raise ValueError("Workspace descriptor must not contain local paths or harness-specific state")
    return workspace_id, company.encoded(descriptor).encode("utf-8")


def sync_workspaces(project, mapping, repository, branch, runner):
    directory = company.destination(project, ".boss-and-company/outbox/workspaces")
    results = []
    for path in sorted(directory.glob("*.json")) if directory.is_dir() else []:
        workspace_id = path.stem
        try:
            descriptor = company.read(path)
            workspace_id, payload = validate_workspace_descriptor(descriptor, mapping)
            remote_name = f"workspaces/{workspace_id}.json"
            remote = get_remote_file(runner, repository, remote_name, branch)
            if remote is not None and remote[0] == payload:
                results.append({"workspace_id": workspace_id, "status": "already-synced"})
                continue
            if remote is not None:
                results.append({"workspace_id": workspace_id, "status": "conflict",
                                "detail": "Remote workspace identity has different content"})
                continue
            put_remote_file(runner, repository, remote_name, branch, payload,
                            f"Register BossAndCompany workspace {workspace_id}")
            readback = get_remote_file(runner, repository, remote_name, branch)
            if readback is None or readback[0] != payload:
                results.append({"workspace_id": workspace_id, "status": "failed",
                                "detail": "Remote workspace readback did not match"})
            else:
                results.append({"workspace_id": workspace_id, "status": "synced",
                                "verification": "remote-content-readback", "remote_url": readback[1]})
        except (ValueError, OSError, KeyError, TypeError, AttributeError, SyncError) as error:
            message = str(error) if isinstance(error, (ValueError, SyncError)) else type(error).__name__
            results.append({"workspace_id": workspace_id, "status": "failed", "detail": message})
    return results


def sync(project, runner=default_runner, limit=100):
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    project = Path(project).resolve()
    mapping = company.project_mapping(project)
    repository = mapping["repositories"]["company"]
    ignores = company.destination(project, ".gitignore")
    protected = ("/.boss-and-company/outbox/", "/.boss-and-company/receipts/", "/.boss-and-company/local.json")
    if not ignores.is_file() or any(entry not in ignores.read_text(encoding="utf-8") for entry in protected):
        raise ValueError("Bind project first to protect private files")
    branch = repository_metadata(runner, repository)
    workspace_results = sync_workspaces(project, mapping, repository, branch, runner)
    outbox = company.destination(project, ".boss-and-company/outbox")
    results = []
    for path in sorted(outbox.glob("*.json"))[:limit]:
        event_id = path.stem
        try:
            company.identifier(event_id)
            record = company.read(path)
            company.validate_event(record, mapping["workspace_id"])
            if record["project"].lower() != mapping["project"].lower():
                raise ValueError("Event belongs to a different project")
            if company.receipt_status(project, record, mapping) == "synced":
                results.append({"id": event_id, "status": "already-synced"})
                continue
            results.append(sync_event(project, record, repository, branch, runner))
        except (ValueError, OSError, KeyError, TypeError, AttributeError, SyncError) as error:
            message = str(error) if isinstance(error, (ValueError, SyncError)) else type(error).__name__
            results.append({"id": event_id, "status": "failed", "detail": message})
    acceptable = ("synced", "already-synced")
    return {"schema_version": company.render.SCHEMA_VERSION, "workspace_id": mapping["workspace_id"],
            "repository": repository, "branch": branch, "workspaces": workspace_results, "results": results,
            "ok": all(item["status"] in acceptable for item in workspace_results + results)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    try:
        result = sync(args.project, limit=args.limit)
    except (ValueError, OSError, SyncError) as error:
        parser.exit(1, "Synchronization failed: " + str(error) + "\n")
    print(company.encoded(result), end="")
    if not result["ok"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
