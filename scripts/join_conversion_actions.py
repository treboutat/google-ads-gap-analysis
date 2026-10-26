"""Join queries 5 and 5b at one row per search term, campaign ID and ad-group ID.

    python3 join_conversion_actions.py SEARCH_TERMS.csv ACTIONS.csv --out JOINED.csv
    python3 join_conversion_actions.py KEYWORDS.csv KEYWORD_ACTIONS.csv --grain keyword --out JOINED.csv

Query 5 splits by triggering keyword and search-term match type. Sum those rows
before joining query 5b. Pivot conversion actions into columns so neither spend
nor action outcomes repeat. Use the original query 5 for triggering-keyword proof.
"""
import argparse

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # also under python -I
from load_ads_export import load  # noqa: E402

KEYS = {'search-term': ['search_term', 'campaign_id', 'ad_group_id'],
        'keyword': ['keyword', 'match_type', 'campaign_id', 'ad_group_id']}
BASE_METRICS = ['impressions', 'clicks', 'cost', 'conversions', 'conv_value']
ACTION_METRICS = ['all_conversions', 'all_conv_value']


def join_actions(terms, actions, grain='search-term'):
    keys = KEYS[grain]
    for label, frame, columns in (
        ('performance', terms, keys + BASE_METRICS),
        ('conversion actions', actions, keys + ['conversion_action'] + ACTION_METRICS),
    ):
        missing = set(columns) - set(frame.columns)
        if missing:
            raise ValueError(f'{label}: missing columns: {", ".join(sorted(missing))}')
        if frame[keys].astype(str).apply(lambda col: col.str.strip().eq('')).any().any():
            raise ValueError(f'{label}: blank join identity')
    action_keys = keys + ['conversion_action']
    if actions.duplicated(action_keys).any():
        raise ValueError('Duplicate conversion-action rows: check export overlap and report grain')
    if actions.conversion_action.astype(str).str.strip().eq('').any():
        raise ValueError('Blank conversion action')
    base = terms.groupby(keys, as_index=False, dropna=False)[BASE_METRICS].sum()
    unmatched = actions[keys].merge(base[keys], on=keys, how='left', indicator=True)
    if unmatched['_merge'].eq('left_only').any():
        raise ValueError('Conversion-action keys absent from search terms: check customer, window and coverage')
    result = base.set_index(keys)
    # Each action has its own columns. Never copy coarse action totals onto the
    # keyword-level rows, or repeat base spend once per conversion action.
    for action in sorted(actions.conversion_action.unique()):
        part = actions[actions.conversion_action == action].set_index(keys)[ACTION_METRICS]
        part.columns = [f'{metric}: {action}' for metric in ACTION_METRICS]
        result = result.join(part, how='left', validate='one_to_one')
        result[part.columns] = result[part.columns].fillna(0)
    return result.reset_index()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('search_terms')
    ap.add_argument('actions')
    ap.add_argument('--grain', choices=KEYS, default='search-term')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    try:
        terms, _ = load(args.search_terms)
        actions, _ = load(args.actions)
        result = join_actions(terms, actions, args.grain)
    except ValueError as exc:
        ap.error(str(exc))
    result.to_csv(args.out, index=False)
    print(f'{len(result)} {args.grain} rows written; action totals do not repeat')


if __name__ == '__main__':
    main()
