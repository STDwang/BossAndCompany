import base64
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "boss-and-company"
sys.path.insert(0, str(SKILL / "scripts"))
import company
import render
import history_index
import sync
import classification


def example(name):
    return json.loads((SKILL / f"assets/examples/{name}.json").read_text(encoding="utf-8"))


class FakeGitHub:
    """In-memory GitHub Contents API keyed by the complete remote file path."""

    def __init__(self, private=True, tamper=False):
        self.private = private
        self.tamper = tamper
        self.files = {}
        self.put_count = 0

    @staticmethod
    def remote_file(command):
        prefix = "repos/example-user/Company_Workspace/contents/"
        for argument in command:
            if argument.startswith(prefix):
                return argument[len(prefix):]
        raise AssertionError("Missing Contents API path: " + " ".join(command))

    def __call__(self, command, input_data=None):
        if command[2] == "repos/example-user/Company_Workspace" and "--jq" in command:
            return subprocess.CompletedProcess(command, 0, stdout=json.dumps({"private": self.private, "default_branch": "main"}))
        if "-i" in command:
            path = self.remote_file(command)
            content = self.files.get(path)
            if content is None:
                return subprocess.CompletedProcess(command, 1, stdout="HTTP/2.0 404 Not Found\n\n{}")
            html_url = "https://github.com/example-user/Company_Workspace/blob/main/" + path
            body = json.dumps({"content": base64.b64encode(content).decode("ascii"), "html_url": html_url})
            return subprocess.CompletedProcess(command, 0, stdout="HTTP/2.0 200 OK\n\n" + body)
        if "-X" in command and "PUT" in command:
            path = self.remote_file(command)
            request = json.loads(input_data)
            content = base64.b64decode(request["content"])
            if self.tamper:
                content += b"tampered"
            self.files[path] = content
            self.put_count += 1
            return subprocess.CompletedProcess(command, 0, stdout="{}")
        raise AssertionError("Unexpected gh invocation: " + " ".join(command))


