"""Automation switches, read-only refresh, commit recording and public projection."""
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
import activity
import automation
import auto
import company
import refresh
import sync


def example(name):
    return json.loads((SKILL / f"assets/examples/{name}.json").read_text(encoding="utf-8"))


def completed(command, stdout, code=0):
    return subprocess.CompletedProcess(command, code, stdout=stdout)


class FakeRemote:
    """In-memory gh API covering both private repositories and directory listings."""

    BOSS = "example-user/Boss_Passport"
    COMPANY = "example-user/Company_Workspace"

    def __init__(self, switches=None, private=True):
        self.private = private
        self.put_count = 0
        self.puts = []
        self.boss = {}
        self.company = {}
        self.directories = {}
        settings = copy.deepcopy(automation.DEFAULTS)
        settings.update(switches or {})
        self.boss["automation.json"] = json.dumps(settings, ensure_ascii=False).encode("utf-8")
        self.boss["SUMMARY.md"] = "# Boss\n\n- 近期目标：示例目标\n".encode("utf-8")
        self.company["company.json"] = b'{"schema_version":2,"multi_workspace":true}\n'
        self.company["README.md"] = b"# Company Workspace\n"
        self.company["projects/example-tool/STATE.md"] = "# Example Tool\n\n当前处于原型阶段。\n".encode("utf-8")
        self.company["projects/example-tool/PROJECT.json"] = b"{}\n"
        self.company["events/evt-001.json"] = json.dumps({
            "schema_version": 2, "id": "evt-001", "workspace_id": "ws-remote",
            "harness": "codex", "recorded_at": "2026-11-15T09:00:00Z",
            "project": "example-user/example-tool", "kind": "milestone",
            "summary": "远端示例事件"}, ensure_ascii=False).encode("utf-8")
        self.directories[(self.COMPANY, "projects")] = [{"name": "example-tool", "type": "dir"}]
        self.directories[(self.COMPANY, "events")] = [{"name": "evt-001.json", "type": "file"}]
        self.directories[(self.COMPANY, "workspaces")] = [{"name": "ws-remote.json", "type": "file"}]
        self.directories[(self.COMPANY, "positions")] = [{"name": "Coder_Position", "type": "dir"}]

    @staticmethod
    def endpoint(command):
        for argument in command:
            if argument.startswith("repos/"):
                return argument
        raise AssertionError("Missing repos endpoint: " + " ".join(command))

    @staticmethod
    def split(endpoint):
        parts = endpoint.split("/")
        repository = parts[1] + "/" + parts[2]
        path = "/".join(parts[4:]) if len(parts) > 4 and parts[3] == "contents" else ""
        return repository, path

    def bucket(self, repository):
        return self.boss if repository == self.BOSS else self.company

    def __call__(self, command, input_data=None):
        endpoint = self.endpoint(command)
        repository, path = self.split(endpoint)
        if "/commits/" in endpoint and "--jq" in command:
            return completed(command, "a" * 40)
        if "--jq" in command and not path:
            return completed(command, json.dumps({"private": self.private, "default_branch": "main"}))
        if "-i" in command:
            payload = self.bucket(repository).get(path)
            if payload is None:
                return completed(command, "HTTP/2.0 404 Not Found\n\n{}", 1)
            body = json.dumps({"content": base64.b64encode(payload).decode("ascii"),
                               "html_url": f"https://github.com/{repository}/blob/main/{path}"})
            return completed(command, "HTTP/2.0 200 OK\n\n" + body)
        if "PUT" in command:
            request = json.loads(input_data)
            self.company[path] = base64.b64decode(request["content"])
            self.puts.append(path)
            self.put_count += 1
            return completed(command, "{}")
        listing = self.directories.get((repository, path), [])
        return completed(command, json.dumps(listing))


class FakeGit:
    def __init__(self, sha="a" * 40, subject="feat: example change"):
        self.sha = sha
        self.subject = subject

    def __call__(self, command, input_data=None):
        return completed(command, f"{self.sha}\n2026-11-16T13:00:00+08:00\n{self.subject}\nHEAD -> main, origin/main")


