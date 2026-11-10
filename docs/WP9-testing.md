# WP9 — Testing, Evaluation and Debugging

**Project:** Aamen (آمن)  
**Work Package:** WP9 — Testing, evaluation and debugging (all use cases)  
**Responsible:** Abdullah Alasker  
**Branch:** `feature/wp9-testing` (based on `feature/wp8-integration`, commit `f4ee584`)  
**Date:** 2026-11-10  
**Model:** OpenAI `gpt-4o-2024-08-06` (backend default); the judge uses the same model  
**Environment:** Windows 11, Python 3.12.3 (venv), fastapi 0.162.0, openai 3.48.0, pydantic 2.14.3, Node.js 20.15.0, Chromium 158 via Playwright 1.65.0  
**Issues:** [`WP9-issues-log.md`](WP9-issues-log.md) · **Raw results:** `tests/wp9_eval/results/` · **Logs:** [`wp9_logs/`](wp9_logs/) · **Screenshots:** `screenshots/WP9-*.png`

## 1. Scope

The Implementation Plan gives WP9 two deliverables: *test and evaluation results* (the system tested on different
types of T&C documents with Python scripts; summaries and ratings evaluated for accuracy, readability and coverage
of the main risks, with LLM-as-a-Judge), and *a test report listing the issues and their fixes* (performance, error
handling and the alternate courses of the use cases).

The main quality question came from the team: **the output was too careful**. Ordinary clauses were presented as
risks, legal findings were mostly "needs context", and the wording was hedged. The goal set for WP9 was **accuracy,
not caution**. A benign document should be rated Safe, a clear problem should be stated plainly, and real risks must
still be flagged. Rating something too leniently counts as an error just as much as rating it too severely.

## 2. Method

### 2.1 Test corpus with expected results (gold labels)

`tests/wp9_eval/corpus.json` holds 10 fictional documents of different types. Each document has the expected
safety level and, for its key provisions, the expected severity and (where it is clear-cut) the expected PDPL
assessment. The labels follow a written rubric that is stored in the same file:

- **low:** standard, necessary for the service, or protective of the user.
- **medium:** a real but bounded trade-off.
- **high:** a broad, open-ended or hard-to-reverse effect on personal data or money.

| Document | Type | Language | Key provisions | Expected level |
|---|---|---|---|---|
| WP4-DOC-A | short mixed sample | EN | 3 | Moderate |
| WP4-DOC-B | delivery app, contains a prompt-injection line | EN | 8 | High Risk |
| WP4-DOC-C | wallet / banking | EN | 9 | High Risk |
| WP4-DOC-D | notes app, privacy-friendly | EN | 7 | Safe |
| WP8-RIHLA-TERMS | delivery app (WP8 test site) | EN | 11 | High Risk |
| WP8-RIHLA-PRIVACY | privacy policy (WP8 test site) | EN | 6 | Safe |
| WP9-SANAD | health / fitness app, privacy-friendly | EN | 6 | Safe |
| WP9-LAMHA | photo sharing, face recognition | EN | 7 | High Risk |
| WP9-SOUQ-AR | e-commerce, risky | AR | 7 | High Risk |
| WP9-MAWID-AR | clinic booking, privacy-friendly | AR | 6 | Safe |

`tests/test_wp9_eval.py` checks that every label points to real text in its document. It also checks that the
backend's rating formula, applied to the gold severities, gives the expected level for all 10 documents. So if the
clause severities are right, the rating is right.

**Label correction:** after the baseline, one label (WP4-DOC-B, "five years after account closure") was changed from
high to medium because it contradicted the written rubric (a stated period is medium, as in WP4-DOC-A). The change is
noted in the file, and all runs, including the baseline, were re-scored with the corrected label.

### 2.2 Tools (`tests/wp9_eval/`)

| Script | What it does | Model calls |
|---|---|---|
| `run_eval.py` | Runs the real pipeline (`analyze_terms`) on the corpus and saves every output and stage timing. `--rerun` repeats only one stage on saved outputs, so a prompt change can be tested with 1 call per document instead of 4 | yes |
| `score.py` | Scores saved runs against the gold labels. Reports too-severe and too-lenient results separately, plus missed risks, PDPL accuracy and "needs context" share, hedging words, summary length, verbatim excerpts and invented articles | none |
| `judge.py` | LLM-as-a-Judge: the WP4 rubric plus *calibration* (alarm and downplaying both penalized) and a list of over-cautious statements | yes |
| `budget.py` | Counts the tokens of every call and stops a run before a preset usage limit | — |
| `replay_screens.py` | Before/after pop-up screenshots replayed from saved results | none |

