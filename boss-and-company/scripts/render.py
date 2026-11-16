"""Render an explicit public projection and private archive. No network access."""
import argparse
import html
import json
import re
from pathlib import Path
from string import Template
from urllib.parse import urlsplit


TEMPLATES = Path(__file__).resolve().parents[1] / "assets" / "templates"
SCHEMA_VERSION = 2
STATUSES = ("user-stated", "verified", "inferred", "disputed")


def safe_url(value):
    if not isinstance(value, str):
        raise ValueError("URL must be text")
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Only HTTPS links without embedded credentials are allowed")
    if any(c.isspace() or c in '<>\"()\\' for c in value):
        raise ValueError("Unsafe URL characters")
    return value


def md(value):
    # Escape HTML, links, table delimiters and headings from imported text.
    value = html.escape(value, quote=False).replace("\r", "").replace("\n", " ")
    return re.sub(r"([\\`*_{}\[\]()#+.!|>~-])", r"\\\1", value)


def text_fields(item, fields, context):
    for field in fields:
        if not isinstance(item.get(field), str) or not item[field].strip():
            raise ValueError(f"{context}: invalid {field}")


def validate(data):
    if not isinstance(data, dict):
        raise ValueError("Profile must be an object")
    if data.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Unsupported or missing profile schema_version")
    owner = data.get("owner", "")
    if not isinstance(owner, str) or not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", owner):
        raise ValueError("Invalid GitHub owner")
    repositories = set()
    for collection in ("facts", "projects"):
        if not isinstance(data.get(collection), list):
            raise ValueError(f"{collection} must be an array")
        ids = set()
        for i, item in enumerate(data[collection]):
            context = f"{collection}[{i}]"
            if not isinstance(item, dict):
                raise ValueError(f"{context}: must be an object")
            key = "id" if collection == "facts" else "slug"
            identifier = item.get(key)
            if not isinstance(identifier, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", identifier) or identifier in ids:
                raise ValueError(f"{context}: invalid or duplicate {key}")
            ids.add(identifier)
            if item.get("visibility") not in ("public", "private"):
                raise ValueError(f"{context}: visibility must be explicit")
            sources = item.get("sources")
            if not isinstance(sources, list) or not sources:
                raise ValueError(f"{context}: sources required")
            for source in sources:
                if not isinstance(source, dict):
                    raise ValueError(f"{context}: invalid source")
                text_fields(source, ("ref", "date"), context)
            if collection == "facts":
                text_fields(item, ("label", "value"), context)
                if item.get("status") not in STATUSES:
                    raise ValueError(f"{context}: invalid status")
            else:
                text_fields(item, ("title", "summary", "contribution", "state"), context)
                if item.get("status") not in STATUSES:
                    raise ValueError(f"{context}: invalid status")
                repository = item.get("repository")
                if not isinstance(repository, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_.-]+", repository):
                    raise ValueError(f"{context}: invalid repository")
                if repository.lower() in repositories:
                    raise ValueError(f"{context}: duplicate repository")
                repositories.add(repository.lower())
                if not isinstance(item.get("tech"), list) or not all(isinstance(t, str) for t in item["tech"]):
                    raise ValueError(f"{context}: invalid tech")
                if item.get("source_visibility") not in ("public", "private"):
                    raise ValueError(f"{context}: explicit source_visibility required")
                for link in ("source", "demo"):
                    if item.get(link):
                        safe_url(item[link])
                if item["source_visibility"] == "public" and not item.get("source"):
                    raise ValueError(f"{context}: public source needs URL")


def projection(data):
    # Construct allowed keys rather than deleting known private fields.
    return {
        "owner": data["owner"],
        "facts": [{k: f[k] for k in ("id", "label", "value")} for f in data["facts"]
                  if f["visibility"] == "public" and f["status"] in ("verified", "user-stated")],
        "projects": [{**{k: p[k] for k in ("slug", "title", "summary", "contribution", "state", "tech")},
                      **({"source": p["source"]} if p["source_visibility"] == "public" else {}),
                      **({"demo": p["demo"]} if p.get("demo") else {})}
                     for p in data["projects"]
                     if p["visibility"] == "public" and p["status"] in ("verified", "user-stated")],
    }


def svg(title, subtitle):
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="675" viewBox="0 0 1200 675">'
            '<rect width="1200" height="675" fill="#15282d"/><circle cx="1100" cy="50" r="370" fill="#234b49"/>'
            '<path d="M70 120H1130M70 560H1130" stroke="#688b80"/>'
            '<text x="72" y="85" fill="#b8edcc" font-family="sans-serif" font-size="22">BOSS AND COMPANY / SELECTED WORK</text>'
            f'<text x="70" y="325" fill="#f5f4ed" font-family="sans-serif" font-size="60">{html.escape(title[:26])}</text>'
            f'<text x="74" y="400" fill="#b8edcc" font-family="sans-serif" font-size="24">{html.escape(subtitle[:65])}</text>'
            '<text x="74" y="610" fill="#b8edcc" font-family="sans-serif" font-size="18">PROFILE · PROJECTS · PRACTICE</text></svg>')


