# WP9 — Issues Log (testing, evaluation and debugging)

**Project:** Aamen (آمن) · **Work package:** WP9 · **Responsible:** Abdullah Alasker  
**Branch:** feature/wp9-testing · **Date:** 2026-11-10  
Test results: [`WP9-testing.md`](WP9-testing.md) · Raw results: `tests/wp9_eval/results/` · Logs: [`wp9_logs/`](wp9_logs/)

## Issues found in WP9

| ID | Issue | Found in | Severity | Status | Owner |
|---|---|---|---|---|---|
| W9-01 | Standard and protective clauses rated too severe (22.4% of ratings) | TC01 | High | Fixed (0.8%) | WP4 |
| W9-02 | Benign documents rated Moderate (Safe 1/4) | TC01 | High | Fixed (Safe 8/8) | WP4 |
| W9-03 | PDPL "needs context" used by default (42.4%) | TC01 | Medium | Fixed (15.7%; accuracy 69.6% → 86.7%) | WP5 |
| W9-04 | Hedged, general explanations (24.0%); the few-shot example itself was hedged | TC01 | Medium | Fixed (8.8%) | WP4 |
| W9-05 | Some real risks rated too low (financial data to lenders, indefinite retention) | TC01 | Medium | Mostly fixed; credit-bureau clause still borderline (high in 1 of 2 final runs) | WP4 |
| W9-06 | Extraction picked boilerplate and skipped content licences and second sentences of a section | TC01 | Medium | Fixed (licences 4/4 in the probe run) | WP4 |
| W9-07 | Quotes with an added full stop or capital letter were dropped by the exact-match check | TC02 diagnosis | Medium | Fixed | WP3 |
| W9-08 | Clauses crossing a line break in the page source were dropped (5 of 11 kept on a real page) | TC06 browser regression | High | Fixed (11 of 11; 12 clauses in the browser) | WP3 |
| W9-09 | Invalid PDPL citations rejected the whole PDPL answer (3 of 10 in v6) | TC02 | Medium | Fixed for most cases; 1 of 20 final runs still without PDPL | WP5 + WP3 |
| W9-10 | Pop-up showed a normal partial PDPL result as a warning and listed every clause as a "Warning" | Review of TC01 results | Medium | Fixed | WP7 |
| W9-11 | Summary and PDPL ran one after the other although they are independent | TC05 | Medium | Fixed (mean 16.0 s → 11.0 s) | WP3 |
| W9-12 | The LLM judge did not detect over-caution on its own | TC04 | Low | Noted (gold labels are the main measure) | WP9 |
| W9-13 | Evaluation text was cleaner than the extension's real page text, which hid W9-08 | TC06 | Low | Mitigated (unit test + browser regression) | WP9 |

## Details

### W9-01 / W9-02 — Over-severe ratings and benign documents rated Moderate
- **Symptom:** "We email you at least 14 days before material changes" and "not liable for loss … outside our reasonable control" were rated *medium*, and the legally required ID check in PayNest was rated *high*. Three privacy-friendly documents were rated Moderate (scores 50–54).
- **Cause:** The classification prompt had no severity scale, so the model rated by how sensitive the topic sounds (location, banking, health), not by what the clause does. With the existing formula, one medium clause is enough to make a document Moderate.
- **Fix:** A two-sided rubric with examples for low, medium and high, plus the rule that "over-rating a normal clause is as wrong as under-rating a harmful one". The rating formula was not changed: on the gold severities it gives the expected level for all 10 documents (`test_02`).
- **Evidence:** TC02 table; `WP9-before/after-privacy-policy.png` (Moderate 49 → Safe 86), `WP9-before/after-fitness-policy.png`.

### W9-03 — PDPL "needs context" by default
- **Symptom:** 25 of 59 baseline findings were "needs context", including "we do not store full card numbers" and the Arabic "ولا نبيع بياناتك".
- **Cause:** The WP5 instructions said "Use needs_context whenever the limited summaries, exceptions, legal basis, or actual practices are unclear" and asked for "cautious" explanations.
- **Fix:** The assessment is decided by the clause's own wording: *potential concern* when the wording conflicts with a supplied principle; *no concern identified* when it is consistent (including protective clauses); *needs context* only when the answer depends on a fact the clause cannot show. WP5's validation (only verified references, no invented articles) is unchanged.

### W9-04 — Hedged, general explanations
- **Symptom:** "Collecting precise GPS location can affect user privacy" (for location used only so the rider can find you). The WP4 few-shot example said "may reduce privacy", and the model copies the example's style.
- **Fix:** One plain, factual sentence about what the clause lets the company do; no *may/could/potentially* unless the clause itself is conditional; no general advice. New few-shot examples in that tone, including a protective low clause.

### W9-05 — Borderline under-rating
- **Symptom:** Before WP9, "Your banking details may be shared with our lending partners" was rated *medium*. In the final run, "share transaction data with credit bureaus … to assess eligibility for credit offers" was *high* in one run and *medium* in the other, so WP4-DOC-C was Moderate once.
- **Status:** Open (run-to-run variance on a borderline clause). The rubric names this case as high. Running the classification twice and keeping the more severe rating would remove it, at the cost of one extra model call.

