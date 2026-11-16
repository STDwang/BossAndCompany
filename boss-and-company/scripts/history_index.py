"""List matching Codex conversation metadata; never export conversation bodies."""
import argparse
import json
from pathlib import Path


def find(root, queries, limit):
    index = root / "session_index.jsonl"
    if not index.is_file():
        raise ValueError("session_index.jsonl is unavailable; use an explicit export")
    latest = {}
    malformed = 0
    with index.open(encoding="utf-8-sig") as stream:
        for line in stream:
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                malformed += 1
                continue
            if not isinstance(item, dict):
                malformed += 1
                continue
            title, identifier = item.get("thread_name", ""), item.get("id", "")
            if not isinstance(title, str) or not isinstance(identifier, str):
                continue
            if identifier and any(q.casefold() in title.casefold() for q in queries):
                latest[identifier] = {"id": identifier, "title": title, "updated_at": str(item.get("updated_at", ""))}
    selected = sorted(latest.values(), key=lambda r: r["updated_at"], reverse=True)[:limit]
    wanted = {r["id"]: r for r in selected}
    # Enumerate only session JSONL paths, not credentials/config/database contents.
    for dirname in ("sessions", "archived_sessions"):
        directory = root / dirname
        if directory.is_dir():
            for path in directory.rglob("*.jsonl"):
                for identifier, item in wanted.items():
                    if identifier in path.name:
                        item.setdefault("paths", []).append(str(path))
    return {"candidates": selected, "malformed_index_lines": malformed, "bodies_read": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--query", nargs="+", required=True)
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    if not 1 <= args.limit <= 100:
        parser.error("limit must be between 1 and 100")
    try:
        result = find(args.root, args.query, args.limit)
    except (OSError, ValueError):
        parser.exit(1, "Cannot read conversation index; use an explicit export.\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
