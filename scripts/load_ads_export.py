"""Load Google Ads report rows into one normalized table.

Accepts the three shapes a gap analysis meets:
- Google Ads UI exports (UTF-16 or UTF-8, tab or comma separated, title rows above
  the header, 'Total:' footer rows).
- GAQL CSV from the Google Ads API or any tool that runs GAQL
  (`search_term_view.search_term`, `metrics.cost_micros`, ...).
- Plain CSV already using the normalized names below.

    from load_ads_export import load, totals
    df, window = load('Search_terms_report.csv')

Normalized columns (present when the source has them): search_term, keyword,
match_type, search_term_match_type, keyword_match_type, status, campaign, campaign_id,
campaign_status, ad_group, ad_group_id, ad_group_status, added_excluded, negative,
impressions, clicks, cost, conversions, conv_value, all_conversions, all_conv_value.
Metric columns are always numeric; '--' and blanks become 0. Text such as 'None'
stays text, so filter values like Added/Excluded = None remain visible. When two source
columns map to one name, the alias listed first below takes it (so 'Keyword status' beats
the UI serving 'Status'); the other keeps its own header, suffixed if that is taken.
"""
import csv
import io
import re

import pandas as pd

ALIASES = {
    'search_term': ['search term', 'search_term_view.search_term', 'search_term'],
    'keyword': ['keyword', 'search keyword', 'negative keyword', 'campaign_criterion.keyword.text',
                'shared_criterion.keyword.text', 'ad_group_criterion.keyword.text',
                'segments.keyword.info.text', 'keyword_text'],
    'match_type': ['match type', 'campaign_criterion.keyword.match_type',
                   'shared_criterion.keyword.match_type', 'ad_group_criterion.keyword.match_type',
                   'match_type'],
    # Query 5 carries both; keep them apart (the search-term label is not the keyword's type).
    'search_term_match_type': ['segments.search_term_match_type', 'search terms match type',
                               'search_term_match_type'],
    'keyword_match_type': ['segments.keyword.info.match_type', 'keyword match type',
                           'keyword_match_type'],
    'negative': ['negative', 'ad_group_criterion.negative', 'campaign_criterion.negative'],
    'shared_set_id': ['shared_set.id', 'shared set id', 'shared_set_id'],
    'shared_set_name': ['shared_set.name', 'negative keyword list', 'list name', 'shared_set_name'],
    'conversion_action': ['segments.conversion_action_name', 'conversion action', 'conversion_action'],
    'all_conversions': ['metrics.all_conversions', 'all conv.', 'all_conversions'],
    'all_conv_value': ['metrics.all_conversions_value', 'all conv. value', 'all_conv_value'],
    'status': ['keyword status', 'ad_group_criterion.status', 'status'],
    'level': ['level'],
    'campaign': ['campaign', 'campaign.name', 'campaign_name'],
    'campaign_id': ['campaign id', 'campaign.id', 'campaign_id'],
    'campaign_status': ['campaign status', 'campaign.status', 'campaign_status'],
    'ad_group': ['ad group', 'ad_group.name', 'ad_group_name'],
    'ad_group_id': ['ad group id', 'ad_group.id', 'ad_group_id'],
    'ad_group_status': ['ad group status', 'ad_group.status', 'ad_group_status'],
    'added_excluded': ['added/excluded', 'search_term_view.status'],
    'impressions': ['impr.', 'impressions', 'metrics.impressions'],
    'clicks': ['clicks', 'metrics.clicks'],
    'cost': ['cost', 'metrics.cost'],
    'cost_micros': ['metrics.cost_micros', 'cost_micros'],
    'conversions': ['conversions', 'conv.', 'metrics.conversions'],
    'conv_value': ['conv. value', 'conversion value', 'metrics.conversions_value', 'conv_value'],
}
METRICS = ('impressions', 'clicks', 'cost', 'conversions', 'conv_value',
           'all_conversions', 'all_conv_value')
