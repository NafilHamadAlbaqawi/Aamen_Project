/*
WP8 — offline tests for extension/background.js (the service worker).

Runs with Node's built-in test runner, no packages needed:
    node --test tests/wp8_js/

background.js is loaded into a separate context with a fake `chrome` object and a fake `fetch`,
so the tests check exactly what the service worker sends to FastAPI and what it gives back to the popup.
*/
'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const nodeCrypto = require('node:crypto');

const SOURCE = fs.readFileSync(path.join(__dirname, '..', '..', 'extension', 'background.js'), 'utf8');
const EXT_ID = 'aamenextensionid';
const POPUP_SENDER = { id: EXT_ID, url: `chrome-extension://${EXT_ID}/popup.html` };
const TERMS = 'We may share your precise location and photos with advertising partners. '.repeat(3);

// A small chrome.storage area kept in memory. get() works with a defaults object, like the real one.
function storageArea(initial = {}) {
  const data = { ...initial };
  return {
    data,
    async get(defaults) {
      if (typeof defaults === 'string') return defaults in data ? { [defaults]: data[defaults] } : {};
      const out = { ...(defaults || {}) };
      Object.keys(out).forEach(key => { if (key in data) out[key] = data[key]; });
      return out;
    },
    async set(values) { Object.assign(data, JSON.parse(JSON.stringify(values))); }
  };
}

function jsonResponse(status, body) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body
  };
}

// Loads a fresh copy of background.js. routes(method, url, body) decides what the fake server answers.
function loadWorker({ routes, local = {}, allowed = true } = {}) {
  const calls = [];
  const timeouts = [];
  let listener = null;

  const chrome = {
    runtime: {
      id: EXT_ID,
      getURL: p => `chrome-extension://${EXT_ID}/${p}`,
      getPlatformInfo: async () => ({ os: 'win' }),
      onMessage: { addListener: fn => { listener = fn; } }
    },
    storage: { local: storageArea(local), session: storageArea() },
    permissions: { contains: async () => allowed }
  };

  const fakeFetch = async (url, options) => {
    const body = options.body ? JSON.parse(options.body) : undefined;
    calls.push({ method: options.method, url, body });
    return routes(options.method, url, body);
  };

  const FakeAbortSignal = {
    timeout(ms) { timeouts.push(ms); return AbortSignal.timeout(ms); }
  };

  const context = vm.createContext({
    chrome, fetch: fakeFetch, AbortSignal: FakeAbortSignal, URL, console,
    crypto: { randomUUID: () => nodeCrypto.randomUUID() },
    setInterval, clearInterval, setTimeout, clearTimeout
  });
  vm.runInContext(SOURCE, context, { filename: 'background.js' });

  // Sends one message the way the popup does and waits for sendResponse.
  function send(message, sender = POPUP_SENDER) {
    return new Promise(resolve => {
      const keepsChannel = listener(message, sender, resolve);
      if (keepsChannel !== true) resolve('IGNORED');
    });
  }

  return { chrome, calls, timeouts, send };
}

const ANALYSIS = {
  status: 'completed', analysis_mode: 'openai', risk_score: 67, risk_level: 'High Risk',
  summary_en: 'Summary', summary_ar: 'ملخص', flagged_clauses: [], input_truncated: false,
  disclaimer: 'AI-generated screening, not a legal compliance determination.', pdpl: null
};

function okRoutes(method, url) {
  if (url.endsWith('/health')) return jsonResponse(200, { status: 'ok' });
  if (method === 'PUT' && url.includes('/preferences/')) return jsonResponse(200, {});
  if (method === 'POST' && url.endsWith('/analyze')) return jsonResponse(200, ANALYSIS);
  return jsonResponse(404, { detail: 'Not Found' });
}

test('TC-JS01 preferences: not accepted topics are sent to WP6 as extra attention (true)', async () => {
  const w = loadWorker({ routes: okRoutes, local: { device_id: 'device_12345678' } });
  const accepted = { location: true, photos: false, banking_information: false, third_party_sharing: true };

  const response = await w.send({ type: 'WP8_SAVE_PREFERENCES', payload: { accepted } });

  assert.equal(response.ok, true);
  assert.equal(response.data.synced, true);
  assert.equal(w.calls.length, 1);
  assert.equal(w.calls[0].method, 'PUT');
  assert.equal(w.calls[0].url, 'http://127.0.0.1:8000/preferences/device_12345678');
  assert.deepEqual(w.calls[0].body, { location: false, photos: true, banking_information: true, third_party_sharing: false });
  assert.deepEqual(w.chrome.storage.local.data.accepted_topics, accepted);
  assert.equal(w.chrome.storage.local.data.preferences_saved, true);
  assert.equal(w.chrome.storage.local.data.preferences_synced, true);
});

