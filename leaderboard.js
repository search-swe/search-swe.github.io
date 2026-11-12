/* Static rows remain readable without JavaScript. Filters never redefine scope. */
(() => {
  'use strict';
  const data = JSON.parse(document.getElementById('page-data').textContent);
  const kind = document.body.dataset.page;
  const params = new URLSearchParams(location.search);
  const numeric = value => value == null ? '—' : value >= 1e9 ? `${(value / 1e9).toFixed(2)}B` : value >= 1e6 ? `${(value / 1e6).toFixed(1)}M` : Math.round(value).toLocaleString('en-US');
  const average = values => values.length && values.every(v => v != null) ? values.reduce((a, b) => a + b, 0) / values.length : null;
  const total = values => values.length && values.every(v => v != null) ? values.reduce((a, b) => a + b, 0) : null;
  const money = value => value == null ? '—' : value.toLocaleString('en-US', {style: 'currency', currency: 'USD'});
  const stats = trials => {
    const times = trials.map(t => t.agent_seconds).filter(value => Number.isFinite(value) && value >= 0);
    return {score: average(trials.map(t => t.score)), tokens: total(trials.map(t => t.tokens.total_tokens)),
      cost: total(trials.map(t => t.cost_usd)), time: total(times), timedTasks: times.length};
  };
  const set = (id, text) => { const node = document.getElementById(id); if (node) node.textContent = text; };
  const suffix = () => params.size ? `?${params}` : '';
  const safeState = value => new URLSearchParams(value || '');
  async function copy(button, value) {
    const label = button.textContent;
    try {
      await navigator.clipboard.writeText(value);
      button.textContent = 'Copied';
    } catch { button.textContent = 'Copy unavailable'; }
    setTimeout(() => { button.textContent = label; }, 1800);
  }
  document.querySelectorAll('[data-copy]').forEach(button => {
    button.hidden = false;
    button.addEventListener('click', () => copy(button, button.dataset.copy));
  });
  const copyPage = document.getElementById('copy-page');
  if (copyPage) { copyPage.hidden = false; copyPage.addEventListener('click', () => copy(copyPage, location.href)); }
  if (kind === 'trial') {
    const state = safeState(params.get('entryState'));
    document.getElementById('back-entry').search = state.toString();
    document.querySelectorAll('[data-adjacent]').forEach(link => {
      if (state.size) link.search = new URLSearchParams({entryState: state.toString()});
    });
    return;
  }
  const tasks = new Map(data.tasks.map(t => [t.name, t]));
  const tbody = document.querySelector('tbody');
  const rows = [...tbody.rows];
  const input = document.getElementById('filter');
  const sort = document.getElementById('sort');
  const defaultSort = kind === 'leaderboard' ? 'score-desc' : 'task';
  let requestedSort = params.get('sort');
  requestedSort = ({score: 'score-desc', tokens: 'tokens-asc'})[requestedSort] || requestedSort;
  input.value = params.get('q') || '';
  sort.value = [...sort.options].some(o => o.value === requestedSort) ? requestedSort : defaultSort;
  document.querySelector('.controls').hidden = false;
  let scope = ['all', 'cpu', 'gpu'].includes(params.get('scope')) ? params.get('scope') : 'all';
  let view = params.get('view') === 'pareto' ? 'pareto' : 'table';
  const axis = document.getElementById('pareto-x');
  if (axis) axis.value = ['cost', 'tokens', 'time'].includes(params.get('x')) ? params.get('x') : 'cost';
  const viewTabs = [...document.querySelectorAll('[data-view]')];
  if (viewTabs.length) document.querySelector('.leaderboard-tabs').hidden = false;
  if (kind === 'entry') {
    document.getElementById('back-leaderboard').search = safeState(params.get('boardState')).toString();
  }

  function update() {
    params.set('scope', scope);
    if (scope === 'all') params.delete('scope');
    if (input.value.trim()) params.set('q', input.value.trim()); else params.delete('q');
    if (sort.value !== defaultSort) params.set('sort', sort.value); else params.delete('sort');
    if (kind === 'leaderboard') {
      if (view === 'pareto') params.set('view', view); else params.delete('view');
      if (axis.value !== 'cost') params.set('x', axis.value); else params.delete('x');
      viewTabs.forEach(tab => {
        const active = tab.dataset.view === view;
        tab.setAttribute('aria-selected', String(active));
        tab.tabIndex = active ? 0 : -1;
        document.getElementById(`panel-${tab.dataset.view}`).hidden = !active;
      });
      document.querySelector('.sort-label').hidden = view === 'pareto';
    }
    history.replaceState(null, '', location.pathname + suffix() + location.hash);
    document.querySelectorAll('[data-scope]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.scope === scope)));
    const included = data.trials.filter(t => scope === 'all' || tasks.get(t.task).hardware === scope);
    const query = input.value.trim().toLowerCase();
    const count = data.tasks.filter(t => scope === 'all' || t.hardware === scope).length;
    let ordered;
    if (kind === 'leaderboard') {
      const entries = data.entries.map((e, colorIndex) => ({...e, colorIndex, trials: included.filter(t => t.entry === e.id)})).map(e => ({...e, ...stats(e.trials)}));
      const ranked = [...entries].sort((a, b) => b.score - a.score || a.id.localeCompare(b.id));
      ranked.forEach((e, i) => { e.rank = i && e.score === ranked[i - 1].score ? ranked[i - 1].rank : i + 1; });
      const [key, direction = 'asc'] = sort.value.split('-');
      const field = key === 'date' ? 'release_date' : key;
      ordered = entries.sort((a, b) => {
        const left = a[field], right = b[field];
        // Missing dates/usage always follow recorded values in either direction.
        if (left == null || right == null) return Number(left == null) - Number(right == null) || a.id.localeCompare(b.id);
        const difference = typeof left === 'string' ? left.localeCompare(right) : left - right;
        return difference * (direction === 'desc' ? -1 : 1) || a.id.localeCompare(b.id);
      });
      ordered.forEach(e => {
        const row = rows.find(r => r.dataset.entry === e.id);
        e.visible = `${e.name} ${e.model} ${e.agent} ${e.effort}`.toLowerCase().includes(query);
        row.hidden = !e.visible;
        row.querySelector('.rank').textContent = e.trials.length === count ? e.rank : '—';
        row.querySelector('.score-value').textContent = e.score == null ? '—' : e.score.toFixed(1);
        row.querySelector('.score-track span').style.width = `${e.score || 0}%`;
        row.querySelector('.coverage').textContent = `${e.trials.length} / ${count}`;
        row.querySelector('.token-cell').textContent = numeric(e.tokens);
        row.querySelector('.token-cell').title = e.tokens == null ? 'Usage unavailable' : `${e.tokens.toLocaleString('en-US')} tokens`;
        row.querySelector('.cost-cell').textContent = money(e.cost);
        const url = `/leaderboard/entries/${e.id}/` + (params.size ? `?${new URLSearchParams({boardState: params.toString(), ...(scope !== 'all' ? {scope} : {})})}` : '');
        e.url = url;
        row.dataset.href = url;
        row.querySelectorAll('a').forEach(a => a.href = url);
        tbody.append(row);
      });
      if (view === 'pareto') window.SearchSwePareto.render(entries, count, axis.value);
      set('scope-caption', `${scope === 'all' ? 'All' : scope.toUpperCase()} ${count} tasks · one selected evaluation per model and task`);
    } else {
      const [key, direction] = sort.value.split('-');
      const byTask = (a, b) => tasks.get(a.task).hardware.localeCompare(tasks.get(b.task).hardware) || a.task.localeCompare(b.task);
      const tokenField = {tokens: 'total_tokens', input: 'input_tokens', output: 'output_tokens', cached: 'cached_input_tokens'}[key];
      const value = trial => tokenField ? trial.tokens[tokenField] : key === 'time' ? trial.agent_seconds : key === 'cost' ? trial.cost_usd : trial.score;
      ordered = [...data.trials].sort((a, b) => {
        if (key === 'task') return byTask(a, b);
        const left = value(a), right = value(b);
        if (left == null || right == null) return Number(left == null) - Number(right == null) || byTask(a, b);
        return (left - right) * (direction === 'desc' ? -1 : 1) || byTask(a, b);
      });
      ordered.forEach(t => {
        const row = rows.find(r => r.dataset.trial === t.id), task = tasks.get(t.task);
        row.hidden = !(scope === 'all' || task.hardware === scope) || !`${task.title} ${task.name}`.toLowerCase().includes(query);
        const url = `/leaderboard/trials/${t.id}/` + (params.size ? `?${new URLSearchParams({entryState: params.toString()})}` : '');
        row.dataset.href = url; row.querySelectorAll('a').forEach(a => a.href = url); tbody.append(row);
      });
      set('scope-caption', `${rows.filter(r => !r.hidden).length} shown / ${included.length} in scope · one selected evaluation per task · valid zero scores included`);
    }
    const [key, direction] = sort.value.split('-');
    document.querySelectorAll('[data-sort-key]').forEach(button => {
      const active = button.dataset.sortKey === key;
      button.closest('th').setAttribute('aria-sort', active ? (direction === 'asc' ? 'ascending' : 'descending') : 'none');
      button.querySelector('.sort-indicator').textContent = active ? (direction === 'asc' ? '↑' : '↓') : '↕';
      const next = active ? (direction === 'asc' ? 'desc' : 'asc') : (['tokens', 'cost'].includes(button.dataset.sortKey) ? 'asc' : 'desc');
      button.setAttribute('aria-label', `${button.dataset.sortLabel}: sort ${next === 'asc' ? 'ascending' : 'descending'}`);
    });
    document.querySelector('.empty-state').hidden = rows.some(r => !r.hidden);
  }
  input.addEventListener('input', update); sort.addEventListener('change', update);
  if (axis) axis.addEventListener('change', update);
  document.querySelectorAll('[data-sort-key]').forEach(button => {
    button.disabled = false;
    button.addEventListener('click', () => {
      const key = button.dataset.sortKey;
      const [current, direction] = sort.value.split('-');
      const next = current === key ? (direction === 'asc' ? 'desc' : 'asc') : (['tokens', 'cost'].includes(key) ? 'asc' : 'desc');
      sort.value = `${key}-${next}`; update();
    });
  });
  document.querySelectorAll('[data-scope]').forEach(b => b.addEventListener('click', () => { scope = b.dataset.scope; update(); }));
  viewTabs.forEach((tab, index) => {
    tab.addEventListener('click', () => { view = tab.dataset.view; update(); });
    tab.addEventListener('keydown', event => {
      let next;
      if (event.key === 'ArrowRight') next = (index + 1) % viewTabs.length;
      if (event.key === 'ArrowLeft') next = (index + viewTabs.length - 1) % viewTabs.length;
      if (event.key === 'Home') next = 0;
      if (event.key === 'End') next = viewTabs.length - 1;
      if (next == null) return;
      event.preventDefault();
      viewTabs[next].focus();
      viewTabs[next].click();
    });
  });
  if (kind === 'leaderboard') {
    let previousWidth = 0;
    new ResizeObserver(([entry]) => {
      if (entry.contentRect.width > 0 && entry.contentRect.width !== previousWidth) {
        previousWidth = entry.contentRect.width;
        if (view === 'pareto') update();
      }
    }).observe(document.getElementById('pareto-chart'));
  }
  rows.forEach(row => row.addEventListener('click', event => {
    if (event.target.closest('a,button,input,select') || getSelection().toString() || event.button !== 0) return;
    if (event.ctrlKey || event.metaKey) window.open(row.dataset.href, '_blank', 'noopener'); else location.href = row.dataset.href;
  }));
  update();
})();
