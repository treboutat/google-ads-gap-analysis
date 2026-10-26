# Test: Requests that belong to a different job

## Input and expected route

| Request | Expected |
|---|---|
| "Run a gap analysis on my account" / "what search terms should we add as keywords?" | This skill |
| "Go through last 14 days of search terms and tell me what to negate" | Not this skill: a negatives-only search-term review |
| "Build keywords for our new on-site personalization feature" | Not this skill: capability-led keyword research with no search-term history |
| "Audit my whole Google Ads account" | Not this skill: a full account audit |
| "Should we raise the budget?" | Not this skill: a budget decision |
| "Refresh the ad copy in the Pricing ad group" (no new keywords going there) | Not this skill: an ad-copy refresh |

## Failure cases

Running a full gap analysis for a negatives-only or budget-only ask, or answering a gap-analysis ask with a general account summary.
