"""Offline generation contracts: name validation, task growth and stale-page cleanup."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class TaskPages(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "site"
        (self.root / "scripts").mkdir(parents=True)
        shutil.copy2(ROOT / "scripts/build_tasks.py", self.root / "scripts/build_tasks.py")
        shutil.copy2(ROOT / "index.html", self.root / "index.html")
        shutil.copytree(ROOT / "content", self.root / "content")
        self.catalog = self.root / "content/tasks/catalog.json"
        self.tasks = json.loads(self.catalog.read_text())

    def run_builder(self, *args, success=True):
        # Invocation from outside the checkout must resolve its own source files.
        result = subprocess.run([sys.executable, str(self.root / "scripts/build_tasks.py"), *args],
                                cwd=self.root.parent, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0 if success else 1, result.stdout + result.stderr)
        return result

    def write_catalog(self):
        self.catalog.write_text(json.dumps(self.tasks))

    def test_full_build_check_and_generated_links(self):
        self.run_builder()
        self.run_builder("--check")
        homepage = (self.root / "index.html").read_text()
        for task in self.tasks:
            page = self.root / "tasks" / task["name"] / "index.html"
            text = page.read_text()
            self.assertIn(task["title"], text)
            self.assertIn(f'aria-current="page"><span class="task-directory-title">{task["navTitle"]}', text)
            for neighbor in self.tasks:
                self.assertIn(f'../{neighbor["name"]}/', text)
            self.assertEqual(f'href="tasks/{task["name"]}/"' in homepage, task.get("featured", False))
            self.assertNotIn("home-task-mode", text)
        self.assertEqual(len(list((self.root / "tasks").glob("*/index.html"))), len(self.tasks))

    def test_new_task_updates_directory_adjacent_and_featured_cards(self):
        self.run_builder()
        name = "hybrid-evidence-search"
        task = {"name": name, "title": "Hybrid Evidence Search", "summary": "Build and improve evidence retrieval.",
                "tag": "hybrid retrieval", "status": "setting", "featured": True, "hardware": "cpu"}
        self.tasks.append(task)
        self.write_catalog()
        (self.root / f"content/tasks/{name}.md").write_text(
            f'# {task["title"]}\n\n* **Task name**: `search-swe/{name}`\n\n## Goal\n\nRetrieve evidence.\n')
        self.run_builder("--check", success=False)
        self.run_builder()
        self.run_builder("--check")
        self.assertIn(f'href="tasks/{name}/"', (self.root / "index.html").read_text())
        ordered = sorted(self.tasks, key=lambda t: (t["hardware"] == "gpu", t["title"].casefold(), t["name"]))
        previous_task = ordered[ordered.index(task) - 1]
        previous = (self.root / "tasks" / previous_task["name"] / "index.html").read_text()
        self.assertIn(f'../{name}/', previous)
        self.assertIn("Next task", previous)
        self.assertTrue((self.root / "tasks" / name / "index.html").is_file())

    def test_full_build_removes_only_obsolete_generated_pages(self):
        self.run_builder()
        removed = self.tasks.pop()
        self.write_catalog()
        (self.root / "content/tasks" / (removed["name"] + ".md")).unlink()
        stale = self.root / "tasks" / removed["name"] / "index.html"
        extra = stale.parent / "notes.txt"
        extra.write_text("unrelated content")
        manual = self.root / "tasks/manual/index.html"
        manual.parent.mkdir()
        manual.write_text("hand-written page")
        before = stale.read_bytes()
        self.assertIn("obsolete", self.run_builder("--check", success=False).stdout)
        self.assertEqual(stale.read_bytes(), before)
        self.run_builder()
        self.assertFalse(stale.exists())
        self.assertTrue(extra.exists())
        self.assertTrue(manual.exists())
        self.run_builder("--check")

    def test_catalog_only_keeps_detail_pages_and_defers_cleanup(self):
        self.run_builder()
        removed = self.tasks.pop()
        self.write_catalog()
        detail = self.root / "tasks" / removed["name"] / "index.html"
        before = detail.read_bytes()
        self.run_builder("--catalog-only")
        self.assertEqual(detail.read_bytes(), before)
        self.run_builder("--catalog-only", "--check")
        self.run_builder("--check", success=False)

    def test_invalid_names_duplicates_and_legacy_metadata_fail_before_writing(self):
        original = self.catalog.read_text()
        for name in ("task-1-1", "all", "../escape", "Title", "one-two-three-four-five-six", "double--dash"):
            with self.subTest(name=name):
                self.tasks[0]["name"] = name
                self.write_catalog()
                self.run_builder(success=False)
                self.assertFalse((self.root / "tasks").exists())
        self.tasks = json.loads(original)
        self.tasks.append(self.tasks[0].copy())
        self.write_catalog()
        self.run_builder(success=False)
        for key, value in (("mode", "implementation"), ("id", "task-1-1")):
            self.tasks = json.loads(original)
            self.tasks[0][key] = value
            self.write_catalog()
            self.run_builder(success=False)

    def test_hardware_groups_order_and_copy_names(self):
        self.run_builder()
        text = (self.root / "tasks/index.html").read_text()
        for hardware in ("cpu", "gpu"):
            section = text.split(f'aria-labelledby="{hardware}-tasks">', 1)[1].split('</section>', 1)[0]
            expected = sorted((t for t in self.tasks if t["hardware"] == hardware),
                              key=lambda t: (t["title"].casefold(), t["name"]))
            positions = [section.index(f'<li id="{t["name"]}">') for t in expected]
            self.assertEqual(positions, sorted(positions))
            for task in expected:
                self.assertIn(f'<code>{task["name"]}</code>', section)
                self.assertIn(f'data-task-name="{task["name"]}"', section)
            for task in self.tasks:
                self.assertEqual(f'<li id="{task["name"]}">' in section, task["hardware"] == hardware)
        self.tasks[0]["hardware"] = "unknown"
        self.write_catalog()
        self.assertIn("hardware must be cpu or gpu", self.run_builder(success=False).stderr)

    def test_missing_or_mismatched_setting_fails(self):
        task = self.tasks[0]
        source = self.root / "content/tasks" / (task["name"] + ".md")
        original = source.read_text()
        for text in (original.replace("# " + task["title"], "# Wrong title"),
                     original.replace("search-swe/" + task["name"], "search-swe/wrong-name"),
                     original.replace("## ", "* **Task type**: `create`\n\n## ", 1)):
            source.write_text(text)
            self.run_builder(success=False)
        source.unlink()
        self.run_builder(success=False)


if __name__ == "__main__":
    unittest.main()
