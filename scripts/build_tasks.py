"""Generate the task catalog and standalone pages from repository-local Markdown."""
from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "tasks"
TICK = chr(96)
MODES = {
    "implementation": "Implementation",
    "optimization": "Optimization",
    "repair": "Repair",
}
MODE_VISUALS = {
    "implementation": {
        "color": "blue",
        "icon": '<rect x="3" y="3" width="7" height="7" rx="1.3"/><rect x="3" y="14" width="7" height="7" rx="1.3"/><rect x="14" y="14" width="7" height="7" rx="1.3"/><path d="M17.5 3v7M14 6.5h7"/>',
    },
    "optimization": {
        "color": "violet",
        "icon": '<path d="M3 3v18h18M6 15l5-5 4 3 6-8M16 5h5v5"/>',
    },
    "repair": {
        "color": "teal",
        "icon": '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94Z"/>',
    },
}
STATUSES = {"setting", "draft", "planned"}
META_PATTERN = re.compile(r"^\* \*\*([^*]+)\*\*: (.*)$")
TOKEN_PATTERN = re.compile(
    TICK + r"([^" + TICK + r"]+)" + TICK
    + r"|\*\*(.+?)\*\*|\[([^\]]+)\]\(([^)\s]+)\)"
)


def esc(value: str) -> str:
    return html.escape(value, quote=True)


def inline(value: str) -> str:
    """Render the inline Markdown used by task settings, escaping raw HTML."""
    result, cursor = [], 0
    for match in TOKEN_PATTERN.finditer(value):
        result.append(esc(value[cursor:match.start()]))
        code, bold, label, url = match.groups()
        if code is not None:
            result.append(f"<code>{esc(code)}</code>")
        elif bold is not None:
            result.append(f"<strong>{inline(bold)}</strong>")
        elif url.startswith(("https://", "http://", "#", "./", "../")):
            result.append(f'<a href="{esc(url)}">{inline(label)}</a>')
        else:
            result.append(esc(match.group()))
        cursor = match.end()
    result.append(esc(value[cursor:]))
    return "".join(result)


def read_setting(task: dict) -> dict:
    source = CONTENT / f'{task["id"]}.md'
    lines = source.read_text(encoding="utf-8-sig").splitlines()
    if not lines or not lines[0].startswith("# "):
        raise ValueError(f"{source.name}: expected a Markdown title")
    title, metadata, preamble = lines[0][2:].strip(), {}, []
    index = 1
    while index < len(lines) and not lines[index].startswith("## "):
        match = META_PATTERN.match(lines[index])
        if match:
            metadata[match[1]] = match[2]
        else:
            preamble.append(lines[index])
        index += 1
    expected = f'search-swe/{task["id"]}'
    if metadata.get("Task ID", "").strip(TICK) != expected:
        raise ValueError(f"{source.name}: Task ID must be {expected}")
    body, toc = markdown("\n".join(lines[index:]))
    intro, _ = markdown("\n".join(preamble))
    return {
        "title": title, "metadata": metadata, "intro": intro,
        "body": body, "toc": toc,
    }


