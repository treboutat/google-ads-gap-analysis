"""Aggregate search terms and surface GAP and negative-review candidates.

    python3 gap_candidates.py STR.csv KEYWORDS.csv [--negatives NEG.csv]
        [--pattern "alternativ|pricing|cost"] [--days 90] [--out DIR] [--keyword-status-only]

Inputs are UI exports or GAQL CSVs (see load_ads_export.py). KEYWORDS should list
every keyword with keyword, ad-group and campaign status (query 4 has all three). A
keyword export without the parent statuses stops the run: an enabled keyword under a
paused campaign would count as active and hide its terms. --keyword-status-only runs
anyway and labels that limit. NEG lists current negatives with text, match type and
the campaign each applies to ('ACCOUNT' for account-level; resolve shared lists to
their attached campaigns first); the search-term and keyword files then need campaign
(and ad group, for ad-group negatives) columns.

Prints coverage (visible vs Total-row cost, campaigns, Added/Excluded values),
converting terms that are not enabled keywords, theme-matched terms, terms that only
exist as paused keywords, terms an existing negative blocks, and top non-converting
spend. Quarterly columns scale by 90/days. With --out, writes the same tables as CSV
for the workbook. Text cells that a spreadsheet would read as a formula (=, +, -, @)
get a leading apostrophe in those CSVs; search terms are public input. This is a
candidate list, not a decision: judge every row with the skill's method.
"""
import argparse
import json
import os
import re
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from load_ads_export import load, normalize_text, totals  # noqa: E402
from negative_match import NegativeIndex, match_type  # noqa: E402

# Off states only. UI serving statuses ('Eligible (limited)', 'Low search volume',
# 'Below first page bid') describe a keyword that is on, so an allowlist would call it paused.
OFF = re.compile(r'paused|removed|ended|suspended|not eligible|disapproved')
REQUIRED_METRICS = ('clicks', 'cost', 'conversions')
OPTIONAL_METRICS = ('impressions', 'conv_value')


PARENT_STATUS = ('campaign_status', 'ad_group_status')
_FORMULA = ('=', '+', '-', '@', '\t', '\r')


def sheet_safe(df):
    """Copy for review CSVs: text a spreadsheet would run as a formula becomes literal."""
    out = df.copy()
    for col in out.columns:
        if not pd.api.types.is_numeric_dtype(out[col]):  # object or pandas 3 str dtype
            out[col] = out[col].map(lambda v: "'" + v if isinstance(v, str) and v.startswith(_FORMULA) else v)
    return out


def is_off(value):
    return bool(OFF.search(str(value).strip().lower()))


def enabled(df, col):
    return ~df[col].map(is_off) if col in df.columns else True


def positive_keywords(kw):
    if 'negative' in kw.columns:
        kw = kw[kw['negative'].astype(str).str.lower() != 'true']
    return kw


def live_mask(kw):
    live = enabled(kw, 'status') & enabled(kw, 'ad_group_status') & enabled(kw, 'campaign_status')
    return pd.Series(live, index=kw.index) if not isinstance(live, pd.Series) else live


def keyword_sets(kw):
    """Enabled keyword text, and where text that is not enabled anywhere sits.

    The second value maps text to the reason it is off ('keyword paused', 'ad group
    paused/removed', 'campaign paused'): only a paused keyword in a live ad group and
    campaign can simply be re-enabled.
    """
    kw = positive_keywords(kw)
    live = live_mask(kw)
    active = set(kw.loc[live, 'keyword_norm'])
    reasons = {}
    for term, places in off_locations(kw).items():
        if term not in active:
            reasons[term] = '; '.join(sorted(set(places.values())))
    return active, reasons


def _off_reason(r, columns):
    if 'campaign_status' in columns and is_off(r['campaign_status']):
        return f"campaign {str(r['campaign_status']).lower()}: {r.get('campaign', '')}"
    if 'ad_group_status' in columns and is_off(r['ad_group_status']):
        return f"ad group {str(r['ad_group_status']).lower()}: {r.get('ad_group', '')}"
    status = str(r.get('status', 'paused')).strip().lower()
    # A UI serving status can name the parent ('Campaign paused'); the keyword itself is on.
    if status.startswith('campaign'):
        return f"{status}: {r.get('campaign', '')}"
    if status.startswith('ad group'):
        return f"{status}: {r.get('campaign', '')} / {r.get('ad_group', '')}"
    return f"keyword {status}: {r.get('campaign', '')} / {r.get('ad_group', '')}"


