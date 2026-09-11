# Task content

The website is static. Each task has a standalone page under `tasks/task-N-N/index.html`. GitHub Pages or any local static server can serve these pages without a runtime build or Markdown service.

## Edit a task

- Edit its Markdown setting in this directory.
- Edit `catalog.json` for the card title, summary, category, status, and homepage selection.
- Keep `featured: true` on the six tasks shown on the homepage.
- Use `homepageSummary` for a shorter description in the homepage and catalog task lists; otherwise they use `summary`. Detail-page prose comes from the Markdown setting.
- Icons and colors are assigned by engineering mode in `MODE_VISUALS` in `scripts/build_tasks.py`: implementation uses blue modules and optimization a violet growth chart. Tasks of the same mode share a visual identity across the homepage and catalog.
- Use `setting` for an available setting, `draft` for provisional specifications, and `planned` for a scope-only placeholder. These statuses are editorial metadata and are not displayed on the site.

The five initial settings (1-1, 1-2, 2-1, 2-2, 2-3) were copied unchanged from the supplied task materials. Task 2-5 describes sparse-index optimization. Other planned tasks contain the requested scope and mark missing specifications as pending.

## Generate pages

From the repository root:

~~~sh
python scripts/build_tasks.py
python scripts/build_tasks.py --check
~~~

Only the Python standard library is required. The generator reads paths relative to its own repository location. It writes the task catalog, standalone detail pages, and the homepage task list between the `TASK_CARDS` markers. It preserves the rest of the homepage. All pages share document typography and navigation styles from `home-sections.css`; `task-pages.css` adds the grouped catalog and detail-reader layouts.

For catalog titles, summaries, or catalog layout changes, update only the catalog and homepage cards:

~~~sh
python scripts/build_tasks.py --catalog-only
python scripts/build_tasks.py --catalog-only --check
~~~

This leaves task detail pages unchanged. The current detail HTML for tasks 2-4, 2-5, and 2-6 contains specifications not yet reflected in its Markdown source; reconcile those sources before regenerating all detail pages.

Commit the Markdown, catalog metadata, generator, stylesheet, and generated HTML together. Serving the site does not require Python.

The supported Markdown constructs are level-two/three headings, paragraphs, flat ordered/unordered lists, inline code, bold text, HTTP(S)/relative links, and fenced code blocks. Raw HTML is escaped. Markdown setting files are maintained here as the source for the generated task pages.

## Local preview

~~~sh
python -m http.server 8765 --bind 127.0.0.1
~~~

Open the local server root or `tasks.html`. Site links and assets use relative paths so the site also works below a project subdirectory.