def markdown(source: str) -> tuple[str, list[tuple[int, str, str]]]:
    """Headings, paragraphs, flat lists, and fenced code; no raw HTML execution."""
    lines, blocks, toc, used = source.splitlines(), [], [], {"overview"}
    index = 0

    def slug(text: str) -> str:
        base = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "section"
        value, count = base, 2
        while value in used:
            value, count = f"{base}-{count}", count + 1
        used.add(value)
        return value

    def starts_block(line: str) -> bool:
        return bool(
            re.match(r"^#{2,3} ", line)
            or re.match(r"^(?:[-*]|\d+\.) ", line)
            or line.startswith(("~~~", TICK * 3))
        )

    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            continue
        if line.startswith(("~~~", TICK * 3)):
            fence, language = line[:3], line[3:].strip()
            code_lines = []
            index += 1
            while index < len(lines) and not lines[index].startswith(fence):
                code_lines.append(lines[index])
                index += 1
            if index == len(lines):
                raise ValueError("Unclosed Markdown code fence")
            language = re.sub(r"[^a-zA-Z0-9_-]", "", language)
            code = esc("\n".join(code_lines))
            blocks.append(f'<pre><code class="language-{language}">{code}</code></pre>')
            index += 1
            continue
        heading = re.match(r"^(#{2,3}) (.+)$", line)
        if heading:
            level, label = len(heading[1]), heading[2]
            anchor = slug(label)
            toc.append((level, anchor, label))
            blocks.append(f'<h{level} id="{anchor}">{inline(label)}</h{level}>')
            index += 1
            continue
        item = re.match(r"^([-*]|\d+\.) (.+)$", line)
        if item:
            ordered = item[1][0].isdigit()
            tag, items = ("ol" if ordered else "ul"), []
            while index < len(lines):
                match = re.match(r"^([-*]|\d+\.) (.+)$", lines[index])
                if not match or match[1][0].isdigit() != ordered:
                    break
                items.append(f"<li>{inline(match[2])}</li>")
                index += 1
            blocks.append(f"<{tag}>" + "".join(items) + f"</{tag}>")
            continue
        paragraph = [line.strip()]
        index += 1
        while index < len(lines) and lines[index].strip() and not starts_block(lines[index]):
            paragraph.append(lines[index].strip())
            index += 1
        blocks.append("<p>" + inline(" ".join(paragraph)) + "</p>")
    return "\n".join(blocks), toc


def header(prefix: str) -> str:
    return f"""<a class="skip-link" href="#main-content">Skip to content</a>
<header class="home-header">
  <div class="home-header-inner">
    <a class="home-brand" href="{prefix or './'}" aria-label="Search-SWE home">
      <img src="{prefix}assests/logo.png" width="32" height="32" alt="" />
      <span>Search-SWE</span>
    </a>
    <nav class="home-nav" aria-label="Main navigation">
      <a href="{prefix or './'}">Overview</a>
      <a href="{prefix}tasks.html" aria-current="{('page' if not prefix else 'true')}">Tasks</a>
      <a href="https://github.com/VectorSpaceLab/Search-SWE" target="_blank" rel="noreferrer">GitHub <span aria-hidden="true">↗</span></a>
    </nav>
  </div>
</header>"""


def footer() -> str:
    return """<footer class="home-footer">
  <span>Search-SWE · VectorSpaceLab</span>
  <a href="#top">Back to top ↑</a>
</footer>"""