### W9-06 — Extraction choices
- **Symptom:** The perpetual photo licence (Rihla, Lamha) and "Any wallet balance on a closed account may be forfeited" were missed, while "By creating an account … you agree to these Terms" was returned.
- **Fix:** Extraction now asks for clauses with a practical effect, says to return both sentences when a section has two different effects, never to return the general acceptance sentence, and that content licences always count (category *other*). Probe: 4 of 4 runs extracted both licences and rated them *high*.

### W9-07 / W9-08 — Real clauses silently dropped by the verbatim check
- **Symptom:** The model quoted "We collect your location only with permission**.**" where the source continues ", and …", and quoted sentences with a space where the page source has a line break ("collect your⏎location"). WP3 drops any quote that is not an exact substring, so on the real Rihla page only 5 of the 11 returned clauses were kept. This has been the case since WP3, and it also limited the WP8 browser runs to 6–8 clauses.
- **Fix:** `locate_excerpt()` in `backend/analysis/clause_extractor.py` also accepts the quote without surrounding quotes or trailing punctuation, in any letter case, and with any whitespace between the same words. It always stores the span **as written in the source**, so excerpts stay 100% verbatim, and invented text is still rejected.
- **Evidence:** `tests/test_wp9_fixes.py` (7 tests), TC07, `wp9_logs/e2e_regression_results.json` (12 clauses, 10 PDPL references).

### W9-09 — Rejected PDPL answers
- **Symptom:** After the new PDPL instructions, some answers cited a reference supplied for a different clause. WP5 correctly rejects the whole answer, so the user got no PDPL section (v6: 3 of 10).
- **Fix:** The instructions now say references must come from the clause's own list (v6p: 0 of 10), and `screen_pdpl()` in the pipeline retries once when WP5 rejects an answer. Service errors are not retried.
- **Remaining:** In the final run, 2 of 21 PDPL attempts were rejected, and both were on the same document, so 1 of 20 runs had no PDPL result. Three fresh attempts on that same input were all valid. The user sees the analysis with "The legal (PDPL) check is incomplete".
- **Recommendation (WP5):** Instead of rejecting the whole answer, drop only the invalid citation, and drop the finding only if no valid reference is left. This would change WP5's validation rule and two of its tests, so it is left to the WP5 owner.

### W9-10 — Alarm added by the pop-up
- **Symptom:** On almost every real page the pop-up showed an amber "The legal (PDPL) check is incomplete" because the result was *partial* (liability and fee clauses have no PDPL article). The clause list was titled "Warnings" and counted protective clauses too.
- **Fix:** A neutral note explains that some clauses are not about personal data; the warning is kept for a failed check. The list is now "Key clauses" / "أهم البنود"; the High/Medium/Low tiles still show what needs attention.

### W9-11 — Analysis time
- **Fix:** The summary and the PDPL screening both need only the classified clauses, so they run in parallel. The mean time per fresh analysis went from 16.0 s to 11.0 s; a summary failure still fails the analysis, and a PDPL failure still does not (`test_wp9_fixes.py`).

### W9-12 — Judge leniency
- The judge rated 9 of 10 baseline analyses "acceptable", including the three benign documents that the system had rated Moderate. Its calibration score moved only from 4.2 to 4.4, while gold-label accuracy moved from 70% to 95%. A same-family LLM judge is a useful second opinion but not enough on its own.

### W9-13 — Clean evaluation text
- `corpus.py` joins the HTML text into clean paragraphs, but the extension keeps the source's line breaks. That is why W9-08 appeared in the browser and not in the evaluation. It is now covered by a unit test and by the browser regression, which should be part of every future evaluation.

## Status of earlier open issues

| ID | Issue | Status after WP9 |
|---|---|---|
| I-04 (WP4) | Classifier omitted clauses → 502 | Not seen in 54 evaluation analyses or the browser runs |
| I-06 (WP4) | Overstated claims from short excerpts | Judge: 0 unsupported claims in the final run; excerpts keep their conditions |
| I-07 (WP4) | Analysis time vs "a few seconds" | Partly open: 11.0 s mean for a fresh analysis (was 16.0 s); 0.1 s for a repeat (cache) |
| I-08 (WP4) | Rating sensitive to one clause | Addressed by accurate severities (W9-01); formula unchanged |
| I-13 (WP4) | Summaries longer than the sentence limit | Open: 10 of 20 final summaries have 5–7 sentences. A stricter prompt was tested on the same 20 results and made no difference, so a code or UI limit is recommended |
| I-02, I-03 (WP4) | `/health` key check; `analysis_mode` always "openai" | Open (WP3), not changed in WP9 |
| W8-10 (WP8) | Language in the cache key | Open (WP6/WP3) |
| W8-12 (WP8) | First analysis 9–21 s | See I-07 |