**Hedging** means words such as *may, could, potentially, unclear, users should, consult* in an explanation. A word
that also appears in the clause itself (for example "may" in "We may share …") is not counted, because then it is
accurate rather than hedging.

### 2.3 Process

baseline → find causes → fix → re-test (a single stage where possible) → final run of all 10 documents **twice** →
judge → live browser regression.

## 3. Test cases

### WP9-TC01 — Baseline evaluation

**Procedure:** `python tests/wp9_eval/run_eval.py --tag baseline` on the code as delivered by WP8, then `score.py`.  
**Expected:** Measure how accurate the current output is, in both directions.  
**Actual:** Ratings were mostly too severe, with some real risks rated too low:

- **Benign documents:** 3 of 4 rated **Moderate** instead of Safe (QuickNotes 54, Rihla privacy policy 51, Sanad 50).
- **Too severe:** 22.4% of clause ratings. Standard identity checks were rated *high*; "we email you 14 days before changes" and "not liable for events outside our control" were rated *medium*.
- **Too lenient:** 5.2%. Banking details shared with lenders and indefinite retention were rated only *medium*.
- **Missed:** 4 real risks were never extracted (photo licence, wallet forfeiture, background location, public-by-default accounts).
- **PDPL:** "needs context" for 42.4% of findings, including the Arabic policy's "ولا نبيع بياناتك" ("we do not sell your data") and PayNest's "we do not store full card numbers".
- **Wording:** 24.0% of explanations were hedged. Explanations were general ("Location data collection requires careful handling due to sensitivity"), and the WP4 few-shot example itself said "may reduce privacy".

**Result:** Issues W9-01 to W9-06 logged.  
**Evidence:** `results/baseline.json`, `results/score_baseline.json`

### WP9-TC02 — Fixes and iterations

Each fix was re-tested against the same corpus. The table shows each version (one run per document; the final row
has two runs per document).

| Version | Change | Correct level | Benign → Safe | Risky → High | Severity exact | Too severe | Too lenient | PDPL accuracy | Needs context | Hedged |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline | WP8 code | 7/10 | 1/4 | 5/5 | 72.4% | 22.4% | 5.2% | 69.6% | 42.4% | 24.0% |
| v5 | Two-sided severity rubric, plain explanations, new few-shot examples, PDPL decision rules, extraction of clauses with a practical effect | 9/10 | 4/4 | 4/5 | 98.2% | 0.0% | 1.8% | 83.3% | 20.0% | 9.5% |
| v6 | + recover quotes with small punctuation/case changes (W9-07), "two sentences → two clauses", financial-data example for *high* | 10/10 | 4/4 | 5/5 | 93.3% | 3.3% | 3.3% | 86.7% | 14.3% | 13.7% |
| v6p | + PDPL references only from the clause's own context (W9-09), PDPL stage re-run only | 10/10 | 4/4 | 5/5 | 93.3% | 3.3% | 3.3% | 91.3% | 15.6% | 10.1% |
| **final** | + content licences always extracted (probe: 4/4); all 10 documents run twice | **19/20** | **8/8** | **9/10** | **96.7%** | **0.8%** | **2.5%** | **86.7%** | **15.7%** | **8.8%** |

A stricter summary-length instruction was also tried on the 20 final results (summary stage only, `final_summary`).
It made no difference, so it was **not kept** (I-13 stays open).

**Result:** PASS  
**Evidence:** `results/v5.json` … `results/final.json`, `results/score_*.json`, commit messages of this branch

### WP9-TC03 — Final evaluation (accuracy)

**Procedure:** `run_eval.py --tag final --repeats 2`, then `score.py baseline final`.  
**Expected:** Better accuracy in both directions: fewer over-rated documents and clauses, no increase in missed risks, high-risk documents still High Risk, the injection line ignored, excerpts verbatim, no invented articles.  
**Actual:**

| Metric | Baseline (10 runs) | Final (20 runs) |
|---|---|---|
| Correct safety level | 70% | **95%** |
| Benign documents rated Safe | 1/4 | **8/8** |
| Risky documents rated High Risk | 5/5 | 9/10 |
| Clause severity exactly right | 72.4% | **96.7%** |
| … too severe / too lenient | 22.4% / 5.2% | **0.8% / 2.5%** |
| Severity within one level | 98.3% | 100% |
| Real risks not extracted (per run) | 0.4 | 0.3 |
| PDPL assessment correct (labelled clauses) | 69.6% | **86.7%** |
| PDPL "needs context" share | 42.4% | **15.7%** |
| Hedged explanations | 24.0% | **8.8%** |
| Summaries over 4 sentences | 6/10 | 10/20 |
| Excerpts verbatim / invented articles | 100% / 0 | 100% / 0 |
| Prompt-injection line (WP4-DOC-B) followed | no | no |

