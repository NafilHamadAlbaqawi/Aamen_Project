
/*
WP2 — Chrome Extension to FastAPI Communication
WP8 — System integration

Responsibilities:
- Validate and read the backend server address.
- Check Chrome host permissions.
- Send HTTP requests to FastAPI.
- Maintain an anonymous device identifier.
- Send legal text for analysis.
- Return server responses to the popup.
- (WP8) Save the user's preferences in the WP6 database so WP4 can personalize the prompts.
- (WP8) Return errors with a stable code, so the popup does not have to read English sentences.
- (WP8) Keep long analyses alive and remember the last run, so closing the popup does not lose the result.
*/

// 1. Define and validate the backend URL.
const DEFAULT_SERVER_URL = 'http://127.0.0.1:8000';

// WP8: time limits. The analysis makes four model calls in a row (extract, classify, summarize, PDPL),
// each with a 45 second limit on the backend, so 55 seconds was too short for long documents.
const ANALYZE_TIMEOUT_MS = 150000;
const REQUEST_TIMEOUT_MS = 20000;
const KEEP_ALIVE_MS = 20000;

// WP8: the four preference topics. Same names as backend/prompt_adjuster/preferences.py and the popup.
const PREFERENCE_FIELDS = ['location', 'photos', 'banking_information', 'third_party_sharing'];

// WP8: where the last analysis run is kept (chrome.storage.session is cleared when the browser closes).
const RUN_KEY = 'aamen_run';

// WP8: an error with a code the popup understands (see errorCodeFor below).
class BackendError extends Error {
  constructor(message, code, status) {
    super(message);
    this.code = code || 'unknown';
    this.status = status || 0;
  }
}

function normalizeServerUrl(value) {
  if (typeof value !== 'string') throw new BackendError('Server URL is missing.', 'permission');

  let url;
  try {
    url = new URL(value.trim());
  } catch {
    throw new BackendError('Enter a server origin such as http://192.168.1.5:8000', 'permission');
  }

  if (!['http:', 'https:'].includes(url.protocol) ||
      url.username || url.password ||
      url.pathname !== '/' || url.search || url.hash) {
    throw new BackendError('Enter a server origin such as http://192.168.1.5:8000', 'permission');
  }

  return url.origin;
}

// 2. Read the server URL and verify Chrome host access.
async function getServerUrl() {
  const { server_url } = await chrome.storage.local.get({
    server_url: DEFAULT_SERVER_URL
  });

  const origin = normalizeServerUrl(server_url);
  const parsed = new URL(origin);
  const hostPattern = `${parsed.protocol}//${parsed.hostname}/*`;

  const allowed = await chrome.permissions.contains({
    origins: [hostPattern]
  });

  if (!allowed) {
    throw new BackendError('Backend permission missing. Allow this server in Aamen settings.', 'permission');
  }

  return origin;
}

// WP8: turn an HTTP status and the backend's detail text into one of the popup's error codes.
// The detail texts come from backend/main.py and backend/analysis/clause_extractor.py.
function errorCodeFor(status, detail) {
  const text = String(detail || '');

  if (status === 503 && /not configured/i.test(text)) return 'ai_not_configured';
  if (status === 503 && /preference storage/i.test(text)) return 'storage_unavailable';
  if (status === 502 && /source-grounded/i.test(text)) return 'no_clauses';
  if (status === 422 && /terms_text|at least 50|between 50/i.test(text)) return 'too_short';
  if (status === 504 || status === 408) return 'timeout';
  if (status >= 500) return 'ai_unavailable';
  return 'bad_request';
}

// WP8: FastAPI validation errors (422) send a list instead of a sentence. Make it one readable line.
function detailText(data, status) {
  if (typeof data?.detail === 'string') return data.detail;

  if (Array.isArray(data?.detail) && data.detail.length) {
    const first = data.detail[0] || {};
    const where = Array.isArray(first.loc) ? first.loc.filter(part => part !== 'body').join('.') : '';
    const message = typeof first.msg === 'string' ? first.msg : 'Invalid request';
    return `Invalid request${where ? ' (' + where + ')' : ''}: ${message}`;
  }

  return `Backend returned HTTP ${status}`;
}