_LOOKUP = {alias: name for name, aliases in ALIASES.items() for alias in aliases}
_FOOTER = re.compile(r'Total:')


def _read(path):
    with open(path, 'rb') as fh:
        raw = fh.read()
    encodings = ('utf-16',) if raw[:2] in (b'\xff\xfe', b'\xfe\xff') else ('utf-8-sig', 'utf-16', 'latin-1')
    for enc in encodings:
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise ValueError(f'Cannot decode {path}')


def _header_index(lines):
    """First line that names at least two known columns; title rows sit above it."""
    for i, line in enumerate(lines[:15]):
        sep = '\t' if '\t' in line else ','
        cells = [c.strip().strip('"').lower() for c in next(csv.reader([line], delimiter=sep))]
        if sum(c in _LOOKUP for c in cells) >= 2:
            return i, sep
    raise ValueError('No recognizable header row in the first 15 lines')


def _number(series):
    text = series.astype(str).str.replace(',', '', regex=False).str.replace('%', '', regex=False)
    text = text.str.replace(r'[^\d.\-eE]', '', regex=True).str.strip()
    return pd.to_numeric(text.replace({'': '0', '-': '0', '--': '0'}), errors='coerce').fillna(0.0)


def normalize_text(value):
    """Lowercase, collapse spaces, drop match-type punctuation ([x], "x", +x) and stray end quotes."""
    text = str(value).strip().lower()
    text = re.sub(r'^\[(.*)\]$', r'\1', text)
    text = text.strip('"\'')  # also stray quotes left in malformed keywords
    text = re.sub(r'(?<!\S)\+(?=\w)', '', text)  # legacy BMM prefix; preserve C++
    return re.sub(r'\s+', ' ', text).strip()


def _rank(raw):
    name = _LOOKUP.get(raw.lower())
    return ALIASES[name].index(raw.lower()) if name else 0


def _names(raw):
    """Normalized names; on a collision the earlier-listed alias wins, the rest keep
    their own header (suffixed __2, __3 if that is taken too). Nothing is dropped."""
    winners = {}
    for i, c in enumerate(raw):
        name = _LOOKUP.get(c.lower())
        if name and (name not in winners or _rank(c) < _rank(raw[winners[name]])):
            winners[name] = i
    names = [None] * len(raw)
    for name, i in winners.items():
        names[i] = name
    for i, c in enumerate(raw):
        if names[i] is None:
            name, n = c, 2
            while name in names or name in winners:
                name, n = f'{c}__{n}', n + 1
            names[i] = name
    return names


def load(path):
    lines = _read(path).replace('\r\n', '\n').split('\n')
    start, sep = _header_index(lines)
    window = ' '.join(l.strip().strip('"') for l in lines[:start] if l.strip())
    df = pd.read_csv(io.StringIO('\n'.join(lines[start:])), sep=sep, dtype=str,
                     keep_default_na=False)
    first = df.iloc[:, 0].astype(str)
    df = df[~first.str.match(_FOOTER)].copy()  # 'Total: Account', not a term like 'Total care'
    df.columns = _names([c.strip() for c in df.columns])
    if 'cost_micros' in df.columns and 'cost' not in df.columns:
        df['cost'] = _number(df.pop('cost_micros')) / 1_000_000
    for col in METRICS:
        if col in df.columns:
            df[col] = _number(df[col])
    for col in ('search_term', 'keyword'):
        if col in df.columns:
            df[col + '_norm'] = df[col].map(normalize_text)
    return df.reset_index(drop=True), window


def totals(path):
    """The export's own 'Total:' rows, for reconciling visible vs reported spend."""
    return [l for l in _read(path).split('\n') if _FOOTER.match(l.lstrip('"'))]


if __name__ == '__main__':
    import sys
    df, w = load(sys.argv[1])
    print(w, df.shape)
    print(df.head())
    for t in totals(sys.argv[1]):
        print(t[:200])
