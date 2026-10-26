# Test: Pricing theme gap on a tCPA account

All account identifiers, terms and figures below are synthetic.

## Input

"Run a gap analysis on Northwind Scheduling." GAQL route. Non-brand campaign `NB - Core` bids Maximize conversions with a $180 target; Brand bids Target impression share. The user states that demo requests are the agreed outcome, verified against the CRM, with a 10-day lag, and that branded pricing and cost searches are served in `NB - Core` on purpose so they reach the pricing page (Brand carries only bare-brand and login searches). 90-day window July 27–October 24, 2026; mature window ends October 14.

Search terms (mature window): `northwind pricing` is an exact keyword. `how much does northwind cost` ($1,240, 9 demos, served by phrase `northwind cost`), `northwind price per user` ($310, 2 demos), `scheduling software for clinics` ($2,050, 12 demos, served by broad `scheduling software`), `northwind login` ($140, 0), `scheduling jobs` ($95, 0). Visible search-term cost is 71% of campaign Search cost. No current negative blocks any of these terms.

## Expected decisions

- Winners judged against the $180 target on the mature window, not the account's average CPA. Brand and the branded pricing terms excluded from the non-brand benchmark; the branded pricing terms are judged on their own results.
- GAP keywords: `how much does northwind cost` and `northwind price per user` (branded pricing theme kept in `NB - Core` per the recorded routing decision, purpose: routing to the pricing page and pricing copy) and `scheduling software for clinics` (purpose: a distinct clinic need; a new ad group with a clinic page if one exists, otherwise a page-brief dependency). All Exact, Paused.
- `northwind pricing` variants already covered by the exact keyword are not duplicated.
- Negatives: `scheduling jobs` as a clear mismatch (no spend threshold needed); `northwind login` excluded from `NB - Core` with a campaign phrase negative `"northwind login"` (an exact negative would leave `northwind login help` eligible), with protected queries `northwind pricing` and `how much does northwind cost` still eligible.
- Lift shown as a low/high range of platform conversion value, labelled as not revenue.
- Read Me states the 71% visibility, the mature window and the method release.

## Failure cases

Using a capped or impression-sorted search-term summary as the only search-term source; judging winners on the last 10 days; a GAP keyword without a purpose; negatives chosen by a spend cutoff; claiming savings; any account change.
