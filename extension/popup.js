
/* WP2 — Keep WP1 extraction and add FastAPI communication. */

// 1. Connect to the HTML elements created in WP1 and WP2.
const appTitle = document.getElementById('appTitle');
const description = document.getElementById('description');
const analyzeButton = document.getElementById('analyzeButton');
const englishButton = document.getElementById('englishButton');
const arabicButton = document.getElementById('arabicButton');
const extractionTitle = document.getElementById('extractionTitle');
const previewTitle = document.getElementById('previewTitle');
const linksTitle = document.getElementById('linksTitle');
const statusBox = document.getElementById('status');
const pageTitle = document.getElementById('pageTitle');
const manualHelp = document.getElementById('manualHelp');
const termsInput = document.getElementById('termsInput');
const legalLinksList = document.getElementById('legalLinksList');
const footerText = document.getElementById('footerText');
const serverTitle = document.getElementById('serverTitle');
const serverLabel = document.getElementById('serverLabel');
const serverUrlInput = document.getElementById('serverUrl');
const saveServerButton = document.getElementById('saveServerButton');
const checkServerButton = document.getElementById('checkServerButton');
const backendStatus = document.getElementById('backendStatus');

// 2. Interface text in English and Arabic.
const translations = {
  en: {
    title: 'Aamen', description: 'T&C and Privacy Policy Extraction',
    extraction: 'Legal Document Extraction', analyze: 'Analyze Current Page',
    preview: 'Extracted Legal Text', links: 'Discovered Legal Documents',
    help: 'You can paste legal text manually if extraction fails.',
    placeholder: 'Extracted Terms & Conditions or Privacy Policy text will appear here.',
    footer: 'Aamen — Legal document extraction', ready: 'Ready to extract.',
    working: 'Extracting legal documents...', terms: 'Terms & Conditions',
    privacy: 'Privacy Policy', other: 'Legal document',
    missing: 'No legal text extracted. You can paste it manually.',
    found: 'legal document(s) extracted', failed: 'Some links could not be retrieved',
    serverTitle: 'Backend Server Settings', serverLabel: 'Backend URL',
    save: 'Save Server', check: 'Check Connection', send: 'Send Text to Server',
    saved: 'Server address saved and permission granted.',
    connected: 'Connected to the Aamen backend.',
    sending: 'Sending text to FastAPI...', received: 'Analysis response received.',
    results: 'Backend Response', risk: 'Risk score', summary: 'Summary',
    empty: 'Extract or paste at least 50 characters before sending.'
  },
  ar: {
    title: 'آمن', description: 'استخراج الشروط والأحكام وسياسة الخصوصية',
    extraction: 'استخراج المستندات القانونية', analyze: 'تحليل الصفحة الحالية',
    preview: 'النص القانوني المستخرج', links: 'المستندات القانونية المكتشفة',
    help: 'يمكنك لصق النص القانوني يدويًا إذا فشل الاستخراج.',
    placeholder: 'سيظهر هنا نص الشروط والأحكام أو سياسة الخصوصية.',
    footer: 'آمن — استخراج المستندات القانونية', ready: 'جاهز للاستخراج.',
    working: 'جارٍ استخراج المستندات القانونية...', terms: 'الشروط والأحكام',
    privacy: 'سياسة الخصوصية', other: 'مستند قانوني',
    missing: 'لم يتم استخراج نص قانوني. يمكنك لصقه يدويًا.',
    found: 'مستندات قانونية تم استخراجها', failed: 'تعذر جلب بعض الروابط',
    serverTitle: 'إعدادات الخادم', serverLabel: 'رابط الخادم',
    save: 'حفظ الخادم', check: 'اختبار الاتصال', send: 'إرسال النص إلى الخادم',
    saved: 'تم حفظ عنوان الخادم والسماح بالاتصال.',
    connected: 'تم الاتصال بخادم آمن بنجاح.',
    sending: 'جارٍ إرسال النص إلى الخادم...', received: 'تم استلام نتيجة التحليل.',
    results: 'استجابة الخادم', risk: 'درجة الخطورة', summary: 'الملخص',
    empty: 'استخرج أو الصق نصًا لا يقل عن 50 حرفًا قبل الإرسال.'
  }
};

