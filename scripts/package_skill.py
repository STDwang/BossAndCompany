"""Package only the portable skill, never local user data or development outputs."""
import argparse
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
skill = root / "boss-and-company"
if args.output.resolve().is_relative_to(skill.resolve()):
    parser.error("Archive must be outside the skill source")
args.output.parent.mkdir(parents=True, exist_ok=True)
candidates = [skill / "SKILL.md"]
for folder in ("agents", "references", "assets", "scripts"):
    candidates.extend((skill / folder).rglob("*"))
with ZipFile(args.output, "x", compression=ZIP_DEFLATED) as archive:
    count = 0
    for path in sorted(set(candidates)):
        # Package an explicit allowlist only; hidden files, caches and symlinks never travel.
        if not path.is_file() or path.is_symlink() or any(part.startswith(".") for part in path.relative_to(skill).parts):
            continue
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        archive.write(path, path.relative_to(root).as_posix())
        count += 1
print(f"Packaged portable skill only ({count} files)")
