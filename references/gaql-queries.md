# GAQL queries for a gap analysis

Run each through the Google Ads API or any connector that runs GAQL, and save the result as CSV. Follow pagination to the end; if a tool truncates inline results, download the full file instead. Compare row counts and cost with campaign totals before relying on a file.

Replace `START` and `END` with dates (`'2026-07-27'`). `END` is yesterday in the account time zone. For the mature window, set `END` to yesterday minus the conversion lag. Queries 1–7, 3b and 5b were run against a live account in October 2026. The identity fields, the Search-channel filter, and the campaign-goal and `customer_negative_criterion` queries below were added afterward and have offline checks only; confirm your API version or connector supports them.

## 1. Campaigns and bid strategy (all statuses)

```sql
SELECT campaign.id, campaign.name, campaign.status, campaign.advertising_channel_type,
  campaign.bidding_strategy_type, campaign.bidding_strategy,
  campaign.maximize_conversions.target_cpa_micros, campaign.target_cpa.target_cpa_micros,
  campaign.maximize_conversion_value.target_roas, campaign.target_roas.target_roas
FROM campaign WHERE campaign.status != 'REMOVED'
```

A `bidding_strategy` resource name means a portfolio strategy; read its target from `bidding_strategy`. Ad-group tCPA overrides: `SELECT campaign.name, ad_group.name, ad_group.target_cpa_micros FROM ad_group WHERE ad_group.target_cpa_micros > 0`.

## 2. Campaign performance (for spend reconciliation)

```sql
SELECT campaign.id, campaign.name, campaign.advertising_channel_type, metrics.impressions,
  metrics.clicks, metrics.cost_micros, metrics.conversions, metrics.conversions_value
FROM campaign WHERE segments.date BETWEEN START AND END
```

## 3. Conversion actions

```sql
SELECT conversion_action.name, conversion_action.category, conversion_action.status,
  conversion_action.primary_for_goal, conversion_action.counting_type,
  conversion_action.value_settings.default_value, conversion_action.type
FROM conversion_action WHERE conversion_action.status = 'ENABLED'
```

### 3b. Results by conversion action, keyword level

Cost and clicks do not split by conversion action. Read them from query 4 and use `scripts/join_conversion_actions.py keyword_performance.csv keyword_actions.csv --grain keyword --out keywords_with_actions.csv`. Join on campaign ID, ad-group ID, keyword text **and match type**; the same text can exist as both Exact and Phrase. Pivot actions before joining so spend is not repeated.

```sql
SELECT campaign.id, campaign.name, ad_group.id, ad_group.name, ad_group_criterion.keyword.text,
  ad_group_criterion.keyword.match_type, segments.conversion_action_name,
  metrics.all_conversions, metrics.all_conversions_value
FROM keyword_view WHERE segments.date BETWEEN START AND END
```

Use `all_conversions` so secondary actions (often the agreed outcome, such as admits) appear. For the campaign level, select campaign ID/name, conversion action and the two metrics with `FROM campaign`; omit the ad-group and keyword fields.