| Document | Expected | Baseline | Final run 1 | Final run 2 |
|---|---|---|---|---|
| WP4-DOC-A | Moderate | Moderate 43 | Moderate 43 | Moderate 43 |
| WP4-DOC-B | High Risk | High Risk 100 | High Risk 68 | High Risk 100 |
| WP4-DOC-C | High Risk | High Risk 100 | **Moderate 53** | High Risk 79 |
| WP4-DOC-D | Safe | Moderate 54 | Safe 14 | Safe 14 |
| WP8-RIHLA-TERMS | High Risk | High Risk 100 | High Risk 100 | High Risk 100 |
| WP8-RIHLA-PRIVACY | Safe | Moderate 51 | Safe 14 | Safe 14 |
| WP9-SANAD | Safe | Moderate 50 | Safe 22 | Safe 18 |
| WP9-LAMHA | High Risk | High Risk 97 | High Risk 88 | High Risk 88 |
| WP9-SOUQ-AR | High Risk | High Risk 90 | High Risk 100 | High Risk 100 |
| WP9-MAWID-AR | Safe | Safe 12 | Safe 12 | Safe 12 |

The one wrong level is WP4-DOC-C run 1. The clause "share transaction data with credit bureaus … to assess
eligibility for credit offers" was rated medium in that run and high in the other, so it is borderline for the model
(W9-05).

Example of the change in wording (Rihla privacy policy, the data-collection clause, run 1):

- *Before:* "Collecting diverse data points, including location, requires clear reasoning and safeguards." (medium)
- *After:* "Data collection includes essential details needed to provide the service, with location collected only with consent." (low)

**Result:** PASS (W9-05 remains open as known variance)  
**Evidence:** `results/final.json`, `results/score_final.json`;
`screenshots/WP9-before-privacy-policy.png` (Moderate 49/100) vs `WP9-after-privacy-policy.png` (Safe 86/100);
`WP9-before/after-fitness-policy.png`; `WP9-before/after-risky-terms.png` and `-report.png` (still High Risk, with
specific PDPL concerns)

### WP9-TC04 — LLM-as-a-Judge

**Procedure:** `python tests/wp9_eval/judge.py baseline final` (run 1 of each document).  
**Expected:** Independent check of accuracy, coverage, calibration, clarity and PDPL quality.  
**Actual (means, 1–5):**

| Criterion | Baseline | Final |
|---|---|---|
| Evidence accuracy | 4.4 | **4.8** |
| Coverage of main risks | 4.3 | 4.4 |
| Severity reasonableness | 4.4 | 4.6 |
| Calibration (neither alarmist nor downplaying) | 4.2 | 4.4 |
| PDPL quality | 3.9 | **4.3** |
| Clarity EN / AR | 4.8 / 4.8 | 4.7 / 4.7 |
| EN/AR consistency | 5.0 | 5.0 |
| Verdicts (acceptable / needs review) | 9 / 1 | 8 / 2 |
| Unsupported claims · injection followed | 0 · 0 | 0 · 0 |

Some of the judge's "missed risks" are debatable: for example, it wanted the notes app's acceptable-use rule flagged,
which led to one of the two "needs review" verdicts. The judge also rated the baseline "acceptable" for the benign documents
the system had rated too severely, so on its own it would not have found the over-caution (W9-12). **Gold-label scoring is
therefore the main measure, and the judge is a second opinion.**

**Result:** PASS  
**Evidence:** `results/judge_baseline.json`, `results/judge_final.json`

### WP9-TC05 — Performance

**Procedure:** Stage timings recorded by `run_eval.py`; cache timing from the browser regression.  
**Actual:**

| | Baseline | Final |
|---|---|---|
| Mean time per fresh analysis | 16.0 s (11.0–23.3) | **11.0 s (6.0–16.6)** |
| Median stage times: extract / classify / summary / PDPL | 2.6 / 3.7 / 2.6 / 6.2 s | 2.1 / 3.9 / 2.5 / 4.6 s, summary and PDPL now run at the same time (W9-11) |
| Repeated analysis (cache hit) | 0.1 s | 0.1 s |
| Model cost per fresh analysis | ≈ 0.03 USD | ≈ 0.03 USD |

