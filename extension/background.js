
/*
WP2 — Chrome Extension to FastAPI Communication

Responsibilities:
- Validate and read the backend server address.
- Check Chrome host permissions.
- Send HTTP requests to FastAPI.
- Maintain an anonymous device identifier.
- Send legal text for analysis.
- Return server responses to the popup.
*/

// 1. Define and validate the backend URL.
const DEFAULT_SERVER_URL = 'http://127.0.0.1:8000';

function normalizeServerUrl(value) {
  if (typeof value !== 'string') throw new Error('Server URL is missing.');

  const url = new URL(value.trim());

  if (!['http:', 'https:'].includes(url.protocol) ||
      url.username || url.password ||
      url.pathname !== '/' || url.search || url.hash) {
    throw new Error('Enter a server origin such as http://192.168.1.5:8000');
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
    throw new Error('Backend permission missing. Allow this server in Aamen settings.');
  }

  return origin;
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
      signal: AbortSignal.timeout(55000)
    });
  } catch (error) {
    throw new Error('Cannot reach the FastAPI server: ' + error.message);
  }

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    const detail = typeof data.detail === 'string'
      ? data.detail
      : `Backend returned HTTP ${response.status}`;

    throw new Error(detail);
  }

  return data;
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

// 5. Prepare and send the FastAPI analysis request.
async function analyzeText(payload) {
  const terms_text = typeof payload?.terms_text === 'string'
    ? payload.terms_text.trim()
    : '';

  if (terms_text.length < 50 || terms_text.length > 120000) {
    throw new Error('Legal text must contain between 50 and 120000 characters.');
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

  return requestBackend('/analyze', { method: 'POST', body: body });
}

// 6. Receive extension messages and return backend responses.
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (sender.id !== chrome.runtime.id || sender.tab) return false;

  if (message?.type !== 'WP2_CHECK_CONNECTION' &&
      message?.type !== 'WP2_ANALYZE') {
    return false;
  }

  (async () => {
    try {
      const data = message.type === 'WP2_CHECK_CONNECTION'
        ? await requestBackend('/health')
        : await analyzeText(message.payload);

      sendResponse({ ok: true, data: data });
    } catch (error) {
      sendResponse({
        ok: false,
        error: error.message || 'Unexpected backend error'
      });
    }
  })();

  return true;
});