test('TC-JS02 preferences: invalid values are rejected before any request', async () => {
  const w = loadWorker({ routes: okRoutes });
  const response = await w.send({
    type: 'WP8_SAVE_PREFERENCES',
    payload: { accepted: { location: 'yes', photos: false, banking_information: false, third_party_sharing: false } }
  });

  assert.equal(response.ok, false);
  assert.equal(response.code, 'bad_request');
  assert.equal(w.calls.length, 0);
  assert.equal(w.chrome.storage.local.data.accepted_topics, undefined);
});

test('TC-JS03 preferences: saved offline, then sent before the next analysis', async () => {
  let serverUp = false;
  const routes = (method, url, body) => {
    if (!serverUp) throw new TypeError('Failed to fetch');
    return okRoutes(method, url, body);
  };
  const w = loadWorker({ routes, local: { device_id: 'device_12345678' } });
  const accepted = { location: false, photos: true, banking_information: false, third_party_sharing: false };

  const saved = await w.send({ type: 'WP8_SAVE_PREFERENCES', payload: { accepted } });
  assert.equal(saved.ok, true);
  assert.equal(saved.data.synced, false);
  assert.equal(saved.data.code, 'server_unreachable');
  assert.equal(w.chrome.storage.local.data.preferences_synced, false);

  serverUp = true;
  w.calls.length = 0;
  const analyzed = await w.send({ type: 'WP2_ANALYZE', payload: { terms_text: TERMS, language: 'en' } });

  assert.equal(analyzed.ok, true);
  assert.deepEqual(w.calls.map(c => c.method + ' ' + new URL(c.url).pathname),
    ['PUT /preferences/device_12345678', 'POST /analyze']);
  assert.equal(w.chrome.storage.local.data.preferences_synced, true);
});

test('TC-JS04 analysis: body keeps the WP2 contract and the long timeout is used', async () => {
  const w = loadWorker({ routes: okRoutes, local: { device_id: 'device_12345678' } });
  const response = await w.send({
    type: 'WP2_ANALYZE',
    payload: { terms_text: '  ' + TERMS + '  ', language: 'ar', page_url: 'https://example.com/terms', page_title: 'Terms' }
  });

  assert.equal(response.ok, true);
  assert.deepEqual(response.data, ANALYSIS);
  const body = w.calls[0].body;
  assert.deepEqual(Object.keys(body).sort(), ['device_id', 'language', 'page_title', 'page_url', 'terms_text']);
  assert.equal(body.terms_text, TERMS.trim());
  assert.equal(body.language, 'ar');
  assert.equal('preferences' in body, false, 'preferences come from the WP6 database, not from the request');
  assert.ok(w.timeouts.includes(150000));
});

test('TC-JS05 analysis: text outside 50..120000 characters never reaches the server', async () => {
  const w = loadWorker({ routes: okRoutes });
  const response = await w.send({ type: 'WP2_ANALYZE', payload: { terms_text: 'too short' } });

  assert.equal(response.ok, false);
  assert.equal(response.code, 'too_short');
  assert.equal(w.calls.length, 0);
});

const ERROR_CASES = [
  { name: 'missing API key', status: 503, detail: 'AI analysis is not configured on this server.', code: 'ai_not_configured' },
  { name: 'preference database down', status: 503, detail: 'Preference storage is unavailable.', code: 'storage_unavailable' },
  { name: 'no clauses found', status: 502, detail: 'No source-grounded clauses could be extracted. Try a clearer T&C document.', code: 'no_clauses' },
  { name: 'classifier omitted clauses', status: 502, detail: 'The classifier omitted one or more clauses.', code: 'ai_unavailable' },
  { name: 'OpenAI rejected', status: 502, detail: 'AI service unavailable or rejected the request.', code: 'ai_unavailable' },
  { name: 'unexpected error', status: 500, detail: 'Unexpected analysis error.', code: 'ai_unavailable' },
  { name: 'text too short after trimming', status: 422, detail: 'At least 50 characters of Terms and Conditions are required.', code: 'too_short' },
  {
    name: 'FastAPI validation list', status: 422, code: 'too_short',
    detail: [{ loc: ['body', 'terms_text'], msg: 'String should have at least 50 characters' }],
    message: 'Invalid request (terms_text): String should have at least 50 characters'
  },
  {
    name: 'other validation error', status: 422, code: 'bad_request',
    detail: [{ loc: ['body', 'device_id'], msg: 'String should match pattern' }],
    message: 'Invalid request (device_id): String should match pattern'
  }
];

