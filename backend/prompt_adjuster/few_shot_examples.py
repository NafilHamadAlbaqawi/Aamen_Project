"""WP4 fictional few-shot examples; they are NEVER evidence from a user's document.

WP9: the examples now show the expected tone (plain facts, no hedging) and include a protective, low clause,
because the model copies the style of the example.
"""

EXTRACTION_EXAMPLE = (
    "FICTIONAL EXAMPLE (not from the user's document):\n"
    'Source: By using the app you agree to these terms. We may share your email with our advertising '
    'partners. You can delete your account at any time.\n'
    'Expected JSON: {"clauses":[{"category":"third_party_sharing",'
    '"source_excerpt":"We may share your email with our advertising partners."},'
    '{"category":"account_termination","source_excerpt":"You can delete your account at any time."}]}\n'
    "Do not repeat this example excerpt unless it literally appears in the current input."
)

CLASSIFICATION_EXAMPLE = (
    "FICTIONAL EXAMPLE (illustrative only, not a mandatory rating):\n"
    'Input: [{"clause_number":1,"category":"third_party_sharing",'
    '"source_excerpt":"We may share your email with our advertising partners."},'
    '{"clause_number":2,"category":"account_termination",'
    '"source_excerpt":"You can delete your account at any time."}]\n'
    'Expected JSON: {"clauses":[{"clause_number":1,"severity":"medium",'
    '"explanation_en":"Your email can be given to advertising partners, who can send you promotions.",'
    '"explanation_ar":"يمكن إعطاء بريدك الإلكتروني لشركاء الإعلان لإرسال العروض إليك."},'
    '{"clause_number":2,"severity":"low",'
    '"explanation_en":"You can delete your account whenever you want, which protects you.",'
    '"explanation_ar":"يمكنك حذف حسابك متى شئت، وهذا في صالحك."}]}\n'
    "Determine real severity from the submitted clause context, never from this example alone."
)

SUMMARY_EXAMPLE = (
    "FICTIONAL EXAMPLE (not from the user's document):\n"
    'Findings: [{"category":"third_party_sharing","severity":"medium",'
    '"source_excerpt":"We may share your email with our advertising partners."},'
    '{"category":"account_termination","severity":"low",'
    '"source_excerpt":"You can delete your account at any time."}]\n'
    'Expected JSON: {"summary_en":"Your email can be shared with advertising partners for promotions. '
    'You can delete your account at any time.",'
    '"summary_ar":"يمكن مشاركة بريدك الإلكتروني مع شركاء الإعلان لإرسال العروض. ويمكنك حذف حسابك في أي وقت."}\n'
    "Do not introduce claims unsupported by the current submitted findings."
)
