# Method rules for a gap analysis

The judgment rules this skill applies, taken from TNT Growth's Google Ads method (release 2026-10-14.1): search-term review, keyword research, match types, campaign structure, ad copy, starter negatives and budget economics. Only the parts a gap analysis uses are here. Platform statements link to Google's documentation; Google changes the platform often, so re-check one before a decision depends on it.

## Economics and evidence

- Start from the business outcome and the acceptable cost to get it. If 20% of qualified leads become customers and the business can afford $500 of ad spend per customer, the qualified-lead limit is $100, assuming the close rate holds.
- Without stated economics, the observed CPA or ROAS is a baseline. It describes the account; it does not prove profitability and does not justify scaling by itself.
- Keep Brand and non-brand apart when reading results. A cheap brand conversion is not the same opportunity as a new non-brand customer.
- Judge clicks old enough for the conversion lag. Recent cost is fully reported while conversions arrive later. [Conversion delay](https://support.google.com/google-ads/answer/6239119)
- Match CRM outcomes to the click cohort that produced them. Customers closed this month may come from earlier clicks.
- When joining conversion-action or CRM detail, keep the report's grain so spend is not repeated. Keep raw leads, qualified outcomes and customers distinct.
- Doubtful measurement is not a reason to stop working acquisition. Broken measurement is a reason not to optimize confidently against that signal.

## Search terms: relevance, economics, confidence

Assess each query in its campaign separately on three questions:

| Question | Ask |
|---|---|
| Relevance | Does it fit the offer and this campaign's buyer? |
| Economics | What do mature outcomes show against acceptable cost and value? |
| Confidence | How strong is the evidence, and what is unknown? |

A 1-10 relevance score can sort the list. It never decides an exclusion or a keyword addition by itself, and missing information is not a reason to lower it.

| Evidence | Action |
|---|---|
| Clear mismatch with the offer or campaign | Narrow exclusion now, even at one impression and zero clicks |
| Plausible buyer, thin or immature evidence | Keep eligible and watch, with a review condition and an affordable exposure limit |
| Relevant demand, acceptable mature economics | Protect it; consider a specific improvement or a keyword |
| Relevant demand, persistently unacceptable mature economics | Find the fitting control first: bid or target, page, offer, signal; a narrow economic exclusion only if testing is not justified |
| Looks like wrong intent but has conversions | Inspect which conversion action fired and what it means before trusting it |

- No universal click, spend or day cutoff. Do not exclude automatically at 100 clicks, protect forever after one conversion, or wait 14 days to exclude something clearly irrelevant.
- An economic exclusion needs a way back: record the reason, scope, date and a reassessment about one month out.
- Search-term reports do not show every query. Report the visible share of cost; hidden spend is unknown, not waste. [Search terms report](https://support.google.com/google-ads/answer/2472708)
- A row labelled Exact does not prove the triggering keyword is exact match. Read the keyword's own match type.
- AI Max has "Other" search terms; include them in coverage. [AI Max reporting](https://support.google.com/google-ads/answer/16470459)
- PMax search terms come from their own report, and Search negatives do not cover every PMax channel. [PMax reporting](https://support.google.com/google-ads/answer/16327396)
- Look up any business or product name you cannot place before calling it a competitor.

## Adding keywords

- Add a keyword only for a purpose: better routing control, ad or page relevance for a distinct need, or reach not served today. "It converted" alone is not a purpose. Adding an exact keyword does not guarantee exclusive routing. [Keyword prioritization](https://support.google.com/google-ads/answer/2756257)
- Zero explicit keywords does not prove missing demand: phrase, broad, close variants or AI Max may already reach it. Absence from the report does not prove zero coverage either.
- Existing reach is not a reason to leave a distinct need behind a generic ad and page. Give it a relevant ad group, copy and page.
- Thin data or a zero volume estimate is not a reason to hold back a relevant term.
- Route by what must differ: a keyword-level final URL when only the destination differs; a new ad group when the message differs; a new campaign only when a campaign control (budget, bid strategy, conversion goal, geography, schedule) must differ. Ad groups share their campaign's budget. [Keyword final URLs](https://support.google.com/google-ads/answer/6371202)
- Exact is the starting default for unproven non-brand demand. An established account does not become unproven because keywords are reorganized; keep match types that work. Exact still includes close variants. [Close variants](https://support.google.com/google-ads/answer/9342105)
- Create new objects paused so nothing spends before it is checked.

## Negatives

- Negatives do not expand to close variants, synonyms or plurals. Exact blocks that query with nothing added; phrase blocks the words together in order; broad blocks when all words appear in any order. [Negative matching](https://support.google.com/google-ads/answer/2453972)
- Use the narrowest text, match type and scope that does the job. Do not turn one weak query into a broad word negative without evidence for that wider decision.
- Show, for each proposed negative, a search it blocks and a nearby buyer search it must keep. Check the combined effect of account, shared-list, campaign and ad-group negatives. A protected-query list does not override an active negative.
- Before changing a shared or account-level list, check every campaign it applies to. [Shared lists](https://support.google.com/google-ads/answer/2453983)
- Own brand is its own decision per campaign: exclude it, buy it in Brand, or allow it. An exact `[acme]` negative blocks only `acme`, not `acme pricing`. Brand lists match more broadly. New Search brand exclusions can require AI Max; never enable it silently. If routing brand elsewhere, check the destination campaign is live and eligible. [Brand settings](https://support.google.com/google-ads/answer/13721847)
- Group proposals into about ten families with three example queries each, and attach the full term list.
- Reviewer verdicts: **Exclude** (clear mismatch or failed mature economics), **Keep relevant** (confident it is a buyer), **Keep unsure** (left on because nobody knows enough yet).
- Report spend on proposed exclusions as historical spend in the stated window. Never call it savings or project a CPA reduction.

## Ads

- Write a full set of useful, truthful assets: normally 15 headlines and 4 descriptions. Do not invent proof to fill the count.
- Two meaningfully different RSAs when the offer supports it; at most three enabled per ad group. [Account limits](https://support.google.com/google-ads/answer/6372658)
- Asset metrics describe assets serving together. They are diagnostic, not an asset's isolated effect. [Asset report](https://support.google.com/google-ads/answer/9564897)
- Unpinned by default. Pin only to keep a required message visible, and name the message. Final URL expansion and campaign text disclaimers can defeat a pin. [Pinning](https://support.google.com/google-ads/answer/7684791)
- No keyword insertion in competitor or trademark ad groups; competitor ads must make the advertiser's identity clear.
- Ad Strength is a diagnostic, not the performance score.

## Results and tests

- A before/after comparison after changes is observational. It does not prove incrementality, because bids, budgets, creative and the market change too.
- Every test has a hypothesis, scope, spend allowance and a stop or success rule judged on mature outcomes.
- Budget and target changes are separate decisions with their own evidence. This skill recommends; it does not decide them.