def off_locations(kw):
    """Term -> {campaign: reason} for every keyword that is not live, live elsewhere or not."""
    kw = positive_keywords(kw)
    out = {}
    for _, r in kw.loc[~live_mask(kw)].iterrows():
        places = out.setdefault(r['keyword_norm'], {})
        campaign, why = str(r.get('campaign', '')), _off_reason(r, kw.columns)
        places[campaign] = '; '.join(sorted({*places.get(campaign, '').split('; '), why} - {''}))
    return out


def enabled_campaigns(kw):
    """Term -> campaigns where it is a live keyword (geo-tier copies can miss one)."""
    kw = positive_keywords(kw)
    kw = kw[live_mask(kw)]
    if 'campaign' not in kw.columns:
        return {}
    return kw.groupby('keyword_norm')['campaign'].agg(lambda x: set(map(str, x))).to_dict()


def aggregate(st, active, paused, days, enabled_in=None, off_in=None):
    if days <= 0:
        raise ValueError('days must be greater than zero')
    missing = [c for c in REQUIRED_METRICS if c not in st.columns]
    if missing:
        raise ValueError(f'Search-term file lacks {", ".join(missing)}')
    st = st.copy()
    for col in OPTIONAL_METRICS:
        if col not in st.columns:
            st[col] = 0.0
    if 'campaign' not in st.columns:
        st['campaign'] = ''
    # Search-term match label: its own column in GAQL, 'Match type' in the UI report.
    label = next((c for c in ('search_term_match_type', 'match_type') if c in st.columns), None)
    st['_label'] = st[label] if label else ''
    if 'ad_group' not in st.columns:
        st['ad_group'] = ''
    g = st.groupby('search_term_norm').agg(
        impr=('impressions', 'sum'), clicks=('clicks', 'sum'), cost=('cost', 'sum'),
        conv=('conversions', 'sum'), value=('conv_value', 'sum'),
        campaigns=('campaign', lambda x: ' | '.join(sorted(set(map(str, x))))),
        match=('_label', lambda x: ' | '.join(sorted(set(map(str, x)))))).reset_index()
    g = g.rename(columns={'search_term_norm': 'search_term'})
    locations = {term: json.dumps(sorted(set(zip(rows.campaign, rows.ad_group))))
                 for term, rows in st.groupby('search_term_norm')}
    g['served_in'] = g.search_term.map(locations)
    g['enabled_keyword'] = g.search_term.isin(active)
    enabled_in = enabled_in or {}
    g['enabled_in'] = g.search_term.map(lambda t: ' | '.join(sorted(enabled_in.get(t, ()))))
    # Served in a campaign where it is not a live keyword, though live elsewhere, and
    # whether that campaign already holds it paused (re-enable, do not duplicate). Work
    # from the sets: campaign names can themselves contain ' | '.
    off_in = off_in or {}
    missing = [sorted({c for c, _ in json.loads(p)} - enabled_in[t]) if t in enabled_in else []
               for t, p in zip(g.search_term, g.served_in)]
    g['served_without_keyword'] = [' | '.join(m) for m in missing]
    g['paused_in_served_campaign'] = [
        '; '.join(off_in[t][c] for c in m if c in off_in.get(t, {}))
        for t, m in zip(g.search_term, missing)]
    g['paused_keyword_only'] = g.search_term.map(paused).fillna('')
    factor = 90 / days
    g['q_clicks'] = g.clicks * factor
    g['q_cost'] = g.cost * factor
    g['value_per_conv'] = (g.value / g.conv).where(g.conv > 0)
    return g


def blocked_by(g, negatives):
    """Per term: the current negatives that block it, and whether every campaign it
    served in now blocks it ('all'), only some ('some'), or only an ad-group negative
    does ('ad group only', which blocks it in that ad group alone)."""
    index = NegativeIndex(negatives.to_dict('records'))
    hits, extent = [], []
    for term, placements in zip(g.search_term, g.served_in):
        placements = set(map(tuple, json.loads(placements)))
        served = {c for c, _ in placements}
        found = index.hits(term, served | {'ACCOUNT'})
        found = [n for n in found if n['level'] != 'ad group'
                 or (n['scope'], n['ad_group']) in placements]
        hits.append('; '.join(sorted({f"{n['text']} ({n['match_type']}, {n['source']}, {n['scope']})"
                                      + (f" / {n['ad_group']}" if n['level'] == 'ad group' else '')
                                      for n in found})))
        wide = [n for n in found if n.get('level') != 'ad group']
        blocked_in = {n['scope'] for n in wide}
        groups = sorted({f"{n['scope']} / {n['ad_group']}" for n in found if n.get('level') == 'ad group'})
        if not found:
            extent.append('')
        elif 'ACCOUNT' in blocked_in or served <= blocked_in:
            extent.append('all')
        elif not wide:
            extent.append('ad group only: ' + ', '.join(groups))
        else:
            extent.append('some: ' + ', '.join(sorted(blocked_in))
                          + ('; ad group: ' + ', '.join(groups) if groups else ''))
    return hits, extent


