
/*
WP1 — Terms & Conditions Extraction
Detects legal documents and extracts relevant text.
Also discovers Terms & Conditions and Privacy Policy links.
*/

(() => {
  // 1. Define legal keywords and excluded webpage elements.
  const legalWords = /terms(?:\s+(?:and|&)\s+conditions)?|conditions\s+of\s+use|terms\s+of\s+service|user\s+agreement|privacy\s+policy|سياسة\s+الخصوصية|الشروط\s+والأحكام|شروط\s+الاستخدام|اتفاقية\s+المستخدم|الأحكام\s+والشروط/i;
  const contentWords = /agreement|legal|policy|privacy|terms|conditions|الشروط|الأحكام|الخصوصية|سياسة|اتفاقية/i;
  const excludedSelectors = 'script, style, noscript, nav, header, footer, aside, form, svg, iframe, [hidden], [aria-hidden="true"], [role="navigation"], [role="banner"], [role="contentinfo"], .cookie-banner, .cookie-consent, .popup, .modal, .advertisement, .ads';

  // 2. Identify the current webpage.
  const pageUrl = location.href;
  const pageTitle = document.title || '';
  const pageHeading = [...document.querySelectorAll('h1')].map(element => element.innerText || '').join(' ');
  const isLegalPage = legalWords.test([location.pathname, pageTitle, pageHeading].join(' '));

  // 3. Discover links to legal documents.
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

  // 4. Extract readable text while excluding unnecessary elements.
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

  // 5. Define legal sections and general document containers.
  const dedicatedSelectors = [
    '[id*="terms" i]', '[class*="terms" i]',
    '[id*="privacy-policy" i]', '[class*="privacy-policy" i]',
    '[id*="agreement" i]', '[class*="agreement" i]',
    '[itemprop="articleBody"]'
  ];

  const documentSelectors = ['main', 'article', '[role="main"]', '.entry-content', '.post-content'];

  let cleanedText = '';
  let selectedSource = '';

  // 6. Prefer dedicated legal-document sections.
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

  // 7. Search the main content only when the page appears to be legal.
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

  // 8. Fall back to the body of a recognized legal page.
  if (!cleanedText && isLegalPage) {
    const pageText = extractText(document.body);

    if (pageText.length >= 350) {
      cleanedText = pageText;
      selectedSource = 'legal_page_body';
    }
  }

  // 9. Return data using the existing Aamen response structure.
  return {
    page_url: pageUrl,
    page_title: pageTitle,
    terms_text: cleanedText.slice(0, 120000),
    needs_manual_paste: cleanedText.length < 350,
    legal_links: legalLinks,
    extraction_source: selectedSource || 'none'
  };
})();
