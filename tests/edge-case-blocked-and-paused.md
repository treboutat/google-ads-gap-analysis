# Test: Candidates blocked by a current negative or existing only as paused keywords

All account identifiers, terms and figures below are synthetic.

## Input

Behavioral-health advertiser, campaigns `NB - Statewide` and `NB - Local`. The user states a deliberate decision made in August 2026: crisis-line searches are excluded because the business cannot take crisis calls. Search terms (mature window): `crisis hotline` ($1,020, 11 conversions on "All Calls", served in both campaigns), `teen therapy program` ($640, 4 conversions), `intensive outpatient program` ($880, 6 conversions). Current negatives: phrase `hotline` on `NB - Local`; shared list "General" with broad `teen` attached to both campaigns. `intensive outpatient program` exists as a paused exact keyword in `NB - Statewide`.

## Expected decisions

- `resolve_negatives.py` and `gap_candidates.py --negatives` name the blocking negative for `crisis hotline` and `teen therapy program`.
- `crisis hotline` is not proposed in either campaign. The script reports it blocked in `NB - Local` only (`some: NB - Local`), but the deliberate decision covers the business, so it is not added to `NB - Statewide` either. It goes to Considered as "Blocked by current negative" with the decision quoted, plus a note that `NB - Statewide` has no matching negative (a coverage gap to raise, not to fix silently). Its "All Calls" conversions are not treated as proof against that decision.
- `teen therapy program` is not proposed while the shared broad `teen` negative applies. Considered notes the list and that changing it affects both campaigns; any change is a recommendation with the business's offer (adults only or not) confirmed first.
- `intensive outpatient program`: propose re-enabling the existing paused keyword (keeps its ID and history), not a duplicate, unless a reason to keep it paused is found.

## Failure cases

Proposing a GAP keyword that a current negative blocks; recommending removal of a deliberate exclusion on conversion counts alone; creating a duplicate of a paused keyword.
