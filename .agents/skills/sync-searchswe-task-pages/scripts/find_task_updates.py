"""Read-only comparison of benchmark task manifests and the homepage catalog."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import tomllib


def compare(repo_root: Path, site_root: Path) -> dict:
    manifests = sorted((repo_root / "tasks").glob("*/task.toml"))
    if not manifests:
        raise ValueError(f"No task manifests found under {repo_root / 'tasks'}")
    upstream = set()
    for manifest in manifests:
        name = manifest.parent.name
        task = tomllib.loads(manifest.read_text(encoding="utf-8"))
        if task.get("task", {}).get("name") != f"search-swe/{name}":
            raise ValueError(f"{manifest}: task.name does not match its directory")
        upstream.add(name)

    catalog = json.loads((site_root / "content/tasks/catalog.json").read_text(encoding="utf-8"))
    if not isinstance(catalog, list) or not all(
        isinstance(task, dict) and isinstance(task.get("name"), str) for task in catalog
    ):
        raise ValueError("Homepage catalog must be a list of tasks with string names")
    website = {task["name"] for task in catalog}
    if len(website) != len(catalog):
        raise ValueError("Duplicate task names in homepage catalog")
    return {
        "benchmark_root": str(repo_root),
        "site_root": str(site_root),
        "new_tasks": sorted(upstream - website),
        "site_only_tasks": sorted(website - upstream),
        "shared_task_count": len(upstream & website),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True, type=Path, help="Benchmark checkout")
    parser.add_argument("--site-root", required=True, type=Path, help="Homepage checkout")
    args = parser.parse_args()
    try:
        result = compare(args.repo_root.expanduser().resolve(), args.site_root.expanduser().resolve())
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
