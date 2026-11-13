/* Serve the public package on a second origin; run the real viewer regression suite. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const crypto = require('node:crypto');
const {gunzipSync} = require('node:zlib');
const {spawn, spawnSync} = require('node:child_process');
const {chromium} = require('playwright');
const root = path.resolve(__dirname, '..');
const packageRoot = path.resolve(process.env.HF_PACKAGE || path.join(root, '.build/hf-trajectories-astra-deepseek'));
const origin = process.env.LEADERBOARD_ORIGIN || 'http://127.0.0.1:7788';
const manifest = JSON.parse(gunzipSync(fs.readFileSync(path.join(packageRoot, 'publication.json.gz'))));
const snapshot = JSON.parse(fs.readFileSync(path.join(root, 'content/leaderboard/release.json')));
assert.deepEqual(JSON.parse(fs.readFileSync(path.join(packageRoot, manifest.release_path, 'snapshot.json'))), snapshot,
  'HF_PACKAGE must match the current website snapshot');
const configPath = path.join(root, '.build/test-cross-origin-storage.json');
let requests = 0, credentialRequests = 0;
const server = http.createServer((req, res) => {
  requests++;
  if (req.headers.authorization || req.headers.cookie) credentialRequests++;
  const filename = path.resolve(packageRoot, '.' + new URL(req.url, 'http://localhost').pathname);
  res.setHeader('Access-Control-Allow-Origin', '*');
  if (!filename.startsWith(packageRoot + path.sep) || !fs.existsSync(filename) || !fs.statSync(filename).isFile()) {
    res.writeHead(404); res.end(); return;
  }
  res.setHeader('Content-Type', filename.endsWith('.gz') ? 'application/gzip' : 'application/json');
  fs.createReadStream(filename).pipe(res);
});

(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const dataOrigin = `http://127.0.0.1:${server.address().port}`;
  let browser;
  try {
    fs.writeFileSync(configPath, JSON.stringify({provider: 'preview', snapshot_id: snapshot.id,
      source_hashes: snapshot.source_hashes, data_base_url: `${dataOrigin}/${manifest.release_path}/`}));
    const built = spawnSync('python', ['scripts/build_leaderboard.py', '--storage', configPath], {cwd: root, encoding: 'utf8'});
    assert.equal(built.status, 0, built.stderr);
    browser = await chromium.launch({headless: true, args: ['--no-sandbox']});
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    await page.context().addCookies([{name: 'test_site_cookie', value: 'must-not-reach-data', domain: '127.0.0.1', path: '/'}]);
    const trial = snapshot.trials.find(t => t.task === 'agentic-search' && t.configuration.model === 'openai/gpt-6-luna');
    await page.goto(`${origin}/leaderboard/trials/${trial.id}/?tab=config`);
    await page.locator('#panel-config .file-text').waitFor();
    const config = await page.locator('#panel-config .file-text').innerText();
    assert(!config.includes('/data/Search-SWE-Workspace'));
    assert(!config.includes('/root/Search-SWE'));
    assert((await page.locator('#page-data').textContent()).includes(dataOrigin));
    // Real selected trials include nested repeated-judge rewards before the root
    // reward in the file inventory. Default to the final reward for every model.
    for (const selected of snapshot.trials.filter(t => t.task === 'agentic-search')) {
      await page.goto(`${origin}/leaderboard/trials/${selected.id}/?tab=verifier`);
      await page.locator('#panel-verifier .file-preview-footer').getByText('Complete file', {exact: true}).waitFor();
      assert.equal(await page.locator('#panel-verifier .file-heading strong').innerText(), 'reward.json');
      const reward = JSON.parse(await page.locator('#panel-verifier .file-text').innerText());
      assert(Math.abs((typeof reward === 'number' ? reward : reward.reward) * 100 - selected.score) < 1e-7);
    }
    const sol = snapshot.entries.find(e => e.model === 'gpt-6.1-sol');
    for (const [model, provider] of [['gpt-6-astra', 'OpenAI'],
      ['deepseek/deepseek-v4.1-flash-1017', 'DeepSeek (via OpenRouter)']]) {
      const entry = snapshot.entries.find(e => e.model === model);
      assert.equal(entry.agent, 'Codex');
      assert.equal(entry.agent_version, '0.164.0');
      await page.goto(`${origin}/leaderboard/entries/${entry.id}/`);
      const label = provider === 'DeepSeek (via OpenRouter)' ? 'DeepSeek' : provider;
      assert.deepEqual(await page.locator('tbody .provider-cell').allTextContents(), Array(47).fill(label));
      assert.equal(await page.locator('tbody .provider-cell').first().getAttribute('title'), provider);
      if (label === 'DeepSeek') assert.match(await page.locator('.entry-subtitle').innerText(), /DeepSeek via OpenRouter/);
    }
    await page.goto(`${origin}/leaderboard/entries/${sol.id}/`);
    assert.deepEqual(await page.locator('tbody .provider-cell').allTextContents(), Array(47).fill('OpenAI'));
    const recovered = snapshot.trials.find(t => t.entry === sol.id && t.task === 'large-scale-formula-retrieval');
    await page.goto(`${origin}/leaderboard/trials/${recovered.id}/`);
    await page.locator('.tool-call').first().waitFor();
    const fileIndex = JSON.parse(fs.readFileSync(path.join(packageRoot, manifest.release_path, 'trials', recovered.id, 'files/index.json')));
    const session = fileIndex.groups.agent.find(f => f.name.startsWith('original-codex-sessions/') && f.name.endsWith('.jsonl'));
    assert(session && session.download && session.parts.length, 'Recovered original session must be publicly readable');
    const kimi = snapshot.entries.find(e => e.model === 'kimi-k3.1-pro');
    assert.equal(kimi.agent, 'Claude Code');
    assert.equal(kimi.agent_version, '2.1.309');
    await page.goto(`${origin}/leaderboard/entries/${kimi.id}/`);
    assert.deepEqual(await page.locator('tbody .provider-cell').allTextContents(), Array(47).fill('Moonshot AI'));
    const kimiTrial = snapshot.trials.find(t => t.entry === kimi.id && t.task === 'evolving-personal-memory');
    const kimiFiles = JSON.parse(fs.readFileSync(path.join(packageRoot, manifest.release_path, 'trials', kimiTrial.id, 'files/index.json')));
    const sessions = kimiFiles.groups.agent.filter(f => f.name.endsWith('.jsonl'));
    assert.equal(sessions.length, 4, 'Publish the main Claude session and all three subagents');
    assert(sessions.every(f => f.download && f.parts.length));
    await page.goto(`${origin}/leaderboard/trials/${kimiTrial.id}/?tab=agent`);
    await page.locator('#panel-agent .file-text').waitFor();
    await page.locator('#panel-agent summary').filter({hasText: 'Coding time & token usage'}).click();
    const accounting = await page.locator('#panel-agent .evidence-summary').innerText();
    assert(accounting.includes('Final token usage unavailable; totals use recorded responses.'));
    assert(!accounting.includes('lower bounds'));
    const download = await page.locator('.download-links a').first().getAttribute('href');
    assert(download.startsWith(dataOrigin));
    const remoteHash = await page.evaluate(async url => {
      const response = await fetch(url, {credentials: 'omit'});
      if (!response.ok) throw new Error(`Download failed: ${response.status}`);
      return [...new Uint8Array(await crypto.subtle.digest('SHA-256', await response.arrayBuffer()))]
        .map(byte => byte.toString(16).padStart(2, '0')).join('');
    }, download);
    const localFile = path.join(packageRoot, new URL(download).pathname);
    assert.equal(remoteHash, crypto.createHash('sha256').update(fs.readFileSync(localFile)).digest('hex'));
    assert.equal(credentialRequests, 0, 'Cross-origin data requests must omit browser cookies and credentials');
    const opus = snapshot.entries.find(e => e.model === 'anthropic/claude-opus-5.5');
    await page.goto(`${origin}/leaderboard/entries/${opus.id}/`);
    assert.deepEqual(await page.locator('tbody .provider-cell').allTextContents(), Array(47).fill('OpenRouter'));
    const fallback = snapshot.trials.find(t => t.entry === opus.id && t.task === 'constrained-molecular-search');
    await page.locator('.model-substitution-note a').click();
    assert(page.url().includes(fallback.id));
    assert.match(await page.locator('.model-substitution-note').innerText(), /Claude Opus 5 after five Opus 5.5/);
    assert((await page.locator('.entry-subtitle').innerText()).startsWith('Claude Opus 5 ·'));
    await page.locator('.tool-call').first().waitFor();
    const fallbackManifest = JSON.parse(fs.readFileSync(path.join(packageRoot, manifest.release_path, 'trials', fallback.id, 'evaluation.json')));
    assert.equal(fallbackManifest.configuration.model, 'anthropic/claude-opus-5');
    assert.equal(fallbackManifest.score, 19.5839);
    assert.deepEqual(errors, []);
    await browser.close(); browser = null;
    const status = await new Promise(resolve => {
      const child = spawn(process.execPath, ['scripts/test_leaderboard_browser.cjs'], {cwd: root, env: process.env, stdio: 'inherit'});
      child.on('exit', resolve);
    });
    assert.equal(status, 0);
    assert(requests > 20);
    console.log(`Cross-origin public-data checks passed (${requests} anonymous requests).`);
  } finally {
    if (browser) await browser.close();
    server.closeAllConnections();
    await new Promise(resolve => server.close(resolve));
    fs.rmSync(configPath, {force: true});
    const restored = spawnSync('python', ['scripts/build_leaderboard.py'], {cwd: root, encoding: 'utf8'});
    if (restored.status !== 0) console.error(restored.stderr);
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