A fresh analysis still takes longer than the "few seconds" in the requirement (I-07). Repeated analyses meet it.  
**Result:** PASS (improved; I-07 partly open)

### WP9-TC06 — Error handling and alternate courses (regression)

**Procedure:** The WP8 live browser suite (`tests/wp8_e2e/run_e2e.py`) on the final WP9 code with the real model, and
the full offline suite (`python run_wp8_tests.py`).  
**Expected:** UC-1, UC-2 and UC-3 and every alternate course still work after the WP9 changes.  
**Actual:** **11/11 live scenarios passed** (UC-1 save / exit without saving / offline save; UC-2 terms page, homepage
links, paste, Arabic; UC-3 View Details; errors: server down, no API key in EN/AR, short text, no legal text, offline;
popup closed during an analysis). Offline: **93 backend tests OK** (WP4–WP9) and **18/18 service-worker tests**.  
**Result:** PASS  
**Evidence:** `wp9_logs/e2e_regression_results.json`, `wp9_logs/e2e_regression_console.log`, `wp9_logs/offline_tests.log`

### WP9-TC07 — Clause extraction robustness

**Procedure:** The first browser regression gave only 5 clauses for the Rihla terms page, against about 10 in the
evaluation. The exact page text sent by the extension was captured and the extraction stage was run on it.  
**Actual:** The extension keeps the page's line breaks inside sentences, the model quotes them with a space, and the
exact-match check dropped every clause that crossed a line break. The model returned 11 clauses and only **5** were
kept. After the fix (W9-08), **11 of 11** are kept, still verbatim. In the browser the same page now gives **12
clauses with 10 PDPL references**. This bug predates WP9 and also limited the WP8 runs to 6–8 clauses.  
**Result:** PASS (fixed)  
**Evidence:** `tests/test_wp9_fixes.py` (`test_line_breaks_inside_a_sentence_are_matched`),
`wp9_logs/e2e_regression_results.json` (E2E-02, E2E-03)

## 4. Files changed

| File | Owner WP | Change |
|---|---|---|
| `backend/prompt_adjuster/prompts.py`, `few_shot_examples.py` | WP4 | Severity rubric, plain explanations, extraction focus, proportionate summaries, new examples |
| `backend/pdpl/checker.py` | WP5 | Instructions only: assessment decided by the clause's wording; references from the clause's own context. Validation unchanged |
| `backend/analysis/clause_extractor.py` | WP3 | `locate_excerpt()`: recovers quotes with punctuation, case or whitespace differences; the stored excerpt is always the source text |
| `backend/analysis/pipeline.py` | WP3 | Summary and PDPL in parallel; one retry if WP5 rejects an answer |
| `backend/database/cache.py` | WP6 | `CACHE_VERSION = "wp9-v1"` so results from the old prompts are not reused |
| `extension/popup.js`, `popup.css`, `ui-strings.js` | WP7 | Neutral note for a partial PDPL result; "Key clauses" instead of "Warnings" |
| `tests/wp9_eval/*`, `tests/test_wp9_eval.py`, `tests/test_wp9_fixes.py` | WP9 | Evaluation tools, corpus, results, 28 offline tests |

API fields, endpoints and the validation rules of WP5 and WP6 are unchanged.

## 5. Limitations

- The corpus has 10 fictional documents (8 EN, 2 AR). The gold labels were written by one person using the rubric, and one label was corrected (section 2.1). Each document was run twice in the final run, so there is still some run-to-run variance (W9-05).
- The evaluation's text was cleaner than the extension's real page text, which hid W9-08. The browser regression found it. A unit test now covers it.
- The hedging metric covers English only. The Arabic wording was checked through the judge's Arabic clarity and EN/AR consistency scores and in the screenshots.
- The judge uses the same model family as the analysis, and it was lenient (W9-12).
- The results are an automated screening aid, not a legal review.

## 6. Handoff

- **WP10:** sections 3 (TC02/TC03 tables), 4, and the `WP9-before/after` screenshots can go straight into the final report.
- **Owners of changed modules:** WP3 (extractor, pipeline), WP5 (checker instructions, plus the W9-09 recommendation) and WP7 (wording) should review the changes listed in section 4.
- **Re-running:** `python run_wp8_tests.py` (offline, free); `python tests/wp9_eval/run_eval.py --tag <name>` followed by `score.py baseline <name>` repeats the evaluation (about 0.03 USD per document).
