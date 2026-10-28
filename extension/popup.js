
/* Aamen WP1: extraction-only popup, without backend analysis. */

// 1. Connect JavaScript to existing popup.html elements.
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

// 2. Define English and Arabic interface text.
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
    found: 'legal document(s) extracted', failed: 'Some links could not be retrieved'
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
    found: 'مستندات قانونية تم استخراجها', failed: 'تعذر جلب بعض الروابط'
  }
};

let language = 'en';
let lastLinks = [];
const termsWords = /terms|conditions|agreement|tos|eula|الشروط|الأحكام|اتفاقية|الاستخدام/i;
const privacyWords = /privacy|personal.data|data.protection|الخصوصية|حماية.البيانات/i;

// 3. Update interface language and keep the header buttons in their order.
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
  if (!lastLinks.length && !termsInput.value) statusBox.textContent = t.ready;
  renderLinks(lastLinks);
  chrome.storage.local.set({ language }).catch(() => {});
}

// 4. Classify URLs as Terms, Privacy Policy, or another legal link.
function classifyLink(text) {
  if (privacyWords.test(text)) return 'privacy';
  if (termsWords.test(text)) return 'terms';
  return 'other';
}

// 5. Render discovered links without inserting untrusted HTML.
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

// 6. Restrict automatic downloads to public HTML on the current origin.
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

// 7. Fetch a legal HTML page only after asking for Chrome site access.
async function fetchLegalText(url) {
  const site = new URL(url);
  const originPattern = `${site.protocol}//${site.hostname}/*`;
  const allowed = await chrome.permissions.contains({ origins: [originPattern] }) ||
    await chrome.permissions.request({ origins: [originPattern] });
  if (!allowed) throw new Error('Site permission denied');
  const response = await fetch(url, {
    credentials: 'omit', redirect: 'error', signal: AbortSignal.timeout(15000)
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
  return (main?.textContent || '').replace(/\u00a0/g, ' ').replace(/[ \t]+/g, ' ')
    .replace(/\n[ \t]+/g, '\n').replace(/\n{3,}/g, '\n\n').trim().slice(0, 55000);
}

// 8. Run the extractor, discover linked documents, and display their contents.
async function analyzeCurrentPage() {
  analyzeButton.disabled = true;
  statusBox.textContent = translations[language].working;
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab?.id || !/^https?:\/\//.test(tab.url || '')) {
      throw new Error('Open an HTTP or HTTPS website first');
    }
    const injected = await chrome.scripting.executeScript({
      target: { tabId: tab.id }, files: ['content.js']
    });
    const extracted = injected?.[0]?.result;
    if (!extracted) throw new Error('Could not extract the webpage');
    pageTitle.textContent = extracted.page_title || tab.url;
    lastLinks = [...new Set((extracted.legal_links || [])
      .filter(url => /^https?:\/\//i.test(url)))];
    renderLinks(lastLinks);

    const documents = [];
    const warnings = [];
    const pageKind = classifyLink(new URL(tab.url).pathname + ' ' + (extracted.page_title || ''));
    if (pageKind !== 'other' && !extracted.needs_manual_paste && extracted.terms_text) {
      documents.push({ kind: pageKind, url: tab.url, text: extracted.terms_text.slice(0, 55000) });
    }
    for (const kind of ['terms', 'privacy']) {
      if (documents.some(doc => doc.kind === kind)) continue;
      const url = lastLinks.find(link => isSameOrigin(link, tab.url) && classifyLink(link) === kind);
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

// 9. Connect buttons and restore the saved language preference.
englishButton.addEventListener('click', () => setLanguage('en'));
arabicButton.addEventListener('click', () => setLanguage('ar'));
analyzeButton.addEventListener('click', analyzeCurrentPage);
chrome.storage.local.get({ language: 'en' })
  .then(saved => setLanguage(saved.language))
  .catch(() => setLanguage('en'));
