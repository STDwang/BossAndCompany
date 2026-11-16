"""Build the strictly public '最近在忙' projection for a future website module.

This module is the ONLY place where work activity may leave the private company
space. It never writes to a website repository on its own. An event contributes
an item only when ALL of the following hold:

  * activity_public is ON in the user-level switches;
  * the event explicitly carries visibility == "public" AND a `public` object;
  * the event's project is in the normalized profile, is public, and has status
    user-stated or verified.

Output fields are an allowlist. Event summaries, artifacts, actors, harnesses,
workspace ids, commit hashes, private repositories, paths and contact details
can never appear. A final self-check rejects any projection that leaks them.
"""
import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import automation
import company
import render

STAGES = ("planning", "in-progress", "shipped", "paused")
DEFAULT_LIMIT = 12
MAX_TITLE = 80
FORBIDDEN_KEYS = ("summary", "artifacts", "actor", "role", "next", "harness", "workspace_id",
                  "workspace_root", "commit", "path", "repositories", "email", "phone",
                  "verification", "sources", "note")
ALLOWED_KEYS = ("date", "project", "title", "stage", "url")
TOP_LEVEL_KEYS = ("schema_version", "generated_at", "enabled", "source", "items")
REPOSITORY = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_.-]+")


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def project_allowlist(profile):
    """Public, verified project repositories and their display titles."""
    render.validate(profile)
    allowed = {}
    for item in profile["projects"]:
        if item["visibility"] == "public" and item["status"] in ("verified", "user-stated"):
            allowed[item["repository"].lower()] = item["title"]
    return allowed


def clean_title(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Public activity title must be non-empty text")
    text = re.sub(r"\s+", " ", value).strip()[:MAX_TITLE]
    return text


def load_events(directory):
    directory = Path(directory)
    if not directory.is_dir():
        return []
    records = []
    for path in sorted(directory.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if isinstance(data, dict):
            records.append(data)
    return records


def build_items(records, allowed, limit=DEFAULT_LIMIT):
    items = []
    for record in records:
        if record.get("visibility") != "public":
            continue
        public = record.get("public")
        if not isinstance(public, dict):
            continue
        repository = record.get("project")
        if not isinstance(repository, str) or repository.lower() not in allowed:
            continue
        recorded_at = record.get("recorded_at")
        if not isinstance(recorded_at, str):
            continue
        try:
            parsed = datetime.fromisoformat(recorded_at.replace("Z", "+00:00"))
        except ValueError:
            continue
        stage = public.get("stage")
        if stage not in STAGES:
            continue
        try:
            title = clean_title(public.get("title"))
            url = render.safe_url(f"https://github.com/{repository}")
        except (ValueError, TypeError):
            continue
        items.append({"date": parsed.date().isoformat(), "project": repository,
                      "title": title, "stage": stage, "url": url})
    items.sort(key=lambda item: (item["date"], item["project"]), reverse=True)
    # One item per project per day is enough for a "recently working on" strip.
    seen, unique = set(), []
    for item in items:
        key = (item["date"], item["project"].lower())
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
        if len(unique) >= limit:
            break
    return unique


def validate_projection(projection):
    """Defense in depth: reject the file if any private detail slipped through."""
    if not isinstance(projection, dict):
        raise ValueError("Activity projection must be an object")
    if projection.get("schema_version") != render.SCHEMA_VERSION:
        raise ValueError("Unsupported activity schema_version")
    if not isinstance(projection.get("items"), list):
        raise ValueError("Activity items must be an array")
    if set(projection) != set(TOP_LEVEL_KEYS):
        raise ValueError("Activity projection has non-allowlisted top-level fields")
    for item in projection["items"]:
        if not isinstance(item, dict) or set(item) != set(ALLOWED_KEYS):
            raise ValueError("Activity item has non-allowlisted fields")
        if any(key in item for key in FORBIDDEN_KEYS):
            raise ValueError("Activity item contains a forbidden field")
        if item["stage"] not in STAGES:
            raise ValueError("Activity item has an unknown stage")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", item["date"]):
            raise ValueError("Activity item has an invalid date")
        if not REPOSITORY.fullmatch(item["project"]):
            raise ValueError("Activity item has an invalid public repository")
        title = item["title"]
        if not isinstance(title, str) or not title.strip() or len(title) > MAX_TITLE:
            raise ValueError("Activity item has an invalid title")
        # A title is display text only: no contact details, paths or commit hashes.
        if "@" in title or "\\" in title or "/" in title or re.search(r"[0-9a-f]{7,40}", title, re.I):
            raise ValueError("Activity title contains a private-looking token")
        url = render.safe_url(item["url"])
        if not url.startswith(f"https://github.com/{item['project']}"):
            raise ValueError("Activity URL does not match its public project")
    return projection


def settings_for(project):
    effective = automation.effective_settings(project)
    snapshot = company.destination(project, f"{automation.CACHE_RELATIVE}/snapshot.json")
    if snapshot.is_file():
        try:
            cached = json.loads(snapshot.read_text(encoding="utf-8-sig"))
            resolved = cached.get("automation")
            if isinstance(resolved, dict) and isinstance(resolved.get("settings"), dict):
                effective = automation.effective_settings(project, resolved["settings"])
        except (OSError, json.JSONDecodeError, ValueError):
            pass
    return effective


def build_activity(project, profile, limit=DEFAULT_LIMIT):
    project = Path(project).resolve()
    effective = settings_for(project)
    settings = effective["settings"]
    projection = {"schema_version": render.SCHEMA_VERSION,
                  "generated_at": now(),
                  "enabled": settings["activity_public"],
                  "source": effective["source"],
                  "items": []}
    if not settings["activity_public"]:
        return projection, effective
    allowed = project_allowlist(profile)
    cached = company.destination(project, f"{automation.CACHE_RELATIVE}/company/events")
    outbox = company.destination(project, ".boss-and-company/outbox")
    # Merge both sources by event id; a locally recorded event wins over the
    # cached remote copy so newly staged public items are not silently dropped.
    merged = {}
    for source in (load_events(cached), load_events(outbox)):
        for record in source:
            merged[record.get("id") or json.dumps(record, sort_keys=True)] = record
    projection["items"] = build_items(list(merged.values()), allowed, limit)
    return validate_projection(projection), effective


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--output")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    args = parser.parse_args()
    try:
        projection, effective = build_activity(args.project, company.read(args.profile), args.limit)
    except (ValueError, OSError) as error:
        parser.exit(1, "Activity projection refused: " + str(error) + "\n")
    if not projection["enabled"]:
        print(company.encoded({"enabled": False, "reason": "activity_public is off",
                               "written": False, "remote_writes": False}), end="")
        return
    if not args.output:
        parser.exit(1, "Specify --output; this tool never chooses a website path on its own\n")
    output = Path(args.output)
    if output.exists() and output.is_dir():
        parser.exit(1, "Output must be a file\n")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(company.encoded(projection), encoding="utf-8", newline="\n")
    print(company.encoded({"enabled": True, "written": str(output), "items": len(projection["items"]),
                           "source": effective["source"], "remote_writes": False}), end="")


if __name__ == "__main__":
    main()