// 3. Send HTTP requests and handle backend errors.
async function requestBackend(path, options = {}) {
  const serverUrl = await getServerUrl();
  let response;

  try {
    response = await fetch(`${serverUrl}${path}`, {
      method: options.method || 'GET',
      headers: { 'Content-Type': 'application/json' },
      body: options.body ? JSON.stringify(options.body) : undefined,
      credentials: 'omit',
      signal: AbortSignal.timeout(options.timeout || REQUEST_TIMEOUT_MS)
    });
  } catch (error) {
    if (error && error.name === 'TimeoutError') {
      throw new BackendError('The Aamen server took too long to answer (timed out).', 'timeout');
    }
    throw new BackendError('Cannot reach the FastAPI server: ' + error.message, 'server_unreachable');
  }

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    const detail = detailText(data, response.status);
    throw new BackendError(detail, errorCodeFor(response.status, detail), response.status);
  }

  return data;
}

// WP8: an extension service worker is stopped after about 30 seconds without any extension events.
// Calling a cheap extension API every 20 seconds while a request is open keeps it running until the answer arrives.
async function withKeepAlive(task) {
  const timer = setInterval(() => {
    chrome.runtime.getPlatformInfo().catch(() => {});
  }, KEEP_ALIVE_MS);

  try {
    return await task();
  } finally {
    clearInterval(timer);
  }
}

// 4. Generate or reuse an anonymous device identifier.
async function getDeviceId() {
  const { device_id } = await chrome.storage.local.get({ device_id: '' });

  if (typeof device_id === 'string' &&
      /^[a-zA-Z0-9_-]{8,100}$/.test(device_id)) {
    return device_id;
  }

  const newId = crypto.randomUUID();
  await chrome.storage.local.set({ device_id: newId });

  return newId;
}

// WP8: preferences.
// The popup asks "what do you accept?" (Senior Project I: allowLocation, allowPhotos, ...).
// The backend (WP4/WP6) stores "which topics need extra attention". A topic the user does NOT accept is a
// topic they are sensitive about, so it is sent as true (extra attention). An accepted topic is sent as false.
function validateAccepted(value) {
  if (!value || typeof value !== 'object') {
    throw new BackendError('Preferences are missing.', 'bad_request');
  }

  const accepted = {};

  for (const field of PREFERENCE_FIELDS) {
    if (typeof value[field] !== 'boolean') {
      throw new BackendError(`Preference "${field}" must be true or false.`, 'bad_request');
    }
    accepted[field] = value[field];
  }

  return accepted;
}

function toBackendPreferences(accepted) {
  const preferences = {};
  PREFERENCE_FIELDS.forEach(field => { preferences[field] = !accepted[field]; });
  return preferences;
}

async function pushPreferences(accepted) {
  const deviceId = await getDeviceId();

  return requestBackend(`/preferences/${encodeURIComponent(deviceId)}`, {
    method: 'PUT',
    body: toBackendPreferences(accepted)
  });
}

// Saves on this device first, then on the server. If the server can't be reached the choice is still kept,
// and it is sent again before the next analysis (see syncPendingPreferences).
async function savePreferences(payload) {
  const accepted = validateAccepted(payload?.accepted);

  await chrome.storage.local.set({
    accepted_topics: accepted,
    preferences_saved: true,
    preferences_synced: false
  });

  try {
    await pushPreferences(accepted);
    await chrome.storage.local.set({ preferences_synced: true });
    return { accepted, synced: true };
  } catch (error) {
    return { accepted, synced: false, error: error.message, code: error.code || 'unknown' };
  }
}

async function syncPendingPreferences() {
  const stored = await chrome.storage.local.get({
    accepted_topics: null,
    preferences_saved: false,
    preferences_synced: true
  });

  if (!stored.preferences_saved || stored.preferences_synced) return;

  try {
    await pushPreferences(validateAccepted(stored.accepted_topics));
    await chrome.storage.local.set({ preferences_synced: true });
  } catch {
    // The analysis still runs, with the last preferences the server has.
  }
}

