/* Lazily browse exported trial evidence; source files are never executed. */
(() => {
  'use strict';
  const {trial} = JSON.parse(document.getElementById('page-data').textContent);
  const base = new URL('files/', new URL(trial.trajectory_url, location.origin));
  const loaded = new Set();
  const labels = {agent: 'Agent logs', verifier: 'Verifier output', artifacts: 'Artifacts'};
  let indexPromise;
  const el = (tag, text, cls) => {
    const node = document.createElement(tag);
    if (text != null) node.textContent = text;
    if (cls) node.className = cls;
    return node;
  };
  const button = (text, action, cls) => {
    const node = el('button', text, cls); node.type = 'button'; node.addEventListener('click', action); return node;
  };
  const bytes = size => size >= 1024**3 ? `${(size / 1024**3).toFixed(1)} GiB` : size >= 1024**2 ? `${(size / 1024**2).toFixed(1)} MiB` : size >= 1024 ? `${(size / 1024).toFixed(1)} KiB` : `${size} B`;
  const paths = {
    chevron: 'm9 5 7 7-7 7', folder: 'M3 7V5h6l2 2h10v12H3Z',
    file: 'M14 2H6v20h14V8ZM14 2v6h6M9 13h8M9 17h6',
    code: 'm8 8-4 4 4 4m8-8 4 4-4 4m-3-11-2 14',
    copy: 'M9 9h12v12H9ZM15 5V3H3v12h2',
    wrap: 'M3 5h18M3 10h14a4 4 0 0 1 0 8h-6m3-3-3 3 3 3M3 15h3',
    download: 'M12 3v12m-5-5 5 5 5-5M4 17v4h16v-4',
  };
  function icon(name) {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', '0 0 24 24'); svg.setAttribute('aria-hidden', 'true');
    svg.setAttribute('fill', 'none'); svg.setAttribute('stroke', 'currentColor');
    svg.setAttribute('stroke-width', '1.5'); svg.setAttribute('stroke-linecap', 'round'); svg.setAttribute('stroke-linejoin', 'round');
    const path = document.createElementNS(svg.namespaceURI, 'path'); path.setAttribute('d', paths[name]); svg.append(path);
    return svg;
  }
  function action(name, label, run) {
    const node = button('', run, 'file-action'); node.append(icon(name));
    node.title = label; node.setAttribute('aria-label', label); return node;
  }
  function fileTree(files) {
    const root = {children: new Map()};
    for (const file of files) {
      const parts = file.name.split('/'); let parent = root;
      parts.forEach((name, i) => {
        if (!parent.children.has(name)) parent.children.set(name, {name, path: parts.slice(0, i + 1).join('/'), children: new Map()});
        parent = parent.children.get(name);
        if (i === parts.length - 1) parent.file = file;
      });
    }
    return root;
  }
  async function read(name) {
    const response = await fetch(new URL(name, base), {credentials: 'omit'});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  }
  function renderText(pre, text, name) {
    pre.replaceChildren();
    if (!/\.jsonl?$/.test(name) || text.length > 500_000) { pre.textContent = text; return; }
    // Color JSON without interpreting any file content as markup.
    const tokens = /"(?:[^"\\]|\\.)*"\s*(?=:)|"(?:[^"\\]|\\.)*"|\b(?:true|false|null)\b|-?\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b/g;
    let end = 0;
    for (const match of text.matchAll(tokens)) {
      pre.append(document.createTextNode(text.slice(end, match.index)));
      const value = match[0];
      const type = value.startsWith('"') ? (text[match.index + value.length] === ':' ? 'key' : 'string') : 'value';
      pre.append(el('span', value, `json-${type}`)); end = match.index + value.length;
    }
    pre.append(document.createTextNode(text.slice(end)));
  }
  async function open(group) {
    const container = document.querySelector(`[data-file-group="${group}"]`);
    if (!container || loaded.has(group)) return;
    loaded.add(group);
    container.replaceChildren(el('p', 'Loading files…', 'file-status'));
    try {
      indexPromise ||= read('index.json').catch(error => { indexPromise = null; throw error; });
      const index = await indexPromise;
      const files = index.groups[group];
      container.replaceChildren();
      if (group === 'exception' && index.exception) container.append(el('pre', JSON.stringify(index.exception, null, 2), 'json-block'));
      if (!files.length) {
        container.append(el('p', group === 'exception' ? (index.exception ? 'No separate exception text file was saved.' : 'No exception was recorded in this Harbor trial.') : 'No files were collected for this section.', 'files-empty'));
        return;
      }
      const browser = el('div', null, 'file-browser');
      if (!labels[group]) browser.classList.add('single-file');
      const selector = el('div', null, 'file-selector');
      const caption = el('div', null, 'file-tree-heading');
      caption.append(el('span', labels[group] || group), el('span', `${files.length.toLocaleString()} ${files.length === 1 ? 'file' : 'files'}`, 'file-count'));
      const search = el('input'); search.type = 'search'; search.placeholder = 'Search files…'; search.setAttribute('aria-label', `Search ${group} files`);
      const list = el('div', null, 'file-list'); list.setAttribute('aria-label', `${labels[group] || group} directory`);
      const viewer = el('div', null, 'file-viewer');
      selector.append(caption, search, list); browser.append(selector, viewer); container.append(browser);
      // Keep provenance available below the browser, out of the reading area.
      const info = el('details', null, 'file-provenance');
      info.append(el('summary', group === 'verifier' && index.regraded_separately ? 'Final evaluation · regraded separately' : 'About these files'), el('p', index.notes[group], 'file-note'));
      container.append(info);
      let selected, selection = 0, limit = 300;
      const collapsed = new Set();
      const searchCollapsed = new Set();
      function renderList(focusPath) {
        const term = search.value.trim().toLowerCase();
        const closed = term ? searchCollapsed : collapsed;
        const filtered = files.filter(f => f.name.toLowerCase().includes(term));
        const tree = fileTree(filtered);
        list.replaceChildren(); let rows = 0, remaining = false;
        function branch(parent, depth) {
          const ul = el('ul');
          const nodes = [...parent.children.values()].sort((a, b) => Number(!!a.file) - Number(!!b.file) || a.name.localeCompare(b.name, 'en', {numeric: true}));
          for (let node of nodes) {
            if (rows++ >= limit) { remaining = true; break; }
            // Compact chains such as sessions / 2026 / 10 / 24, keeping branches.
            let label = node.name;
            while (!node.file && node.children.size === 1 && ![...node.children.values()][0].file) {
              node = [...node.children.values()][0]; label += ' / ' + node.name;
            }
            const li = el('li');
            const row = button('', () => {
              if (node.file) show(node.file);
              else { closed.has(node.path) ? closed.delete(node.path) : closed.add(node.path); renderList(node.path); }
            }, node.file ? 'file-item' : 'file-folder');
            row.style.setProperty('--depth', depth); row.title = node.path; row.dataset.path = node.path;
            if (node.file) {
              row.setAttribute('aria-pressed', String(selected === node.file));
              const isCode = /\.(?:py|sh|js|ts|jsonl?|toml|ya?ml|rs|sql|cpp|h)$/.test(node.name);
              row.append(icon(isCode ? 'code' : 'file'), el('span', label, 'file-name'));
              if (isCode) row.classList.add(/\.jsonl?$/.test(node.name) ? 'file-json' : 'file-code');
            } else {
              const expanded = !closed.has(node.path);
              row.setAttribute('aria-expanded', String(expanded)); row.append(icon('chevron'), icon('folder'), el('span', label, 'file-name'));
              row.addEventListener('keydown', event => {
                if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
                event.preventDefault(); event.key === 'ArrowLeft' ? closed.add(node.path) : closed.delete(node.path); renderList(node.path);
              });
              li.append(row); if (expanded) li.append(branch(node, depth + 1));
            }
            if (node.file) li.append(row);
            ul.append(li);
          }
          return ul;
        }
        list.append(branch(tree, 0));
        if (!filtered.length) list.append(el('p', 'No matching files.', 'file-status'));
        if (remaining) list.append(button('Show more files', () => { limit += 300; renderList(); }, 'more-files'));
        if (focusPath) [...list.querySelectorAll('[data-path]')].find(row => row.dataset.path === focusPath)?.focus({preventScroll: true});
      }
      async function show(file) {
        selected = file;
        const version = ++selection;
        renderList();
        const heading = el('div', null, 'file-heading');
        const filename = el('strong', file.name); filename.title = file.name;
        heading.append(filename, el('span', bytes(file.bytes), 'file-size'));
        const actions = el('div', null, 'file-actions');
        const pre = el('pre', '', 'file-text');
        let part = 0, text = '';
        if (file.parts.length && file.chars) {
          const wrap = action('wrap', 'Wrap lines', () => {
            pre.classList.toggle('is-wrapped'); wrap.setAttribute('aria-pressed', String(pre.classList.contains('is-wrapped')));
          }); wrap.setAttribute('aria-pressed', 'false');
          const copy = action('copy', 'Copy shown text', async () => {
            try { await navigator.clipboard.writeText(text); copy.title = 'Copied'; copy.setAttribute('aria-label', 'Copied'); }
            catch { copy.title = 'Could not copy'; copy.setAttribute('aria-label', 'Could not copy'); }
          });
          actions.append(wrap, copy);
        }
        if (file.download) {
          const link = el('a', null, 'file-action'); link.append(icon('download')); link.href = new URL(file.download, base); link.download = `${file.name.split('/').pop()}.gz`;
          link.title = 'Download text (.gz)'; link.setAttribute('aria-label', link.title); actions.append(link);
        }
        heading.append(actions); viewer.replaceChildren(heading);
        if (!file.parts.length || !file.chars) {
          const empty = el('div', null, 'file-preview-empty'); empty.append(icon('file'), el('strong', file.parts.length ? 'This file is empty' : 'Preview unavailable'), el('p', file.unavailable || 'No text was recorded in this file.'));
          viewer.append(empty); return;
        }
        if (file.redacted) viewer.append(el('p', 'Private values redacted.', 'file-redaction'));
        const notice = el('span', 'Loading text…'); notice.setAttribute('role', 'status');
        const more = button('Load more text', load, 'file-load-more'); more.hidden = true;
        const footer = el('div', null, 'file-preview-footer'); footer.append(notice, more);
        viewer.append(pre, footer);
        async function load() {
          more.disabled = true;
          try {
            const value = await read(file.parts[part]);
            if (version !== selection) return;
            part++; text += value; renderText(pre, text, file.name);
            notice.textContent = part === file.parts.length ? 'Complete file' : `${text.length.toLocaleString()} of ${file.chars.toLocaleString()} characters · Copy includes this preview`;
            more.textContent = 'Load more text'; more.hidden = part === file.parts.length;
          } catch {
            if (version !== selection) return;
            notice.textContent = 'Could not load this text. Loaded content is preserved.';
            more.textContent = 'Retry'; more.hidden = false;
          } finally { more.disabled = false; }
        }
        await load();
      }
      search.addEventListener('input', () => { limit = 300; searchCollapsed.clear(); renderList(); });
      await show(files.find(file => file.parts.length && file.bytes > 0) || files[0]);
    } catch {
      loaded.delete(group);
      container.replaceChildren(el('p', 'Files are unavailable. The result summary is still available.', 'file-status'), button('Retry', () => open(group)));
    }
  }
  window.addEventListener('trial-tab-change', event => open(event.detail));
  open(document.querySelector('[data-tab][aria-selected="true"]')?.dataset.tab);
})();
