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
const packageRoot = path.resolve(process.env.HF_PACKAGE || path.join(root, '.build/hf-trajectories'));
const origin = process.env.LEADERBOARD_ORIGIN || 'http://127.0.0.1:7788';
const manifest = JSON.parse(gunzipSync(fs.readFileSync(path.join(packageRoot, 'publication.json.gz'))));
const snapshot = JSON.parse(fs.readFileSync(path.join(root, 'content/leaderboard/release.json')));
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