class CompanyTests(unittest.TestCase):
    def setUp(self):
        self.config = example("config")
        self.inventory = example("inventory")
        self.profile = example("profile")

    def fresh_event(self, project, harness="codex"):
        record = example("event")
        for key in ("id", "workspace_id", "harness"):
            record.pop(key, None)
        return company.prepare_event(project, record, harness)

    def test_two_questions_and_decisions_persist(self):
        result = company.plan(self.config, self.inventory, self.profile)
        self.assertEqual({q["id"] for q in result["questions"]}, {"profile_readme", "website"})
        self.config["decisions"] = {"profile_readme": "keep", "website": "reuse"}
        result = company.plan(self.config, self.inventory, self.profile)
        self.assertEqual(result["questions"], [])
        self.assertEqual(result["blockers"], [])
        self.assertEqual(result["actions"][2]["action"], "keep")

    def test_new_projects_private_existing_projects_unchanged(self):
        self.inventory["repositories"].append({"full_name": "example-user/existing", "visibility": "public"})
        self.inventory["projects"].append({"full_name": "example-user/existing"})
        existing = copy.deepcopy(self.profile["projects"][0])
        existing.update(slug="existing", title="Existing", repository="example-user/existing", visibility="private")
        self.profile["projects"].append(existing)
        actions = company.plan(self.config, self.inventory, self.profile)["actions"]
        self.assertEqual(actions[-2]["visibility"], "private")
        self.assertEqual(actions[-1]["visibility"], "public")
        self.assertEqual(actions[-1]["action"], "register")

    def test_private_target_public_blocks_sensitive_write(self):
        self.inventory["repositories"].append({"full_name": "example-user/Boss_Passport", "visibility": "public"})
        result = company.plan(self.config, self.inventory, self.profile)
        self.assertIn("visibility-mismatch", [b["reason"] for b in result["blockers"]])

    def test_new_website_cannot_replace_existing_target(self):
        self.config["decisions"] = {"profile_readme": "keep", "website": "new"}
        result = company.plan(self.config, self.inventory, self.profile)
        self.assertIn("new-website-needs-unused-repository-name", [b["reason"] for b in result["blockers"]])

    def test_unanswered_choices_do_not_generate(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "output"
            with self.assertRaises(ValueError):
                company.scaffold(self.config, self.profile, target)
            self.assertFalse(target.exists())

    def test_reuse_site_keeps_engineering_and_keep_preserves_homepage(self):
        self.config["decisions"] = {"profile_readme": "keep", "website": "reuse"}
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "output"
            company.scaffold(self.config, self.profile, output)
            self.assertFalse((output / "Profile").exists())
            self.assertFalse((output / "Website").exists())
            self.assertTrue((output / "Website_Adaptation/public-profile.json").is_file())
            self.assertTrue((output / "Boss_Passport/profile.json").is_file())
            self.assertFalse((output / "Boss_Passport/ai-notes").exists())
            positions = list((output / "Company_Workspace/positions").glob("*/POSITION.md"))
            self.assertEqual(len(positions), 3)

    def test_new_site_has_public_only_pages_artifact(self):
        self.config["decisions"] = {"profile_readme": "create", "website": "create"}
        self.profile["facts"][-1]["value"] = "PRIVATE_SENTINEL"
        self.profile["facts"][0]["sources"][0]["ref"] = "PRIVATE_SOURCE"
        self.profile["facts"][0]["extra"] = "PRIVATE_EXTRA"
        self.profile["projects"][0]["source"] = "https://example.org/PRIVATE_CODE"
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "output"
            company.scaffold(self.config, self.profile, output)
            for part in ("Website", "Profile"):
                for path in (output / part).rglob("*"):
                    if path.is_file():
                        self.assertNotIn("PRIVATE_", path.read_text(encoding="utf-8"))
            self.assertIn("path: site", (output / "Website/.github/workflows/pages.yml").read_text())
            self.assertTrue((output / "Profile/projects/example-tool/README.md").exists())
            self.assertFalse(json.loads((output / "manifest.json").read_text(encoding="utf-8"))["deployed"])

    def test_bind_preserves_existing_rules_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "AGENTS.md").write_text("# Existing\nKeep my rules.\n", encoding="utf-8")
            company.bind(root, self.config, "example-user/example-tool")
            first = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            company.bind(root, self.config, "example-user/example-tool")
            second = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            self.assertEqual(first, second)
            self.assertTrue((root / "AGENTS.md").read_text(encoding="utf-8").startswith("# Existing\nKeep my rules."))
            for path in company.PLATFORMS.values():
                self.assertTrue((root / path).exists())
            config = json.loads((root / ".boss-and-company/company.json").read_text(encoding="utf-8"))
            self.assertNotIn("workspace_roots", config)
            self.assertTrue(config["multi_workspace"])
            self.assertEqual(config["skill_version"], company.SKILL_VERSION)

    def test_bind_protects_private_mapping_and_preserves_unknown_local_fields(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            company.bind(root, self.config, "example-user/example-tool")
            public_path = root / ".boss-and-company/company.json"
            local_path = root / ".boss-and-company/local.json"
            public = json.loads(public_path.read_text(encoding="utf-8"))
            local = json.loads(local_path.read_text(encoding="utf-8"))
            self.assertNotIn("repositories", public)
            self.assertIn("workspace_id", local)
            self.assertEqual(local["repositories"]["company"], "example-user/Company_Workspace")
            self.assertIn("/.boss-and-company/local.json", (root / ".gitignore").read_text(encoding="utf-8"))
            for name in company.PLATFORMS.values():
                self.assertNotIn("Company_Workspace", (root / name).read_text(encoding="utf-8"))
            public["local_convention"] = "must not diverge across checkouts"
            public["repositories"] = {"company": "example-user/Company_Workspace"}
            local["tool_secret"] = "ignored file"
            public_path.write_text(company.encoded(public), encoding="utf-8")
            local_path.write_text(company.encoded(local), encoding="utf-8")
            company.bind(root, self.config, "example-user/example-tool")
            canonical = json.loads(public_path.read_text(encoding="utf-8"))
            self.assertNotIn("local_convention", canonical)
            self.assertNotIn("repositories", canonical)
            self.assertEqual(json.loads(local_path.read_text(encoding="utf-8"))["tool_secret"], "ignored file")

    def test_corrupt_receipt_does_not_report_synced(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            company.bind(root, self.config, "example-user/example-tool")
            record = self.fresh_event(root)
            company.event(root, record)
            url = "https://github.com/example-user/Company_Workspace/blob/main/events/" + record["id"] + ".json"
            company.acknowledge(root, record["id"], url)
            (root / f".boss-and-company/receipts/{record['id']}.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValueError):
                company.event(root, record)

    def test_malformed_rule_block_fails_before_writes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "CLAUDE.md").write_text(company.BEGIN, encoding="utf-8")
            with self.assertRaises(ValueError):
                company.bind(root, self.config, "example-user/example-tool")
            self.assertFalse((root / "AGENTS.md").exists())

    def test_install_skill_for_three_native_hosts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result = company.bind(root, self.config, "example-user/example-tool", install=True)
            self.assertTrue(result["skills_installed"])
            for folder in company.SKILL_DIRS.values():
                installed = root / folder / "boss-and-company"
                self.assertEqual((installed / "SKILL.md").read_bytes(), (SKILL / "SKILL.md").read_bytes())
                self.assertTrue((installed / "scripts/company.py").exists())
            company.bind(root, self.config, "example-user/example-tool", install=True)

    def test_conflicting_installed_skill_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / ".claude/skills/boss-and-company/SKILL.md"
            target.parent.mkdir(parents=True)
            target.write_text("User custom version", encoding="utf-8")
            with self.assertRaises(ValueError):
                company.bind(root, self.config, "example-user/example-tool", install=True)
            self.assertEqual(target.read_text(encoding="utf-8"), "User custom version")
            self.assertFalse((root / "AGENTS.md").exists())

    def test_event_pending_idempotence_conflict_and_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            company.bind(root, self.config, "example-user/example-tool")
            record = self.fresh_event(root)
            self.assertEqual(company.event(root, record)["status"], "pending")
            self.assertEqual(company.event(root, record)["status"], "pending")
            changed = copy.deepcopy(record)
            changed["summary"] = "different"
            with self.assertRaises(ValueError):
                company.event(root, changed)
            with self.assertRaises(ValueError):
                company.acknowledge(root, record["id"], "https://github.com/other/repo/blob/main/events/" + record["id"] + ".json")
            url = "https://github.com/example-user/Company_Workspace/blob/main/events/" + record["id"] + ".json"
            self.assertEqual(company.acknowledge(root, record["id"], url)["status"], "synced")
            self.assertEqual(company.event(root, record)["status"], "synced")
            self.assertTrue((root / f".boss-and-company/outbox/{record['id']}.json").exists())

    def test_event_rejects_other_project_and_path_traversal(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            company.bind(root, self.config, "example-user/example-tool")
            for key, value in (("id", "../../escape"), ("project", "example-user/different"), ("kind", "every-tool-call"), ("recorded_at", "yesterday")):
                record = self.fresh_event(root)
                record[key] = value
                with self.assertRaises(ValueError):
                    company.event(root, record)

    def test_unsafe_links_escape_and_public_projection(self):
        self.profile["facts"][0]["value"] = '<script>alert(1)</script> [click](javascript:evil) |'
        inferred = copy.deepcopy(self.profile["facts"][0])
        inferred.update(id="guess", value="INFERRED_SECRET", status="inferred")
        self.profile["facts"].append(inferred)
        inferred_project = copy.deepcopy(self.profile["projects"][0])
        inferred_project.update(slug="inferred-project", repository="example-user/inferred-project",
                                summary="INFERRED_PROJECT_SECRET", status="inferred")
        self.profile["projects"].append(inferred_project)
        with tempfile.TemporaryDirectory() as temp:
            render.render(self.profile, temp)
            html = (Path(temp) / "public/index.html").read_text(encoding="utf-8")
            self.assertNotIn("<script>", html)
            self.assertNotIn("INFERRED_SECRET", html)
            self.assertNotIn("INFERRED_PROJECT_SECRET", html)
            readme = (Path(temp) / "public/README.md").read_text(encoding="utf-8")
            self.assertIn(r"\[click\]", readme)
        self.profile["projects"][0]["demo"] = "javascript:alert(1)"
        with self.assertRaises(ValueError):
            render.validate(self.profile)

    def test_discovered_project_must_join_canonical_registry(self):
        self.inventory["projects"].append({"full_name": "example-user/unregistered"})
        result = company.plan(self.config, self.inventory, self.profile)
        self.assertIn("project-profile-missing", [b["reason"] for b in result["blockers"]])
        record = copy.deepcopy(self.profile["projects"][0])
        record.update(slug="unregistered", repository="example-user/unregistered")
        self.profile["projects"].append(record)
        result = company.plan(self.config, self.inventory, self.profile)
        self.assertNotIn("project-profile-missing", [b["reason"] for b in result["blockers"]])

    def test_history_does_not_read_transcript(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "sessions").mkdir()
            (root / "sessions/rollout-id-1.jsonl").write_text("PRIVATE_BODY", encoding="utf-8")
            (root / "session_index.jsonl").write_text(json.dumps({"id":"id-1", "thread_name":"简历", "updated_at":"2026-11-15"}, ensure_ascii=False) + "\nmalformed\n", encoding="utf-8")
            result = history_index.find(root, ["简历"], 5)
            self.assertEqual(len(result["candidates"]), 1)
            self.assertFalse(result["bodies_read"])
            self.assertNotIn("PRIVATE_BODY", json.dumps(result))

    def test_existing_output_is_not_overwritten(self):
        self.config["decisions"] = {"profile_readme":"create", "website":"create"}
        with tempfile.TemporaryDirectory() as temp:
            marker = Path(temp) / "keep.txt"
            marker.write_text("keep")
            with self.assertRaises(ValueError):
                company.scaffold(self.config, self.profile, temp)
            self.assertEqual(marker.read_text(), "keep")

    def test_command_line_initialization_and_handoff_roundtrip(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config_path = root / "config.json"
            config_path.write_text(company.encoded(self.config), encoding="utf-8")
            script = str(SKILL / "scripts/company.py")

            def command(*args):
                process = subprocess.run([sys.executable, "-B", "-X", "utf8", script, *map(str, args)], capture_output=True, text=True, encoding="utf-8")
                self.assertEqual(process.returncode, 0, process.stderr)
                return json.loads(process.stdout)

            result = command("plan", "--config", config_path, "--inventory", SKILL / "assets/examples/inventory.json", "--profile", SKILL / "assets/examples/profile.json")
            self.assertEqual(len(result["questions"]), 2)
            self.config["decisions"] = {"profile_readme":"create", "website":"create"}
            config_path.write_text(company.encoded(self.config), encoding="utf-8")
            result = command("scaffold", "--config", config_path, "--profile", SKILL / "assets/examples/profile.json", "--output", root / "generated")
            self.assertFalse(result["deployed"])
            project = root / "project"
            project.mkdir()
            command("bind", "--config", config_path, "--project", project, "--repo", "example-user/example-tool", "--install-skills")
            command("workspace", "--project", project)
            record = self.fresh_event(project, "workbuddy")
            record_path = root / "record.json"
            record_path.write_text(company.encoded(record), encoding="utf-8")
            args = ("event", "--project", project, "--record", record_path, "--harness", "workbuddy")
            self.assertEqual(command(*args)["status"], "pending")
            url = "https://github.com/example-user/Company_Workspace/blob/main/events/" + record["id"] + ".json"
            command("acknowledge", "--project", project, "--id", record["id"], "--remote-url", url)
            self.assertEqual(command(*args)["status"], "synced")

    def test_sync_verifies_private_repo_uploads_and_reads_back(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            company.bind(root, self.config, "example-user/example-tool")
            company.workspace(root)
            record = self.fresh_event(root)
            company.event(root, record)
            runner = FakeGitHub()
            first = sync.sync(root, runner=runner)
            self.assertTrue(first["ok"], first)
            self.assertEqual(first["workspaces"][0]["status"], "synced")
            self.assertEqual(first["results"][0]["status"], "synced")
            self.assertEqual(runner.put_count, 2)
            self.assertEqual(company.event(root, record)["status"], "synced")
            second = sync.sync(root, runner=runner)
            self.assertEqual(second["workspaces"][0]["status"], "already-synced")
            self.assertEqual(second["results"][0]["status"], "already-synced")
            self.assertEqual(runner.put_count, 2)

    def test_sync_blocks_public_company_repo_and_remote_conflicts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            company.bind(root, self.config, "example-user/example-tool")
            record = self.fresh_event(root)
            company.event(root, record)
            with self.assertRaises(sync.SyncError):
                sync.sync(root, runner=FakeGitHub(private=False))
            conflicted = FakeGitHub()
            conflicted.files[f"events/{record['id']}.json"] = b"different remote content"
            result = sync.sync(root, runner=conflicted)
            self.assertFalse(result["ok"])
            self.assertEqual(result["results"][0]["status"], "conflict")
            self.assertFalse((root / f".boss-and-company/receipts/{record['id']}.json").exists())
            tampered = sync.sync(root, runner=FakeGitHub(tamper=True))
            self.assertFalse(tampered["ok"])
            self.assertEqual(tampered["results"][0]["status"], "failed")
            self.assertIn("readback", tampered["results"][0]["detail"])
            self.assertFalse((root / f".boss-and-company/receipts/{record['id']}.json").exists())

    def test_multiple_checkouts_and_harnesses_do_not_collide(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workbuddy = root / "workbuddy-checkout"
            codex = root / "codex-checkout"
            workbuddy.mkdir()
            codex.mkdir()
            company.bind(workbuddy, self.config, "example-user/example-tool")
            company.bind(codex, self.config, "example-user/example-tool")
            self.assertEqual((workbuddy / ".boss-and-company/company.json").read_bytes(),
                             (codex / ".boss-and-company/company.json").read_bytes())
            first_ws = company.project_mapping(workbuddy)["workspace_id"]
            second_ws = company.project_mapping(codex)["workspace_id"]
            self.assertNotEqual(first_ws, second_ws)
            company.workspace(workbuddy)
            company.workspace(codex)
            first = self.fresh_event(workbuddy, "workbuddy")
            second = self.fresh_event(codex, "codex")
            same_checkout_other_harness = self.fresh_event(workbuddy, "claude-code")
            self.assertEqual(first["project"], second["project"])
            self.assertNotEqual(first["id"], second["id"])
            self.assertTrue(first["id"].startswith(first_ws + "-"))
            self.assertTrue(second["id"].startswith(second_ws + "-"))
            self.assertEqual(first["workspace_id"], same_checkout_other_harness["workspace_id"])
            self.assertNotEqual(first["harness"], same_checkout_other_harness["harness"])
            company.event(workbuddy, first)
            company.event(codex, second)
            runner = FakeGitHub()
            first_sync = sync.sync(workbuddy, runner=runner)
            second_sync = sync.sync(codex, runner=runner)
            self.assertTrue(first_sync["ok"], first_sync)
            self.assertTrue(second_sync["ok"], second_sync)
            self.assertEqual(len(runner.files), 4)
            self.assertTrue(any(path.startswith("workspaces/") for path in runner.files))
            self.assertTrue(any(path.startswith("events/") for path in runner.files))
            self.assertTrue((workbuddy / f".boss-and-company/receipts/{first['id']}.json").exists())
            self.assertTrue((codex / f".boss-and-company/receipts/{second['id']}.json").exists())


class ClassificationTests(unittest.TestCase):
    def setUp(self):
        self.valid = example("classification")
        self.config = example("config")
        self.profile = example("profile")

    def test_example_is_valid(self):
        self.assertTrue(classification.validate_classification(self.valid))
        self.assertEqual(classification.CLASSIFICATION_VERSION, 1)

    def test_rejects_unknown_missing_and_bad_values(self):
        for mutate in (
            lambda d: d.pop("stars"),
            lambda d: d.update(extra="x"),
            lambda d: d.update(showcase="unknown"),
            lambda d: d.update(activity_tier="hot"),
            lambda d: d.update(stars=-1),
            lambda d: d.update(stars=True),
            lambda d: d.update(data_source="guess"),
            lambda d: d.update(reviewed_at="16-11-2026"),
            lambda d: d.update(pushed_at="2026-11-16"),
            lambda d: d.update(is_fork="no"),
            lambda d: d.update(stars=5, visibility="private"),
        ):
            record = copy.deepcopy(self.valid)
            mutate(record)
            with self.assertRaises(ValueError):
                classification.validate_classification(record)

    def test_activity_tier_thresholds(self):
        from datetime import datetime, timezone, timedelta
        now = datetime(2026, 11, 16, tzinfo=timezone.utc)
        self.assertEqual(classification.activity_tier_from_pushed_at(
            (now - timedelta(days=7)).isoformat(), now), "active")
        self.assertEqual(classification.activity_tier_from_pushed_at(
            (now - timedelta(days=200)).isoformat(), now), "recent")
        self.assertEqual(classification.activity_tier_from_pushed_at(
            (now - timedelta(days=400)).isoformat(), now), "dormant")
        self.assertEqual(classification.activity_tier_from_pushed_at(None, now), "dormant")

    def test_attach_preserves_unknown_keys_and_replaces_only_valid(self):
        record = {"slug": "x", "schema_version": 2, "custom": "keep"}
        attached = classification.attach(record, self.valid)
        self.assertEqual(attached["custom"], "keep")
        self.assertEqual(attached["classification_version"], 1)
        self.assertEqual(attached["classification"], self.valid)
        self.assertNotIn("classification", record)
        with self.assertRaises(ValueError):
            classification.attach(record, {"showcase": "bad"})

    def test_sort_key_is_stars_then_pushed_at(self):
        def rec(stars, pushed, vis="public"):
            c = dict(self.valid, stars=stars, pushed_at=pushed, visibility=vis)
            return {"classification": c}
        newest = rec(0, "2026-11-16T00:00:00Z")
        older = rec(0, "2026-01-01T00:00:00Z")
        starred = rec(1, "2020-01-01T00:00:00Z")
        nopush = rec(0, None)
        ordered = sorted([older, nopush, newest, starred], key=classification.sort_key)
        self.assertEqual(ordered, [starred, newest, older, nopush])

    def test_scaffold_emits_valid_classification_and_profile_validates(self):
        self.config["decisions"] = {"profile_readme": "keep", "website": "reuse"}
        self.profile["projects"][0]["classification"] = copy.deepcopy(self.valid)
        render.validate(self.profile)
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "output"
            company.scaffold(self.config, self.profile, output)
            data = json.loads((output / "Company_Workspace/projects/example-tool/PROJECT.json").read_text(encoding="utf-8"))
            self.assertEqual(data["classification_version"], 1)
            self.assertEqual(data["classification"], self.valid)
            self.assertEqual(data["schema_version"], 2)
            self.assertNotIn("classification", json.loads((output / "Website_Adaptation/public-profile.json").read_text(encoding="utf-8"))["projects"][0])

    def test_bad_profile_classification_is_rejected(self):
        bad = copy.deepcopy(self.valid)
        bad["showcase"] = "leak"
        self.profile["projects"][0]["classification"] = bad
        with self.assertRaises(ValueError):
            render.validate(self.profile)


if __name__ == "__main__":
    unittest.main()
