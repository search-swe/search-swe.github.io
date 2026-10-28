# Task content

Each task has a static page at `tasks/<task-name>/index.html`, generated from
`content/tasks/<task-name>.md` and `catalog.json`. Serve the generated site as
static files. Task names match the benchmark repository and its
Hugging Face dataset paths.

## Add or edit a task

1. Choose the same descriptive name as the benchmark package: at most five
   lowercase hyphen-separated words, starting with a letter. The `task-` prefix
   and `all` are reserved. Names must be unique.
2. Add a Markdown setting with a level-one title matching the catalog title and
   `* **Task name**: ` followed by the canonical name in inline code, for example
   `search-swe/reasoning-query-rewriting`. Copy the structure of an existing
   setting and verify every fact against the task README, instruction and TOML.
3. Add a catalog entry with `name`, `title`, `summary`, `tag`, `status`, and `hardware` (`cpu` or `gpu`). Set hardware from the benchmark
   task.toml: `environment.gpus > 0` means GPU.
   Optional `navTitle` shortens navigation text; `homepageSummary` shortens the
   homepage card; `featured: true` includes the task on the homepage. Catalog
   order controls the selected homepage cards. The task catalog, directories and
   previous/next navigation use CPU then GPU groups, sorted A–Z by display title. The generator
   discovers tasks and featured cards from the catalog.
4. Run the full generator and checks below. Review and commit sources and
   generated HTML together.

Each task displays its short repository name in code formatting, with a copy
button for use with `--task`. Clipboard support lives in `task-pages.js`, with
an HTTP-preview fallback and manual selection when copying is unavailable. Detail
headers also link to the task directory on the benchmark’s GitHub `main` branch;
version-pinned instruction and configuration links remain in the task setting.

Cards share one visual style, with topic tags describing each task's focus.
Status is editorial metadata: use `setting` for available settings,
`draft` for provisional specifications, and
`planned` for scope-only placeholders; it is not displayed.

## Generate and check pages

From the repository root:

~~~sh
python scripts/build_tasks.py
python scripts/build_tasks.py --check
python -m unittest discover -s scripts -p 'test_*.py'
~~~

Only the Python standard library is required. The generator resolves paths
relative to its repository location. It writes the catalog, all task pages,
and homepage cards between the `TASK_CARDS` markers, preserving the rest of the
homepage. Shared styles live in `home-sections.css` and `task-pages.css`.

To remove a task, remove its catalog entry and Markdown, then run the full
generator. It removes obsolete detail pages carrying its generated-file marker;
`--check` reports them as stale. Unmarked pages and unrelated assets are left
alone. Renaming follows the same remove/add process.

For changes only to catalog summaries or homepage selection:

~~~sh
python scripts/build_tasks.py --catalog-only
python scripts/build_tasks.py --catalog-only --check
~~~

This leaves detail pages unchanged and performs no stale-page cleanup. Use a
full build for names, ordering, titles, settings or task membership changes.
Edit the catalog and Markdown sources, then regenerate HTML.

Supported Markdown includes level-two/three headings, paragraphs, flat ordered
and unordered lists, inline code, bold text, HTTP(S)/relative links, and fenced
code blocks. Raw HTML is escaped.

## Local preview

~~~sh
python -m http.server 8765 --bind 127.0.0.1
~~~

Open the server root or `tasks/`. Links and assets are relative, so the site also
works below a project subdirectory. Check desktop and mobile layouts before
publishing. The demo video and poster are independent assets.
