---
name: google-ads-gap-analysis
description: "Google Ads gap analysis: find search terms worth adding as keywords, judge them against mature conversions and the campaign's economics, and prepare new RSAs, scoped negative proposals, a review workbook and clean Google Ads Editor CSVs. Use for gap analysis, keyword gaps, mining search terms for new keywords, or finding tests to grow an existing Search account. Read-only: it never changes the account. Not for negatives-only reviews, brand-new accounts with no search-term history, budget-only decisions or full account audits."
metadata:
  author: TNT Growth
  version: "1.0.0"
  method-release: "2026-10-14.1"
---

# Google Ads Gap Analysis

Turn the last quarter of a Google Ads account's data into one workbook you can review and import: what drives value today, which search terms deserve to become keywords (GAP keywords), new RSAs built from proven assets, and negative keywords. Nothing is uploaded or changed in the account. The deliverable is a reviewable plan plus clean Editor files.

## 0. Load the method

This file is the workflow and output format. [references/method-rules.md](references/method-rules.md) holds the judgment rules (TNT Growth's Google Ads method, release 2026-10-14.1). Read it in full before analysis. The other references cover the queries, the workbook and ad assets. If a reference is missing, say so in the Read Me and do not claim it was applied.

Route neighbouring requests elsewhere:

- Negatives only ("what should I exclude from last month's search terms?"): a search-term review, not a gap analysis.
- A new account or a new capability with no search-term history: keyword research, not mining.
- Refreshing ads in ad groups that get no new keywords, budget-only questions, and full account audits: out of scope here.

## 1. Get the business context

Confirm the account: customer ID, account name and the campaign inventory. Accounts with similar names are common. The negative helpers use campaign and ad-group names as scope, so check that campaign names are unique in the account and ad-group names are unique within each campaign. If they are not, work by stable IDs and keep the affected negative check pending.

Collect what changes the decisions:

- The offer, what the business does not sell, service geography, brand terms, competitor strategy and query families that must stay eligible (protected queries).
- The agreed outcome and acceptable economics: target CPA/ROAS or cost per quality outcome, and what the bidding conversion means. A platform conversion counts as a business outcome only when someone has checked it against the CRM or sales records.
- Conversion lag: how long until the bidding conversion and the quality outcome are reliable.
- Deliberate decisions already made, such as a competitor or brand exclusion someone chose on purpose.

Ask once, in one message, only for facts that would change a decision (most often acceptable economics and lag). Continue the rest. Without stated economics, use the observed non-brand CPA or ROAS as a labelled baseline: it describes the account, it does not prove profitability.

## 2. Get the data

Use the first route that works and say which you used.

**A. GAQL.** Run the queries in [references/gaql-queries.md](references/gaql-queries.md) through the Google Ads API or any connector that runs GAQL. Get every row: follow pagination to the end, or download the full file when a tool truncates inline results. Do not substitute summary tools that cap rows, sort by impressions, filter to "wasted spend", or only offer 7/14/30-day windows; check the row count and cost against campaign totals. Use only credentials you are authorized to use. You need:

1. Campaigns: name, status, channel type, bid strategy type and targets, for **all** non-removed campaigns, paused included. Campaign names lie; use the API value.
2. Campaign performance for the window, to reconcile search-term spend.
3. Conversion actions: primary/secondary, category, counting and value settings.
4. Keywords with keyword, ad group and campaign status; 90-day keyword performance.
5. Search terms for the window with campaign, ad group, triggering keyword and both match types, every row including zero-click rows.
6. Negatives: campaign negatives, ad-group negatives, shared lists with their contents, which campaigns each list is attached to, and account-level negatives.
7. RSAs and asset performance for the campaigns that will receive keywords.

**B. Google Ads UI exports.** Otherwise ask for last-quarter exports in one message, naming the columns the scripts need: Search keyword report (Keyword, Match type, Keyword status, Campaign, Campaign status, Ad group, Ad group status, Clicks, Cost, Conversions, Conv. value), Search terms report (Search term, Match type, Added/Excluded, Campaign, Ad group, Keyword, Impr., Clicks, Cost, Conversions, Conv. value), Asset performance report, and the negative keyword and shared-list reports with their Match type column, one report per level. Load them with `scripts/load_ads_export.py`.

The scripts need Python 3 and pandas (`pip install -r scripts/requirements.txt`).

### Coverage checks that change conclusions

- **Spend in the window.** If the account has no Search spend in the last 90 days, stop and say so. Offer a run on the last 90 days with spend only if the user wants it, labelled stale, and check that the campaigns and offer still exist.
- **Window and maturity.** Default window: the 90 days ending yesterday, in the account time zone. Judge economics only on clicks old enough for the conversion lag: pull the mature window (90 days ending lag days ago) for winners and negatives, and report the newest lag days as pending. With unknown lag, say so and treat the last 14 days as pending.
- **Search-term visibility.** Compare search-term cost with campaign Search cost (query 2 or the campaign report, not the search-term file's own Total row) for the same window and campaigns. Report the visible share. Hidden spend is unknown, not waste.
- **Paused campaigns.** If quarterly conversions came from campaigns now paused, say how much of the quarter the GAP search covers.
- **Conversion signal.** Read which actions count in Conversions and what each one is. If the agreed outcome (qualified leads, booked calls, customers) is a secondary action, read it by action in all conversions (queries 3b and 5b). A secondary action can still be biddable through a custom goal; inspect campaign goal selection and custom-goal membership rather than inferring bidding use from primary/secondary alone. For query 5b, use `scripts/join_conversion_actions.py` with the matching-window query 5 export: it aggregates triggering-keyword rows and pivots actions without repeating spend or outcomes. Keep the raw report separately for proof. A button click such as "Get a demo" is not a lead; say how many conversions are real leads or quality outcomes, and judge on those when the bidding conversion is weak.
- **Conversion values.** Values like $1 versus $250/$500/$2,500 are stage weights; a $1 conversion is a raw lead. Confirm the value schedule with the user.
- **Bid strategy and goal history.** GAQL gives the current strategy, target and goals. If they changed inside the window, say so (`change_event` covers only the last 30 days), and do not judge the quarter against today's target: derive the acceptable cost per outcome from the business's economics (for example acceptable cost per customer × the qualified-lead-to-customer rate = acceptable cost per qualified lead) and label it.
- **PMax and AI Max.** PMax search terms use a different report and Search negatives do not control every PMax channel; list them as a handoff. For AI Max, include its "Other" search terms in coverage.

## 3. Decide what "highest worth" means from the bid strategy

Judge keywords the way the campaign bids, against the acceptable economics when known:

| Bid strategy | What makes a keyword a winner |
|---|---|
| Maximize conversion value | Highest conversion value and value per click, with real volume |
| Target ROAS | ROAS at or above the target **and** meaningful volume; a 20x ROAS on one click is not a winner |
| Target CPA / Maximize conversions with a target | At or below the effective target (campaign or ad-group override) on mature data |
| Maximize conversions without a target, Maximize clicks, Manual CPC | At or below the acceptable cost per outcome; without one, the labelled 90-day non-brand baseline |
| Target impression share (usually Brand) | Not a benchmark source: it bids for visibility, not outcomes. Judge its terms on their own results |

When the account records stage values, a winner must also carry real value per conversion, not just cheap $1 conversions. Keep Brand separate; brand performance never sets the non-brand benchmark. Group winners into themes (competitor pricing, a vertical, a capability). Themes, not single rows, drive the GAP search.

## 4. Find GAP keywords

A GAP keyword is a search term from the window that fits a winning theme, is not an enabled keyword in an enabled ad group and campaign, and can actually serve. Run `scripts/resolve_negatives.py` (all current negatives scoped to campaigns), then `scripts/gap_candidates.py` with `--negatives` and `--pattern` set to the winning themes as whole words (`\bpricing\b|\balternatives?\b`; a bare `nj` also matches every business name containing it). Pass `--days` with the number of days the search-term file covers (the mature window's length when you used it), so quarterly figures scale correctly. The script prints the window each file states; if the keyword and search-term files cover different windows, say so in the Read Me. The keyword file needs campaign and ad-group status (query 4): without them an enabled keyword under a paused campaign hides its terms. If only an export without them exists, pass `--keyword-status-only` and state the limit in the Read Me. Then:

1. Pull candidates that share intent with the winning themes, plus any term with pipeline-valued conversions.
2. **Blocked by a current negative:** the script names the negative, its source and the extent: `all` (every campaign it served in), `some: <campaigns>` (add it only where it is not blocked; any ad-group blocks are listed after `; ad group:`), or `ad group only: <campaign / ad group>` (blocked in that ad group; another ad group can take it). Someone may have excluded it on purpose (a crisis-line or competitor exclusion, for example). Do not add the keyword. Put it in Considered with the negative, and recommend changing the negative only with evidence and the business's deliberate decisions in view. A positive keyword cannot overrule a negative.
3. **Exists only as a paused keyword:** the script says where. A paused keyword in a live ad group and campaign: propose re-enabling it (keeps its ID and history) or say why it stays paused. In a paused campaign or a paused or removed ad group: treat the term as a GAP candidate for a live ad group and note the old location. Do not create a duplicate in the same ad group.
4. **Live in one campaign, missing in another** (`converting_keyword_missing_in_served_campaign`): the term is a live keyword somewhere but also converts in a campaign without it, often a geo-tier copy. If `paused_in_served_campaign` shows it paused there, treat it as step 3 (re-enable, never duplicate). Otherwise add it there (one row per campaign) or say why that campaign should keep serving it through another keyword.
5. Drop exact duplicates and inflections an exact keyword already covers as a close variant (price/prices/pricing, singular/plural). Keep genuinely different phrasings (cost vs pricing, "how much does X cost", "alternatives to X").
6. Look up any name you cannot place before calling it a competitor. Business names, logins, phone numbers and hotline searches are rarely GAP keywords even when they convert: when intent looks wrong but conversions are recorded, inspect which conversion action fired before trusting it.
7. Give each GAP keyword a **purpose**: better routing control, ad or page relevance for a distinct need, or reach not served today. A term with no purpose beyond "it converted" stays where it serves.
8. Tier by fit, not volume. **Tier 1:** clear fit with the offer and the theme, supported by its own or its parent's mature evidence. **Tier 2:** clear fit with thin data. Thin data is not a reason to hold a relevant term; include Tier 2 unless page or message fit is missing, and say what to watch.
9. Route each: an existing ad group only when its ad promise and page fit the need; a keyword-level final URL when only the destination differs; a new ad group when the message differs; a new campaign only when a campaign control (budget, goal, geo, bid strategy) must differ. Existing reach is not a reason to leave a distinct need behind a generic ad and page. Brand misspellings and modifiers go to Brand unless the business has decided to serve branded searches such as pricing elsewhere on purpose; then follow that and judge them apart from the non-brand benchmark. The candidate script checks historical serving placements only. Before marking a proposed destination Clear, check its campaign and ad-group negatives plus inherited shared/account negatives; historical clearance in another ad group is not destination clearance.

Use Exact for new non-brand keywords in unproven areas. Where the receiving ad group's working keywords use another match type with acceptable mature results, follow it: an established account does not become unproven when keywords are reorganized. Be honest about size: many GAP terms already serve as close variants, so the explicit keyword mainly buys control plus modest new volume. Record every rejected candidate with its reason.

### Account findings outside the GAP list

The checks above often find bigger problems than missing keywords. Report them in their own Read Me section with evidence, unsized, each with a suggested next step:

- **Enabled keywords blocked by a current negative** (`enabled_keywords_blocked_by_negative`): this checks the literal keyword query against account, attached-list, campaign and same-ad-group negatives. A positive exact keyword can still serve close variants that an identical exact negative does not block. Report the blocked query and scope; do not call the whole keyword unable to serve without further delivery evidence. Name the negative and the list; changing a shared list affects every attached campaign.
- Malformed keyword text (stray quotes), the same term both active and excluded, own brand negated with no Brand campaign, ad claims the landing page contradicts.

### Lift estimate

Per theme: quarterly clicks and cost at stake × the theme's mature value per click = value at stake. When conversion values are flat ($0/$1, or one default value), use quality outcomes per click instead and say so; value per click would be meaningless. Apply a low and high incremental share as labelled, editable assumptions (low for terms already served as close variants, high for terms not reached today). Present a range. It is platform conversion value, not revenue, and a later before/after comparison is observational, not proof of incrementality.

## 5. Build ads for the new keywords only

Build ads only for ad groups that receive GAP keywords and need copy for them. Do not refresh ads elsewhere; note weak ones as a separate follow-up. Read [references/asset-selection.md](references/asset-selection.md) first. In short: reuse proven assets verbatim and label new or derived ones; asset metrics are diagnostic, not isolated effects; the CTA matches the final URL; no competitor names or keyword insertion in competitor or trademark groups; flag claim conflicts; normally 15 headlines and 4 descriptions, two meaningfully different RSAs when the offer supports it, at most three enabled (if the ad group already has three, name the one to pause or route the keywords to a new ad group); unpinned unless a required message needs a pin. Check Final URL expansion and campaign text disclaimers before relying on a pin. Validate the RSA upload file with `python3 scripts/validate_rsa.py <rsa csv>`.

## 6. Negative keywords

Follow the negative rules in [references/method-rules.md](references/method-rules.md):

- **Clear mismatch** with the offer or campaign (another category, jobs, free tools the business does not offer, services outside the offer): a narrow exclusion now. No spend is needed.
- **Relevant demand, poor mature economics:** first name the fitting control (bid or target, page, offer, signal). Propose a narrow economic exclusion only when mature spend has failed against the acceptable cost per quality outcome and further testing is not justified. There is no universal spend or click cutoff. Judge families rather than single rows, record the evidence, and set a reassessment about one month out.
- **Plausible buyer, thin or immature evidence:** keep eligible on a watch list with a review condition and an affordable exposure limit.
- **Own brand in non-brand or competitor campaigns:** a separate decision. Confirm the chosen strategy for each campaign: exclude brand there, buy it in Brand, or allow it. When brand should route to an eligible Brand campaign, propose campaign-specific exclusions that cover the intended brand variants: an exact `[acme]` blocks only the bare brand and leaves `acme pricing` and `acme login` eligible. Test those variants with `scripts/negative_match.py`. Brand lists are the broader alternative; new Search brand exclusions can require AI Max, so never enable it silently. With no Brand campaign, do not negate brand; flag the routing decision for the user. Never on the Brand campaign.

Use the narrowest text, match type and scope that does the job; campaign-level Exact by default. For every proposed negative, give one search it blocks and a nearby buyer search it must keep, and check that no negative (proposed or current) blocks an enabled keyword, a GAP keyword or a protected query in the same scope: put the resolved current negatives and the proposals in one CSV, the queries in a text file, and run `scripts/negative_match.py --negatives <csv> --queries <txt>`. The check models Google's documented rules (no close variants, periods ignored, only the first 16 words of a query count). It cannot model the misspellings Google says negatives also catch, and it compares other punctuation literally, so a clean result is necessary, not sufficient: mark near-misspellings of a negative and hits near hyphens or apostrophes CHECK in QA. Group proposals into about ten families for review, each with its full term list. Leave a reviewer verdict column: Exclude, Keep relevant, Keep unsure. Show past spend as historical spend, not savings. PMax terms go to a separate UI handoff list.

## 7. Tests and reallocation (when asked to improve results or plan the rest of the month)

These requests use the same analysis: cutting low intent is the negatives section; pushing where performance is strong is GAP keywords and ads on proven themes. Add a short **Tests & reallocation** section to the Read Me with 3–5 tests ranked by expected value, each with hypothesis, scope, spend allowance and a stop or success rule judged on mature conversions. With only a few weeks left, prefer changes that can show results inside the conversion lag (clear-mismatch negatives, routing, ads on proven keywords) and say which results will not be readable by month end. Budget or target shifts are recommendations with evidence attached, for a separate budget decision; do not decide them here.

## 8. Deliver

Build one review workbook per [references/workbook-spec.md](references/workbook-spec.md), and alongside it one clean CSV per Editor upload tab (keywords, RSAs, negatives) that contains only importable fields. Keep all proposals in the review workbook. Build the keyword and RSA CSVs from the reviewed workbook tabs. Generate the negatives CSV only from recorded Exclude verdicts with `scripts/export_negative_verdicts.py --customer-id <CID>` and put the customer ID in its file name (Editor matches campaigns by name in whichever account is open); Keep and pending rows must be absent. If no verdicts exist, deliver the review workbook and a header-only negatives CSV labelled pending review. Regenerate after verdict changes and compare the final CSV with the approved rows. The helper supports campaign negatives and preserves their match types; prepare account, shared-list or ad-group operations as a separate, explicitly scoped upload. New keywords, ad groups and ads are Paused. New campaigns are not created from these files: a campaign needs complete budget, bidding, goal, network and location settings, so list it as a build handoff with the evidence. Build the workbook with openpyxl (or a spreadsheet skill if one is installed) and recalculate the formulas with LibreOffice when available, fixing any errors before delivering. If it cannot recalculate, say so in the Read Me and the chat: Excel calculates the formulas on open, but other previewers show blanks.

Keep the chat answer short and lead with the answer:

- The recommendation in two or three sentences, with the GAP count, lift range, the biggest negative family and the most important account finding.
- Outcome tie: the bidding conversion, whether it maps to the agreed outcome, the target or baseline, and maturity.
- Coverage: the route used, window, visible search-term share, what could not be read.
- Open checks with owners, and the method release used.

Read-only. Do not change the account, post or message anyone. Pushing the plan live is a separate step, done by the account owner in Google Ads Editor or the API, with a readback of the resulting settings afterward.