let language = 'en';
let lastLinks = [];
let lastResult = null;
let lastPageUrl = '';
let lastPageTitle = '';
const DEFAULT_SERVER_URL = 'http://127.0.0.1:8000';
const termsWords = /terms|conditions|agreement|tos|eula|الشروط|الأحكام|اتفاقية|الاستخدام/i;
const privacyWords = /privacy|personal.data|data.protection|الخصوصية|حماية.البيانات/i;

// 3. Create a send button and results panel, using the existing CSS classes.
const sendActions = document.createElement('div');
sendActions.className = 'server-actions';
const sendTextButton = document.createElement('button');
sendTextButton.id = 'sendTextButton';
sendTextButton.type = 'button';
sendTextButton.style.background = '#0D5B43';
sendTextButton.style.color = '#FFFFFF';
sendActions.append(sendTextButton);
backendStatus.after(sendActions);

const resultPanel = document.createElement('section');
resultPanel.className = 'card';
resultPanel.hidden = true;
document.getElementById('serverSection').after(resultPanel);

// 4. Switch interface language without making a new backend request.
function setLanguage(value) {
  language = value === 'ar' ? 'ar' : 'en';
  const t = translations[language];
  document.documentElement.lang = language;
  document.body.dir = language === 'ar' ? 'rtl' : 'ltr';
  appTitle.textContent = t.title;
  description.textContent = t.description;
  extractionTitle.textContent = t.extraction;
  analyzeButton.textContent = t.analyze;
  previewTitle.textContent = t.preview;
  linksTitle.textContent = t.links;
  manualHelp.textContent = t.help;
  termsInput.placeholder = t.placeholder;
  footerText.textContent = t.footer;
  serverTitle.textContent = t.serverTitle;
  serverLabel.textContent = t.serverLabel;
  saveServerButton.textContent = t.save;
  checkServerButton.textContent = t.check;
  sendTextButton.textContent = t.send;
  if (!lastLinks.length && !termsInput.value) statusBox.textContent = t.ready;
  renderLinks(lastLinks);
  renderBackendResult();
  chrome.storage.local.set({ language }).catch(() => {});
}

function setBackendStatus(message, state = '') {
  backendStatus.textContent = message;
  backendStatus.dataset.state = state;
}

// 5. Preserve WP1 legal-link discovery and display.
function classifyLink(text) {
  if (privacyWords.test(text)) return 'privacy';
  if (termsWords.test(text)) return 'terms';
  return 'other';
}

function renderLinks(links) {
  legalLinksList.replaceChildren();
  for (const url of links) {
    const item = document.createElement('li');
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.target = '_blank';
    anchor.rel = 'noopener noreferrer';
    anchor.textContent = `${translations[language][classifyLink(url)]}: ${url}`;
    item.append(anchor);
    legalLinksList.append(item);
  }
}

function isSameOrigin(url, currentUrl) {
  try {
    const candidate = new URL(url);
    const current = new URL(currentUrl);
    return ['http:', 'https:'].includes(candidate.protocol) &&
      candidate.origin === current.origin &&
      !candidate.username && !candidate.password &&
      !/\.(pdf|docx?|zip|png|jpe?g)$/i.test(candidate.pathname);
  } catch {
    return false;
  }
}

