/*
Aamen popup.

popup.html is an empty <div id="app">. This file builds everything inside it.
All the data the screen depends on sits in one object (st). You change it only
through set(), which updates st and redraws the whole popup.

It talks to background.js with two messages, same as the old popup:
  WP2_CHECK_CONNECTION   checks the backend /health
  WP2_ANALYZE            sends legal text to POST /analyze
Reading the page (content.js and the same-site legal links) is the old WP1 code, moved over as it was.
English and Arabic text is in ui-strings.js.
*/
(function () {
  'use strict';

  const { STRINGS, ERRORS } = window.AAMEN_TEXT;
  const DEFAULT_SERVER_URL = 'http://127.0.0.1:8000';
  const PASTE_MIN = 50, PASTE_MAX = 120000;   // same limits as backend/main.py

  // Extra text that ui-strings.js doesn't have: server settings, loading steps, a couple of errors.
  Object.assign(STRINGS.en, {
    settingsLink: 'Server settings', settingsTitle: 'Server settings', serverLabel: 'Server address',
    serverSave: 'Save server', serverCheck: 'Check connection',
    serverHelp: 'Chrome asks for permission the first time you use a new address.',
    serverIdle: 'Not checked yet.', serverSaved: 'Server saved and access allowed.',
    serverOk: 'Connected to the Aamen server.', serverChecking: 'Checking the server…',
    serverDenied: 'Chrome did not allow access to that address.',
    stageReading: 'Reading the page…', stageSending: 'Analyzing the terms…',
    analyzeAgain: 'Analyze again', refLocator: 'Locator',
    openSettings: 'Open server settings', openPaste: 'Paste text instead', pastedText: 'Pasted text',
    emptyBody: 'Open a site’s terms or privacy page, then press the button.',
    noDetails: 'No details are available for this result.'
  });
  Object.assign(STRINGS.ar, {
    settingsLink: 'إعدادات الخادم', settingsTitle: 'إعدادات الخادم', serverLabel: 'عنوان الخادم',
    serverSave: 'حفظ الخادم', serverCheck: 'اختبار الاتصال',
    serverHelp: 'يطلب المتصفح إذنًا في أول مرة تستخدم فيها عنوانًا جديدًا.',
    serverIdle: 'لم يتم الاختبار بعد.', serverSaved: 'تم حفظ الخادم والسماح بالوصول إليه.',
    serverOk: 'تم الاتصال بخادم آمن.', serverChecking: 'جارٍ اختبار الخادم…',
    serverDenied: 'لم يسمح المتصفح بالوصول إلى هذا العنوان.',
    stageReading: 'جارٍ قراءة الصفحة…', stageSending: 'جارٍ تحليل الشروط…',
    analyzeAgain: 'حلّل مرة أخرى', refLocator: 'موضع الإشارة',
    openSettings: 'افتح إعدادات الخادم', openPaste: 'الصق النص بدلًا من ذلك', pastedText: 'نص ملصوق',
    emptyBody: 'افتح صفحة الشروط أو الخصوصية في الموقع ثم اضغط الزر.',
    noDetails: 'لا توجد تفاصيل متاحة لهذه النتيجة.'
  });
  ERRORS.no_clauses = {
    en: ['No clear clauses found', 'The AI could not find terms or privacy clauses in this text. Try the full terms page, or paste the text.'],
    ar: ['لم يتم العثور على بنود واضحة', 'لم يتمكن الذكاء الاصطناعي من إيجاد بنود شروط أو خصوصية في هذا النص. جرّب صفحة الشروط كاملة أو الصق النص.']
  };
  ERRORS.unknown = { en: ['Something went wrong', ''], ar: ['حدث خطأ ما', ''] };
  ERRORS.offline = {
    en: ['No internet connection', 'Your browser is offline. Check your connection and try again.'],
    ar: ['لا يوجد اتصال بالإنترنت', 'المتصفح غير متصل بالإنترنت. تحقق من اتصالك ثم حاول مرة أخرى.']
  };
  ERRORS.bad_result = {
    en: ['Could not read the result', 'The server sent back something the popup could not read. Try again, or ask whoever runs the server to check it.'],
    ar: ['تعذّرت قراءة النتيجة', 'أرسل الخادم نتيجة تعذّرت قراءتها. حاول مرة أخرى، أو اطلب من مسؤول الخادم التحقق منها.']
  };

  // The four things a user can accept or refuse. These are the same four the backend has for preferences.
  const TOPICS = [
    { id: 'location', label: 'pLocation', desc: 'pLocationD' },
    { id: 'photos', label: 'pPhotos', desc: 'pPhotosD' },
    { id: 'banking_information', label: 'pBanking', desc: 'pBankingD' },
    { id: 'third_party_sharing', label: 'pThirdParty', desc: 'pThirdPartyD' }
  ];
  // Everything "not accepted". The starting point, and what the reset button goes back to.
  const NONE = { location: false, photos: false, banking_information: false, third_party_sharing: false };

  // The state. tab is summary, prefs or paste. view is main, report or settings.
  // openId is the warning that is open in the list, if any.
  const st = {
    lang: 'en', tab: 'summary', view: 'main', openId: null,
    scenario: 'empty',          // empty | loading | result | error
    stage: 'stageReading', errorId: null, errorDetail: '',
    result: null, source: null, lastAction: 'page',
    accepted: Object.assign({}, NONE),
    pasteText: '', pasteError: null,
    serverUrl: DEFAULT_SERVER_URL, serverInput: DEFAULT_SERVER_URL, serverMsg: null
  };
  // Counts analysis runs. If the user starts a new one while an old one is still waiting, the old answer gets thrown away.
  let runToken = 0;

  // Save the language and the accepted topics so they are still there next time the popup opens.
  function persist() {
    chrome.storage.local.set({ language: st.lang, accepted_topics: st.accepted }).catch(() => {});
  }

  // The only way to change state. Merges the changes into st, saves if the language or choices changed, then redraws.
  function set(patch) {
    const saveNeeded = 'lang' in patch || 'accepted' in patch;
    Object.assign(st, patch);
    if (saveNeeded) persist();
    document.documentElement.lang = st.lang;
    document.documentElement.dir = st.lang === 'ar' ? 'rtl' : 'ltr';
    draw();
    watchFocus();
  }

  // t('key') returns the text in the current language. Anything like {n} in the text is filled in from vars.
  const t = (key, vars) => {
    let text = (STRINGS[st.lang] || STRINGS.en)[key];
    if (text === undefined) text = STRINGS.en[key] === undefined ? key : STRINGS.en[key];
    if (vars) Object.keys(vars).forEach(name => { text = text.replace('{' + name + '}', vars[name]); });
    return text;
  };
  // The backend sends both languages (summary_en, summary_ar). pick(obj, 'summary') takes the one we need.
  const pick = (obj, field) => obj[field + '_' + st.lang] || obj[field + '_en'] || '';
  // In Arabic, show digits as ٠١٢٣ instead of 0123.
  const num = value => st.lang === 'ar' ? String(value).replace(/\d/g, d => '٠١٢٣٤٥٦٧٨٩'[d]) : String(value);
  // Thousands separator for the paste counter, like 120,000.
  const group = n => String(n).replace(/\B(?=(\d{3})+(?!\d))/g, st.lang === 'ar' ? '٬' : ',');
  // The backend calls the level "Safe", "Moderate" or "High Risk". These turn it into a css name, a label and a one line note.
  const levelId = level => level === 'Safe' ? 'safe' : level === 'Moderate' ? 'moderate' : 'high';
  const levelText = level => t('level' + (level === 'Safe' ? 'Safe' : level === 'Moderate' ? 'Moderate' : 'High'));
  const levelNote = level => t('level' + (level === 'Safe' ? 'Safe' : level === 'Moderate' ? 'Moderate' : 'High') + 'Note');
  // Labels for a severity, a clause category and a topic.
  const severityText = sev => t('sev' + sev[0].toUpperCase() + sev.slice(1));
  const categoryText = category => t('cat_' + category);
  const topicLabel = id => t(TOPICS.find(x => x.id === id).label);

  // Makes one element: h('div', { class: 'x', onclick: fn }, child, 'text').
  // Text always goes in as a text node, never as HTML, so nothing from a web page or the AI can inject markup.
  function h(tag, props, ...kids) {
    const el = document.createElement(tag);
    Object.keys(props || {}).forEach(name => {
      const value = props[name];
      if (value === false || value === null || value === undefined) return;
      if (name.startsWith('on')) el.addEventListener(name.slice(2), value);
      else if (name === 'class') el.className = value;
      else el.setAttribute(name, value === true ? '' : value);
    });
    const add = kid => {
      if (Array.isArray(kid)) kid.forEach(add);
      else if (kid !== null && kid !== undefined && kid !== false) el.append(kid.nodeType ? kid : document.createTextNode(kid));
    };
    kids.forEach(add);
    return el;
  }

  // An accepted topic lowers a clause by one level: high becomes medium, medium becomes low.
  const DOWN = { high: 'medium', medium: 'low', low: 'low' };

  // Risk score from a list of severities. Same formula as backend/analysis/rating.py, so if that file changes this one has to change too.
  // Start at 67 if there is any high, else 34 if any medium. Add 12 per extra high, 7 per extra medium, 2 per low.
  // 67 and up is High Risk, 34 and up is Moderate, below that is Safe.
  function backendRating(severities) {
    const high = severities.filter(s => s === 'high').length;
    const medium = severities.filter(s => s === 'medium').length;
    const low = severities.filter(s => s === 'low').length;
    const baseline = high ? 67 : medium ? 34 : 0;
    const bonus = Math.max(0, high - 1) * 12 + Math.max(0, medium - 1) * 7 + low * 2;
    const score = Math.min(100, baseline + bonus);
    return { score, level: score >= 67 ? 'High Risk' : score >= 34 ? 'Moderate' : 'Safe' };
  }

  // The backend doesn't say which preference a clause is about, so we guess from the words in it. English and Arabic.
  const TOPIC_WORDS = {
    location: /\b(location|gps|geolocation|whereabouts)\b|الموقع|موقع|المكان/i,
    photos: /\b(photos?|pictures?|images?|camera)\b|الصور|صورة|صور|كاميرا/i,
    banking_information: /\b(bank|banking|payment|credit|debit|card|financial|iban)\b|بنك|مصرف|مصرفي|الدفع|بطاقة|بطاقات|مالية|مالي/i,
    third_party_sharing: /third[- ]part|advertis|affiliate|partners|الطرف الثالث|أطراف ثالثة|المعلنين|شركاء/i
  };
  // Which of the four topics a clause is about. A third_party_sharing clause always counts for that topic.
  function topicsFor(clause) {
    // Only look at the excerpt, which is copied from the document. The AI's explanation can use a word like
    // "location" loosely, and that gave us a wrong match once.
    const text = clause.source_excerpt;
    const found = TOPICS.map(x => x.id).filter(id => TOPIC_WORDS[id].test(text));
    if (clause.category === 'third_party_sharing' && !found.includes('third_party_sharing')) found.push('third_party_sharing');
    return found;
  }

  // The numbers the user sees. Rates the clauses twice: as the backend gave them (standard), and again with the
  // user's accepted topics applied (mine). safety is 100 minus risk, so higher is better. delta is how much the choices helped.
  function calculateRating(result, accepted) {
    const items = result.flagged_clauses.map(clause => {
      const topics = topicsFor(clause);
      const isAccepted = topics.some(id => accepted[id]);
      return { clause, topics, accepted: isAccepted, effective: isAccepted ? DOWN[clause.severity] : clause.severity };
    });
    const standard = backendRating(items.map(i => i.clause.severity));
    const mine = backendRating(items.map(i => i.effective));
    // How many warnings of each severity, after the user's choices. They are the three tiles under the gauge.
    const counts = { high: 0, medium: 0, low: 0 };
    items.forEach(i => { counts[i.effective] += 1; });
    return {
      items, counts, level: mine.level, safety: 100 - mine.score, standardSafety: 100 - standard.score,
      delta: standard.score - mine.score
    };
  }
  // Shortcut: the current result with the current choices.
  const rating = () => calculateRating(st.result, st.accepted);

  // How many risk points would change if this one switch were flipped. Negative means safer.
  // It is the hint under each preference.
  function topicImpact(topicId) {
    const now = backendRating(calculateRating(st.result, st.accepted).items.map(i => i.effective)).score;
    const flipped = calculateRating(st.result, Object.assign({}, st.accepted, { [topicId]: !st.accepted[topicId] }));
    return backendRating(flipped.items.map(i => i.effective)).score - now;
  }

  // Worst first, then by clause id so the list doesn't shuffle.
  const SEVERITY_ORDER = { high: 0, medium: 1, low: 2 };
  const sortedItems = r => r.items.slice().sort((a, b) =>
    SEVERITY_ORDER[a.effective] - SEVERITY_ORDER[b.effective] || a.clause.clause_id.localeCompare(b.clause.clause_id));
  // The PDPL check result for one clause, or null if it has none. assessmentText turns the result into a label.
  const pdplFinding = id => ((st.result.pdpl && st.result.pdpl.findings) || []).find(f => f.clause_id === id) || null;
  const assessmentText = v => v === 'potential_concern' ? t('aConcern') : v === 'needs_context' ? t('aContext') : t('aNone');

  // background.js gives errors back as plain English sentences. This reads the sentence and picks one of our
  // error screens, so the same error can also be shown in Arabic. If nothing matches it is 'unknown'.
  function errorIdFor(message) {
    const m = String(message || '');
    if (/Cannot reach the FastAPI server/i.test(m)) return 'server_unreachable';
    if (/permission missing|server origin|Server URL/i.test(m)) return 'permission';
    if (/not configured/i.test(m)) return 'ai_not_configured';
    if (/source-grounded/i.test(m)) return 'no_clauses';
    if (/between 50 and 120000|at least 50/i.test(m)) return 'too_short';
    if (/HTTP or HTTPS|Cannot access|extensions gallery/i.test(m)) return 'not_web';
    if (/AI service|rejected|Unexpected analysis|Backend returned HTTP 5/i.test(m)) return 'ai_unavailable';
    if (/Could not extract|No legal text/i.test(m)) return 'no_text';
    return 'unknown';
  }

  // Is this something the popup can show? It needs a list of clauses, and every clause needs a severity we know.
  // Anything else would break the screens, so it is treated as an error instead.
  function isUsableResult(data) {
    return !!data && Array.isArray(data.flagged_clauses) &&
      data.flagged_clauses.every(c => c && ['high', 'medium', 'low'].includes(c.severity));
  }

  // The browser says it has no network at all. It can't tell us about a router with no internet, only about no network.
  const isOffline = () => navigator.onLine === false;

  // Show the error screen for a message and drop any old result. id is optional, for when we already know which error it is.
  // If the browser is offline, a failure that was probably caused by that is shown as "no internet" instead.
  function fail(message, id) {
    let errorId = id || errorIdFor(message);
    if (isOffline() && ['server_unreachable', 'ai_unavailable', 'no_text', 'unknown'].includes(errorId)) errorId = 'offline';
    set({ scenario: 'error', errorId, errorDetail: String(message || ''), tab: 'summary', view: 'main', result: null });
  }

  // Sends the text to the backend through background.js, then shows the result or an error.
  // source says where the text came from (a page or pasted text). action is 'page' or 'paste' so retry knows what to repeat.
  async function sendText(text, source, action) {
    if (isOffline()) { st.lastAction = action; fail('No internet connection', 'offline'); return; }
    const token = ++runToken;
    set({ scenario: 'loading', stage: 'stageSending', tab: 'summary', view: 'main', result: null, openId: null, source, lastAction: action });
    try {
      const response = await chrome.runtime.sendMessage({
        type: 'WP2_ANALYZE',
        payload: { page_url: source.url, page_title: source.title, terms_text: text, language: st.lang }
      });
      if (token !== runToken) return;
      if (!response || !response.ok) throw new Error((response && response.error) || 'No response from the extension.');
      if (!isUsableResult(response.data)) throw new Error('The result could not be read.', { cause: 'bad_result' });
      set({ scenario: 'result', result: response.data, errorId: null });
    } catch (error) {
      if (token === runToken) fail(error.message, error.cause === 'bad_result' ? 'bad_result' : undefined);
    }
  }

  // Reading the current page. This part is the old WP1 code from the first popup.
  const termsWords = /terms|conditions|agreement|tos|eula|الشروط|الأحكام|اتفاقية|الاستخدام/i;
  const privacyWords = /privacy|personal.data|data.protection|الخصوصية|حماية.البيانات/i;
  // Is a link or title about privacy, about terms, or neither.
  const classifyLink = text => privacyWords.test(text) ? 'privacy' : termsWords.test(text) ? 'terms' : 'other';
  const DOC_LABEL = { terms: 'Terms & Conditions', privacy: 'Privacy Policy', other: 'Legal document' };

  // Only follow links on the same website, and skip files like PDF or Word.
  function isSameOrigin(url, currentUrl) {
    try {
      const candidate = new URL(url);
      const current = new URL(currentUrl);
      return ['http:', 'https:'].includes(candidate.protocol) && candidate.origin === current.origin &&
        !candidate.username && !candidate.password && !/\.(pdf|docx?|zip|png|jpe?g)$/i.test(candidate.pathname);
    } catch (e) {
      return false;
    }
  }

  // Downloads a terms or privacy page from the same site and returns just its text (up to 55,000 characters).
  // Asks Chrome for permission to that site first, refuses redirects, and gives up on pages over 1 MB.
  async function fetchLegalText(url) {
    const site = new URL(url);
    const originPattern = `${site.protocol}//${site.hostname}/*`;
    const allowed = await chrome.permissions.contains({ origins: [originPattern] }) ||
      await chrome.permissions.request({ origins: [originPattern] });
    if (!allowed) throw new Error('Site permission denied');

    const response = await fetch(url, { credentials: 'omit', redirect: 'error', signal: AbortSignal.timeout(15000) });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    if (!/text\/html|application\/xhtml\+xml/i.test(response.headers.get('content-type') || '')) throw new Error('Link is not an HTML page');
    if (!response.body) throw new Error('Empty response');

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let html = '';
    let byteCount = 0;
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      byteCount += value.byteLength;
      if (byteCount > 1000000) { await reader.cancel(); throw new Error('Legal document is too large'); }
      html += decoder.decode(value, { stream: true });
    }
    html += decoder.decode();
    const parsed = new DOMParser().parseFromString(html, 'text/html');
    parsed.querySelectorAll('script,style,noscript,nav,header,footer,aside,form,svg,iframe,[hidden],[aria-hidden="true"]').forEach(el => el.remove());
    parsed.querySelectorAll('p,li,h1,h2,h3,h4').forEach(el => el.append('\n'));
    const main = parsed.querySelector('main,article,[role="main"],.entry-content,.post-content') || parsed.body;
    return (main && main.textContent || '')
      .replace(/ /g, ' ').replace(/[ \t]+/g, ' ').replace(/\n[ \t]+/g, '\n').replace(/\n{3,}/g, '\n\n')
      .trim().slice(0, 55000);
  }

  // The Analyze this page button. Runs content.js on the open tab. If that page isn't the legal text itself,
  // it downloads the site's terms and privacy pages instead. Then everything goes to sendText().
  async function analyzePage() {
    if (isOffline()) { st.lastAction = 'page'; fail('No internet connection', 'offline'); return; }
    const token = ++runToken;
    set({ scenario: 'loading', stage: 'stageReading', tab: 'summary', view: 'main', result: null, openId: null, lastAction: 'page' });
    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!tab || !tab.id || !/^https?:\/\//.test(tab.url || '')) throw new Error('Open an HTTP or HTTPS website first');

      const injected = await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ['content.js'] });
      const extracted = injected && injected[0] && injected[0].result;
      if (!extracted) throw new Error('Could not extract the webpage');

      const links = [...new Set((extracted.legal_links || []).filter(url => /^https?:\/\//i.test(url)))];
      const documents = [];
      const pageKind = classifyLink(new URL(tab.url).pathname + ' ' + (extracted.page_title || ''));
      if (pageKind !== 'other' && !extracted.needs_manual_paste && extracted.terms_text) {
        documents.push({ kind: pageKind, url: tab.url, text: extracted.terms_text.slice(0, 55000) });
      }
      for (const kind of ['terms', 'privacy']) {
        if (documents.some(doc => doc.kind === kind)) continue;
        const url = links.find(link => isSameOrigin(link, tab.url) && classifyLink(link) === kind);
        if (!url) continue;
        try {
          const text = await fetchLegalText(url);
          if (text.length < 350) throw new Error('Not enough legal text found');
          documents.push({ kind, url, text });
        } catch (error) { /* this link could not be read, but the other one may still work */ }
      }
      if (token !== runToken) return;
      if (!documents.length) throw new Error('No legal text found');

      const text = documents.map(doc => `${DOC_LABEL[doc.kind]}\nSource: ${doc.url}\n\n${doc.text}`)
        .join('\n\n----------------------------------------\n\n').slice(0, PASTE_MAX);
      await sendText(text, { kind: 'page', url: tab.url, title: extracted.page_title || tab.url }, 'page');
    } catch (error) {
      if (token === runToken) fail(error.message);
    }
  }

  // Try again and Analyze again. Pasted text is sent again, anything else reads the page again.
  function retry() {
    if (st.lastAction === 'paste' && st.pasteText.trim().length >= PASTE_MIN) {
      sendText(st.pasteText.trim(), { kind: 'paste', url: '', title: t('pastedText') }, 'paste');
    } else {
      analyzePage();
    }
  }

  // Accepts only an address like http://host:port with nothing after the port. Returns it cleaned up, or throws.
  function normalizeServerUrl(value) {
    let url;
    try { url = new URL(String(value).trim()); } catch (e) { throw new Error('Enter a valid address, for example http://192.168.1.5:8000'); }
    if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.pathname !== '/' || url.search || url.hash) {
      throw new Error('Enter only the server address, for example http://192.168.1.5:8000');
    }
    return url.origin;
  }

  // Asks Chrome for permission to reach the server, then saves the address. Chrome only shows the permission
  // prompt if this runs straight from a click, so don't put an await in front of it.
  function grantAndSave() {
    const origin = normalizeServerUrl(st.serverInput);
    const url = new URL(origin);
    return chrome.permissions.request({ origins: [`${url.protocol}//${url.hostname}/*`] }).then(async granted => {
      if (!granted) throw new Error(t('serverDenied'));
      await chrome.storage.local.set({ server_url: origin });
      st.serverUrl = origin;
      st.serverInput = origin;
      return origin;
    });
  }

  // The Save server button.
  function saveServer() {
    let pending;
    try { pending = grantAndSave(); } catch (error) { set({ serverMsg: { text: error.message, state: 'error' } }); return; }
    pending.then(() => set({ serverMsg: { key: 'serverSaved', state: 'success' } }))
      .catch(error => set({ serverMsg: { text: error.message, state: 'error' } }));
  }

  // The Check connection button. Saves the address as well, then asks background.js to call /health.
  function checkServer() {
    let pending;
    try { pending = grantAndSave(); } catch (error) { set({ serverMsg: { text: error.message, state: 'error' } }); return; }
    set({ serverMsg: { key: 'serverChecking', state: '' } });
    pending.then(() => chrome.runtime.sendMessage({ type: 'WP2_CHECK_CONNECTION' })).then(response => {
      if (!response || !response.ok) throw new Error((response && response.error) || 'No response from the extension.');
      if (!response.data || response.data.status !== 'ok') throw new Error('Unexpected /health response.');
      set({ serverMsg: { key: 'serverOk', state: 'success' } });
    }).catch(error => set({ serverMsg: { text: error.message, state: 'error' } }));
  }

  // The screens below each return the DOM for one part of the popup.

  // Go to another page or open the sheet. openerKey is the button that was pressed, so focus can go back to it when we close.
  let lastOpener = null;
  function open(view, openerKey, extra) {
    lastOpener = openerKey || null;
    set(Object.assign({ view }, extra));
  }
  // Close the sheet, or go back to the main page.
  const close = () => set({ view: 'main' });

  // The small High / Medium / Low tag. Its colour comes from the data-sev of the tag itself.
  const chip = sev => h('span', { class: 'chip', 'data-sev': sev }, severityText(sev));

  // Notices above the result: the text was cut because it was long, or the PDPL check didn't finish.
  function notices() {
    const r = st.result, out = [];
    const make = text => h('div', { class: 'notice', role: 'note' }, h('span', null, text));
    if (r.input_truncated) out.push(make(t('warnTruncated')));
    if (!r.pdpl || r.pdpl.status !== 'completed') out.push(make(t('warnPdpl')));
    return out;
  }

  // The PDPL part of a warning: the assessment, the explanation and the articles it points to.
  // ref.excerpt is only a short locator from the backend, not the article text, so it is labelled as a locator.
  function refs(clause) {
    const finding = pdplFinding(clause.clause_id);
    if (!finding) return h('p', { class: 'ref-none' }, t('noRefs'));
    return h('div', null,
      h('span', { class: 'assess' }, t('assessment') + ': ' + assessmentText(finding.assessment)),
      h('p', null, pick(finding, 'explanation')),
      (finding.legal_references || []).map(ref => h('div', { class: 'ref' },
        h('b', null, ref.title + ', ' + ref.article_id),
        ref.excerpt && h('p', { dir: 'auto' }, t('refLocator') + ': ' + ref.excerpt),
        h('a', { href: ref.source_url, target: '_blank', rel: 'noopener noreferrer' }, t('openSource')))));
  }

  // Don't accept / Accept buttons for one topic. scope goes in front of the focus key. The same topic can be on
  // screen twice at once (in an open warning and in the report), and focus is found again by that key after a redraw.
  function seg(topicId, scope) {
    const on = !!st.accepted[topicId];
    const button = (value, label, pressed) => h('button', {
      type: 'button', 'data-v': value, 'aria-pressed': String(pressed), 'data-focus-key': scope + 'seg-' + topicId + '-' + value,
      onclick: () => set({ accepted: Object.assign({}, st.accepted, { [topicId]: value === 'yes' }) })
    }, label);
    return h('div', { class: 'seg', role: 'group', 'aria-label': topicLabel(topicId) },
      button('no', t('dontAccept'), !on), button('yes', t('accept'), on));
  }

  // The inside of one warning: what the document says, why it was flagged, the user's preference, the legal references.
  function detail(item, scope) {
    const c = item.clause;
    return [
      h('div', { class: 'field' }, h('h3', null, t('whatItSays')), h('blockquote', { dir: 'auto' }, c.source_excerpt)),
      h('div', { class: 'field' }, h('h3', null, t('whyFlagged')), h('p', null, pick(c, 'explanation'))),
      item.topics.length > 0 && h('div', { class: 'field' }, h('h3', null, t('yourPref')),
        item.topics.map(id => h('div', { class: 'pref-inline' },
          h('p', null, topicLabel(id) + ': ' + (st.accepted[id] ? t('countedLower') : t('countedFull'))), seg(id, scope)))),
      h('div', { class: 'field' }, h('h3', null, t('legalRefs')), refs(c))
    ];
  }

  // One warning in the list. Tapping it opens the details right under it, tapping again closes them.
  function accordion(item) {
    const c = item.clause, isOpen = st.openId === c.clause_id;
    return h('div', { class: 'acc', 'data-open': String(isOpen), 'data-sev': item.effective },
      h('button', {
        type: 'button', class: 'acc-h', 'aria-expanded': String(isOpen), 'aria-controls': 'p-' + c.clause_id, 'data-focus-key': 'acc-' + c.clause_id,
        onclick: () => set({ openId: isOpen ? null : c.clause_id })
      },
        h('span', { class: 'dot' }),
        h('span', { class: 'name' }, categoryText(c.category), item.accepted && h('span', { class: 'tag-ok' }, t('acceptedBadge'))),
        chip(item.effective)),
      isOpen && h('div', { class: 'acc-b', id: 'p-' + c.clause_id }, detail(item, 'a-')));
  }

  // Back button and title at the top of a page.
  function subbar(title) {
    return h('div', { class: 'subbar' },
      h('button', { type: 'button', class: 'back', 'data-focus-key': 'back', onclick: close }, t('back')), h('h2', null, title));
  }

  // The half circle with the score. Two arcs on top of each other: a grey one, and a coloured one cut short to the score.
  // Built with createElementNS and numbers only, so nothing from outside ends up inside the svg.
  function gauge(r) {
    const NS = 'http://www.w3.org/2000/svg', length = Math.PI * 90;
    const arc = name => {
      const path = document.createElementNS(NS, 'path');
      path.setAttribute('class', name);
      path.setAttribute('d', 'M20 110 A90 90 0 0 1 200 110');
      return path;
    };
    const svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('viewBox', '0 0 220 120');
    svg.setAttribute('aria-hidden', 'true');
    const value = arc('val');
    value.setAttribute('stroke-dasharray', length.toFixed(1));
    value.setAttribute('stroke-dashoffset', (length * (1 - r.safety / 100)).toFixed(1));
    svg.append(arc('trk'), value);
    return h('div', { class: 'gauge', role: 'img', 'aria-label': t('safetyRating') + ': ' + num(r.safety) + ' ' + t('outOf') + ', ' + levelText(r.level) },
      svg, h('div', { class: 'gauge-num' }, h('b', null, num(r.safety)), h('small', null, t('outOf'))));
  }

  // Summary tab when there is a result. Top to bottom: the page name, the gauge, the count of each severity,
  // notices, the summary with View Details, then the list of warnings. Clicking the summary also opens the report.
  function summaryResult() {
    const r = rating();
    const items = sortedItems(r);
    const subject = st.source ? st.source.title : '';
    return h('div', { class: 'stack' },
      subject && h('p', { class: 'page', dir: 'auto' }, t('analyzedPage') + ': ' + subject),
      h('section', { class: 'card gauge-card', 'data-level': levelId(r.level) },
        gauge(r),
        h('div', { class: 'gauge-label' }, t('safetyRating')),
        h('span', { class: 'level' }, levelText(r.level)),
        h('p', { class: 'gauge-note' }, levelNote(r.level)),
        r.delta !== 0 && h('p', { class: 'delta' }, t('changedBy', { n: num(Math.abs(r.delta)) }))),
      h('div', { class: 'tiles' }, ['high', 'medium', 'low'].map(sev =>
        h('div', { class: 'tile', 'data-sev': sev }, h('b', null, num(r.counts[sev])), h('span', null, severityText(sev))))),
      notices(),
      h('section', { class: 'card summary', onclick: () => open('report', 'view-details') },
        h('h2', null, t('summaryTitle')),
        h('p', null, pick(st.result, 'summary')),
        h('button', { type: 'button', class: 'btn primary', 'data-focus-key': 'view-details', onclick: e => { e.stopPropagation(); open('report', 'view-details'); } }, t('viewDetails'))),
      h('div', { class: 'list-head' }, h('h2', null, t('warningsTitle')), h('span', null, t('warningCount', { n: num(items.length) }))),
      items.length === 0 ? h('p', { class: 'msg' }, t('noDetails')) : h('div', { class: 'accs' }, items.map(accordion)),
      h('button', { type: 'button', class: 'btn ghost', 'data-focus-key': 'again', onclick: retry }, t('analyzeAgain')));
  }

  // Summary tab when there is no result: the start screen, the loading screen, or an error.
  // Each error gets its own extra button (server settings, or paste text) where that helps.
  function statePanel() {
    if (st.scenario === 'loading') {
      return h('section', { class: 'card panel', role: 'status' }, h('div', { class: 'spinner' }), h('h2', null, t(st.stage)), h('p', null, t('loadingBody')));
    }
    if (st.scenario === 'empty') {
      return h('section', { class: 'card panel' }, h('h2', null, t('emptyTitle')), h('p', null, t('emptyBody')),
        h('button', { type: 'button', class: 'btn primary', 'data-focus-key': 'analyze', onclick: analyzePage }, t('analyze')),
        h('button', { type: 'button', class: 'foot-link', 'data-focus-key': 'to-paste', onclick: () => set({ tab: 'paste', view: 'main' }) }, t('openPaste')));
    }
    const message = ERRORS[st.errorId] ? ERRORS[st.errorId][st.lang] : ERRORS.unknown[st.lang];
    const body = st.errorId === 'unknown' ? st.errorDetail : message[1];
    const extra = [];
    if (st.errorId === 'permission' || st.errorId === 'server_unreachable') {
      extra.push(h('button', { type: 'button', class: 'btn ghost', 'data-focus-key': 'to-settings', onclick: () => open('settings', 'to-settings') }, t('openSettings')));
    }
    if (st.errorId === 'no_text' || st.errorId === 'too_short' || st.errorId === 'no_clauses') {
      extra.push(h('button', { type: 'button', class: 'btn ghost', 'data-focus-key': 'to-paste', onclick: () => set({ tab: 'paste', view: 'main' }) }, t('openPaste')));
    }
    return h('section', { class: 'card panel error', role: 'alert' },
      h('span', { class: 'err-tag' }, t('errorLabel')), h('h2', null, message[0]), body && h('p', null, body),
      h('button', { type: 'button', class: 'btn primary', 'data-focus-key': 'retry', onclick: retry }, t('retry')), extra);
  }

  // Preferences tab. A live card with the score and a bar showing where it was (the ring) and where it is now (the line),
  // then one card per topic with Don't accept / Accept and a hint of how many points it moves. The score card only
  // shows once there is a result.
  function prefsTab() {
    const hasResult = st.scenario === 'result' && st.result;
    const r = hasResult ? rating() : null;
    return h('div', { class: 'stack' },
      hasResult && h('section', { class: 'card live', 'data-level': levelId(r.level), 'aria-live': 'polite' },
        h('div', { class: 'live-top' }, h('b', null, num(r.safety)), h('span', { class: 'level' }, t('personalized') + ': ' + levelText(r.level))),
        h('div', { class: 'bar', role: 'img', 'aria-label': t('personalized') + ' ' + num(r.safety) + ', ' + t('baseline') + ' ' + num(r.standardSafety) },
          h('span', { class: 'mark old', style: 'inset-inline-start:' + r.standardSafety + '%' }),
          h('span', { class: 'mark', style: 'inset-inline-start:' + r.safety + '%' })),
        h('div', { class: 'bar-legend' }, h('span', null, t('levelHigh')), h('span', null, t('levelModerate')), h('span', null, t('levelSafe'))),
        h('p', { class: 'sub' }, t('baseline') + ': ' + num(r.standardSafety) + ', ' + (r.delta === 0 ? t('unchanged') : t('changedBy', { n: num(Math.abs(r.delta)) })))),
      h('h2', { class: 'prefs-title' }, t('prefsTitle')),
      h('p', { class: 'intro' }, t('prefsIntro')),
      TOPICS.map(topic => {
        const on = !!st.accepted[topic.id];
        const impact = hasResult ? topicImpact(topic.id) : 0;
        const hint = !hasResult ? '' : impact === 0 ? t('impactNone') : impact < 0 ? t('impactLower', { n: num(-impact) }) : t('impactRaise', { n: num(impact) });
        return h('div', { class: 'pcard', 'data-on': String(on) },
          h('div', { class: 'pcard-top' }, h('div', null, h('b', null, t(topic.label)), h('span', null, t(topic.desc)))),
          h('div', { class: 'pcard-foot' }, seg(topic.id, 'p-'), hint && h('span', { class: 'hint ' + (impact === 0 ? 'none' : impact > 0 ? 'up' : '') }, hint)));
      }),
      h('div', { class: 'pair' },
        h('button', { type: 'button', class: 'btn ghost', 'data-focus-key': 'none', onclick: () => set({ accepted: Object.assign({}, NONE) }) }, t('resetPrefs')),
        h('button', { type: 'button', class: 'btn ghost', 'data-focus-key': 'all', onclick: () => set({ accepted: { location: true, photos: true, banking_information: true, third_party_sharing: true } }) }, t('acceptAll'))));
  }

  // Paste tab, for sites the popup can't read by itself. Typing doesn't redraw the page, it only updates
  // st.pasteText. If it did, the cursor would jump out of the box on every key.
  function pasteTab() {
    const field = h('textarea', {
      id: 'paste-input', class: 'paste-input', rows: 6, dir: 'auto', spellcheck: 'false',
      placeholder: t('pastePlaceholder'), 'aria-describedby': 'paste-limit paste-count paste-error', 'data-focus-key': 'paste-input'
    });
    field.value = st.pasteText;
    const count = h('span', { id: 'paste-count', class: 'paste-count' });
    const clear = h('button', { type: 'button', class: 'paste-clear', 'data-focus-key': 'paste-clear' }, t('pasteClear'));
    const error = h('p', { id: 'paste-error', class: 'paste-error', role: 'alert' });

    // Show or hide the error under the box. kind is 'short', 'long' or null.
    const showError = kind => {
      st.pasteError = kind;
      error.hidden = !kind;
      error.textContent = !kind ? '' : kind === 'short' ? t('pasteMin', { min: num(PASTE_MIN) }) : t('pasteMax', { max: num(group(PASTE_MAX)) });
    };
    // Update the character counter, and turn Clear on or off.
    const sync = () => {
      const length = st.pasteText.trim().length;
      count.textContent = t('pasteCount', { n: num(group(length)), max: num(group(PASTE_MAX)) });
      count.setAttribute('data-over', String(length > PASTE_MAX));
      clear.disabled = st.pasteText.length === 0;
    };
    field.addEventListener('input', () => { st.pasteText = field.value; showError(null); sync(); });
    clear.addEventListener('click', () => { field.value = ''; st.pasteText = ''; showError(null); sync(); field.focus(); });
    // Analyze pasted text. Checks the same 50 to 120,000 limit as the backend before sending anything.
    const submit = () => {
      const length = st.pasteText.trim().length;
      if (length < PASTE_MIN || length > PASTE_MAX) {
        showError(length < PASTE_MIN ? 'short' : 'long');
        field.focus();
        error.scrollIntoView({ block: 'nearest' });
        return;
      }
      sendText(st.pasteText.trim(), { kind: 'paste', url: '', title: t('pastedText') }, 'paste');
    };
    showError(st.pasteError);
    sync();

    return h('section', { class: 'paste' },
      h('div', { class: 'paste-head' }, h('h2', null, t('pasteTitle')), h('p', null, t('pasteIntro'))),
      h('label', { class: 'sr-only', for: 'paste-input' }, t('pasteTitle')),
      field,
      h('div', { class: 'paste-meta' }, h('span', { id: 'paste-limit' }, t('pasteLimit', { min: num(PASTE_MIN), max: num(group(PASTE_MAX)) })), count, clear),
      error,
      h('button', { type: 'button', class: 'btn primary paste-go', 'data-focus-key': 'paste-go', onclick: submit }, t('pasteAnalyze')),
      h('p', { class: 'paste-tip' }, t('pasteTip')));
  }

  // Server settings page: the address box, Save, Check connection and the message under them.
  function settingsPage() {
    const input = h('input', {
      id: 'server-url', class: 'text-input', type: 'url', dir: 'ltr', autocomplete: 'off', spellcheck: 'false',
      placeholder: 'http://192.168.1.5:8000', 'data-focus-key': 'server-url'
    });
    input.value = st.serverInput;
    input.addEventListener('input', () => { st.serverInput = input.value; });
    const msg = st.serverMsg;
    return h('div', { class: 'stack' },
      subbar(t('settingsTitle')),
      h('div', { class: 'field' }, h('label', { class: 'label', for: 'server-url' }, t('serverLabel')), input),
      h('div', { class: 'pair' },
        h('button', { type: 'button', class: 'btn primary', 'data-focus-key': 'server-save', onclick: saveServer }, t('serverSave')),
        h('button', { type: 'button', class: 'btn ghost', 'data-focus-key': 'server-check', onclick: checkServer }, t('serverCheck'))),
      h('p', { class: 'msg', role: 'status', 'aria-live': 'polite', 'data-state': msg ? msg.state : '' }, msg ? (msg.key ? t(msg.key) : msg.text) : t('serverIdle')),
      h('p', { class: 'msg' }, t('serverHelp')));
  }

  // The full report, in a sheet that slides up from the bottom: the score, then every warning with its details.
  // The Close button, Esc, or a click on the dark area closes it.
  function sheet() {
    const r = rating();
    const dialog = h('div', { class: 'sheet', role: 'dialog', 'aria-modal': 'true', 'aria-label': t('report') },
      h('div', { class: 'sheet-head' }, h('h2', null, t('report')),
        h('button', { type: 'button', class: 'x', 'aria-label': t('close'), 'data-focus-key': 'close', onclick: close }, t('close'))),
      h('div', { class: 'sheet-body', 'data-scroll': 'sheet' },
        h('div', { class: 'rep gauge-card', 'data-level': levelId(r.level) },
          h('div', { class: 'rep-score' }, h('b', null, num(r.safety)), h('span', { class: 'level' }, levelText(r.level))),
          st.source && h('p', { class: 'page', dir: 'auto' }, st.source.title)),
        notices(),
        r.items.length === 0 ? h('p', { class: 'msg' }, t('noDetails')) : sortedItems(r).map(item => h('section', { class: 'rep', 'data-sev': item.effective },
          h('div', { class: 'rep-head' }, h('b', null, categoryText(item.clause.category)), chip(item.effective)),
          detail(item, 'r-'))),
        h('p', { class: 'disc' }, st.result.disclaimer || t('disclaimer'))));
    dialog.addEventListener('keydown', e => { if (e.key === 'Escape') close(); });
    return h('div', { style: 'display:contents' }, h('div', { class: 'scrim', onclick: close }), dialog);
  }

  // The EN and ع buttons. Switching only redraws. No new request is needed, the backend already sent both languages.
  function langSwitch() {
    const button = (code, label, name) => h('button', {
      type: 'button', class: 'lang-btn', 'aria-pressed': String(st.lang === code), lang: code, 'aria-label': name,
      'data-focus-key': 'lang-' + code, onclick: () => set({ lang: code })
    }, label);
    return h('div', { class: 'lang-switch', role: 'group', 'aria-label': 'Language / اللغة', dir: 'ltr' }, button('en', 'EN', 'English'), button('ar', 'ع', 'العربية'));
  }

  // The whole popup: header, the content of the current tab, footer, bottom tabs, and the report sheet on top if it is open.
  // While the sheet is open the page behind it is inert, so keyboard focus can't wander behind it.
  function frame() {
    const hasSheet = !!(st.tab === 'summary' && st.view === 'report' && st.scenario === 'result' && st.result);
    let content;
    if (st.view === 'settings') content = settingsPage();
    else if (st.tab === 'paste') content = pasteTab();
    else if (st.tab === 'prefs') content = prefsTab();
    else if (st.scenario === 'result' && st.result) content = summaryResult();
    else content = statePanel();

    const navBtn = (id, label) => h('button', {
      type: 'button', role: 'tab', 'aria-selected': String(st.tab === id && st.view !== 'settings'), 'data-focus-key': 'nav-' + id,
      onclick: () => set({ tab: id, view: 'main' })
    }, label);

    return h('div', { style: 'display:contents' },
      h('div', { class: 'g-main', inert: hasSheet },
        h('header', { class: 'top' },
          h('div', { class: 'brand' }, h('h1', null, t('appName')), h('p', null, t('tagline'))),
          langSwitch()),
        h('main', { class: 'body', role: 'tabpanel', 'data-scroll': 'body:' + st.tab + ':' + st.view }, content),
        h('footer', { class: 'foot' },
          h('span', null, t('disclaimer')),
          h('button', { type: 'button', class: 'foot-link', 'data-focus-key': 'settings', onclick: () => open('settings', 'settings') }, t('settingsLink'))),
        h('nav', { class: 'nav', role: 'tablist' }, navBtn('summary', t('tabSummary')), navBtn('prefs', t('tabPrefs')), navBtn('paste', t('tabPaste')))),
      hasSheet && sheet());
  }

  // Redraws the popup from st. Everything is rebuilt each time, so before that it remembers the scroll position
  // and which button had focus, and puts them back afterwards.
  const root = document.getElementById('app');
  function draw() {
    const holder = document.activeElement && document.activeElement.closest ? document.activeElement.closest('[data-focus-key]') : null;
    const key = holder && root.contains(holder) ? holder.getAttribute('data-focus-key') : null;
    const scrolls = {};
    root.querySelectorAll('[data-scroll]').forEach(el => { scrolls[el.getAttribute('data-scroll')] = el.scrollTop; });
    let page;
    try {
      page = frame();
    } catch (error) {
      // The result had a shape the screens can't handle. Show the error screen instead of leaving the popup blank.
      if (st.result) Object.assign(st, { result: null, scenario: 'error', errorId: 'bad_result', errorDetail: '', tab: 'summary', view: 'main' });
      try { page = frame(); } catch (again) { page = h('p', { class: 'msg' }, 'Something went wrong. Close the popup and open it again.'); }
    }
    root.replaceChildren(page);
    root.querySelectorAll('[data-scroll]').forEach(el => {
      const saved = scrolls[el.getAttribute('data-scroll')];
      if (saved !== undefined) el.scrollTop = saved;
    });
    if (key) {
      const again = root.querySelector('[data-focus-key="' + key + '"]');
      if (again) again.focus({ preventScroll: true });
    }
  }

  // Keyboard focus follows the view. Opening a page or the sheet moves focus into it, closing moves it back to the
  // button that opened it. It leaves focus alone if the user clicked something else, like a tab.
  let previousView = st.view;
  const watchFocus = () => {
    if (st.view === previousView) return;
    previousView = st.view;
    const active = document.activeElement;
    const holder = active && active.closest ? active.closest('[data-focus-key]') : null;
    const key = holder ? holder.getAttribute('data-focus-key') : null;
    if (key && key !== 'back' && key !== 'close' && key !== lastOpener) return;
    const target = st.view !== 'main'
      ? root.querySelector('[data-focus-key="back"], [data-focus-key="close"]')
      : lastOpener && root.querySelector('[data-focus-key="' + lastOpener + '"]');
    if (target) target.focus();
  };

  // Start: load the saved language, accepted topics and server address, then draw the popup for the first time.
  chrome.storage.local.get({ language: 'en', accepted_topics: {}, server_url: DEFAULT_SERVER_URL }).then(saved => {
    const accepted = Object.assign({}, NONE);
    TOPICS.forEach(x => { if (typeof saved.accepted_topics[x.id] === 'boolean') accepted[x.id] = saved.accepted_topics[x.id]; });
    set({ lang: saved.language === 'ar' ? 'ar' : 'en', accepted, serverUrl: saved.server_url, serverInput: saved.server_url });
  }).catch(() => set({ lang: 'en' }));
})();
