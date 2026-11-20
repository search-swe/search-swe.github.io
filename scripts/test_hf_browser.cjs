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
const packageRoot = path.resolve(process.env.HF_PACKAGE || path.join(root, '.build/hf-trajectories-pr3'));
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
    for (const entry of snapshot.entries.filter(e => e.model.startsWith('xiaomi/mimo-v2.6-') || ['gpt-6-astra', 'deepseek/deepseek-v4.1-flash-1017', 'kimi-k3'].includes(e.model))) {
      const provider = entry.model.startsWith('xiaomi/') ? 'Xiaomi (via OpenRouter)' : entry.model === 'gpt-6-astra' ? 'OpenAI' : entry.model === 'kimi-k3' ? 'Moonshot AI' : 'DeepSeek (via OpenRouter)';
      assert.equal(entry.agent_version, entry.agent === 'Pi' ? '1.4.0' : entry.agent === 'Codex' ? '0.164.0' : '2.1.309');
      await page.goto(`${origin}/leaderboard/entries/${entry.id}/`);
      const label = provider.replace(' (via OpenRouter)', '');
      assert.deepEqual(await page.locator('tbody .provider-cell').allTextContents(), Array(47).fill(label));
      assert.equal(await page.locator('tbody .provider-cell').first().getAttribute('title'), provider);
      if (label === 'DeepSeek') assert.match(await page.locator('.entry-subtitle').innerText(), /DeepSeek via OpenRouter/);
      if (label === 'Xiaomi') assert.match(await page.locator('.entry-subtitle').innerText(), /Xiaomi via OpenRouter/);
    }
    await page.goto(`${origin}/leaderboard/entries/${sol.id}/`);
    assert.deepEqual(await page.locator('tbody .provider-cell').allTextContents(), Array(47).fill('OpenAI'));
    const recovered = snapshot.trials.find(t => t.entry === sol.id && t.task === 'large-scale-formula-retrieval');
    await page.goto(`${origin}/leaderboard/trials/${recovered.id}/`);
    await page.locator('.tool-call').first().waitFor();
    const fileIndex = JSON.parse(fs.readFileSync(path.join(packageRoot, manifest.release_path, 'trials', recovered.id, 'files/index.json')));
    const session = fileIndex.groups.agent.find(f => f.name.startsWith('original-codex-sessions/') && f.name.endsWith('.jsonl'));
    assert(session && session.download && session.parts.length, 'Recovered original session must be publicly readable');
    for (const [task, seconds] of [['budgeted-bimetric-retrieval', 7201.120332], ['constrained-molecular-search', 16127.410464]]) {
      const selected = snapshot.trials.find(t => t.task === task && t.configuration.model === 'xiaomi/mimo-v2.6-flash');
      assert.equal(selected.configuration.run_mode, 'regrade');
      assert(Math.abs(selected.agent_seconds - seconds) < 1e-6);
      const inventory = JSON.parse(fs.readFileSync(path.join(packageRoot, manifest.release_path, 'trials', selected.id, 'files/index.json')));
      const originals = inventory.groups.agent.filter(f => f.name.startsWith('original-coding/'));
      assert.equal(originals.length, 5);
      assert(originals.every(f => f.download && f.parts.length));
      const originalResult = originals.find(f => f.name === 'original-coding/result.json');
      const original = await page.evaluate(async url => {
        const response = await fetch(url, {credentials: 'omit'});
        return JSON.parse(await response.json());
      }, `${dataOrigin}/${manifest.release_path}/trials/${selected.id}/files/${originalResult.parts[0]}`);
      assert.equal(original.id, selected.configuration.coding_source_trial_id);
      assert.notEqual(original.id, selected.configuration.grading_trial_id);
    }
    const timedRegrade = snapshot.trials.find(t => t.task === 'instruction-following-embedding' && t.configuration.model === 'xiaomi/mimo-v2.6-flash');
    assert(Math.abs(timedRegrade.agent_seconds - 7201.244785) < 1e-6);
    assert.equal(timedRegrade.agent_status, 'AgentTimeoutError');
    const hy4 = snapshot.entries.find(e => e.model === 'tencent/hy4');
    assert.equal(hy4.effort, 'high');
    assert.equal(hy4.provider, 'Tencent');
    await page.goto(`${origin}/leaderboard/entries/${hy4.id}/`);
    assert.deepEqual(await page.locator('tbody .provider-cell').allTextContents(), Array(47).fill('Tencent'));
    assert(!(await page.locator('.entry-subtitle').innerText()).includes('OpenRouter'));
    for (const task of ['code-context-retrieval', 'code-reranker-finetuning', 'decision-model-training', 'rust-bm25-search']) {
      const selected = snapshot.trials.find(t => t.entry === hy4.id && t.task === task);
      const trialRoot = path.join(packageRoot, manifest.release_path, 'trials', selected.id);
      const atif = JSON.parse(gunzipSync(fs.readFileSync(path.join(trialRoot, 'trajectory.json.gz'))));
      const inventory = JSON.parse(fs.readFileSync(path.join(trialRoot, 'files/index.json')));
      assert.equal(atif.agent.version, '2.1.309');
      assert.equal(atif.final_metrics.total_completion_tokens, selected.tokens.output_tokens);
      assert(selected.tokens.output_tokens > 0);
      assert.equal(selected.tokens.response_count, 0);
      assert(atif.steps.filter(s => s.source === 'agent' && s.metrics).every(s => s.metrics.completion_tokens === null));
      assert(inventory.groups.agent.some(f => f.name === 'claude-code-cli-output.json' && f.download && f.parts.length));
      assert(!inventory.groups.agent.some(f => f.name.endsWith('.jsonl')));
      await page.goto(`${origin}/leaderboard/trials/${selected.id}/`);
      await page.locator('.trajectory-step').first().waitFor();
    }
    const step5 = snapshot.entries.find(e => e.model === 'step-5-preview');
    assert.equal(step5.agent_version, '2.1.309');
    assert.equal(step5.effort, 'max');
    assert.equal(step5.provider, 'StepFun');
    await page.goto(`${origin}/leaderboard/entries/${step5.id}/`);
    assert.deepEqual(await page.locator('tbody .provider-cell').allTextContents(), Array(47).fill('StepFun'));
    let step5Sessions = 0;
    for (const selected of snapshot.trials.filter(t => t.entry === step5.id)) {
      const inventory = JSON.parse(fs.readFileSync(path.join(packageRoot, manifest.release_path, 'trials', selected.id, 'files/index.json')));
      const native = inventory.groups.agent.filter(f => f.name.endsWith('.jsonl'));
      assert(native.length > 0 && native.every(f => f.download && f.parts.length), 'Step 5 native sessions must be downloadable');
      step5Sessions += native.length;
    }
    assert.equal(step5Sessions, 50);
    for (const [task, seconds] of [['evolving-personal-memory', 7201.643989], ['instruction-following-embedding', 7201.056449]]) {
      const selected = snapshot.trials.find(t => t.entry === step5.id && t.task === task);
      assert(Math.abs(selected.agent_seconds - seconds) < 1e-6);
      const inventory = JSON.parse(fs.readFileSync(path.join(packageRoot, manifest.release_path, 'trials', selected.id, 'files/index.json')));
      const proof = inventory.groups.agent.find(f => f.name === 'original-coding/result.json');
      assert(proof && proof.download && proof.parts.length);
      const original = await page.evaluate(async url => {
        const response = await fetch(url, {credentials: 'omit'});
        if (!response.ok) throw new Error(`Original coding proof failed: ${response.status}`);
        return JSON.parse(await response.json());
      }, `${dataOrigin}/${manifest.release_path}/trials/${selected.id}/files/${proof.parts[0]}`);
      assert.equal(original.id, selected.configuration.coding_source_trial_id);
      await page.goto(`${origin}/leaderboard/trials/${selected.id}/?tab=agent`);
      await page.locator('#panel-agent .file-text').waitFor();
    }
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