def bound(tmp):
    root = Path(tmp) / "project"
    root.mkdir()
    company.bind(root, example("config"), "example-user/example-tool")
    return root


def override(root, values):
    path = root / ".boss-and-company/local.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data[automation.LOCAL_OVERRIDE_KEY] = values
    path.write_text(company.encoded(data), encoding="utf-8")


def public_event(root, name, extra=None):
    record = {
        "schema_version": 2, "id": name, "workspace_id": "ws-public",
        "harness": "codex", "recorded_at": "2026-11-15T10:00:00Z",
        "task_id": "public-task", "project": "example-user/example-tool",
        "role": "Coder_Position", "actor": "codex", "kind": "milestone",
        "summary": "PRIVATE_SENTINEL 不应出现在公开投影",
        "artifacts": ["PRIVATE_ARTIFACT"], "next": "继续", "verification": {"status": "passed", "detail": "ok"},
        "visibility": "public", "public": {"title": "公开进展示例", "stage": "in-progress"},
    }
    record.update(extra or {})
    path = root / f".boss-and-company/outbox/{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(company.encoded(record), encoding="utf-8")
    return record


class AutomationTests(unittest.TestCase):
    def test_defaults_and_local_downgrade_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root = bound(temp)
            resolved = automation.effective_settings(root)
            self.assertEqual(resolved["source"], "defaults")
            self.assertTrue(resolved["settings"]["auto_refresh"])
            for key in ("auto_record", "sync_after_record", "activity_public"):
                self.assertFalse(resolved["settings"][key])
            override(root, {"auto_refresh": False, "auto_record": True, "unknown": True})
            resolved = automation.effective_settings(root)
            self.assertFalse(resolved["settings"]["auto_refresh"])
            self.assertFalse(resolved["settings"]["auto_record"], "Local must not escalate a write switch")
            self.assertIn("auto_refresh", resolved["local_overrides_applied"])
            reasons = {item["key"]: item["reason"] for item in resolved["local_overrides_ignored"]}
            self.assertEqual(reasons["auto_record"], "local-escalation-blocked")
            self.assertEqual(reasons["unknown"], "unknown-switch")

    def test_remote_switches_and_dependent_switch(self):
        with tempfile.TemporaryDirectory() as temp:
            root = bound(temp)
            remote = {"schema_version": 2, "automation_version": 1,
                      "auto_refresh": True, "auto_record": True,
                      "sync_after_record": True, "activity_public": True}
            parsed = automation.validate_remote(remote)
            self.assertTrue(parsed["activity_public"])
            override(root, {"auto_record": False})
            resolved = automation.effective_settings(root, remote)
            self.assertEqual(resolved["source"], "boss-passport")
            self.assertFalse(resolved["settings"]["auto_record"])
            self.assertFalse(resolved["settings"]["sync_after_record"], "Dependent switch must be forced off")
            self.assertTrue(resolved["settings"]["activity_public"])
            for broken in ({**remote, "automation_version": 99},
                           {**remote, "auto_record": "yes"},
                           {key: value for key, value in remote.items() if key != "schema_version"}):
                with self.assertRaises(ValueError):
                    automation.validate_remote(broken)

    def test_bind_gitignores_private_cache(self):
        with tempfile.TemporaryDirectory() as temp:
            root = bound(temp)
            ignores = (root / ".gitignore").read_text(encoding="utf-8")
            self.assertIn("/.boss-and-company/cache/", ignores)
            self.assertEqual(automation.cache_guard(root), root / ".boss-and-company/cache")
            (root / ".gitignore").write_text(ignores.replace("/.boss-and-company/cache/\n", ""), encoding="utf-8")
            with self.assertRaises(ValueError):
                automation.cache_guard(root)

    def test_session_start_reads_private_state_without_remote_writes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = bound(temp)
            remote = FakeRemote()
            result = auto.session_start(root, "workbuddy", runner=remote)
            self.assertEqual(result["status"], "refreshed", result)
            self.assertFalse(result["remote_writes"])
            self.assertEqual(remote.put_count, 0)
            self.assertEqual(result["source"], "boss-passport")
            self.assertEqual(result["boss_sha"], "a" * 40)
            cache = root / ".boss-and-company/cache"
            self.assertTrue((cache / "CONTEXT.md").is_file())
            self.assertTrue((cache / "boss/SUMMARY.md").is_file())
            self.assertTrue((cache / "company/projects/example-tool/STATE.md").is_file())
            self.assertTrue((cache / "company/events/evt-001.json").is_file())
            context = (cache / "CONTEXT.md").read_text(encoding="utf-8")
            self.assertIn("example-user/example-tool", context)
            self.assertIn("不得提交", context)
            snapshot = json.loads((cache / "snapshot.json").read_text(encoding="utf-8"))
            self.assertFalse(snapshot["stale"])
            self.assertEqual(snapshot["project_count"], 1)
            self.assertEqual(snapshot["event_count"], 1)

    def test_refresh_failure_preserves_cache_and_marks_stale(self):
        with tempfile.TemporaryDirectory() as temp:
            root = bound(temp)
            self.assertEqual(auto.session_start(root, runner=FakeRemote())["status"], "refreshed")
            broken = FakeRemote(private=False)
            result = auto.session_start(root, runner=broken)
            self.assertEqual(result["status"], "stale", result)
            self.assertTrue(result["previous_cache_preserved"])
            self.assertFalse(result["remote_writes"])
            cache = root / ".boss-and-company/cache"
            self.assertTrue((cache / "CONTEXT.md").is_file())
            snapshot = json.loads((cache / "snapshot.json").read_text(encoding="utf-8"))
            self.assertTrue(snapshot["stale"])
            self.assertIn("stale_reason", snapshot)

    def test_post_commit_disabled_by_default(self):
        with tempfile.TemporaryDirectory() as temp:
            root = bound(temp)
            result = auto.post_commit(root, "codex", runner=FakeRemote(), git=FakeGit())
            self.assertEqual(result["status"], "disabled")
            self.assertFalse(result["remote_writes"])
            self.assertEqual(list((root / ".boss-and-company/outbox").glob("*.json")), [])

    def test_post_commit_is_private_idempotent_and_local_by_default(self):
        with tempfile.TemporaryDirectory() as temp:
            root = bound(temp)
            remote = FakeRemote(switches={"auto_record": True})
            self.assertEqual(auto.session_start(root, runner=remote)["status"], "refreshed")
            git = FakeGit(subject="feat: 提交含 PRIVATE_SENTINEL 的工作")
            first = auto.post_commit(root, "codex", runner=remote, git=git)
            self.assertEqual(first["status"], "recorded", first)
            self.assertEqual(first["visibility"], "private")
            self.assertEqual(first["local_status"], "pending")
            self.assertFalse(first["remote_writes"])
            self.assertEqual(remote.put_count, 0)
            path = root / f".boss-and-company/outbox/{first['id']}.json"
            record = json.loads(path.read_text(encoding="utf-8"))
            self.assertTrue(first["id"].startswith(record["workspace_id"] + "-commit-"))
            self.assertEqual(record["verification"]["status"], "not-run")
            self.assertEqual(record["commit"]["branch"], "main")
            self.assertNotIn(str(root), json.dumps(record, ensure_ascii=False), "No absolute local path")
            self.assertEqual(record["artifacts"], [])
            second = auto.post_commit(root, "codex", runner=remote, git=git)
            self.assertEqual(second["id"], first["id"])
            self.assertEqual(len(list((root / ".boss-and-company/outbox").glob("*.json"))), 1)

    def test_sync_after_record_only_uploads_the_commit_event(self):
        with tempfile.TemporaryDirectory() as temp:
            root = bound(temp)
            remote = FakeRemote(switches={"auto_record": True, "sync_after_record": True})
            self.assertEqual(auto.session_start(root, runner=remote)["status"], "refreshed")
            unrelated = public_event(root, "ws-public-unrelated")
            result = auto.post_commit(root, "workbuddy", runner=remote, git=FakeGit())
            self.assertEqual(result["status"], "synced", result)
            self.assertTrue(result["remote_writes"])
            self.assertEqual(remote.puts, [f"events/{result['id']}.json"],
                             "Unrelated pending event must stay local")
            self.assertFalse((root / f".boss-and-company/receipts/{unrelated['id']}.json").exists())
            self.assertTrue((root / f".boss-and-company/receipts/{result['id']}.json").exists())

    def test_activity_disabled_until_user_enables_it(self):
        with tempfile.TemporaryDirectory() as temp:
            root = bound(temp)
            public_event(root, "ws-public-1")
            projection, _ = activity.build_activity(root, example("profile"))
            self.assertFalse(projection["enabled"])
            self.assertEqual(projection["items"], [])

    def test_activity_strict_allowlist_and_privacy_selfcheck(self):
        with tempfile.TemporaryDirectory() as temp:
            root = bound(temp)
            remote = FakeRemote(switches={"activity_public": True})
            self.assertEqual(auto.session_start(root, runner=remote)["status"], "refreshed")
            public_event(root, "ws-public-ok")
            public_event(root, "ws-public-nomarker", {"visibility": "private"})
            public_event(root, "ws-public-nopublic", {"public": None})
            public_event(root, "ws-public-otherrepo", {"project": "example-user/private-project"})
            public_event(root, "ws-public-badstage", {"public": {"title": "x", "stage": "done"}})
            projection, effective = activity.build_activity(root, example("profile"))
            self.assertTrue(projection["enabled"])
            self.assertEqual(effective["source"], "boss-passport")
            self.assertEqual(len(projection["items"]), 1)
            item = projection["items"][0]
            self.assertEqual(set(item), {"date", "project", "title", "stage", "url"})
            self.assertEqual(item["title"], "公开进展示例")
            self.assertNotIn("PRIVATE_SENTINEL", json.dumps(projection, ensure_ascii=False))
            self.assertNotIn("PRIVATE_ARTIFACT", json.dumps(projection, ensure_ascii=False))
            activity.validate_projection(projection)
            for mutation in ({**item, "summary": "leak"}, {**item, "title": "a@b.com"},
                             {**item, "url": "https://github.com/other/repo"},
                             {**item, "title": "fix 0123456789abcdef"}):
                broken = copy.deepcopy(projection)
                broken["items"] = [mutation]
                with self.assertRaises(ValueError):
                    activity.validate_projection(broken)

    def test_status_is_offline_and_reports_effective_switches(self):
        with tempfile.TemporaryDirectory() as temp:
            root = bound(temp)
            result = auto.status(root)
            self.assertEqual(result["action"], "status")
            self.assertTrue(result["settings"]["auto_refresh"])
            self.assertFalse(result["settings"]["auto_record"])
            self.assertEqual(result["cache"]["files"], 0)
            self.assertFalse(result["remote_writes"])

    def test_auto_cli_status_roundtrip(self):
        with tempfile.TemporaryDirectory() as temp:
            root = bound(temp)
            script = str(SKILL / "scripts/auto.py")
            process = subprocess.run([sys.executable, "-B", "-X", "utf8", script,
                                      "status", "--project", str(root)],
                                     capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertEqual(json.loads(process.stdout)["action"], "status")
            activity_process = subprocess.run(
                [sys.executable, "-B", "-X", "utf8", script, "activity", "--project", str(root),
                 "--profile", str(SKILL / "assets/examples/profile.json"), "--output", str(Path(temp) / "activity.json")],
                capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(activity_process.returncode, 0, activity_process.stderr)
            self.assertFalse(json.loads(activity_process.stdout)["enabled"])
            self.assertFalse((Path(temp) / "activity.json").exists())


if __name__ == "__main__":
    unittest.main()