def keywords_blocked(kw, negatives):
    """Enabled keywords whose literal query an applicable negative blocks.

    This is a query conflict, not proof that the keyword cannot serve close variants.
    """
    kw = positive_keywords(kw)
    kw = kw[live_mask(kw)]
    index = NegativeIndex(negatives.to_dict('records'))
    rows = []
    for _, k in kw.iterrows():
        found = index.hits(k['keyword_norm'], {k.get('campaign', ''), 'ACCOUNT'})
        found = [n for n in found if n['level'] != 'ad group'
                 or n['ad_group'] == k.get('ad_group', '')]
        if found:
            rows.append({'campaign': k.get('campaign', ''), 'ad_group': k.get('ad_group', ''),
                         'keyword': k.get('keyword', ''), 'match_type': k.get('match_type', ''),
                         'blocked_query': k['keyword_norm'],
                         'coverage': 'literal query only; close variants not assessed',
                         'blocked_by': '; '.join(sorted({f"{n['text']} ({n['match_type']}, {n['source']})"
                                                         for n in found}))})
    return pd.DataFrame(rows, columns=['campaign', 'ad_group', 'keyword', 'match_type',
                                       'blocked_query', 'coverage', 'blocked_by'])


def read_negatives(path):
    """Campaign-scoped negatives, ideally the output of resolve_negatives.py."""
    neg, _ = load(path)
    text_col = next((c for c in ('text', 'keyword') if c in neg.columns), None)
    if text_col is None:
        raise ValueError('Negatives file needs an explicit text or keyword column')
    if 'match_type' not in neg.columns:
        raise SystemExit('Negatives file needs a match type column; Google matches exact, phrase and broad differently')
    if 'campaign' not in neg.columns:
        raise ValueError('Negatives need campaign scope; use ACCOUNT explicitly for account negatives')
    out = pd.DataFrame({'text': neg[text_col].astype(str).str.strip(),
                        'match_type': neg['match_type'].map(lambda v: match_type(v).upper()),
                        'scope': neg['campaign'].str.strip()})
    if out['text'].eq('').any() or out['scope'].eq('').any():
        raise ValueError('Blank negative text or campaign scope; use ACCOUNT explicitly')
    out['source'] = neg['source'] if 'source' in neg.columns else out['scope']
    out['level'] = (neg['level'] if 'level' in neg.columns
                    else out['scope'].map(lambda v: 'account' if v == 'ACCOUNT' else 'campaign'))
    out['level'] = out['level'].str.strip().str.lower()
    if not out['level'].isin(['account', 'shared list', 'campaign', 'ad group']).all():
        raise ValueError('Unknown negative level')
    if ((out['level'] == 'account') != (out['scope'] == 'ACCOUNT')).any():
        raise ValueError('Account negatives require level account and scope ACCOUNT')
    out['ad_group'] = neg['ad_group'].str.strip() if 'ad_group' in neg.columns else ''
    # Read earlier resolved files, which kept the ad-group name only in source.
    legacy = (out['level'] == 'ad group') & (out['ad_group'] == '')
    out.loc[legacy, 'ad_group'] = out.loc[legacy, 'source'].str.extract(r'^ad group: (.+)$', expand=False).fillna('')
    if ((out['level'] == 'ad group') & (out['ad_group'] == '')).any():
        raise ValueError('Ad-group negatives need an explicit ad_group; scope cannot be inferred')
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('str_csv')
    ap.add_argument('kw_csv')
    ap.add_argument('--negatives')
    ap.add_argument('--pattern', default='')
    ap.add_argument('--days', type=float, default=90)
    ap.add_argument('--out')
    ap.add_argument('--keyword-status-only', action='store_true')
    a = ap.parse_args()

    st, w = load(a.str_csv)
    kw, kw_w = load(a.kw_csv)
    missing_metrics = [c for c in REQUIRED_METRICS if c not in st.columns]
    if missing_metrics:
        ap.error(f'Search-term file lacks {", ".join(missing_metrics)}; re-export with Clicks, Cost, '
                 'Conversions, Impr. and Conv. value')
    for col in OPTIONAL_METRICS:
        if col not in st.columns:
            print(f'LIMIT: search-term file has no {col}; treated as 0')
    if 'status' not in kw.columns:
        ap.error('Keyword file has no keyword status column')
    missing_parent = [c for c in PARENT_STATUS if c not in kw.columns]
    if missing_parent and not a.keyword_status_only:
        ap.error(f'Keyword file lacks {", ".join(missing_parent)}: an enabled keyword in a paused '
                 'campaign or ad group would hide its terms. Use query 4 or add the status columns, '
                 'or pass --keyword-status-only and report the limit.')
    if missing_parent:
        print('LIMIT: keyword liveness from keyword status only; terms under paused campaigns or '
              'ad groups may be hidden as covered')
    if a.negatives:
        for label, frame in (('search-term', st), ('keyword', kw)):
            if 'campaign' not in frame.columns:
                ap.error(f'The {label} file has no campaign column, so campaign negatives cannot be checked')
    print('STR window:', w or 'not stated in file', '| keyword window:', kw_w or 'not stated in file')
    print('Visible STR cost:', round(st['cost'].sum(), 2))
    for t in totals(a.str_csv):
        print('  ', t[:160])
    if 'added_excluded' in st.columns:
        print('Added/Excluded values:', st['added_excluded'].astype(str).value_counts().to_dict())
    print('Campaigns in STR:', sorted(st['campaign'].astype(str).unique()) if 'campaign' in st else 'none')

    for col in ('status',) + PARENT_STATUS:
        if col in kw.columns:
            print(f'{col} values:', kw[col].astype(str).value_counts().to_dict())
    active, paused = keyword_sets(kw)
    g = aggregate(st, active, paused, a.days, enabled_campaigns(kw), off_locations(kw))
    blocked_kw = None
    if a.negatives:
        negatives = read_negatives(a.negatives)
        if (negatives.level == 'ad group').any():
            for label, frame in (('search-term', st), ('keyword', kw)):
                if 'ad_group' not in frame.columns:
                    ap.error(f'The {label} file has no ad group column, so ad-group negatives cannot be checked')
        g['blocked_by_existing_negative'], g['blocked_extent'] = blocked_by(g, negatives)
        blocked_kw = keywords_blocked(kw, negatives)
    else:
        g['blocked_by_existing_negative'] = 'not checked'
        g['blocked_extent'] = ''
        print('Existing negatives: not supplied, so blocking is unchecked')

    pd.set_option('display.width', 250)
    pd.set_option('display.max_colwidth', 60)
    pd.set_option('display.max_rows', 300)
    new = ~g.enabled_keyword
    tables = {
        'converting_not_keyword': g[(g.conv > 0) & new].sort_values('value', ascending=False),
        'paused_keyword_only': g[g.paused_keyword_only != ''].sort_values('cost', ascending=False),
        'non_converting_spend': g[g.conv == 0].sort_values('cost', ascending=False).head(200),
        'converting_keyword_missing_in_served_campaign':
            g[(g.conv > 0) & (g.served_without_keyword != '')].sort_values('value', ascending=False),
    }
    if a.pattern:
        theme = g.search_term.str.contains(a.pattern, regex=True)
        tables['theme_not_keyword'] = g[theme & new].sort_values(['clicks', 'impr'], ascending=False)
    if a.negatives:
        tables['blocked_by_negative'] = g[g.blocked_by_existing_negative != ''].sort_values('cost', ascending=False)
        tables['enabled_keywords_blocked_by_negative'] = blocked_kw
    for name, table in tables.items():
        print(f'\n== {name} ({len(table)} rows) ==')
        print(table.head(200).to_string() if len(table) else '(none)')
    if a.out:
        os.makedirs(a.out, exist_ok=True)
        sheet_safe(g).to_csv(os.path.join(a.out, 'search_terms_aggregated.csv'), index=False)
        for name, table in tables.items():
            sheet_safe(table).to_csv(os.path.join(a.out, name + '.csv'), index=False)
        print('\nWrote CSVs to', a.out)


if __name__ == '__main__':
    main()
