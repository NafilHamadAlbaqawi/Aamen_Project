/* Code overview: All the standard interface labels are kept here in English and Arabic. The new WP10 labels are grouped with the WP10 interface code. */
/* English and Arabic text for the Aamen popup. Text that only the extension needs is added in popup.js. */
(function () {
  'use strict';
  const STRINGS = {
      en: {
        appName: 'Aamen', tagline: 'Terms & privacy checker',
        tabSummary: 'Summary', tabPrefs: 'Preferences',
        safetyRating: 'Safety rating', outOf: '/ 100',
        levelSafe: 'Safe', levelModerate: 'Moderate', levelHigh: 'High risk',
        levelSafeNote: 'No major concerns found.',
        levelModerateNote: 'Some clauses need your attention.',
        levelHighNote: 'Several serious concerns found.',
        summaryTitle: 'Summary', warningsTitle: 'Key clauses',
        warningCount: '{n} clauses', viewDetails: 'View Details',
        back: 'Back', report: 'Full report', issueOf: 'Issue {i} of {n}',
        prev: 'Previous', next: 'Next', close: 'Close',
        sevHigh: 'High', sevMedium: 'Medium', sevLow: 'Low',
        whatItSays: 'What the document says', whyFlagged: 'Why it was flagged',
        legalRefs: 'Saudi PDPL references', noRefs: 'No legal reference was matched for this clause.',
        openSource: 'Open official source', assessment: 'Assessment',
        aConcern: 'Potential concern', aContext: 'Needs context', aNone: 'No concern identified',
        yourPref: 'Your preference', accepted: 'You accept this', notAccepted: 'You don’t accept this',
        acceptedBadge: 'Accepted by you', countedLower: 'Counted one level lower in your rating.',
        countedFull: 'Counted at full weight in your rating.',
        prefsTitle: 'What do you accept?',
        prefsIntro: 'Switch on what you are comfortable with. Accepted topics count less against the rating. Topics you don’t accept count fully.',
        accept: 'Accept', dontAccept: 'Don’t accept',
        prefAccepted: 'Accepted', prefNotAccepted: 'Not accepted',
        impactLower: 'Accepting lowers risk by {n}', impactRaise: 'Not accepting raises risk by {n}',
        impactNone: 'No clause in this document is affected',
        baseline: 'Standard rating', personalized: 'Your rating', changedBy: 'Your choices changed the rating by {n} points',
        unchanged: 'Your choices haven’t changed the rating yet',
        resetPrefs: 'Don’t accept anything', acceptAll: 'Accept everything',
        pLocation: 'Location', pLocationD: 'Where you are, including background tracking',
        pPhotos: 'Photos', pPhotosD: 'Your photos and how the service may use them',
        pBanking: 'Banking details', pBankingD: 'Cards, accounts and payment information',
        pThirdParty: 'Third-party sharing', pThirdPartyD: 'Your data passed to advertisers and partners',
        tabPaste: 'Paste / PDF', pasteTitle: 'Paste the text yourself',
        pasteIntro: 'Use this when Aamen can’t read a site automatically. Copy the terms or privacy policy, paste it here and analyze it.',
        pastePlaceholder: 'Paste the terms or privacy policy here…',
        pasteCount: '{n} / {max} characters', pasteLimit: 'Needs {min} to {max} characters.',
        pasteMin: 'Add at least {min} characters before analyzing.',
        pasteMax: 'This is over the {max}-character limit. Paste a shorter part of the document.',
        pasteAnalyze: 'Analyze pasted text', pasteClear: 'Clear',
        pasteTip: 'Tip: on the terms page press Ctrl+A to select all, Ctrl+C to copy, then paste here with Ctrl+V.',
        analyzedPage: 'Analyzed page', disclaimer: 'AI-generated screening, not a legal compliance determination.',
        warnTruncated: 'The document was long, so only the first part was analyzed.',
        warnPdpl: 'The legal (PDPL) check is incomplete. Some clauses have no legal reference.',
        loadingTitle: 'Reading the terms…', loadingBody: 'This can take up to a minute for long documents.',
        emptyTitle: 'No analysis yet', emptyBody: 'Open a site’s terms or privacy page, then analyze it.',
        analyze: 'Analyze this page', retry: 'Try again',
        errorLabel: 'Error',
        clausesHigh: 'High', clausesMedium: 'Medium', clausesLow: 'Low',
        demoState: 'Preview state', demoNote: 'Preview controls (not part of the extension)',
        sState_result: 'Result', sState_loading: 'Loading', sState_empty: 'Empty',
        sState_server_unreachable: 'Error: server unreachable', sState_permission: 'Error: no permission',
        sState_ai_not_configured: 'Error: AI not configured', sState_ai_unavailable: 'Error: AI unavailable',
        sState_too_short: 'Error: text too short', sState_not_web: 'Error: not a website', sState_no_text: 'Error: no legal text',
        cat_data_collection: 'Data collection', cat_third_party_sharing: 'Third-party sharing',
        cat_data_retention: 'Data retention', cat_consent: 'Consent', cat_account_termination: 'Account termination',
        cat_terms_changes: 'Changes to terms', cat_liability: 'Liability', cat_sensitive_data: 'Sensitive data', cat_other: 'Other'
      },
      ar: {
        appName: 'آمن', tagline: 'فاحص الشروط والخصوصية',
        tabSummary: 'الملخص', tabPrefs: 'التفضيلات',
        safetyRating: 'تقييم الأمان', outOf: '/ ١٠٠',
        levelSafe: 'آمن', levelModerate: 'متوسط', levelHigh: 'خطر مرتفع',
        levelSafeNote: 'لم نجد مخاوف كبيرة.',
        levelModerateNote: 'بعض البنود تحتاج إلى انتباهك.',
        levelHighNote: 'وجدنا عدة مخاوف خطيرة.',
        summaryTitle: 'الملخص', warningsTitle: 'أهم البنود',
        warningCount: 'عدد البنود: {n}', viewDetails: 'عرض التفاصيل',
        back: 'رجوع', report: 'التقرير الكامل', issueOf: 'الملاحظة {i} من {n}',
        prev: 'السابق', next: 'التالي', close: 'إغلاق',
        sevHigh: 'عالية', sevMedium: 'متوسطة', sevLow: 'منخفضة',
        whatItSays: 'ما تنص عليه الوثيقة', whyFlagged: 'سبب التنبيه',
        legalRefs: 'مراجع نظام حماية البيانات الشخصية', noRefs: 'لم يتم مطابقة مرجع قانوني لهذا البند.',
        openSource: 'فتح المصدر الرسمي', assessment: 'التقييم',
        aConcern: 'مخاوف محتملة', aContext: 'يحتاج إلى سياق', aNone: 'لا توجد مخاوف',
        yourPref: 'تفضيلك', accepted: 'أنت تقبل هذا', notAccepted: 'أنت لا تقبل هذا',
        acceptedBadge: 'مقبول منك', countedLower: 'يُستحسب بمستوى أقل في تقييمك.',
        countedFull: 'يُستحسب بوزنه الكامل في تقييمك.',
        prefsTitle: 'ماذا تقبل؟',
        prefsIntro: 'فعّل ما تشعر بالراحة تجاهه. المواضيع المقبولة تؤثر أقل في التقييم، وما لا تقبله يُستحسب بالكامل.',
        accept: 'أقبل', dontAccept: 'لا أقبل',
        prefAccepted: 'مقبول', prefNotAccepted: 'غير مقبول',
        impactLower: 'القبول يخفض الخطر بـ {n}', impactRaise: 'عدم القبول يرفع الخطر بـ {n}',
        impactNone: 'لا يوجد بند في هذه الوثيقة يتأثر',
        baseline: 'التقييم القياسي', personalized: 'تقييمك', changedBy: 'غيّرت اختياراتك التقييم بمقدار {n} نقطة',
        unchanged: 'لم تغيّر اختياراتك التقييم بعد',
        resetPrefs: 'لا أقبل أي شيء', acceptAll: 'أقبل كل شيء',
        pLocation: 'الموقع', pLocationD: 'مكانك، بما في ذلك التتبع في الخلفية',
        pPhotos: 'الصور', pPhotosD: 'صورك وكيف قد تستخدمها الخدمة',
        pBanking: 'البيانات المصرفية', pBankingD: 'البطاقات والحسابات ومعلومات الدفع',
        pThirdParty: 'مشاركة الطرف الثالث', pThirdPartyD: 'تمرير بياناتك إلى المعلنين والشركاء',
        tabPaste: 'لصق / PDF', pasteTitle: 'الصق النص بنفسك',
        pasteIntro: 'استخدم هذا عندما لا يستطيع آمن قراءة الموقع تلقائيًا. انسخ الشروط أو سياسة الخصوصية، والصقها هنا ثم حلّلها.',
        pastePlaceholder: 'الصق الشروط أو سياسة الخصوصية هنا…',
        pasteCount: '{n} / {max} حرف', pasteLimit: 'يلزم من {min} إلى {max} حرف.',
        pasteMin: 'أضف {min} حرفًا على الأقل قبل التحليل.',
        pasteMax: 'النص يتجاوز حد {max} حرف. الصق جزءًا أقصر من الوثيقة.',
        pasteAnalyze: 'حلّل النص الملصوق', pasteClear: 'مسح',
        pasteTip: 'نصيحة: في صفحة الشروط اضغط Ctrl+A لتحديد الكل، ثم Ctrl+C للنسخ، ثم Ctrl+V للصق هنا.',
        analyzedPage: 'الصفحة المحللة', disclaimer: 'فحص آلي بالذكاء الاصطناعي، وليس حكمًا قانونيًا بالامتثال.',
        warnTruncated: 'الوثيقة طويلة، لذا تم تحليل جزئها الأول فقط.',
        warnPdpl: 'فحص نظام حماية البيانات غير مكتمل، وبعض البنود بلا مرجع قانوني.',
        loadingTitle: 'جارٍ قراءة الشروط…', loadingBody: 'قد يستغرق الأمر حتى دقيقة للوثائق الطويلة.',
        emptyTitle: 'لا يوجد تحليل بعد', emptyBody: 'افتح صفحة الشروط أو الخصوصية في الموقع ثم حلّلها.',
        analyze: 'حلّل هذه الصفحة', retry: 'أعد المحاولة',
        errorLabel: 'خطأ',
        clausesHigh: 'عالية', clausesMedium: 'متوسطة', clausesLow: 'منخفضة',
        demoState: 'حالة المعاينة', demoNote: 'أدوات المعاينة (ليست جزءًا من الإضافة)',
        sState_result: 'نتيجة', sState_loading: 'تحميل', sState_empty: 'فارغ',
        sState_server_unreachable: 'خطأ: الخادم غير متاح', sState_permission: 'خطأ: لا إذن',
        sState_ai_not_configured: 'خطأ: الذكاء غير معد', sState_ai_unavailable: 'خطأ: الذكاء غير متاح',
        sState_too_short: 'خطأ: نص قصير', sState_not_web: 'خطأ: ليس موقعًا', sState_no_text: 'خطأ: لا نص قانوني',
        cat_data_collection: 'جمع البيانات', cat_third_party_sharing: 'مشاركة الطرف الثالث',
        cat_data_retention: 'الاحتفاظ بالبيانات', cat_consent: 'الموافقة', cat_account_termination: 'إنهاء الحساب',
        cat_terms_changes: 'تغيير الشروط', cat_liability: 'المسؤولية', cat_sensitive_data: 'بيانات حساسة', cat_other: 'أخرى'
      }
    };
  const ERRORS = {
      server_unreachable: {
        en: ['Can’t reach the server', 'Cannot reach the Aamen server. Make sure the backend is running and the address in Server Settings is correct.'],
        ar: ['تعذّر الوصول إلى الخادم', 'تعذّر الاتصال بخادم آمن. تأكد من تشغيل الخادم وصحة العنوان في إعدادات الخادم.']
      },
      permission: {
        en: ['Server access not allowed', 'Chrome hasn’t been given permission to contact this server. Open Server Settings and allow access.'],
        ar: ['لم يُسمح بالوصول إلى الخادم', 'لم يُمنح المتصفح إذن الاتصال بهذا الخادم. افتح إعدادات الخادم واسمح بالوصول.']
      },
      ai_not_configured: {
        en: ['Analysis isn’t set up yet', 'AI analysis is not configured on this server. Ask the server administrator to add the API key.'],
        ar: ['التحليل غير مفعّل بعد', 'لم يتم إعداد التحليل بالذكاء الاصطناعي على هذا الخادم. اطلب من مسؤول الخادم إضافة المفتاح.']
      },
      ai_unavailable: {
        en: ['Analysis service unavailable', 'The AI service is unavailable or rejected the request. Try again in a moment.'],
        ar: ['خدمة التحليل غير متاحة', 'خدمة الذكاء الاصطناعي غير متاحة أو رفضت الطلب. حاول مرة أخرى بعد قليل.']
      },
      too_short: {
        en: ['Not enough text', 'Legal text must be between 50 and 120,000 characters. Paste the full terms and try again.'],
        ar: ['النص غير كافٍ', 'يجب أن يتراوح النص القانوني بين 50 و120,000 حرف. الصق الشروط كاملة وحاول مرة أخرى.']
      },
      not_web: {
        en: ['Open a website first', 'Aamen can only read http or https pages. Open the site’s terms page and try again.'],
        ar: ['افتح موقعًا أولًا', 'يمكن لآمن قراءة صفحات http وhttps فقط. افتح صفحة شروط الموقع وحاول مرة أخرى.']
      },
      no_text: {
        en: ['No legal text found', 'We couldn’t find terms or a privacy policy on this page. You can paste the text manually.'],
        ar: ['لم يُعثر على نص قانوني', 'لم نعثر على شروط أو سياسة خصوصية في هذه الصفحة. يمكنك لصق النص يدوياً.']
      }
    };
  window.AAMEN_TEXT = { STRINGS: STRINGS, ERRORS: ERRORS };
})();