for (const c of ERROR_CASES) {
  test(`TC-JS06 error code: ${c.name} -> ${c.code}`, async () => {
    const w = loadWorker({ routes: () => jsonResponse(c.status, { detail: c.detail }) });
    const response = await w.send({ type: 'WP2_ANALYZE', payload: { terms_text: TERMS } });

    assert.equal(response.ok, false);
    assert.equal(response.code, c.code);
    assert.equal(response.status, c.status);
    assert.equal(response.error, c.message || c.detail);
  });
}

test('TC-JS07 error code: server down, timeout and missing permission', async () => {
  const down = loadWorker({ routes: () => { throw new TypeError('Failed to fetch'); } });
  const downResponse = await down.send({ type: 'WP2_CHECK_CONNECTION' });
  assert.equal(downResponse.code, 'server_unreachable');
  assert.match(downResponse.error, /^Cannot reach the FastAPI server/);

  const slow = loadWorker({ routes: () => { const e = new Error('signal timed out'); e.name = 'TimeoutError'; throw e; } });
  const slowResponse = await slow.send({ type: 'WP2_ANALYZE', payload: { terms_text: TERMS } });
  assert.equal(slowResponse.code, 'timeout');
  assert.match(slowResponse.error, /timed out/);

  const blocked = loadWorker({ routes: okRoutes, allowed: false });
  const blockedResponse = await blocked.send({ type: 'WP2_CHECK_CONNECTION' });
  assert.equal(blockedResponse.code, 'permission');
  assert.equal(blocked.calls.length, 0);
});

test('TC-JS08 run record: a finished analysis is kept for a popup opened later', async () => {
  const w = loadWorker({ routes: okRoutes });
  const source = { kind: 'page', url: 'https://example.com/terms', title: 'Example terms' };
  await w.send({ type: 'WP2_ANALYZE', payload: { terms_text: TERMS, source } });

  const run = w.chrome.storage.session.data.aamen_run;
  assert.equal(run.status, 'done');
  assert.deepEqual(run.source, source);
  assert.deepEqual(run.result, ANALYSIS);
  assert.ok(run.finished_at >= run.started_at);

  const failing = loadWorker({ routes: () => jsonResponse(503, { detail: 'AI analysis is not configured on this server.' }) });
  await failing.send({ type: 'WP2_ANALYZE', payload: { terms_text: TERMS, source } });
  const failedRun = failing.chrome.storage.session.data.aamen_run;
  assert.equal(failedRun.status, 'error');
  assert.equal(failedRun.code, 'ai_not_configured');
});

test('TC-JS09 run record: an older run that ends late does not replace a newer one', async () => {
  const pending = [];
  const routes = () => new Promise(resolve => pending.push(resolve));
  const w = loadWorker({ routes });
  const first = w.send({ type: 'WP2_ANALYZE', payload: { terms_text: TERMS, source: { kind: 'paste', url: '', title: 'first' } } });
  await new Promise(r => setTimeout(r, 20));
  const second = w.send({ type: 'WP2_ANALYZE', payload: { terms_text: TERMS, source: { kind: 'paste', url: '', title: 'second' } } });
  await new Promise(r => setTimeout(r, 20));

  pending[1](jsonResponse(200, ANALYSIS));
  await second;
  pending[0](jsonResponse(200, { ...ANALYSIS, summary_en: 'old' }));
  await first;

  const run = w.chrome.storage.session.data.aamen_run;
  assert.equal(run.source.title, 'second');
  assert.equal(run.result.summary_en, 'Summary');
});

test('TC-JS10 messages: only the extension\'s own pages are answered', async () => {
  const w = loadWorker({ routes: okRoutes });

  const fromWebsite = await w.send({ type: 'WP2_CHECK_CONNECTION' },
    { id: EXT_ID, url: 'https://evil.example/page', tab: { id: 3 } });
  assert.equal(fromWebsite, 'IGNORED');

  const otherExtension = await w.send({ type: 'WP2_CHECK_CONNECTION' },
    { id: 'someoneelse', url: 'chrome-extension://someoneelse/popup.html' });
  assert.equal(otherExtension, 'IGNORED');

  const unknownType = await w.send({ type: 'SOMETHING_ELSE' });
  assert.equal(unknownType, 'IGNORED');

  const popupInTab = await w.send({ type: 'WP2_CHECK_CONNECTION' }, { ...POPUP_SENDER, tab: { id: 9 } });
  assert.equal(popupInTab.ok, true);
  assert.equal(w.calls.length, 1);
});