// 6. Preserve WP1 public same-origin HTML extraction and its size limit.
async function fetchLegalText(url) {
  const site = new URL(url);
  const originPattern = `${site.protocol}//${site.hostname}/*`;
  const allowed = await chrome.permissions.contains({ origins: [originPattern] }) ||
    await chrome.permissions.request({ origins: [originPattern] });
  if (!allowed) throw new Error('Site permission denied');

  const response = await fetch(url, {
    credentials: 'omit',
    redirect: 'error',
    signal: AbortSignal.timeout(15000)
  });

  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  if (!/text\/html|application\/xhtml\+xml/i.test(response.headers.get('content-type') || '')) {
    throw new Error('Link is not an HTML page');
  }
  if (!response.body) throw new Error('Empty response');

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let html = '';
  let byteCount = 0;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    byteCount += value.byteLength;
    if (byteCount > 1000000) {
      await reader.cancel();
      throw new Error('Legal document is too large');
    }
    html += decoder.decode(value, { stream: true });
  }

  html += decoder.decode();
  const parsed = new DOMParser().parseFromString(html, 'text/html');
  parsed.querySelectorAll('script,style,noscript,nav,header,footer,aside,form,svg,iframe,[hidden],[aria-hidden="true"]')
    .forEach(element => element.remove());
  parsed.querySelectorAll('p,li,h1,h2,h3,h4').forEach(element => element.append('\n'));

  const main = parsed.querySelector('main,article,[role="main"],.entry-content,.post-content') || parsed.body;
  return (main?.textContent || '')
    .replace(/\u00a0/g, ' ')
    .replace(/[ \t]+/g, ' ')
    .replace(/\n[ \t]+/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
    .slice(0, 55000);
}

