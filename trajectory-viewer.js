/* Read-only ATIF viewer. Every piece of trajectory content is rendered as text. */
(() => {
  'use strict';
  const {trial, entry} = JSON.parse(document.getElementById('page-data').textContent);
  const base = new URL('.', new URL(trial.trajectory_url, location.origin));
  const status = document.getElementById('trace-status');
  const content = document.getElementById('step-content');
  const query = document.getElementById('trace-query');
  const type = document.getElementById('trace-type');
  const BATCH_SIZE = 12;
  const earlier = document.getElementById('load-earlier');
  const next = document.getElementById('load-next');
  const feedStatus = document.getElementById('feed-status');
  const sentinel = document.getElementById('trace-more');
  let feedStart = 0, feedEnd = 0, feedVersion = 0, loading = false, loadFailed = false;
  let manifest, filtered = [], searchIndex, searchPromise;
  let searchVersion = 0, navigationVersion = 0;
  const chunks = new Map();
  const stepTimes = new Map();
  const messageObserver = new ResizeObserver(entries => {
    for (const {target} of entries) {
      const box = target.closest('.step-message');
      if (!box?.isConnected || !box.classList.contains('is-collapsed')) continue;
      box.querySelector('.message-toggle').hidden = target.scrollHeight <= target.clientHeight + 1 && !box.dataset.hasParts;
    }
  });

  function el(tag, text, className) {
    const node = document.createElement(tag);
    if (text != null) node.textContent = text;
    if (className) node.className = className;
    return node;
  }
  function button(text, action, className) {
    const node = el('button', text, className);
    node.type = 'button'; node.addEventListener('click', action); return node;
  }
  async function fetchJSON(name) {
    const response = await fetch(new URL(name, base), {credentials: 'omit'});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  }
  function failure(parent, message, action) {
    parent.replaceChildren(el('p', message), button('Retry', action));
  }
  function payload(value) {
    const box = el('div');
    const pre = el('pre', typeof value === 'string' ? value : value.preview, 'trace-text');
    box.append(pre);
    if (typeof value === 'string') return box;
    let loaded = 0, text = '';
    const more = button(`Load full text · ${value.chars.toLocaleString()} characters`, async () => {
      more.disabled = true;
      try {
        text += await fetchJSON(value.parts[loaded]); loaded++;
        pre.textContent = text;
        more.textContent = `Load more · ${loaded} / ${value.parts.length} parts loaded`;
        more.hidden = loaded === value.parts.length;
      } catch { more.textContent = 'Could not load text. Retry'; }
      more.disabled = false;
    }, 'payload-more');
    box.append(more); return box;
  }
  function disclosure(label, value, open = false) {
    const details = el('details'); details.open = open;
    details.append(el('summary', label));
    let rendered = false;
    const render = () => { if (!rendered) { details.append(payload(value)); rendered = true; } };
    if (open) render();
    details.addEventListener('toggle', () => { if (details.open) render(); });
    return details;
  }
  function message(value, id) {
    const box = el('div', null, 'step-message is-collapsed');
    const body = payload(value), pre = body.querySelector('.trace-text');
    pre.id = `message-${id}`;
    if (typeof value !== 'string') box.dataset.hasParts = 'true';
    const toggle = button('Show more ↓', () => {
      const expanded = box.classList.toggle('is-collapsed') === false;
      toggle.setAttribute('aria-expanded', String(expanded));
      toggle.textContent = expanded ? 'Show less ↑' : 'Show more ↓';
      if (!expanded && box.getBoundingClientRect().top < 90) box.scrollIntoView({block: 'start'});
    }, 'message-toggle');
    toggle.hidden = true;
    toggle.setAttribute('aria-expanded', 'false');
    toggle.setAttribute('aria-controls', pre.id);
    box.append(body, toggle);
    messageObserver.observe(pre);
    return box;
  }
  function readableInput(value) {
    if (typeof value !== 'string') return value;
    try {
      const args = JSON.parse(value);
      const key = ['cmd', 'input', 'code', 'command'].find(k => typeof args?.[k] === 'string');
      if (!key) return value;
      const rest = {...args}; delete rest[key];
      return args[key] + (Object.keys(rest).length ? `\n\nOther arguments\n${JSON.stringify(rest, null, 2)}` : '');
    } catch { return value; }
  }
  function compactTokens(value) {
    if (value == null) return '—';
    if (value >= 1e6) return `${Number((value / 1e6).toFixed(1))}M`;
    if (value >= 1e4) return `${Math.round(value / 1e3)}k`;
    if (value >= 1e3) return `${Number((value / 1e3).toFixed(1))}k`;
    return String(value);
  }
  function interval(ms) {
    if (!Number.isFinite(ms) || ms < 0) return '—';
    if (ms < 1000) return `${Math.round(ms)}ms`;
    if (ms < 10000) return `${Number((ms / 1000).toFixed(1))}s`;
    const total = Math.round(ms / 1000);
    const hours = Math.floor(total / 3600), minutes = Math.floor(total / 60) % 60, seconds = total % 60;
    return [hours && `${hours}h`, minutes && `${minutes}m`, seconds && `${seconds}s`].filter(Boolean).join(' ') || '0s';
  }
  function meta(text, title, className) {
    const node = el('span', text, className); node.title = title; return node;
  }
  function compactDisclosure(label, value, className) {
    const details = disclosure(label, value);
    details.className = className;
    const summary = details.querySelector('summary');
    const preview = (typeof value === 'string' ? value : value.preview).replace(/[*`]/g, '').replace(/\s+/g, ' ').slice(0, 180);
    summary.replaceChildren(el('span', label, 'disclosure-label'), el('span', preview, 'disclosure-preview'));
    return details;
  }
  function inputSummary(value) {
    if (typeof value !== 'string') return value.preview.replace(/\s+/g, ' ').slice(0, 160);
    try {
      const args = JSON.parse(value);
      const key = ['cmd', 'command', 'query', 'file_path', 'path', 'input', 'code'].find(k => typeof args?.[k] === 'string');
      if (key) return `${key}: ${JSON.stringify(args[key].replace(/\s+/g, ' ').slice(0, 150))}`;
    } catch { /* Unstructured inputs are displayed as recorded. */ }
    return value.replace(/\s+/g, ' ').slice(0, 160);
  }
  function go(id) {
    if (location.hash === `#step-${id}`) selectStep(id);
    else location.hash = `step-${id}`;
  }
  function renderStep(step, item) {
    const card = el('article', null, 'trajectory-step');
    card.id = `step-${item.id}`;
    card.dataset.step = item.id;
    card.setAttribute('aria-label', `Step ${item.id}`);
    const heading = el('header', null, 'step-heading');
    const number = el('a', `#${item.id}`, 'step-number');
    number.href = `#step-${item.id}`;
    number.setAttribute('aria-label', `Link to step ${item.id}`);
    number.addEventListener('click', event => { event.preventDefault(); go(item.id); });
    heading.append(number);
    const timing = stepTimes.get(item.id);
    const clock = el('span', null, 'step-clock');
    if (timing?.previous) {
      const delta = interval(timing.delta);
      clock.append(meta(delta === '—' ? '—' : `+${delta}`, 'Time since the previous recorded step (including tool work and waiting)', 'step-delta'));
    }
    clock.append(meta(interval(timing?.elapsed), `Time since the first recorded step. Timestamp: ${step.timestamp || 'not recorded'}`, 'step-elapsed'));
    heading.append(clock);
    const identity = el('span', null, 'step-identity');
    identity.append(meta(step.source === 'agent' ? trial.configuration.agent : step.source, step.source === 'agent' ? `${trial.configuration.agent} (v${trial.configuration.version.replace(/^v/, '')})` : 'Message source', 'step-agent'));
    const model = step.model_name || (step.source === 'agent' ? entry.model : null);
    if (model) identity.append(meta(model.split('/').pop(), model, 'step-model'));
    heading.append(identity);
    if (step.source === 'agent') {
      const usage = el('span', null, 'step-usage');
      for (const [label, key, description] of [
        ['in', 'input_tokens', 'Recorded input tokens, including cached input'],
        ['cache', 'cached_input_tokens', 'Recorded cached input tokens, a subset of input'],
        ['out', 'output_tokens', 'Recorded output tokens; reasoning is not added again'],
      ]) {
        const value = step.usage?.[key];
        const field = meta(null, `${description}: ${value == null ? 'not recorded' : value.toLocaleString('en-US')}`, `step-token step-token-${label}`);
        field.dataset.tokens = value == null ? '' : value;
        field.append(el('span', label), el('span', compactTokens(value)));
        usage.append(field);
      }
      heading.append(usage);
    }
    const copy = button('Copy', async () => {
      try { await navigator.clipboard.writeText(new URL(`#step-${item.id}`, location.href).href); copy.textContent = 'Copied'; }
      catch { copy.textContent = 'Copy unavailable'; }
      setTimeout(() => copy.textContent = 'Copy', 1800);
    }, 'step-copy');
    copy.setAttribute('aria-label', `Copy link to step ${item.id}`);
    heading.append(copy); card.append(heading);
    if (step.message) {
      const isContext = step.source === 'system' || (typeof step.message === 'string' && step.message.startsWith('<environment_context>'));
      if (isContext) {
        card.append(compactDisclosure('Context', step.message, 'setup-context'));
      } else {
        card.append(message(step.message, item.id));
      }
    }
    if (step.reasoning) card.append(compactDisclosure('Reasoning', step.reasoning, 'reasoning'));
    function renderCall(call, before) {
      const panel = el('details', null, 'tool-call'), summary = el('summary', null, 'tool-heading');
      const input = readableInput(call.input);
      const preview = inputSummary(call.input);
      summary.append(el('strong', call.name), el('span', preview, 'tool-preview'));
      panel.append(summary);
      let rendered = false;
      panel.addEventListener('toggle', () => {
        if (!panel.open || rendered) return;
        rendered = true;
        panel.append(el('div', call.id, 'call-id'));
        panel.append(disclosure('Input', input, true));
        if (!call.outputs.length) panel.append(el('p', 'No matching output recorded for this call ID.', 'missing-output'));
        call.outputs.forEach((output, i) => panel.append(disclosure(`Output${call.outputs.length > 1 ? ` ${i + 1}` : ''}`, output, true)));
      });
      card.insertBefore(panel, before || null);
    }
    step.calls.slice(0, 20).forEach(call => renderCall(call));
    let callOffset = Math.min(20, step.calls.length), partOffset = 0;
    if (step.calls.length > callOffset || step.call_parts?.length) {
      const moreCalls = button(`Load more tool calls · ${callOffset} / ${item.calls} shown`, async () => {
        moreCalls.disabled = true;
        try {
          const calls = callOffset < step.calls.length ? step.calls.slice(callOffset, callOffset + 20) : await fetchJSON(step.call_parts[partOffset++]);
          calls.forEach(call => renderCall(call, moreCalls)); callOffset += calls.length;
          moreCalls.textContent = `Load more tool calls · ${callOffset} / ${item.calls} shown`;
          moreCalls.hidden = callOffset >= item.calls;
        } catch { partOffset = Math.max(0, partOffset - 1); moreCalls.textContent = 'Could not load tool calls. Retry'; }
        moreCalls.disabled = false;
      });
      card.append(moreCalls);
    }
    if (step.unmatched_outputs.length) {
      const details = el('details', null, 'unmatched-output');
      const summary = el('summary');
      const count = step.unmatched_outputs.length;
      summary.append(el('span', 'Other observations', 'disclosure-label'),
        el('span', `${count} ${count === 1 ? 'output' : 'outputs'} without matching call IDs`, 'disclosure-preview'));
      details.append(summary);
      let rendered = false;
      details.addEventListener('toggle', () => {
        if (!details.open || rendered) return;
        rendered = true;
        step.unmatched_outputs.forEach((output, index) => {
          const d = disclosure(`Output ${index + 1} · ${output.id || 'no call ID'}`, output.content, true);
          if (output.content === '') d.append(el('p', 'Empty output recorded.', 'empty-observation'));
          details.append(d);
        });
      });
      card.append(details);
    }
    return card;
  }
  function feedControls() {
    earlier.hidden = feedStart === 0;
    earlier.disabled = loading;
    next.hidden = feedEnd >= filtered.length;
    next.disabled = loading;
    next.textContent = loadFailed ? 'Retry' : 'Load more steps';
  }
  function autoLoad() {
    if (!manifest || loading || loadFailed || feedEnd >= filtered.length || document.getElementById('panel-trajectory').hidden) return;
    const rect = sentinel.getBoundingClientRect();
    if (rect.top < innerHeight + 600 && rect.bottom > 0) loadBatch();
  }
  async function loadBatch(direction = 'next') {
    if (loading) return;
    const start = direction === 'earlier' ? Math.max(0, feedStart - BATCH_SIZE) : feedEnd;
    const end = direction === 'earlier' ? feedStart : Math.min(filtered.length, feedEnd + BATCH_SIZE);
    if (start === end) return;
    const version = feedVersion;
    loading = true; loadFailed = false; feedControls();
    feedStatus.textContent = 'Loading steps…';
    try {
      const items = filtered.slice(start, end);
      await Promise.all([...new Set(items.map(s => s.chunk))].map(name => {
        if (!chunks.has(name)) chunks.set(name, fetchJSON(name).catch(error => { chunks.delete(name); throw error; }));
        return chunks.get(name);
      }));
      if (version !== feedVersion) return;
      const fragment = document.createDocumentFragment();
      for (const item of items) {
        const step = (await chunks.get(item.chunk)).find(s => s.step_id === item.id);
        if (!step) throw new Error('Missing step');
        fragment.append(renderStep(step, item));
      }
      if (version !== feedVersion) return;
      if (direction === 'earlier') {
        const anchor = content.firstElementChild, top = anchor?.getBoundingClientRect().top;
        content.prepend(fragment); feedStart = start;
        if (anchor) window.scrollBy(0, anchor.getBoundingClientRect().top - top);
      } else { content.append(fragment); feedEnd = end; }
      feedStatus.textContent = feedEnd === filtered.length ? `End of trajectory · ${feedEnd - feedStart} steps shown` : `${feedEnd - feedStart} steps shown · Scroll down to continue`;
    } catch {
      if (version !== feedVersion) return;
      loadFailed = true;
      feedStatus.textContent = 'These steps could not be loaded. Your loaded steps are still available.';
    } finally {
      if (version === feedVersion) { loading = false; feedControls(); requestAnimationFrame(autoLoad); }
    }
  }
  async function resetFeed(start = 0) {
    feedVersion++; loading = false; loadFailed = false;
    content.querySelectorAll('.step-message .trace-text').forEach(pre => messageObserver.unobserve(pre));
    feedStart = feedEnd = start; content.replaceChildren();
    if (!filtered.length) {
      content.append(el('p', 'No matching steps.', 'empty-state'));
      feedStatus.textContent = ''; feedControls(); return;
    }
    await loadBatch();
  }
  async function selectStep(id) {
    const navigation = ++navigationVersion;
    const item = manifest.steps.find(s => s.id === id);
    if (!item) { failure(status, `Step ${id} is not present in this trajectory.`, () => go(manifest.steps[0].id)); return; }
    if (!filtered.some(s => s.id === id)) {
      searchVersion++; query.value = ''; type.value = 'all'; filtered = manifest.steps;
      status.textContent = `${manifest.steps.length.toLocaleString()} recorded steps · Scroll to read the trajectory`;
    }
    if (!document.getElementById(`step-${id}`)) await resetFeed(filtered.findIndex(s => s.id === id));
    if (navigation !== navigationVersion) return;
    content.querySelectorAll('.is-current').forEach(card => card.classList.remove('is-current'));
    const card = document.getElementById(`step-${id}`);
    if (card) { card.classList.add('is-current'); card.scrollIntoView({block: 'start'}); }
  }
  earlier.addEventListener('click', () => loadBatch('earlier'));
  next.addEventListener('click', () => loadBatch());
  const observer = new IntersectionObserver(autoLoad, {rootMargin: '600px 0px'});
  observer.observe(sentinel);
  async function filter() {
    const version = ++searchVersion;
    const words = [...new Set(query.value.toLowerCase().match(/[\p{L}\p{N}_-]+/gu) || [])];
    status.textContent = words.length ? 'Loading full-trajectory search index…' : 'Filtering steps…';
    try {
      if (words.length && !searchIndex) {
        searchPromise ||= fetchJSON(manifest.search).catch(e => { searchPromise = null; throw e; });
        searchIndex = await searchPromise;
      }
      if (version !== searchVersion) return;
      filtered = manifest.steps.filter((step, i) => {
        const matchesType = type.value === 'all' || (type.value === 'tools' ? step.calls > 0 : step.source === type.value);
        return matchesType && (!words.length || words.every(w => ` ${searchIndex[i]} `.includes(` ${w} `)));
      });
      status.textContent = `${filtered.length.toLocaleString()} / ${manifest.steps.length.toLocaleString()} steps${words.length ? ' match all words across messages, reasoning and tools. Long encoded binary strings are excluded from search.' : ' · Scroll down to read the trajectory.'}`;
      navigationVersion++;
      await resetFeed();
    } catch { failure(status, 'Search index could not be loaded.', filter); }
  }
  document.getElementById('trace-search').addEventListener('submit', event => { event.preventDefault(); filter(); });
  type.addEventListener('change', filter);
  document.getElementById('clear-search').addEventListener('click', () => { query.value = ''; type.value = 'all'; filter(); });
  function tab(name, update = true) {
    name = ({'agent-logs': 'agent', evaluation: 'verifier', configuration: 'config', downloads: 'artifacts'})[name] || name;
    if (!['trajectory', 'agent', 'verifier', 'artifacts', 'config', 'lock', 'log', 'exception'].includes(name)) name = 'trajectory';
    document.querySelector('.tabs').classList.toggle('file-tabs', ['agent', 'verifier', 'artifacts'].includes(name));
    document.querySelectorAll('[data-tab]').forEach(b => {
      const active = b.dataset.tab === name;
      b.setAttribute('aria-selected', String(active)); b.tabIndex = active ? 0 : -1;
      document.getElementById(`panel-${b.dataset.tab}`).hidden = !active;
    });
    if (update) {
      const url = new URL(location.href);
      if (name === 'trajectory') url.searchParams.delete('tab'); else url.searchParams.set('tab', name);
      history.replaceState(null, '', url);
    }
    if (name === 'trajectory') { if (!manifest) init(); else requestAnimationFrame(autoLoad); }
    window.dispatchEvent(new CustomEvent('trial-tab-change', {detail: name}));
  }
  const tabs = [...document.querySelectorAll('[data-tab]')];
  tabs.forEach((b, i) => {
    b.addEventListener('click', () => tab(b.dataset.tab));
    b.addEventListener('keydown', e => {
      const next = e.key === 'ArrowRight' ? (i + 1) % tabs.length : e.key === 'ArrowLeft' ? (i + tabs.length - 1) % tabs.length : e.key === 'Home' ? 0 : e.key === 'End' ? tabs.length - 1 : null;
      if (next != null) { e.preventDefault(); tabs[next].focus(); tab(tabs[next].dataset.tab); }
    });
  });
  document.querySelector('.tabs').hidden = false;
  let initializing = false;
  async function init() {
    if (initializing) return;
    initializing = true;
    try {
      manifest = await fetchJSON('manifest.json'); filtered = manifest.steps;
      const origin = Date.parse(manifest.steps[0]?.time);
      manifest.steps.forEach((step, index) => {
        const now = Date.parse(step.time);
        stepTimes.set(step.id, {previous: index > 0, elapsed: now - origin,
          delta: index ? now - Date.parse(manifest.steps[index - 1].time) : null});
      });
      document.querySelector('.trajectory-tools').hidden = false;
      status.textContent = `${manifest.steps.length.toLocaleString()} steps · Token usage shown per step`;
      const match = location.hash.match(/^#step-(\d+)$/);
      if (match) await selectStep(Number(match[1])); else await resetFeed();
    } catch { failure(status, 'Could not load trajectory data. Please retry.', init); }
    finally { initializing = false; }
  }
  window.addEventListener('hashchange', () => {
    const match = location.hash.match(/^#step-(\d+)$/);
    if (match) { tab('trajectory'); if (manifest) selectStep(Number(match[1])); }
  });
  tab(new URLSearchParams(location.search).get('tab') || 'trajectory', false);
})();
