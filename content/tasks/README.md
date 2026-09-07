# Task content

The website is static. Each task has a standalone page under `tasks/task-N-N/index.html`. GitHub Pages or any local static server can serve these pages without a runtime build or Markdown service.

## Edit a task

- Edit its Markdown setting in this directory.
- Edit `catalog.json` for the card title, summary, category, status, and homepage selection.
- Keep `featured: true` on the six tasks shown on the homepage.
- Use `setting` for an available setting, `draft` for provisional specifications, and `planned` for a scope-only placeholder. These statuses are editorial metadata and are not displayed on the site.

The five initial settings (1-1, 1-2, 2-1, 2-2, 2-3) were copied unchanged from the supplied task materials. Task 3-1 summarizes the supplied sparse-index repair proposal in English; its numeric thresholds are explicitly provisional. Tasks 2-4 through 2-6 contain the requested scope and mark missing specifications as pending.

## Generate pages

From the repository root:

~~~sh
python scripts/build_tasks.py
python scripts/build_tasks.py --check
~~~

Only the Python standard library is required. The generator reads paths relative to its own repository location. It writes the task catalog, standalone detail pages, and the homepage cards between the `TASK_CARDS` markers. It preserves the rest of the homepage.

Commit the Markdown, catalog metadata, generator, stylesheet, and generated HTML together. Serving the site does not require Python.

The supported Markdown constructs are level-two/three headings, paragraphs, flat ordered/unordered lists, inline code, bold text, HTTP(S)/relative links, and fenced code blocks. Raw HTML is escaped. Markdown setting files are maintained here as the source for the generated task pages.

## Local preview

~~~sh
python -m http.server 8765 --bind 127.0.0.1
~~~

Open the local server root or `tasks.html`. Site links and assets use relative paths so the site also works below a project subdirectory.