def render(data, output):
    validate(data)
    output = Path(output)
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("Output must be a new or empty directory")
    public = projection(data)
    facts = public["facts"]
    title = next((f["value"] for f in facts if f["id"] == "display-name"), public["owner"])
    headline = next((f["value"] for f in facts if f["id"] == "headline"), "作品与工程实践")

    def write(path, value):
        target = output / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(value, encoding="utf-8")

    def template(name, **values):
        return Template((TEMPLATES / name).read_text(encoding="utf-8")).substitute(values)

    write("private/profile.json", json.dumps(data, ensure_ascii=False, indent=2))
    private_facts = "\n".join(f"- **{md(f['label'])}**：{md(f['value'])}（{f['status']}；{f['visibility']}）" for f in data["facts"])
    write("private/PROFILE.md", "# 私密个人档案\n\n" + private_facts + "\n\n来源、项目与冲突状态详见 profile.json。\n")
    write("private/ai-notes/README.md", "# AI 留言与交接\n\n在 notes/ 中追加实际协作记录。此处没有自动生成或代写的历史评价。\n")
    write("public/profile.json", json.dumps(public, ensure_ascii=False, indent=2))
    write("public/assets/passport.svg", svg(title, headline))
    table, cards = [], []
    for project in public["projects"]:
        slug = project["slug"]
        links = [("体验", project["demo"])] if project.get("demo") else []
        if project.get("source"):
            links.append(("公开代码", project["source"]))
        link_md = " · ".join(f"[{name}]({url})" for name, url in links) or "仅展示项目介绍；源码未公开。"
        write(f"public/projects/{slug}/cover.svg", svg(project["title"], " / ".join(project["tech"])))
        write(f"public/projects/{slug}/README.md", template("project.md", **{k: md(project[k]) for k in ("title", "summary", "state", "contribution")}, tech=md(" / ".join(project["tech"])), links=link_md))
        table.append(f"| {md(project['title'])} | {md(project['summary'])} | [介绍](projects/{slug}/README.md) |")
        card_links = " · ".join(f'<a href="{html.escape(url, quote=True)}" rel="noreferrer">{name} ↗</a>' for name, url in links)
        cards.append(f'<article class="card"><img src="projects/{slug}/cover.svg" alt="{html.escape(project["title"], quote=True)} 排版封面"><div class="card-body"><h3>{html.escape(project["title"])}</h3><p>{html.escape(project["summary"])}</p><p class="detail">{html.escape(project["contribution"])}</p><p class="detail">状态：{html.escape(project["state"])}</p>' + "".join(f'<span class="tag">{html.escape(t)}</span>' for t in project["tech"]) + f'<p>{card_links or "源码未公开"}</p></div></article>')
    write("public/README.md", template("profile.md", title=md(title), headline=md(headline), owner=public["owner"], facts="\n".join(f"- **{md(f['label'])}**：{md(f['value'])}" for f in facts if f["id"] not in ("display-name", "headline")), projects="\n".join(table)))
    fact_html = "".join(f'<div class="fact"><span>{html.escape(f["label"])}</span><p>{html.escape(f["value"])}</p></div>' for f in facts if f["id"] not in ("display-name", "headline"))
    write("public/index.html", template("site.html", title=html.escape(title, quote=True), description=html.escape(headline, quote=True), headline=html.escape(headline), github=f'https://github.com/{public["owner"]}', facts=fact_html, projects="".join(cards)))
    manifest = {"private_files": ["private/profile.json", "private/PROFILE.md", "private/ai-notes/README.md"], "public_fact_count": len(facts), "public_project_count": len(public["projects"]), "published": False}
    write("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = render(json.loads(args.input.read_text(encoding="utf-8-sig")), args.output)
    except (ValueError, OSError) as error:
        # Never echo source text, file paths from parse failures or private values.
        if isinstance(error, json.JSONDecodeError):
            parser.exit(1, f"Invalid JSON at line {error.lineno}, column {error.colno}\n")
        parser.exit(1, "Generation failed: " + (str(error) if type(error) is ValueError else type(error).__name__) + "\n")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
