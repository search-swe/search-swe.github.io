/* Real browser acceptance for cost totals and the Table / Pareto views. */
const assert = require('node:assert/strict');
const {chromium} = require('playwright');
const origin = process.env.LEADERBOARD_ORIGIN || 'http://127.0.0.1:7788';
const money = value => value.toLocaleString('en-US', {style: 'currency', currency: 'USD'});

(async () => {
  const browser = await chromium.launch({headless: true, args: ['--no-sandbox']});
  try {
    const page = await browser.newPage({viewport: {width: 1440, height: 1000}});
    const errors = [], requests = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => requests.push(request.url()));
    await page.goto(`${origin}/leaderboard/`);
    const data = await page.locator('#page-data').evaluate(node => JSON.parse(node.textContent));
    const byId = new Map(data.entries.map(e => [e.id, e]));
    const totals = scope => data.entries.map(entry => {
      const tasks = new Set(data.tasks.filter(t => scope === 'all' || t.hardware === scope).map(t => t.name));
      const trials = data.trials.filter(t => t.entry === entry.id && tasks.has(t.task));
      return {...entry, cost: trials.reduce((sum, t) => sum + t.cost_usd, 0),
        score: trials.reduce((sum, t) => sum + t.score, 0) / trials.length};
    });
    assert.equal(await page.locator('#view-table').getAttribute('aria-selected'), 'true');
    assert.equal(await page.locator('#panel-pareto').isVisible(), false);
    assert.match(await page.locator('thead th').last().innerText(), /Cost/);
    assert.match(await page.locator('.cost-note').first().innerText(), /estimated.*official API rates/);
    assert.deepEqual(await page.locator('tbody .cost-cell').allTextContents(), totals('all').sort((a, b) => b.score - a.score).map(e => money(e.cost)));
    for (const direction of ['asc', 'desc']) {
      await page.locator('#sort').selectOption(`cost-${direction}`);
      const expected = totals('all').sort((a, b) => (a.cost - b.cost) * (direction === 'asc' ? 1 : -1));
      assert.deepEqual(await page.locator('tbody tr').evaluateAll(rows => rows.map(r => r.dataset.entry)), expected.map(e => e.id));
    }
    await page.locator('#view-table').focus();
    await page.locator('#view-table').press('ArrowRight');
    assert.equal(await page.locator('#view-pareto').getAttribute('aria-selected'), 'true');
    assert.equal(await page.locator('#panel-table').isVisible(), false);
    assert.equal(await page.locator('.sort-label').isVisible(), false);
    assert.equal(await page.locator('.pareto-point').count(), 4);
    assert(await page.locator('.pareto-heading').evaluate(node => {
      const title = node.querySelector('h2').getBoundingClientRect();
      const key = node.querySelector('.pareto-key').getBoundingClientRect();
      return Math.abs(title.y + title.height / 2 - key.y - key.height / 2) < 1;
    }));
    assert.deepEqual((await page.locator('.pareto-point[data-frontier="true"]').evaluateAll(nodes => nodes.map(n => n.dataset.entry))).map(id => byId.get(id).model).sort(), ['gpt-6.1-sol', 'openai/gpt-6-luna', 'openai/gpt-6.1-terra']);
    await page.locator('.pareto-point').first().hover();
    assert.equal(await page.locator('.pareto-tooltip').isVisible(), true);
    await page.locator('#filter').fill('glm');
    assert.equal(await page.locator('.pareto-point').count(), 0);
    assert.equal(await page.locator('#pareto-empty').isVisible(), true);
    await page.locator('#filter').fill('terra');
    assert.equal(await page.locator('.pareto-point').count(), 1);
    assert.equal(await page.locator('.pareto-point').getAttribute('data-frontier'), 'true');
    await page.locator('#filter').fill('no-such-model');
    assert.equal(await page.locator('#pareto-empty').isVisible(), true);
    await page.locator('#filter').fill('');
    for (const scope of ['cpu', 'gpu', 'all']) {
      await page.locator(`[data-scope="${scope}"]`).click();
      const expected = new Map(totals(scope).map(e => [e.id, e]));
      const labels = await page.locator('.pareto-point-label:visible').evaluateAll(nodes => nodes.map(node => {
        const {x, y, width, height} = node.getBoundingClientRect();
        return {x, y, width, height};
      }));
      assert.equal(labels.length, data.entries.length);
      assert(!labels.some((a, i) => labels.slice(i + 1).some(b =>
        a.x < b.x + b.width && a.x + a.width > b.x && a.y < b.y + b.height && a.y + a.height > b.y)));
      const points = await page.locator('.pareto-point').evaluateAll(nodes => nodes.map(n => ({id: n.dataset.entry, cost: Number(n.dataset.cost), score: Number(n.dataset.score)})));
      for (const point of points) {
        assert(Math.abs(point.cost - expected.get(point.id).cost) < 1e-9);
        assert(Math.abs(point.score - expected.get(point.id).score) < 1e-9);
      }
      await page.locator('#view-table').click();
      for (const entry of expected.values()) assert.equal(await page.locator(`tr[data-entry="${entry.id}"] .cost-cell`).innerText(), money(entry.cost));
      await page.locator('#view-pareto').click();
    }
    await page.getByRole('button', {name: 'GPU', exact: true}).click();
    await page.locator('#filter').fill('luna');
    await page.locator('.pareto-point .pareto-dot').click();
    assert.equal(await page.locator('tbody tr:visible').count(), 23);
    await page.locator('#back-leaderboard').click();
    assert.equal(await page.locator('#view-pareto').getAttribute('aria-selected'), 'true');
    assert.equal(await page.locator('#filter').inputValue(), 'luna');
    assert.equal(await page.locator('[data-scope="gpu"]').getAttribute('aria-pressed'), 'true');
    await page.reload();
    assert.equal(await page.locator('.pareto-point').count(), 1);
    await page.locator('#filter').fill('');
    await page.locator('[data-scope="all"]').click();
    await page.setViewportSize({width: 390, height: 844});
    await page.waitForTimeout(150);
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    assert.equal(await page.locator('.pareto-legend-item').count(), 4);
    assert(!(await page.locator('#pareto-chart').innerHTML()).match(/NaN|Infinity/));
    await page.locator('#view-table').click();
    await page.locator('.table-frame').evaluate(node => { node.scrollLeft = node.scrollWidth; });
    assert.equal(await page.locator('tbody .cost-cell').first().isVisible(), true);
    const download = await page.request.get(`${origin}${data.download_url}`);
    const exported = await download.json();
    assert.deepEqual(exported.trials.map(t => t.cost_usd), data.trials.map(t => t.cost_usd));
    assert.equal(exported.cost_methodology.type, 'estimated');
    const noJS = await browser.newPage({javaScriptEnabled: false, viewport: {width: 1440, height: 1000}});
    await page.setViewportSize({width: 1440, height: 1000});
    for (const entry of data.entries) {
      const trials = data.trials.filter(t => t.entry === entry.id);
      await page.goto(`${origin}/leaderboard/entries/${entry.id}/`);
      assert.equal(await page.locator('thead th').last().innerText(), 'Trajectory');
      assert.match(await page.locator('thead th').nth(-2).innerText(), /Cost/);
      const costs = await page.locator('tbody tr').evaluateAll(rows => Object.fromEntries(rows.map(row => [row.dataset.trial, row.querySelector('.cost-cell').textContent])));
      assert.deepEqual(costs, Object.fromEntries(trials.map(t => [t.id, money(t.cost_usd)])));
      for (const direction of ['asc', 'desc']) {
        await page.locator('[data-sort-key="cost"]').click();
        assert.equal(await page.locator('#sort').inputValue(), `cost-${direction}`);
        assert.equal(await page.locator('th.cost-cell').getAttribute('aria-sort'), direction === 'asc' ? 'ascending' : 'descending');
        const ordered = await page.locator('tbody tr').evaluateAll(rows => rows.map(row => row.dataset.trial));
        const values = ordered.map(id => trials.find(t => t.id === id).cost_usd);
        assert.deepEqual(values, [...values].sort((a, b) => (a - b) * (direction === 'asc' ? 1 : -1)));
      }
      await page.reload();
      assert.equal(await page.locator('#sort').inputValue(), 'cost-desc');
      await page.locator('[data-scope="gpu"]').click();
      assert.equal(await page.locator('tbody tr:visible').count(), 23);
      assert.equal(await page.locator('#sort').inputValue(), 'cost-desc');
      await page.setViewportSize({width: 390, height: 844});
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      await page.setViewportSize({width: 1440, height: 1000});
      // Cost is published in HTML and requires no trajectory request or JavaScript.
      const trial = [...trials].sort((a, b) => b.tokens.input_tokens - a.tokens.input_tokens)[0];
      await noJS.goto(`${origin}/leaderboard/trials/${trial.id}/`);
      assert.equal(await noJS.locator('#stat-cost').innerText(), money(trial.cost_usd));
      assert.equal(await noJS.locator('.metrics > div').count(), 6);
      assert.equal(await noJS.locator('#stat-input-tokens').innerText(), trial.tokens.input_tokens.toLocaleString('en-US'));
      assert.equal(await noJS.locator('.metric-detail').innerText(), `including ${trial.tokens.cached_input_tokens.toLocaleString('en-US')} cached`);
      assert.match(await noJS.locator('.cost-note').first().innerText(), /estimated.*official API rates/);
      for (const width of [1440, 1280, 390]) {
        await noJS.setViewportSize({width, height: 1000});
        assert.equal(await noJS.locator('#stat-cost').isVisible(), true);
        assert(await noJS.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
        assert(await noJS.locator('.metrics > div').evaluateAll(nodes => nodes.every(node => node.scrollWidth <= node.clientWidth)));
      }
    }
    assert(!requests.some(url => url.includes('huggingface.co')));
    await noJS.goto(`${origin}/leaderboard/`);
    assert.deepEqual(await noJS.locator('tbody .cost-cell').allTextContents(), totals('all').sort((a, b) => b.score - a.score).map(e => money(e.cost)));
    assert.equal(await noJS.locator('.leaderboard-tabs').isVisible(), false);
    await noJS.close();
    assert.deepEqual(errors, []);
    console.log('Cost and Pareto browser checks passed: main/entry/trial amounts, sorting, scopes, filtering, navigation, keyboard, mobile, download and no-JS.');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
