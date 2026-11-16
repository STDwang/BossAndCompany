"""Check this package without requiring PyYAML."""
import ast
import json
import re
from pathlib import Path

root = Path(__file__).resolve().parents[1]
skill = root / "boss-and-company"
source = (skill / "SKILL.md").read_text(encoding="utf-8-sig")
match = re.match(r"\A---\n(.*?)\n---\n", source, re.DOTALL)
assert match, "Invalid skill frontmatter"
metadata = dict(line.split(": ", 1) for line in match[1].splitlines() if ": " in line)
assert metadata.get("name") == skill.name, "Invalid skill frontmatter/name"
# Skill package version is independent of the bound-data skill_version (still 2):
# company.json / local.json did not change, so existing checkouts need no rebind.
assert metadata.get("version") == "3", "Missing skill version"
assert metadata.get("agent_created") == "true", "Missing agent_created flag"
assert len(metadata.get("description", "")) <= 1024, "Description too long"
for path in [skill / "SKILL.md", *(skill / "references").glob("*.md")]:
    for link in re.findall(r"\]\(([^)#]+)(?:#[^)]*)?\)", path.read_text(encoding="utf-8")):
        if "://" not in link:
            assert (path.parent / link).is_file(), f"Missing reference in {path.name}"
interface = (skill / "agents/openai.yaml").read_text(encoding="utf-8")
assert '$boss-and-company' in interface
for required in ("sync.py", "automation.py", "refresh.py", "activity.py", "auto.py"):
    assert (skill / "scripts" / required).is_file(), f"Required script missing: {required}"
assert (skill / "references/automation.md").is_file(), "Automation reference is required"
assert (skill / "assets/hooks/README.md").is_file(), "Hook registration guide is required"
assert (skill / "assets/hooks/post-commit").is_file(), "Git post-commit template is required"
for path in (skill / "scripts").glob("*.py"):
    ast.parse(path.read_text(encoding="utf-8"))
for path in (skill / "assets/examples").glob("*.json"):
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data.get("schema_version") == 2, "Examples require schema_version"
    if "owner" in data:
        assert data["owner"] == "example-user", "Examples must remain fictional"
automation_example = json.loads((skill / "assets/examples/automation.json").read_text(encoding="utf-8"))
assert automation_example.get("automation_version") == 1, "Automation example needs automation_version"
assert automation_example["auto_refresh"] is True, "Read-only refresh must default on"
for key in ("auto_record", "sync_after_record", "activity_public"):
    assert automation_example[key] is False, f"Write switch {key} must default off"
activity_example = json.loads((skill / "assets/examples/activity.json").read_text(encoding="utf-8"))
assert set(activity_example) == {"schema_version", "generated_at", "enabled", "source", "items"}
assert all(set(item) == {"date", "project", "title", "stage", "url"} for item in activity_example["items"]), \
    "Activity example must use the strict public allowlist"
assert not list(skill.rglob("auth.json"))
assert not list(skill.rglob(".env"))
print("PASS: frontmatter, references, metadata, Python syntax, versioned fictional JSON examples")