// 7. Preserve WP1's Analyze Current Page behavior; do not send text automatically.
async function analyzeCurrentPage() {
  analyzeButton.disabled = true;
  statusBox.textContent = translations[language].working;

  try {
    const [tab] = await chrome.tabs.query({
      active: true,
      currentWindow: true
    });

    if (!tab?.id || !/^https?:\/\//.test(tab.url || '')) {
      throw new Error('Open an HTTP or HTTPS website first');
    }

    const injected = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      files: ['content.js']
    });

    const extracted = injected?.[0]?.result;
    if (!extracted) throw new Error('Could not extract the webpage');

    pageTitle.textContent = extracted.page_title || tab.url;
    lastPageUrl = tab.url;
    lastPageTitle = extracted.page_title || '';

    lastLinks = [...new Set((extracted.legal_links || [])
      .filter(url => /^https?:\/\//i.test(url)))];

    renderLinks(lastLinks);

    const documents = [];
    const warnings = [];
    const pageKind = classifyLink(
      new URL(tab.url).pathname + ' ' + (extracted.page_title || '')
    );

    if (pageKind !== 'other' &&
        !extracted.needs_manual_paste &&
        extracted.terms_text) {
      documents.push({
        kind: pageKind,
        url: tab.url,
        text: extracted.terms_text.slice(0, 55000)
      });
    }

    for (const kind of ['terms', 'privacy']) {
      if (documents.some(doc => doc.kind === kind)) continue;

      const url = lastLinks.find(link =>
        isSameOrigin(link, tab.url) && classifyLink(link) === kind
      );

      if (!url) continue;

      try {
        const text = await fetchLegalText(url);
        if (text.length < 350) throw new Error('Not enough legal text found');
        documents.push({ kind, url, text });
      } catch (error) {
        warnings.push(`${kind}: ${error.message}`);
      }
    }

    termsInput.value = documents.map(doc =>
      `${translations[language][doc.kind]}\nSource: ${doc.url}\n\n${doc.text}`
    ).join('\n\n----------------------------------------\n\n');

    statusBox.textContent = documents.length
      ? `${documents.length} ${translations[language].found}${warnings.length ? ' — ' + translations[language].failed : ''}`
      : translations[language].missing;

  } catch (error) {
    statusBox.textContent = `Error: ${error.message}`;
  } finally {
    analyzeButton.disabled = false;
  }
}

// 8. Validate, authorize, and save the Windows FastAPI server URL.
function normalizeServerUrl(value) {
  let url;

  try {
    url = new URL(value.trim());
  } catch {
    throw new Error('Enter a valid URL, for example http://192.168.1.5:8000');
  }

  if (!['http:', 'https:'].includes(url.protocol) ||
      url.username || url.password ||
      url.pathname !== '/' || url.search || url.hash) {
    throw new Error('Enter only the server origin, such as http://192.168.1.5:8000');
  }

  return url.origin;
}

async function grantAndSaveServer() {
  const origin = normalizeServerUrl(serverUrlInput.value);
  const url = new URL(origin);
  const originPattern = `${url.protocol}//${url.hostname}/*`;

  // Request permission directly from the button click, before any await.
  const granted = await chrome.permissions.request({
    origins: [originPattern]
  });

  if (!granted) {
    throw new Error('Chrome permission for the server was denied.');
  }

  await chrome.storage.local.set({ server_url: origin });
  return origin;
}

async function saveServer() {
  saveServerButton.disabled = true;

  try {
    await grantAndSaveServer();
    setBackendStatus(translations[language].saved, 'success');
  } catch (error) {
    setBackendStatus(error.message, 'error');
  } finally {
    saveServerButton.disabled = false;
  }
}

// 9. Ask background.js to check the FastAPI /health endpoint.
async function checkConnection() {
  checkServerButton.disabled = true;

  try {
    await grantAndSaveServer();

    const response = await chrome.runtime.sendMessage({
      type: 'WP2_CHECK_CONNECTION'
    });

    if (!response?.ok) {
      throw new Error(response?.error || 'No backend response received.');
    }

    if (response.data?.status !== 'ok') {
      throw new Error('Unexpected /health response.');
    }

    setBackendStatus(translations[language].connected, 'success');

  } catch (error) {
    setBackendStatus(error.message, 'error');
  } finally {
    checkServerButton.disabled = false;
  }
}

// 10. Render the returned risk score and bilingual summary without unsafe HTML.
function renderBackendResult() {
  resultPanel.replaceChildren();

  if (!lastResult) {
    resultPanel.hidden = true;
    return;
  }

  resultPanel.hidden = false;
  const t = translations[language];

  const heading = document.createElement('h2');
  heading.textContent = t.results;

  const risk = document.createElement('p');
  risk.textContent = `${t.risk}: ${lastResult.risk_score ?? '—'}/100`;

  const summary = document.createElement('p');
  summary.textContent = `${t.summary}: ${
    lastResult['summary_' + language] || lastResult.summary || '—'
  }`;

  resultPanel.append(heading, risk, summary);
}

// 11. Send extracted or manually pasted legal text using background.js.
async function sendTextToServer() {
  const text = termsInput.value.trim();

  if (text.length < 50) {
    setBackendStatus(translations[language].empty, 'error');
    return;
  }

  sendTextButton.disabled = true;
  setBackendStatus(translations[language].sending);

  try {
    const response = await chrome.runtime.sendMessage({
      type: 'WP2_ANALYZE',
      payload: {
        page_url: lastPageUrl,
        page_title: lastPageTitle,
        terms_text: text,
        language: language
      }
    });

    if (!response?.ok) {
      throw new Error(response?.error || 'No backend response received.');
    }

    lastResult = response.data;
    renderBackendResult();
    setBackendStatus(translations[language].received, 'success');

  } catch (error) {
    setBackendStatus(error.message, 'error');
  } finally {
    sendTextButton.disabled = false;
  }
}

// 12. Connect buttons and restore saved user settings.
englishButton.addEventListener('click', () => setLanguage('en'));
arabicButton.addEventListener('click', () => setLanguage('ar'));
analyzeButton.addEventListener('click', analyzeCurrentPage);
saveServerButton.addEventListener('click', saveServer);
checkServerButton.addEventListener('click', checkConnection);
sendTextButton.addEventListener('click', sendTextToServer);

chrome.storage.local.get({
  language: 'en',
  server_url: DEFAULT_SERVER_URL
})
  .then(saved => {
    serverUrlInput.value = saved.server_url;
    setLanguage(saved.language);
  })
  .catch(() => {
    serverUrlInput.value = DEFAULT_SERVER_URL;
    setLanguage('en');
  });