Primary/secondary flags alone do not establish campaign bidding goals. Read `campaign_conversion_goal` (category, origin, biddable), `conversion_goal_campaign_config` (goal_config_level, custom_conversion_goal) and any referenced `custom_conversion_goal` (conversion_actions). A custom goal can bid on a secondary action. See [Google campaign goals](https://developers.google.com/google-ads/api/docs/conversions/goals/campaign-goals). If those settings cannot be read, label the bidding-action mapping unverified.

## 4. Keywords with status and performance

```sql
SELECT campaign.id, campaign.name, campaign.status, ad_group.id, ad_group.name, ad_group.status,
  ad_group_criterion.keyword.text, ad_group_criterion.keyword.match_type,
  ad_group_criterion.status, ad_group_criterion.negative,
  ad_group_criterion.final_urls
FROM ad_group_criterion
WHERE ad_group_criterion.type = 'KEYWORD' AND ad_group_criterion.status != 'REMOVED'
  AND campaign.advertising_channel_type = 'SEARCH'
```

This inventory includes zero-traffic and paused keywords and the ad-group negatives (`negative = true`). Performance for the benchmark:

```sql
SELECT campaign.id, campaign.name, ad_group.id, ad_group.name, ad_group_criterion.keyword.text,
  ad_group_criterion.keyword.match_type, ad_group_criterion.status,
  ad_group_criterion.quality_info.quality_score, metrics.impressions, metrics.clicks,
  metrics.cost_micros, metrics.conversions, metrics.conversions_value
FROM keyword_view WHERE segments.date BETWEEN START AND END
```

## 5. Search terms

```sql
SELECT search_term_view.search_term, search_term_view.status,
  segments.search_term_match_type, segments.keyword.info.text,
  segments.keyword.info.match_type, campaign.id, campaign.name, ad_group.id,
  ad_group.name, metrics.impressions, metrics.clicks, metrics.cost_micros,
  metrics.conversions, metrics.conversions_value
FROM search_term_view WHERE segments.date BETWEEN START AND END
  AND campaign.advertising_channel_type = 'SEARCH'
```

Before relying on coverage, compare this query's row count and cost with the same query minus the four `segments.keyword.info` and match-type fields. If the version without the keyword fields has more cost (keywordless AI Max matches, for example), use it for the 5b join and coverage, and keep this one for triggering-keyword proof. `search_term_view` also returns Shopping queries. Without the Search filter they have no matching keyword and show up as false GAP candidates. PMax terms come from their own report (see the coverage checks in SKILL.md).

### 5b. Search-term results by conversion action

```sql
SELECT search_term_view.search_term, campaign.id, campaign.name, ad_group.id, ad_group.name,
  segments.conversion_action_name, metrics.all_conversions, metrics.all_conversions_value
FROM search_term_view WHERE segments.date BETWEEN START AND END
  AND campaign.advertising_channel_type = 'SEARCH'
```

Query 5 has a finer grain: the same search term can have multiple triggering-keyword or match-type rows in one ad group. **Do not join query 5b directly onto those rows.** First aggregate query 5 to search term + campaign ID + ad-group ID. Pivot query 5b to one column per action and metric, then join one-to-one on those three keys. Use the same customer and date window; reject duplicate action keys or unmatched identities.

```sh
python3 scripts/join_conversion_actions.py search_terms.csv search_term_actions.csv --out search_terms_with_actions.csv
```

The helper preserves total spend and each action's outcomes. For example, two triggering-keyword rows with three combined qualified leads must still show three qualified leads after joining. Retain the original query 5 export for triggering-keyword proof; do not allocate ad-group/term outcomes to individual triggering keywords as observed facts.

`search_term_view.status` is Added/Excluded (`ADDED`, `EXCLUDED`, `ADDED_EXCLUDED`, `NONE`). A row's Exact match label does not prove the triggering keyword is Exact; read `segments.keyword.info.match_type`. The loader keeps the two apart as `search_term_match_type` and `keyword_match_type`.

## 6. Negatives

Campaign negatives:

```sql
SELECT campaign.name, campaign_criterion.keyword.text,
  campaign_criterion.keyword.match_type, campaign_criterion.negative
FROM campaign_criterion
WHERE campaign_criterion.type = 'KEYWORD' AND campaign_criterion.negative = TRUE
  AND campaign.status != 'REMOVED'
```

Shared negative lists and where they apply:

```sql
SELECT shared_set.id, shared_set.name, shared_criterion.keyword.text,
  shared_criterion.keyword.match_type
FROM shared_criterion
WHERE shared_set.type = 'NEGATIVE_KEYWORDS' AND shared_set.status = 'ENABLED'
```

```sql
SELECT campaign.name, shared_set.id, shared_set.name FROM campaign_shared_set
WHERE campaign_shared_set.status = 'ENABLED' AND shared_set.type = 'NEGATIVE_KEYWORDS'
  AND campaign.status != 'REMOVED'
```

Account-level negative keywords live in a shared set of type `ACCOUNT_LEVEL_NEGATIVE_KEYWORDS`, and the set applies only while it is attached to the customer. Run the shared-list query with that type (it selects `shared_set.id`) and pass that export as `--account`, plus the attachment as `--account-attachments`:

```sql
SELECT customer_negative_criterion.negative_keyword_list.shared_set
FROM customer_negative_criterion
WHERE customer_negative_criterion.type = 'NEGATIVE_KEYWORD_LIST'
```

Rows from a set that is not attached are reported and left out. Do not pass account lists to `--shared`, which expects campaign attachments. Ad-group negatives come from query 4.

Combine them with `scripts/resolve_negatives.py --campaign … --shared … --attachments … --ad-group … --account … --account-attachments … --out negatives_resolved.csv`.

## 7. Ads and assets for the receiving campaigns

```sql
SELECT campaign.name, ad_group.name, ad_group_ad.ad.id, ad_group_ad.status,
  ad_group_ad.ad.final_urls, ad_group_ad.ad.responsive_search_ad.headlines,
  ad_group_ad.ad.responsive_search_ad.descriptions,
  ad_group_ad.ad.responsive_search_ad.path1, ad_group_ad.ad.responsive_search_ad.path2,
  metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions,
  metrics.conversions_value
FROM ad_group_ad
WHERE ad_group_ad.ad.type = 'RESPONSIVE_SEARCH_AD' AND segments.date BETWEEN START AND END
  AND campaign.id IN (IDS)
```

```sql
SELECT campaign.name, ad_group.name, asset.text_asset.text, ad_group_ad_asset_view.field_type,
  ad_group_ad_asset_view.pinned_field, metrics.impressions, metrics.clicks,
  metrics.cost_micros, metrics.conversions, metrics.conversions_value
FROM ad_group_ad_asset_view
WHERE segments.date BETWEEN START AND END AND campaign.id IN (IDS)
```

Asset rows describe assets serving together; they are diagnostic, not isolated effects.

The resolver accepts English UTF-16/tab or UTF-8/CSV UI reports as well as GAQL CSVs. Supply dedicated negative reports to the level-specific inputs. For a mixed criterion inventory, include the negative boolean so positives can be removed. Shared-list criteria and attachments must use the same list identity column (IDs preferred). Unsupported headers, missing scope or malformed match types stop resolution; report the coverage gap instead of calling the inventory clear.
