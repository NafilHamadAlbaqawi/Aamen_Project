/* Code overview: We use this script to collect visible legal text from a page, rather than asking the popup to read the whole browser tab. */

/*
WP1 — Terms & Conditions Extraction

Purpose:
1. Identify Terms & Conditions and Privacy Policy pages.
2. Extract relevant legal text.
3. Discover legal links from website homepages.
4. Return structured information to Aamen.
*/

(() => {
  // Block 1: Define legal keywords and unwanted webpage elements.
  const legalWords = /terms(?:\s+(?:and|&)\s+conditions)?|conditions\s+of\s+use|terms\s+of\s+service|user\s+agreement|privacy\s+policy|سياسة\s+الخصوصية|الشروط\s+والأحكام|شروط\s+الاستخدام|اتفاقية\s+المستخدم|الأحكام\s+والشروط/i;
  const contentWords = /agreement|legal|policy|privacy|terms|conditions|الشروط|الأحكام|الخصوصية|سياسة|اتفاقية/i;
  const excludedSelectors = 'script, style, noscript, nav, header, footer, aside, form, svg, iframe, [hidden], [aria-hidden="true"], [role="navigation"], [role="banner"], [role="contentinfo"], .cookie-banner, .cookie-consent, .popup, .modal, .advertisement, .ads';

  // Block 2: Identify the current webpage.
  const pageUrl = location.href;
  const pageTitle = document.title || '';
  const pageHeading = [...document.querySelectorAll('h1')].map(element => element.innerText || '').join(' ');
  const isLegalPage = legalWords.test([location.pathname, pageTitle, pageHeading].join(' '));

  // Block 3: Discover and normalize legal-document links.
  const legalLinks = [...document.querySelectorAll('a[href]')]
    .filter(element => legalWords.test([element.innerText, element.getAttribute('href')].join(' ')))
    .map(element => {
      try {
        const url = new URL(element.getAttribute('href'), pageUrl);
        return url.protocol === 'http:' || url.protocol === 'https:' ? url.href : null;
      } catch {
        return null;
      }
    })
    .filter(Boolean)
    .filter((url, index, all) => all.indexOf(url) === index)
    .slice(0, 8);

  // Block 4: Extract and clean the text without changing the website.
  function extractText(element) {
    if (!element || !element.getClientRects().length) return '';

    const copy = element.cloneNode(true);
    copy.querySelectorAll(excludedSelectors).forEach(node => node.remove());

    return (copy.innerText || copy.textContent || '')
      .replace(/\u00a0/g, ' ')
      .replace(/[ \t]+/g, ' ')
      .replace(/\n[ \t]+/g, '\n')
      .replace(/\n{3,}/g, '\n\n')
      .trim();
  }

  // Block 5: Define possible locations for legal-document text.
  const dedicatedSelectors = [
    '[id*="terms" i]', '[class*="terms" i]',
    '[id*="privacy-policy" i]', '[class*="privacy-policy" i]',
    '[id*="agreement" i]', '[class*="agreement" i]',
    '[itemprop="articleBody"]'
  ];

  const documentSelectors = [
    'main',
    'article',
    '[role="main"]',
    '.entry-content',
    '.post-content'
  ];

  let cleanedText = '';
  let selectedSource = '';

  // Block 6: Prefer dedicated legal-document sections.
  for (const selector of dedicatedSelectors) {
    for (const element of document.querySelectorAll(selector)) {
      const pageText = extractText(element);

      if (pageText.length >= 350 && pageText.length > cleanedText.length &&
          (isLegalPage || contentWords.test(pageText.slice(0, 600)))) {
        cleanedText = pageText;
        selectedSource = 'legal_section';
      }
    }
  }

  // Block 7: Search general content sections on recognized legal pages.
  if (!cleanedText && isLegalPage) {
    for (const selector of documentSelectors) {
      for (const element of document.querySelectorAll(selector)) {
        const pageText = extractText(element);

        if (pageText.length >= 350 && pageText.length > cleanedText.length) {
          cleanedText = pageText;
          selectedSource = 'legal_page';
        }
      }
    }
  }

  // Block 8: Use the body as a final fallback on legal pages.
  if (!cleanedText && isLegalPage) {
    const pageText = extractText(document.body);

    if (pageText.length >= 350) {
      cleanedText = pageText;
      selectedSource = 'legal_page_body';
    }
  }

  // Block 9: Return results using Aamen's existing field names.
  return {
    page_url: pageUrl,
    page_title: pageTitle,
    terms_text: cleanedText.slice(0, 120000),
    needs_manual_paste: cleanedText.length < 350,
    legal_links: legalLinks,
    extraction_source: selectedSource || 'none'
  };
})();
