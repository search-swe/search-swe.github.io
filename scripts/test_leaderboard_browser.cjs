/* Requires Playwright and a local preview server. No site/package dependencies. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require('playwright');
const root = path.resolve(__dirname, '..');
const origin = process.env.LEADERBOARD_ORIGIN || 'http://127.0.0.1:7788';
const snapshot = JSON.parse(fs.readFileSync(path.join(root, 'content/leaderboard/release.json')));
const read = name => JSON.parse(fs.readFileSync(path.join(root, name)));

(async () => {
  const browser = await chromium.launch({headless: true, args: ['--no-sandbox']});
  try {
    const page = await browser.newPage({viewport: {width: 1440, height: 1000}});
    const errors = [], requests = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => requests.push(request.url()));
    await page.goto(`${origin}/leaderboard/`);
    assert.equal(await page.locator('tbody tr:visible').count(), 4);
    assert.deepEqual(await page.locator('.score-value').allTextContents(), ['17.3', '14.8', '4.6', '1.3']);
    assert.deepEqual(await page.locator('tbody .token-cell').allTextContents(), ['1.12B', '2.47B', '553.0M', '4.72B']);
    assert.equal(await page.locator('tbody .token-cell').first().getAttribute('title'), '1,122,771,166 tokens');
    assert(!requests.some(url => url.includes('/traces/')));
    assert.equal(await page.locator('.model-name').first().innerText(), 'GPT-6 Luna (max)');
    assert.equal(await page.locator('.agent-cell').first().innerText(), 'Codex (v0.164.0)');
    assert(!(await page.locator('tbody').innerText()).includes('OpenRouter'));
    assert.deepEqual(await page.locator('tbody .release-date').allTextContents(), ['2026-09-22', '2026-10-17', '2026-09-21', '2026-08-26']);
    const idFor = name => snapshot.entries.find(entry => entry.name === name).id;
    const rankedIds = ['GPT-6 Luna', 'DeepSeek V4.1 Flash 1017', 'MiMo-V2.6-Flash', 'GLM 5.3 Flash'].map(idFor);
    const sortOrders = {
      'score-desc': [0, 1, 2, 3], 'score-asc': [3, 2, 1, 0],
      'date-desc': [1, 0, 2, 3], 'date-asc': [3, 2, 0, 1],
      'tokens-desc': [3, 1, 0, 2], 'tokens-asc': [2, 0, 1, 3],
    };
    for (const [sort, order] of Object.entries(sortOrders)) {
      await page.locator('#sort').selectOption(sort);
      assert.deepEqual(await page.locator('tbody tr').evaluateAll(rows => rows.map(row => row.dataset.entry)), order.map(i => rankedIds[i]));
      assert.deepEqual(await page.locator('tbody .rank').allTextContents(), order.map(i => String(i + 1)));
    }
    await page.locator('[data-sort-key="date"]').click();
    assert.equal(await page.locator('#sort').inputValue(), 'date-desc');
    assert.equal(await page.locator('th:has([data-sort-key="date"])').getAttribute('aria-sort'), 'descending');
    await page.locator('[data-sort-key="date"]').press('Enter');
    assert.equal(await page.locator('#sort').inputValue(), 'date-asc');
    await page.reload();
    assert.equal(await page.locator('#sort').inputValue(), 'date-asc');
    assert.equal(await page.locator('th:has([data-sort-key="date"])').getAttribute('aria-sort'), 'ascending');
    await page.locator('[data-sort-key="score"]').click();
    assert.equal(await page.locator('#sort').inputValue(), 'score-desc');
    await page.locator('[data-sort-key="score"]').click();
    assert.equal(await page.locator('#sort').inputValue(), 'score-asc');
    await page.locator('[data-sort-key="tokens"]').click();
    assert.equal(await page.locator('#sort').inputValue(), 'tokens-asc');
    await page.locator('[data-sort-key="tokens"]').click();
    assert.equal(await page.locator('#sort').inputValue(), 'tokens-desc');
    await page.getByRole('button', {name: 'GPU', exact: true}).click();
    assert.deepEqual(await page.locator('tbody .coverage').allTextContents(), ['23 / 23', '23 / 23', '23 / 23', '23 / 23']);
    const gpu = new Set(snapshot.tasks.filter(t => t.hardware === 'gpu').map(t => t.name));
    const luna = snapshot.entries.find(e => e.model === 'openai/gpt-6-luna');
    const gpuTotal = snapshot.trials.filter(t => t.entry === luna.id && gpu.has(t.task)).reduce((sum, t) => sum + t.tokens.total_tokens, 0);
    assert.equal(await page.locator(`tr[data-entry="${luna.id}"] .token-cell`).getAttribute('title'), `${gpuTotal.toLocaleString('en-US')} tokens`);
    const gpuTokenTotals = await page.locator('tbody .token-cell').evaluateAll(nodes => nodes.map(node => Number(node.title.replace(/[^0-9]/g, ''))));
    assert.deepEqual(gpuTokenTotals, [...gpuTokenTotals].sort((a, b) => b - a));
    await page.locator('#sort').selectOption('date-asc');
    await page.locator('#filter').fill('luna');
    await page.locator('tbody tr:visible .model-name').click();
    assert.equal(await page.locator('tbody tr:visible').count(), 23);
    assert.equal(await page.getByRole('columnheader', {name: 'Measurement', exact: true}).count(), 0);
    const entryTrials = new Map(snapshot.trials.filter(t => t.entry === luna.id).map(t => [t.id, t]));
    const displayed = await page.locator('tbody tr').evaluateAll(rows => rows.map(row => ({
      id: row.dataset.trial,
      task: row.querySelector('.task-title').textContent,
      provider: row.querySelector('.provider-cell').textContent,
      input: row.querySelector('.input-tokens').textContent,
      output: row.querySelector('.output-tokens').textContent,
      cached: row.querySelector('.cached-tokens').textContent,
      time: row.querySelector('.duration-cell').textContent,
    })));
    const tokenFields = {tokens: 'total_tokens', input: 'input_tokens', output: 'output_tokens', cached: 'cached_input_tokens'};
    for (const row of displayed) {
      const trial = entryTrials.get(row.id);
      assert.equal(row.task, trial.task);
      assert.equal(row.provider, trial.configuration.provider);
      for (const field of ['input', 'output', 'cached']) {
        const value = trial.tokens[tokenFields[field]];
        assert.equal(row[field], value == null ? '—' : value.toLocaleString('en-US'));
      }
      if (trial.agent_seconds == null) assert.equal(row.time, '—');
      else if (trial.agent_seconds > 0 && trial.agent_seconds < 60) assert.equal(row.time, '<1min');
      else {
        const parts = row.time.match(/^(?:(\d+)h )?(\d+)min$/);
        assert(parts, `Unexpected agent time: ${row.time}`);
        assert.equal(Number(parts[1] || 0) * 60 + Number(parts[2]), Math.floor(trial.agent_seconds / 60));
      }
    }
    for (const field of ['score', 'tokens', 'input', 'output', 'cached', 'time']) {
      for (const direction of ['asc', 'desc']) {
        await page.locator('#sort').selectOption(`${field}-${direction}`);
        const ids = await page.locator('tbody tr:visible').evaluateAll(rows => rows.map(row => row.dataset.trial));
        const values = ids.map(id => {
          const trial = entryTrials.get(id);
          return tokenFields[field] ? trial.tokens[tokenFields[field]] : field === 'time' ? trial.agent_seconds : trial.score;
        });
        assert.deepEqual(values, [...values].sort((a, b) => a == null || b == null ? Number(a == null) - Number(b == null) : direction === 'asc' ? a - b : b - a));
      }
    }
    await page.locator('[data-sort-key="score"]').click();
    assert.equal(await page.locator('#sort').inputValue(), 'score-desc');
    await page.locator('[data-sort-key="score"]').click();
    assert.equal(await page.locator('#sort').inputValue(), 'score-asc');
    await page.reload();
    assert.equal(await page.locator('#sort').inputValue(), 'score-asc');
    await page.locator('#sort').selectOption('task');
    await page.locator('tbody tr:visible .task-title').first().click();
    await page.waitForSelector('.tool-call');
    assert.equal(await page.locator('.step-nav').count(), 0);
    assert.deepEqual(await page.getByRole('tab').allTextContents(), ['Trajectory', 'Agent', 'Verifier', 'Artifacts', 'Config', 'Lock', 'Log', 'Exception']);
    assert(!requests.some(url => url.includes('/files/')));
    const firstStepId = await page.locator('.trajectory-step').first().getAttribute('id');
    assert.equal(firstStepId, 'step-1');
    // Read an entire real trial by scrolling; no per-step clicks or replacements.
    const activeTrial = snapshot.trials.find(t => page.url().includes(t.id));
    const expectedIds = read(activeTrial.trajectory_url).steps.map(s => `step-${s.id}`);
    while (await page.locator('.trajectory-step').count() < expectedIds.length) {
      const count = await page.locator('.trajectory-step').count();
      await page.locator('#trace-more').scrollIntoViewIfNeeded();
      await page.waitForFunction(count => document.querySelectorAll('.trajectory-step').length > count, count);
      assert.equal(await page.locator('.trajectory-step').first().getAttribute('id'), firstStepId);
    }
    assert.deepEqual(await page.locator('.trajectory-step').evaluateAll(nodes => nodes.map(n => n.id)), expectedIds);
    assert((await page.locator('#feed-status').innerText()).startsWith('End of trajectory'));
    await page.getByRole('tab', {name: 'Verifier', exact: true}).click();
    await page.reload();
    assert(await page.locator('#panel-verifier').isVisible());
    await page.locator('#back-entry').click();
    await page.locator('#back-leaderboard').click();
    assert.equal(await page.locator('#filter').inputValue(), 'luna');
    assert.equal(new URL(page.url()).searchParams.get('scope'), 'gpu');
    assert.equal(await page.locator('#sort').inputValue(), 'date-asc');
    await page.locator('#filter').fill('absent-model');
    assert(await page.locator('.empty-state').isVisible());

    // Metadata comes from the real step, even when jumping or filtering.
    const codeContext = snapshot.trials.find(t => t.task === 'code-context-retrieval' && t.configuration.model === 'openai/gpt-6-luna');
    await page.goto(`${origin}/leaderboard/trials/${codeContext.id}/#step-7`);
    await page.waitForSelector('#step-7');
    assert.equal(await page.locator('#step-7 .step-number').innerText(), '#7');
    assert.equal(await page.locator('#step-7 .step-delta').innerText(), '+6s');
    assert.equal(await page.locator('#step-7 .step-elapsed').innerText(), '47s');
    assert.equal(await page.locator('#step-7 .step-agent').innerText(), 'Codex');
    assert.equal(await page.locator('#step-7 .step-model').innerText(), 'gpt-6-luna');
    assert.deepEqual(await page.locator('#step-7 .step-token').evaluateAll(nodes => nodes.map(n => n.dataset.tokens)), ['27999', '19607', '5848']);
    assert(!(await page.locator('#step-7 .step-heading').innerText()).includes('$'));
    await page.locator('#trace-type').selectOption('tools');
    await page.waitForSelector('#step-4 .step-token-cache');
    assert.equal(await page.locator('#step-4 .step-token-cache').getAttribute('data-tokens'), '');
    assert((await page.locator('#step-4 .step-token-cache').innerText()).includes('—'));
    assert.equal(await page.locator('#step-7 .step-delta').innerText(), '+6s');
    await page.locator('#step-8 .step-number').click();
    assert.equal(new URL(page.url()).hash, '#step-8');
    assert.equal(await page.locator('#step-8 .step-delta').innerText(), '+1m 24s');
    assert.equal(await page.locator('#step-8 .step-elapsed').innerText(), '2m 11s');

    // Browse real exported evidence, including a separately regraded verifier.
    await page.getByRole('tab', {name: 'Agent', exact: true}).click();
    await page.waitForSelector('#panel-agent .file-text');
    assert.equal(await page.locator('#panel-agent .file-heading strong').innerText(), 'codex.txt');
    assert(await page.locator('#panel-agent .file-selector').isVisible());
    const sessions = page.locator('#panel-agent .file-folder').filter({hasText: 'sessions'});
    const sessionFile = page.locator('#panel-agent .file-item[data-path^="sessions/"]');
    assert.equal(await sessions.getAttribute('aria-expanded'), 'true');
    await sessions.click();
    assert.equal(await sessionFile.count(), 0);
    await sessions.press('ArrowRight');
    assert.equal(await sessionFile.count(), 1);
    await sessionFile.click();
    await page.waitForFunction(() => document.querySelector('#panel-agent .file-text')?.textContent.includes('session_meta'));
    assert((await page.locator('#panel-agent .file-heading strong').innerText()).startsWith('sessions/'));
    const sessionLength = await page.locator('#panel-agent .file-text').evaluate(n => n.textContent.length);
    await page.locator('#panel-agent').getByRole('button', {name: 'Load more text', exact: true}).click();
    await page.waitForFunction(length => document.querySelector('#panel-agent .file-text').textContent.length > length, sessionLength);
    await page.getByRole('tab', {name: 'Verifier', exact: true}).click();
    await page.locator('#panel-verifier .file-preview-footer').getByText('Complete file', {exact: true}).waitFor();
    assert((await page.locator('#panel-verifier .file-provenance summary').innerText()).includes('regraded separately'));
    assert.equal(JSON.parse(await page.locator('#panel-verifier .file-text').innerText()).reward, codeContext.score / 100);
    assert.equal(await page.locator('#panel-verifier h2').count(), 0);
    await page.getByRole('tab', {name: 'Artifacts', exact: true}).click();
    await page.waitForSelector('#panel-artifacts .file-item');
    const appFolder = page.locator('#panel-artifacts .file-folder[data-path="app"]');
    await appFolder.click();
    assert.equal(await page.locator('#panel-artifacts .file-item[data-path^="app/"]').count(), 0);
    // Search reveals the matching file's ancestors without losing collapsed state.
    await page.locator('#panel-artifacts input').fill('search_engine.py');
    assert.equal(await appFolder.getAttribute('aria-expanded'), 'true');
    assert.equal(await page.locator('#panel-artifacts .file-item .file-name').innerText(), 'search_engine.py');
    await page.locator('#panel-artifacts .file-item').click();
    await page.waitForFunction(() => document.querySelector('#panel-artifacts .file-text')?.textContent.includes('import'));
    await page.locator('#panel-artifacts').getByRole('button', {name: 'Wrap lines', exact: true}).click();
    assert(await page.locator('#panel-artifacts .file-text').evaluate(n => n.classList.contains('is-wrapped')));
    await page.context().grantPermissions(['clipboard-read', 'clipboard-write']);
    await page.locator('#panel-artifacts').getByRole('button', {name: 'Copy shown text', exact: true}).click();
    await page.locator('#panel-artifacts').getByRole('button', {name: 'Copied', exact: true}).waitFor();
    assert.equal(await page.evaluate(() => navigator.clipboard.readText()), await page.locator('#panel-artifacts .file-text').textContent());
    await page.locator('#panel-artifacts input').fill('');
    assert.equal(await appFolder.getAttribute('aria-expanded'), 'false');
    await appFolder.click();
    await page.locator('#panel-artifacts .file-item[data-path$=".pyc"]').click();
    assert((await page.locator('#panel-artifacts .file-preview-empty').innerText()).includes('Preview unavailable'));
    assert.equal(await page.locator('#panel-artifacts .file-actions a').count(), 0);
    await page.getByRole('tab', {name: 'Config', exact: true}).click();
    await page.locator('#panel-config .file-preview-footer').getByText('Complete file', {exact: true}).waitFor();
    assert.equal(JSON.parse(await page.locator('#panel-config .file-text').innerText()).agent.model_name, 'openai/gpt-6-luna');
    await page.getByRole('tab', {name: 'Lock', exact: true}).click();
    await page.locator('#panel-lock .file-preview-footer').getByText('Complete file', {exact: true}).waitFor();
    assert(JSON.parse(await page.locator('#panel-lock .file-text').innerText()).task.digest.startsWith('sha256:'));
    await page.getByRole('tab', {name: 'Log', exact: true}).click();
    await page.waitForSelector('#panel-log .file-heading');
    assert.equal(await page.locator('#panel-log .file-heading strong').innerText(), 'trial.log');
    await page.getByRole('tab', {name: 'Exception', exact: true}).click();
    await page.waitForSelector('#panel-exception .files-empty');
    assert((await page.locator('#panel-exception .files-empty').innerText()).includes('No exception'));
    await page.reload();
    await page.waitForSelector('#panel-exception .files-empty');
    assert(await page.locator('#panel-exception').isVisible());
    await page.goto(`${origin}/leaderboard/trials/${codeContext.id}/?tab=evaluation`);
    assert(await page.locator('#panel-verifier').isVisible());
    await page.goto(`${origin}/leaderboard/trials/${codeContext.id}/?tab=agent-logs`);
    assert(await page.locator('#panel-agent').isVisible());

    // Exercise the largest parallel-call step, with a direct refreshable anchor.
    const many = snapshot.trials.find(t => t.task === 'negative-constraint-retrieval' && t.configuration.model.startsWith('xiaomi/'));
    const manifest = read(many.trajectory_url);
    const busiest = [...manifest.steps].sort((a, b) => b.calls - a.calls)[0];
    await page.goto(`${origin}/leaderboard/trials/${many.id}/#step-${busiest.id}`);
    await page.waitForSelector('.tool-call');
    assert((await page.locator(`#step-${busiest.id} .tool-call`).count()) <= 20);
    await page.locator(`#step-${busiest.id}`).getByRole('button', {name: /Load more tool calls/}).click();
    await page.waitForFunction(id => document.querySelectorAll(`#step-${id} .tool-call`).length > 20, busiest.id);
    await page.reload();
    await page.waitForSelector('.tool-call');
    assert.equal(await page.locator(`#step-${busiest.id} .step-number`).innerText(), `#${busiest.id}`);
    await page.locator('#load-earlier').click();
    await page.waitForFunction(id => Number(document.querySelector('.trajectory-step').dataset.step) < id, busiest.id);
    assert.equal(await page.locator(`#step-${busiest.id}`).count(), 1);
    await page.locator('#trace-query').fill('python');
    await page.locator('#trace-search button').click();
    await page.waitForFunction(() => document.getElementById('trace-status').textContent.includes('match all words'));
    await page.waitForSelector('.trajectory-step');
    assert((await page.locator('.trajectory-step').count()) > 0);
    await page.locator('#trace-query').fill('thisworddoesnotexist123456');
    await page.locator('#trace-search button').click();
    await page.waitForFunction(() => document.getElementById('trace-status').textContent.startsWith('0 /'));

    // A text field externalized into several parts is initially just a preview.
    const large = snapshot.trials.find(t => t.task === 'sketch-text-search' && t.configuration.model.startsWith('deepseek/'));
    const largeManifest = read(large.trajectory_url);
    const directory = path.posix.dirname(large.trajectory_url);
    let target;
    for (const item of largeManifest.steps) {
      const step = read(`${directory}/${item.chunk}`).find(s => s.step_id === item.id);
      const outputCall = step.calls.findIndex(c => c.outputs.some(o => typeof o === 'object' && o.parts.length > 1));
      if (outputCall >= 0 && outputCall < 20) { target = {item, outputCall}; break; }
    }
    assert(target, 'A real long output fixture must exist');
    requests.length = 0;
    await page.goto(`${origin}/leaderboard/trials/${large.id}/#step-${target.item.id}`);
    await page.waitForSelector('.tool-call');
    assert(!requests.some(url => /text-\d+\.json/.test(url)));
    const call = page.locator(`#step-${target.item.id} .tool-call`).nth(target.outputCall);
    await call.locator(':scope > summary').click();
    await call.getByRole('button', {name: /Load full text/}).first().click();
    await page.waitForFunction(() => [...document.querySelectorAll('.payload-more')].some(b => b.textContent.includes('1 /')));
    assert(requests.some(url => /text-\d+\.json/.test(url)));
    assert(!requests.some(url => url.includes('trajectory.json.gz')));

    // Failed chunk loads have a working retry, and log HTML remains inert text.
    let fail = true;
    await page.route('**/steps-*.json', route => {
      if (fail) { fail = false; return route.abort(); }
      return route.continue();
    });
    await page.reload();
    await page.getByRole('button', {name: 'Retry', exact: true}).click();
    await page.waitForSelector('.tool-call');
    await page.unroute('**/steps-*.json');
    await page.route('**/steps-*.json', async route => {
      const response = await route.fetch(), body = await response.json();
      body.forEach(s => s.message = '<img src=x onerror="window.badLog=true"><script>window.badLog=true</script>');
      await route.fulfill({response, json: body});
    });
    await page.reload();
    await page.waitForSelector('.step-message');
    assert.equal(await page.locator('.step-message img, .step-message script').count(), 0);
    assert.equal(await page.evaluate(() => window.badLog), undefined);
    await page.unroute('**/steps-*.json');

    for (const width of [390, 320]) {
      await page.setViewportSize({width, height: 844});
      for (const route of ['/leaderboard/', `/leaderboard/entries/${many.entry}/`, `/leaderboard/trials/${many.id}/`]) {
        await page.goto(origin + route);
        if (route.includes('/trials/')) await page.waitForSelector('.tool-call');
        assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `No page overflow at ${width}px: ${route}`);
      }
      await page.goto(`${origin}/leaderboard/trials/${codeContext.id}/?tab=agent`);
      for (const name of ['Agent', 'Verifier', 'Artifacts']) {
        await page.getByRole('tab', {name, exact: true}).click();
        await page.locator(`#panel-${name.toLowerCase()} .file-text`).waitFor();
        assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `No evidence overflow at ${width}px: ${name}`);
        assert(await page.locator(`#panel-${name.toLowerCase()} .file-selector`).isVisible());
      }
    }
    const noJS = await browser.newPage({javaScriptEnabled: false});
    await noJS.goto(`${origin}/leaderboard/`);
    assert.equal(await noJS.locator('tbody tr').count(), 4);
    await noJS.goto(`${origin}/leaderboard/trials/${many.id}/`);
    assert(await noJS.locator('#panel-verifier').isVisible());
    assert.equal(errors.length, 0, errors.join('\n'));
    console.log('Browser checks passed: token totals, scopes, continuous scrolling through a full trial, navigation state, tabs, deep links, earlier steps, parallel calls, full search, lazy text, retry, inert logs, mobile and no-JS.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
