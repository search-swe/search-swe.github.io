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
<header class="topbar">
  <a class="brand" href="{prefix}index.html#top" aria-label="Search-SWE home">
    <span class="brand-mark" aria-hidden="true"><img src="{prefix}assests/logo.png" width="36" height="36" alt="" /></span>
    <span>Search-SWE</span>
  </a>
  <button class="menu-toggle" type="button" aria-expanded="false" aria-controls="site-nav">
    <span></span><span></span><span></span><span class="sr-only">Toggle navigation</span>
  </button>
  <nav id="site-nav" class="site-nav" aria-label="Main navigation">
    <a href="{prefix}index.html#motivation">Why</a>
    <a href="{prefix}index.html#search-swe">What &amp; How</a>
    <a class="nav-active" href="{prefix}tasks.html">Tasks</a>
    <a href="{prefix}index.html#evaluation">Evaluation &amp; Results</a>
    <a class="nav-button" href="https://github.com/VectorSpaceLab/Search-SWE" target="_blank" rel="noreferrer">GitHub <span aria-hidden="true">↗</span></a>
  </nav>
</header>"""


def document(title: str, description: str, prefix: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta name="description" content="{esc(description)}" />
  <title>{esc(title)} — Search-SWE</title>
  <link rel="icon" type="image/png" href="{prefix}assests/logo.png" />
  <link rel="apple-touch-icon" href="{prefix}assests/logo.png" />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&amp;family=Manrope:wght@400;500;600;700;800&amp;display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="{prefix}style.css" />
  <link rel="stylesheet" href="{prefix}task-pages.css" />
</head>
<body>
{header(prefix)}
{body}
<footer class="footer section-shell">
  <span>Search-SWE · VectorSpaceLab</span>
  <a href="{prefix}tasks.html">Browse all tasks <span aria-hidden="true">↗</span></a>
</footer>
<script src="{prefix}script.js"></script>
</body>
</html>
"""


def task_label(task: dict) -> str:
    return "TASK " + task["id"].removeprefix("task-")


def home_card(task: dict) -> str:
    return f"""          <a class="task-card task-{task['color']}" href="tasks/{task['id']}/">
            <div class="task-index">{task_label(task)} <span class="type-chip type-{task['mode']}">{MODES[task['mode']].upper()}</span></div>
            <div class="task-card-heading">
              <span class="task-icon" aria-hidden="true">{task['icon']}</span>
              <h3>{esc(task['title'])}</h3>
            </div>
            <p>{esc(task['summary'])}</p>
            <span class="task-tag">{esc(task['tag'])} <b aria-hidden="true">→</b></span>
          </a>"""


def catalog_card(task: dict) -> str:
    return f"""<a id="{task['id']}" class="catalog-card task-{task['color']}" href="tasks/{task['id']}/">
  <span class="catalog-card-id">{task_label(task)} · {MODES[task['mode']].upper()}</span>
  <div class="task-card-heading">
    <span class="catalog-card-icon" aria-hidden="true">{task['icon']}</span>
    <h2>{esc(task['title'])}</h2>
  </div>
  <p>{esc(task['summary'])}</p>
  <div class="catalog-card-end"><span class="card-open" aria-label="Open task">↗</span></div>
</a>"""


def catalog_page(tasks: list[dict]) -> str:
    cards = "\n".join(catalog_card(task) for task in tasks)
    return document("Task catalog", "Browse Search-SWE task settings for implementation, optimization, and repair.", "", f"""
<main id="main-content">
  <section class="catalog-hero task-catalog-heading">
    <div class="section-shell catalog-hero-inner">
      <p class="eyebrow"><span class="eyebrow-dot"></span> Search-SWE · Task catalog</p>
      <h1>Engineer better <em>search.</em></h1>
      <p>Build new search capabilities, improve retrieval, and repair search systems. Open a task for its setting, input and output contract, and evaluation.</p>
      <div class="catalog-meta"><span>{len(tasks):02d} task scenarios</span><i aria-hidden="true">·</i><span>{len(MODES):02d} engineering modes</span></div>
    </div>
  </section>
  <section class="section-shell catalog-section task-catalog-cards" aria-label="All task scenarios">
    <div class="catalog-grid">
      {cards}
    </div>
  </section>
</main>""")


def directory(tasks: list[dict], current: dict) -> str:
    groups = []
    for key, title in MODES.items():
        links = []
        for task in tasks:
            if task["mode"] != key:
                continue
            active = ' aria-current="page"' if task["id"] == current["id"] else ""
            links.append(f'<a href="../{task["id"]}/"{active}><span>{task["id"].removeprefix("task-")}</span>{esc(task["navTitle"])}</a>')
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
<main id="main-content" class="section-shell task-reader">
  <nav class="task-breadcrumbs" aria-label="Breadcrumb"><a href="../../index.html">Home</a><span aria-hidden="true">/</span><a href="../../tasks.html">Tasks</a><span aria-hidden="true">/</span><span aria-current="page">{task_label(task)}</span></nav>
  <div class="task-reader-layout">
    <aside class="task-directory"><a class="all-tasks-link" href="../../tasks.html">← All tasks</a>{directory(tasks, task)}</aside>
    <article class="task-article">
      <header id="overview" class="task-article-header">
        <div class="task-article-kicker"><span>{task_label(task)}</span><span class="type-chip type-{task['mode']}">{MODES[task['mode']].upper()}</span></div>
        <h1>{esc(setting['title'])}</h1>
        <div class="task-summary">{setting['intro']}</div>
        <dl class="task-specs">{facts}</dl>
        <div class="task-tags" aria-label="Task topics">{tags_html}</div>
      </header>
      <details class="task-mobile-toc"><summary>On this page</summary><nav aria-label="Page contents">{page_toc}</nav></details>
      <div class="task-prose">{setting['body']}</div>
      <nav class="task-adjacent" aria-label="Adjacent tasks">{"".join(adjacent)}</nav>
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
    block = start + '\n        <div class="task-grid task-grid-six">\n' + cards + "\n        </div>\n        " + end
    outputs[ROOT / "index.html"] = homepage[:homepage.index(start)] + block + homepage[homepage.index(end) + len(end):]
    return {path: "\n".join(line.rstrip() for line in content.splitlines()) + "\n" for path, content in outputs.items()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if generated pages need updating.")
    args = parser.parse_args()
    changed = []
    for path, content in generate().items():
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
