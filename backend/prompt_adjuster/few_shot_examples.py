"""WP4 fictional few-shot examples; they are NEVER evidence from a user's document."""

EXTRACTION_EXAMPLE = (
    "FICTIONAL EXAMPLE (not from the user's document):\n"
    'Source: We may share your email with our advertising partners.\n'
    'Expected JSON: {"clauses":[{"category":"third_party_sharing",'
    '"source_excerpt":"We may share your email with our advertising partners."}]}\n'
    "Do not repeat this example excerpt unless it literally appears in the current input."
)

CLASSIFICATION_EXAMPLE = (
    "FICTIONAL EXAMPLE (illustrative risk, not a mandatory rating):\n"
    'Input: [{"clause_number":1,"category":"third_party_sharing",'
    '"source_excerpt":"We may share your email with our advertising partners."}]\n'
    'Expected JSON: {"clauses":[{"clause_number":1,"severity":"medium",'
    '"explanation_en":"Email sharing with advertising partners may reduce privacy.",'
    '"explanation_ar":"قد تقل الخصوصية عند مشاركة البريد الإلكتروني مع شركاء الإعلان."}]}\n'
    "Determine real severity from the submitted clause context, never from this example alone."
)

SUMMARY_EXAMPLE = (
    "FICTIONAL EXAMPLE (not from the user's document):\n"
    'Finding: {"category":"third_party_sharing","severity":"medium",'
    '"source_excerpt":"We may share your email with our advertising partners."}\n'
    'Expected JSON: {"summary_en":"The terms allow email sharing with advertising partners.",'
    '"summary_ar":"تسمح الشروط بمشاركة البريد الإلكتروني مع شركاء الإعلان."}\n'
    "Do not introduce claims unsupported by the current submitted findings."
)
