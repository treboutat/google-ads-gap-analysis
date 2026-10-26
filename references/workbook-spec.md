# Workbook spec

One review .xlsx, Arial, header rows dark navy with white bold text, blue font for hard-coded inputs, formulas for derived metrics (CPA, ROAS, value/conv, char counts, scaled quarterly figures), yellow fill for editable assumptions. Freeze header rows; add filters on long tables.

Next to it, one clean CSV per Editor upload tab (`kw_upload_<CID>.csv`, `rsa_upload_<CID>.csv`, `neg_upload_<CID>.csv`, with the 10-digit customer ID) holding only importable columns, so the account owner imports exactly what was reviewed. Reviewer notes, tiers and verdicts never go in those files.

Tab order:

1. **Read Me** (prose):
   1. Answer first: the recommendation in two or three sentences.
   2. Data used and gaps: route (GAQL or UI exports), windows, mature window and pending days, visible search-term cost as a share of campaign Search cost, paused campaigns' share of the quarter, what could not be read.
   3. Outcome tie: bidding conversion action(s), whether they map to the agreed outcome (and who verified it), conversion values, acceptable economics or the labelled baseline, conversion lag.
   4. Bid strategy per campaign (from the API, paused campaigns included) and how keywords were judged (benchmark cell reference).
   5. What drives value today (themes with the numbers).
   6. GAP themes found, with an honest note on size.
   7. Expected lift table per theme: quarterly clicks, cost, mature value/click, value at stake, low/high incremental share (editable), totals via SUM/SUMPRODUCT, plus one paragraph interpreting it (platform value, not revenue; a later before/after is observational).
   8. Where the new keywords go (existing vs new ad group, keyword-level URL, new campaign handoff) and why.
   9. Candidates held back: blocked by a current negative, paused keywords to re-enable.
   10. Ads built.
   11. Negative keywords summary by family.
   12. Tests & reallocation (when the ask was about improving results or the rest of the month).
   13. Before you upload: Editor import order (keywords → RSAs → negatives), open checks with owners.
   Also: method release, skill version, and a list of tabs.
2. **Keyword Value Benchmark**: 90-day keyword rows: campaign, bid strategy, effective target, ad group, keyword, match, status, QS, impr, clicks, cost, conv, value, CPA, ROAS, value/conv, "Meets target or baseline?", value class (Proven value driver / Meets CPA, low-value conv. / Misses CPA / Spend, no conversions / Immature). Benchmark inputs on top (acceptable CPA/ROAS from the business, or non-brand cost, conv, value → baseline CPA, ROAS labelled "observed baseline"; minimum pipeline value per conversion as an editable assumption). Brand rows greyed.
3. **GAP Keywords**: #, theme, tier, purpose (routing control / ad-page relevance / new reach), keyword, match, campaign, campaign new/existing, ad group, ad group new/existing, final URL (ad group or keyword-level), why selected, parent/benchmark proof, STR impr/clicks/cost/conv/value (mature window), quarterly clicks & cost (formulas), where it serves today, current-negative check (Clear / name of the blocking negative). Tier 2 rows greyed. One row per campaign when an ad group is duplicated across geo-tier campaigns (note not to sum repeats).
4. **GAP Proof - STR Rows**: every raw STR row behind each GAP keyword (term, search-term match type, triggering keyword and its match type, campaign, ad group, metrics).
5. **Considered - Not Added**: rejected terms with metrics, decision (Covered / Blocked by current negative / Paused keyword: re-enable? / Inspect / Confirm / Watch / Do not add / Negative handoff) and reason. For blocked terms, name the negative, its level and list.
6. **KW Editor Upload**: `Campaign | Ad group | Keyword | Criterion Type | Final URL | Status`. A row with only Campaign + Ad group + Status creates a new ad group in an existing campaign. Criterion Type `Exact`; Status `Paused`; keyword text plain. No new campaigns here (see SKILL.md step 8).
7. **Asset Proof**: selected assets: report metrics, CPA/ROAS/value-per-conv formulas, meets target?, Existing–reused vs New/derived, why, where it lives, chars. Then "Existing assets deliberately left out" with reasons. Then 90-day ad-level context (ad, final URL, metrics). Label asset metrics as assets serving together, not isolated effects.
8. **RSA Build Review**: per RSA: id, campaign/ad group, ad group status, copy angle, final URL, display path, pins with the message each protects; each headline/description/path with LEN() formula, limit, OK?, source.
9. **RSA Editor Upload**: `Campaign | Ad group | Ad type ("Responsive search ad") | Headline 1–15 | Description 1–4 | Path 1 | Path 2 | Final URL | Status (Paused)`.
10. **Negative Keywords**: method note and gaps; summary by family (about ten) with totals and three example queries; one row per term (family, negative, match, scope, intent or economic rationale, mature metrics, seen in, blocked query, protected query still eligible, confidence, reviewer verdict: Exclude / Keep relevant / Keep unsure, review condition: economic rows dated about one month out); PMax handoff table; watch/protected table with exposure limits.
11. **NEG Editor Upload**: `Campaign | Ad group (blank) | Keyword | Criterion Type ("Campaign Negative Exact", "Campaign Negative Phrase" or "Campaign Negative Broad", matching the approved row)`, one row per campaign. Confirm the type in Editor's import preview. Generate the clean CSV with `scripts/export_negative_verdicts.py --customer-id <CID>` from review columns `text,match_type,campaign,verdict` (optional `ad_group,level`). Only rows the reviewer marks Exclude go in the clean CSV; Keep and pending rows stay in the workbook. No verdicts means a header-only CSV labelled pending review. Regenerate after changes and reconcile text, match type and scope with the reviewed Exclude set. Account/shared-list/ad-group changes need their own explicitly scoped upload.
12. **QA Checks**: check / result (PASS, CHECK, HANDOFF) / detail: character limits, uniqueness, no duplicate keywords, GAP not already an enabled keyword, GAP not blocked by a current negative, paused keywords reused not duplicated, all Paused, no competitor names in ads, no keyword insertion in competitor groups, enabled-RSA limit, claim substantiation, Final URL expansion and disclaimer assets vs pins and intended pages, new negatives don't block keywords/GAP terms/protected queries, mature window used for economics, negative import route, PMax handoff, clean CSVs match the review tabs, upload file names carry the customer ID and Editor has that account open.

Search terms are public input. In the workbook, write search terms and keywords as text, never formulas: openpyxl stores a string that starts with `=` as a formula, so set `cell.data_type = 's'` for those cells. The review CSVs from `gap_candidates.py --out` already carry a leading apostrophe on such cells; strip it before any value reaches an upload file (`export_negative_verdicts.py` does this for negatives).