// WP8: remember the last analysis run, so a popup that was closed and opened again can show it.
// Only the newest run may write, so an older run that finishes late can't replace a newer one.
async function writeRun(run) {
  try {
    const current = (await chrome.storage.session.get({ [RUN_KEY]: null }))[RUN_KEY];
    if (run.status !== 'running' && current && current.id !== run.id) return;
    await chrome.storage.session.set({ [RUN_KEY]: run });
  } catch {
    // Not being able to remember the run must never break the analysis itself.
  }
}

function cleanSource(source, payload) {
  return {
    kind: source?.kind === 'paste' ? 'paste' : 'page',
    url: typeof source?.url === 'string' ? source.url.slice(0, 2048) : String(payload?.page_url || '').slice(0, 2048),
    title: typeof source?.title === 'string' ? source.title.slice(0, 300) : String(payload?.page_title || '').slice(0, 300)
  };
}

// 5. Prepare and send the FastAPI analysis request.
async function analyzeText(payload) {
  const terms_text = typeof payload?.terms_text === 'string'
    ? payload.terms_text.trim()
    : '';

  if (terms_text.length < 50 || terms_text.length > 120000) {
    throw new BackendError('Legal text must contain between 50 and 120000 characters.', 'too_short');
  }

  const stored = await chrome.storage.local.get({ language: 'en' });

  const language = ['en', 'ar'].includes(payload?.language)
    ? payload.language
    : stored.language === 'ar' ? 'ar' : 'en';

  const body = {
    device_id: await getDeviceId(),
    language: language,
    page_url: typeof payload?.page_url === 'string'
      ? payload.page_url.slice(0, 2048)
      : '',
    page_title: typeof payload?.page_title === 'string'
      ? payload.page_title.slice(0, 300)
      : '',
    terms_text: terms_text
  };

  // WP8: the run record and the preference sync happen around the original WP2 request.
  const run = {
    id: crypto.randomUUID(),
    status: 'running',
    started_at: Date.now(),
    source: cleanSource(payload?.source, payload)
  };

  await writeRun(run);

  try {
    await syncPendingPreferences();

    const result = await withKeepAlive(() =>
      requestBackend('/analyze', { method: 'POST', body: body, timeout: ANALYZE_TIMEOUT_MS }));

    await writeRun({ ...run, status: 'done', finished_at: Date.now(), result: result });
    return result;
  } catch (error) {
    await writeRun({
      ...run,
      status: 'error',
      finished_at: Date.now(),
      error: error.message || 'Unexpected backend error',
      code: error.code || 'unknown'
    });
    throw error;
  }
}

// 6. Receive extension messages and return backend responses.
// WP8: messages are accepted from the extension's own pages only (the popup, or popup.html opened in a tab).
// Content scripts and websites can't use these messages, because their sender URL is the website.
const MESSAGE_TYPES = ['WP2_CHECK_CONNECTION', 'WP2_ANALYZE', 'WP8_SAVE_PREFERENCES'];

function fromExtensionPage(sender) {
  return sender.id === chrome.runtime.id &&
    typeof sender.url === 'string' &&
    sender.url.startsWith(chrome.runtime.getURL(''));
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!fromExtensionPage(sender)) return false;

  if (!MESSAGE_TYPES.includes(message?.type)) {
    return false;
  }

  (async () => {
    try {
      let data;

      if (message.type === 'WP2_CHECK_CONNECTION') {
        data = await requestBackend('/health');
      } else if (message.type === 'WP8_SAVE_PREFERENCES') {
        data = await savePreferences(message.payload);
      } else {
        data = await analyzeText(message.payload);
      }

      sendResponse({ ok: true, data: data });
    } catch (error) {
      sendResponse({
        ok: false,
        error: error.message || 'Unexpected backend error',
        code: error.code || 'unknown',
        status: error.status || 0
      });
    }
  })();

  return true;
});