def document(title: str, description: str, prefix: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta name="description" content="{esc(description)}" />
  <meta name="theme-color" content="#ffffff" />
  <title>{esc(title)} — Search-SWE</title>
  <link rel="icon" type="image/png" href="{prefix}assests/logo.png" />
  <link rel="apple-touch-icon" href="{prefix}assests/logo.png" />
  <link rel="stylesheet" href="{prefix}home-sections.css?v=2" />
  <link rel="stylesheet" href="{prefix}task-pages.css?v=3" />
</head>
<body id="top">
{header(prefix)}
{body}
</body>
</html>
"""


def task_label(task: dict) -> str:
    return "TASK " + task["id"].removeprefix("task-")


def mode_icon(task: dict) -> str:
    shapes = MODE_VISUALS[task["mode"]]["icon"]
    return f'<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">{shapes}</svg>'


def home_card(task: dict) -> str:
    return f"""            <li>
              <a class="home-task task-{MODE_VISUALS[task['mode']]['color']}" href="tasks/{task['id']}/">
                <span class="home-task-id"><span class="sr-only">Task </span>{task['id'].removeprefix('task-')}</span>
                <span class="home-task-copy">
                  <span class="home-task-title">{esc(task['title'])}</span>
                  <span class="home-task-summary">{esc(task.get('homepageSummary', task['summary']))}</span>
                </span>
                <span class="home-task-mode">{mode_icon(task)}<span>{MODES[task['mode']]}</span></span>
              </a>
            </li>"""


def catalog_card(task: dict) -> str:
    return f"""<li id="{task['id']}">
  <a class="catalog-task task-{MODE_VISUALS[task['mode']]['color']}" href="tasks/{task['id']}/">
    <span class="home-task-id"><span class="sr-only">Task </span>{task['id'].removeprefix('task-')}</span>
    <span class="catalog-task-icon" aria-hidden="true">{mode_icon(task)}</span>
    <span class="home-task-copy">
      <span class="home-task-title">{esc(task['title'])}</span>
      <span class="home-task-summary">{esc(task.get('homepageSummary', task['summary']))}</span>
    </span>
  </a>
</li>"""


def catalog_page(tasks: list[dict]) -> str:
    groups, links = [], []
    for key, title in MODES.items():
        members = [task for task in tasks if task["mode"] == key]
        cards = "\n".join(catalog_card(task) for task in members)
        links.append(f'<a href="#{key}">{title}</a>')
        count = f'{len(members)} task' + ('s' if len(members) != 1 else '')
        groups.append(f"""<section id="{key}" class="home-section catalog-group" aria-labelledby="{key}-title">
  <div class="home-section-heading"><h2 id="{key}-title">{title}</h2><span class="catalog-count">{count}</span></div>
  <ul class="home-task-list">{cards}</ul>
</section>""")
    return document("Task catalog", "Browse Search-SWE task settings for implementation, optimization, and repair.", "", f"""
<div class="home-layout">
  <aside class="home-sidebar"><nav aria-label="Task categories"><p>Task categories</p>{''.join(links)}</nav></aside>
  <main id="main-content" class="home-document">
    <header class="home-intro catalog-intro">
      <h1>Tasks</h1>
      <p>Explore search-system engineering tasks across implementation, optimization, and repair under fixed resource constraints. Each task details its objective, requirements, and evaluation.</p>
    </header>
    {''.join(groups)}
    {footer()}
  </main>
</div>""")


def directory(tasks: list[dict], current: dict) -> str:
    groups = []
    for key, title in MODES.items():
        links = []
        for task in tasks:
            if task["mode"] != key:
                continue
            active = ' aria-current="page"' if task["id"] == current["id"] else ""
            links.append(f'<a href="../{task["id"]}/"{active}><span class="task-directory-id">{task["id"].removeprefix("task-")}</span><span class="task-directory-title">{esc(task["title"])}</span></a>')
        groups.append(f'<div class="task-directory-group"><p>{title}</p>{"".join(links)}</div>')
    return '<nav aria-label="Task directory">' + "".join(groups) + "</nav>"


def contents(toc: list[tuple[int, str, str]]) -> str:
    items = ['<a href="#overview">Overview</a>']
    for level, anchor, label in toc:
        klass = ' class="toc-subsection"' if level == 3 else ""
        items.append(f'<a href="#{anchor}"{klass}>{esc(label)}</a>')
    return "".join(items)


def detail_page(task: dict, tasks: list[dict], setting: dict) -> str:
    metadata = setting["metadata"]
    facts = "".join(
        f"<div><dt>{esc(label)}</dt><dd>{inline(metadata.get(label, 'To be specified'))}</dd></div>"
        for label in ("Domain", "Primary focus", "Primary metric")
    )
    tags = re.findall(TICK + "([^" + TICK + "]+)" + TICK, metadata.get("Tags", ""))
    tags_html = "".join(f"<span>{esc(tag)}</span>" for tag in tags)
    page_toc = contents(setting["toc"])
    current_index = tasks.index(task)
    adjacent = []
    for offset, label in ((-1, "Previous task"), (1, "Next task")):
        index = current_index + offset
        if 0 <= index < len(tasks):
            neighbor = tasks[index]
            adjacent.append(f'<a href="../{neighbor["id"]}/"><span>{label} · {task_label(neighbor)}</span><strong>{esc(neighbor["title"])}</strong></a>')
    return document(setting["title"], task["summary"], "../../", f"""
<main id="main-content" class="task-reader">
  <nav class="task-breadcrumbs" aria-label="Breadcrumb"><a href="../../">Home</a><span aria-hidden="true">/</span><a href="../../tasks.html">Tasks</a><span aria-hidden="true">/</span><span aria-current="page">{task_label(task)}</span></nav>
  <div class="task-reader-layout">
    <aside class="task-directory"><a class="all-tasks-link" href="../../tasks.html">← All tasks</a>{directory(tasks, task)}</aside>
    <article class="task-article">
      <header id="overview" class="task-article-header">
        <div class="task-article-kicker task-{MODE_VISUALS[task['mode']]['color']}"><span>{task_label(task)}</span><span class="home-task-mode">{mode_icon(task)}<span>{MODES[task['mode']]}</span></span></div>
        <h1>{esc(setting['title'])}</h1>
        <div class="task-summary">{setting['intro']}</div>
        <dl class="task-specs">{facts}</dl>
        <div class="task-tags" aria-label="Task topics">{tags_html}</div>
      </header>
      <details class="task-mobile-toc"><summary>On this page</summary><nav aria-label="Page contents">{page_toc}</nav></details>
      <div class="task-prose">{setting['body']}</div>
      <nav class="task-adjacent" aria-label="Adjacent tasks">{"".join(adjacent)}</nav>
      {footer()}
    </article>
    <aside class="task-toc"><nav aria-label="On this page"><p>On this page</p>{page_toc}</nav></aside>
  </div>
</main>""")


def generate() -> dict[Path, str]:
    tasks = json.loads((CONTENT / "catalog.json").read_text(encoding="utf-8"))
    ids = [task["id"] for task in tasks]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate task IDs")
    for task in tasks:
        if not re.fullmatch(r"task-\d+-\d+", task["id"]):
            raise ValueError("Invalid task ID")
        if task["mode"] not in MODES or task["status"] not in STATUSES:
            raise ValueError("Unknown task mode or status")
    outputs = {ROOT / "tasks.html": catalog_page(tasks)}
    for task in tasks:
        outputs[ROOT / "tasks" / task["id"] / "index.html"] = detail_page(task, tasks, read_setting(task))
    homepage = (ROOT / "index.html").read_text(encoding="utf-8")
    start, end = "<!-- TASK_CARDS:START -->", "<!-- TASK_CARDS:END -->"
    if homepage.count(start) != 1 or homepage.count(end) != 1:
        raise ValueError("Homepage must have one TASK_CARDS marker pair")
    cards = "\n".join(home_card(task) for task in tasks if task.get("featured"))
    block = start + '\n          <ul class="home-task-list" aria-label="Selected tasks">\n' + cards + "\n          </ul>\n          " + end
    outputs[ROOT / "index.html"] = homepage[:homepage.index(start)] + block + homepage[homepage.index(end) + len(end):]
    return {path: "\n".join(line.rstrip() for line in content.splitlines()) + "\n" for path, content in outputs.items()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if generated pages need updating.")
    parser.add_argument("--catalog-only", action="store_true", help="Update or check only the task catalog and homepage cards.")
    args = parser.parse_args()
    changed = []
    outputs = generate()
    if args.catalog_only:
        outputs = {path: content for path, content in outputs.items() if path in (ROOT / "tasks.html", ROOT / "index.html")}
    for path, content in outputs.items():
        existing = path.read_text(encoding="utf-8") if path.exists() else None
        if existing == content:
            continue
        changed.append(str(path.relative_to(ROOT)))
        if not args.check:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8", newline="\n")
    if args.check and changed:
        print("Pages need regenerating:\n" + "\n".join(changed))
        return 1
    print("Task pages are up to date." if args.check else f"Generated {len(changed)} updated pages.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
