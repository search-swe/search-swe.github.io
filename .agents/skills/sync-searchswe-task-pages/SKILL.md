---
name: sync-searchswe-task-pages
description: Sync task descriptions and the task catalog in the Search-SWE homepage repository from a local benchmark checkout after task contributions are added or revised. Also align the homepage contribution summary when requested. Use for website content, not benchmark task authoring or evaluation.
---

# Sync Search-SWE Task Pages

Update the website's editable task sources and regenerate its static pages from
the public contracts in a user-selected Search-SWE checkout. This skill belongs
under `.agents/skills/` in the homepage repository; no `AGENTS.md` is needed.

## Establish the source and scope

Resolve the homepage root and benchmark root explicitly. Prefer the path supplied
by the user; a sibling `../Search-SWE` is a candidate, not proof of identity.
Read both worktree statuses and record the benchmark HEAD. Preserve existing
edits. Use the selected local snapshot without an implicit pull, commit, push,
or deployment.

Read the site's `content/tasks/README.md`, `content/tasks/catalog.json`, and
`scripts/build_tasks.py`. Check the initial generated state with
`python scripts/build_tasks.py --check` and note pre-existing differences.
Consult the benchmark's current `docs/contributing.md` and task workflow for
the naming and package conventions that apply to the update. These documents
provide context; website synchronization does not require creating a benchmark
task, running its agent/verifier, downloading datasets, or publishing assets.

Discover tasks from package-local `tasks/*/task.toml`, not a manually maintained
list in the benchmark README. Run this skill's read-only inventory helper using
its actual path:

```bash
python "$SKILL_DIR/scripts/find_task_updates.py" \
  --repo-root "$BENCHMARK_ROOT" --site-root "$SITE_ROOT"
```

The helper identifies missing catalog entries, not semantic changes to existing
task contracts. For requested revisions, inspect the relevant package diff and
source files. A website-only entry may reflect an older benchmark checkout or
a rename: investigate it before deleting anything. Do not publish an unreviewed
local scaffold as an available task merely because its directory exists.

Check source history when a package README still says "draft", "pending review",
or "official publication pending". Such authoring notes can survive a merge;
they are not authoritative release status. Confirm inclusion in the selected
reviewed branch and check the current contribution guide. Verified upstream HF
pins may remain the final asset source; an absent official mirror does not by
itself make a merged task unavailable. Report stale source notes without editing
the benchmark or copying them into the public task description.

## Write the public task setting

For each selected task, read its `README.md`, `instruction.md`, `task.toml`, and
`assets.json`; consult `raw-instruction.md` when present. Use environment and
verifier source selectively to resolve resource, interface, or scoring details.
Inspect one similar website setting for formatting, not as a source of facts.
Keep the benchmark checkout read-only.

Build a concise evidence map before editing:

| Website content | Evidence to check |
| --- | --- |
| Canonical name, objective | Package directory, `task.name`, instructions |
| Runtime and constraints | TOML resource/budget fields, instructions, phase-specific environment |
| Public inputs and submission | Instructions, asset manifest, transferred artifact paths |
| Metric, gates and reward | Instructions and the verifier's scoring implementation |
| Data access and provenance | Asset manifest and package documentation |

Do not invent missing limits or silently reconcile contradictory source facts.
Resolve consequential conflicts from the current contract and implementation;
if ambiguity remains, report it and avoid asserting an unsupported detail.
Describe evaluation methodology and public constraints without copying hidden
queries, answers, author solutions, trial logs, or credentials into the site.

Discover actual verifier filenames instead of assuming a common `grade.py`
layout. For scoring, trace the invoked grader and its constants, not an unused
helper or an author-run result. Keep exact quality fractions, reference versions,
reward formulas, units, and agent/verifier/phase budgets distinct. Do not turn
diagnostic timing or memory measurements into extra reward terms.

Copy the existing page's structure, not its Python version, shell entry points,
or artifact convention. Some packages transfer source for independent
recompilation and expose a persistent stdin/stdout protocol instead of
`build.sh`/`run.sh`. Explain what the agent submits and what the verifier rebuilds,
using the actual task's commands and request/response field names. Link the full
instructions/configuration at the inspected commit when publishing a concise
summary, so omitted secondary limits remain traceable.

Create or update `content/tasks/<name>.md` with:

- A level-one title identical to the catalog `title` and a short objective.
- Metadata lines matching existing settings: `Task name` in the form
  `search-swe/<name>`, `Domain`, `Primary focus`, `Primary metric`, and `Tags`.
- Runtime and requirements, public input/output contract, and evaluation sections.
  Preserve meaningful distinctions between quality gates, rewarded metrics,
  diagnostics, timeouts, and infrastructure failures.

Use the site's supported Markdown subset: level-two/three headings, paragraphs,
flat lists, inline code, bold, links, and fenced code. Avoid Markdown tables,
nested lists, raw HTML, or unrendered math in task settings.

Update `content/tasks/catalog.json` with `name`, `title`, `summary`, `tag`, and
`status`; `navTitle`, `homepageSummary`, and `featured` are optional. Use the
canonical descriptive name as both Markdown filename and URL slug; do not
restore numeric task IDs or implementation/optimization categories. Preserve
existing order and featured selection unless asked to change them. New tasks
normally append with `status: "setting"` and `featured: false`, so the catalog
grows without expanding the homepage's curated selection.

When contribution guidance is in scope, update only the relevant summary in
`index.html` against the benchmark's current `docs/contributing.md`. Keep it
brief and link to the authoritative guide instead of copying its full workflow.
The benchmark's rule that ordinary contributions stay inside their task package
does not eliminate this separate website catalog: update the site's catalog and
Markdown here, without adding a shared task inventory to the benchmark.

## Regenerate and verify

From the homepage root:

```bash
python scripts/build_tasks.py
python scripts/build_tasks.py --check
python -m unittest discover -s scripts -p 'test_*.py'
git diff --check
```

Task membership, ordering, or setting changes require the **full** generator,
not `--catalog-only`: every detail page includes the task directory and adjacent
navigation. Edit Markdown/catalog sources rather than generated HTML. The full
builder also removes obsolete pages bearing its generated marker, so review
those deletions against the requested scope.

Rerun the inventory helper and confirm intended new tasks are present. Check the
new `/tasks/<name>/` page, catalog entry, all task-directory entries, previous/next
links, and relative CSS/image paths. Keep website page links free of `.html`
suffixes. Use an existing local preview when available; inspect desktop/mobile
rendering if browser tooling is available, and distinguish HTTP/link checks from
visual inspection in the report. Do not alter shared styles just to add a task.

Report added/updated tasks, source checkout/revision, generated files and any
contribution-summary changes, checks actually run, and unresolved source issues.
If this run exposes a reusable failure in the workflow, make a targeted skill
correction and rerun the affected check; do not accumulate task-specific facts
or a permanent task inventory in the skill.
