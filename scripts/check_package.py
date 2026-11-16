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
assert metadata.get("version") == "2", "Missing skill version"
assert metadata.get("agent_created") == "true", "Missing agent_created flag"
assert len(metadata.get("description", "")) <= 1024, "Description too long"
for path in [skill / "SKILL.md", *(skill / "references").glob("*.md")]:
    for link in re.findall(r"\]\(([^)#]+)(?:#[^)]*)?\)", path.read_text(encoding="utf-8")):
        if "://" not in link:
            assert (path.parent / link).is_file(), f"Missing reference in {path.name}"
interface = (skill / "agents/openai.yaml").read_text(encoding="utf-8")
assert '$boss-and-company' in interface
assert (skill / "scripts/sync.py").is_file(), "Remote event sync script is required"
for path in (skill / "scripts").glob("*.py"):
    ast.parse(path.read_text(encoding="utf-8"))
for path in (skill / "assets/examples").glob("*.json"):
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data.get("schema_version") == 2, "Examples require schema_version"
    if "owner" in data:
        assert data["owner"] == "example-user", "Examples must remain fictional"
assert not list(skill.rglob("auth.json"))
assert not list(skill.rglob(".env"))
print("PASS: frontmatter, references, metadata, Python syntax, versioned fictional JSON examples")
