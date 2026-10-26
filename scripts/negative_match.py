"""Check which queries a negative keyword would block, using Google's negative rules.

Negatives do not expand to close variants, synonyms or plurals:
- exact:  the query is the same words in the same order, nothing added.
- phrase: the words appear together in that order; extra words before/after are fine.
- broad:  every negative word appears somewhere in the query, in any order.
Casing is ignored, and so are periods. Only a query's first 16 words count: Google
can still show the ad when the negative matches only after the 16th word. Google
also says negatives account for misspellings, which this check cannot model, and
minus-prefixed words in negatives are ignored (dark -chocolate means dark).
Internal hyphens, apostrophes and other punctuation are compared literally. A clean result is
necessary, not sufficient: check near-misspellings and punctuation by hand.

    python3 negative_match.py "acme login" phrase "acme login help" "acme pricing"
    python3 negative_match.py --negatives NEG.csv --queries QUERIES.csv
    python3 negative_match.py --negatives NEG.csv --queries QUERIES.txt --scope CAMPAIGN [--ad-group GROUP]

Bulk inputs: NEG.csv uses text (or keyword), match_type, campaign (or scope),
and ad_group/level for ad-group negatives, as resolve_negatives.py writes.
QUERIES.csv uses query (or text/keyword), campaign and ad_group: preserve each
keyword's or protected query's actual/proposed destination, including repeated
text in different destinations. Plain text is one query per line and requires
--scope; add --ad-group if that campaign has ad-group negatives. Missing scope,
columns or values stop the check, rather than becoming an empty or global check.
Only inherited negatives and the destination's own ad-group negatives apply.
An indexed lookup prints each conflict and exits 1; clean checks exit 0, input
errors exit 2. A header-only negative inventory is allowed; no queries is an error.

    from negative_match import blocks, conflicts
    blocks('acme login', 'exact', 'acme login')              # True
    conflicts(negatives, ['acme pricing', 'acme cost'])      # rows that would block them

`negatives` rows are dicts with text, match_type and scope (a campaign name or
'ACCOUNT'); a `campaign` key, as resolve_negatives.py writes, also works as scope.
"""
import re

_MATCH = {'exact': 'exact', 'negative exact': 'exact', 'campaign negative exact': 'exact',
          'phrase': 'phrase', 'negative phrase': 'phrase', 'campaign negative phrase': 'phrase',
          'broad': 'broad', 'negative broad': 'broad', 'campaign negative broad': 'broad'}


def _tokens(text):
    text = str(text).lower().strip().replace('.', '')  # Google ignores periods.
    text = re.sub(r'^\[(.*)\]$', r'\1', text)
    text = re.sub(r'(?<!\S)\+(?=\w)', '', text.strip('"\''))
    return text.split()


def _query(text):
    return _tokens(text)[:16]  # Google ignores negatives that only match past word 16.


def _negative_tokens(text):
    # A minus is an operator only at the start of a negative word. Do not apply
    # this rule to the user's query or to internal hyphens such as sugar-free.
    return [token for token in _tokens(text) if not token.startswith('-')]


def match_type(value):
    key = re.sub(r'\s+', ' ', str(value).lower().replace('_', ' ')).strip()
    if key.endswith(' match'):
        key = key[:-6]
    if key not in _MATCH:
        raise ValueError(f'Unknown negative match type: {value!r}')
    return _MATCH[key]


def blocks(negative, kind, query):
    neg, q = _negative_tokens(negative), _query(query)
    if not neg:
        return False
    kind = match_type(kind)
    if kind == 'exact':
        return neg == q
    if kind == 'phrase':
        n = len(neg)
        return any(q[i:i + n] == neg for i in range(len(q) - n + 1))
    return set(neg) <= set(q)


class NegativeIndex:
    """Fast lookup for many negatives against many queries (real accounts hold tens of
    thousands of shared-list rows). Each negative is filed under its first word; a query
    only checks the negatives filed under its own words, with the same rules as blocks()."""

    def __init__(self, rows):
        self.by_word = {}
        for row in rows:
            neg = _negative_tokens(row['text'])
            if neg:
                self.by_word.setdefault(neg[0], []).append((neg, match_type(row['match_type']), row))

    def hits(self, query, scopes=None):
        q = _query(query)
        found, qset = [], set(q)
        for word in qset:
            for neg, kind, row in self.by_word.get(word, ()):
                if scopes is not None and (row.get('scope') or row.get('campaign') or 'ACCOUNT') not in scopes:
                    continue
                if kind == 'exact':
                    ok = neg == q
                elif kind == 'phrase':
                    n = len(neg)
                    ok = any(q[i:i + n] == neg for i in range(len(q) - n + 1))
                else:
                    ok = set(neg) <= qset
                if ok:
                    found.append(row)
        return found


def conflicts(negatives, queries, scope=None):
    """Rows (negative, match_type, scope, query) where a negative blocks a query.

    With scope set, only negatives whose scope is that campaign or 'ACCOUNT' count.
    """
    out = []
    for row in negatives:
        row_scope = row.get('scope') or row.get('campaign') or 'ACCOUNT'
        if scope is not None and row_scope not in (scope, 'ACCOUNT'):
            continue
        for q in queries:
            if blocks(row['text'], row['match_type'], q):
                out.append({'negative': row['text'], 'match_type': match_type(row['match_type']),
                            'scope': row_scope, 'query': q})
    return out


def scoped_conflicts(negatives, queries):
    """Check normalized negatives against query/destination records, using the index."""
    local_campaigns = {r['campaign'] for r in negatives if r.get('ad_group')}
    index = NegativeIndex(negatives)
    out = []
    for query in queries:
        campaign, group = query['campaign'], query.get('ad_group', '')
        if not group and campaign in local_campaigns:
            raise ValueError(f'Query {query["query"]!r} in {campaign!r} needs ad_group: '
                             'the current inventory includes ad-group negatives')
        for row in index.hits(query['query'], {campaign, 'ACCOUNT'}):
            if row.get('ad_group') and row['ad_group'] != group:
                continue
            out.append({'negative': row['text'], 'match_type': match_type(row['match_type']),
                        'scope': row['campaign'], 'ad_group': row.get('ad_group', ''),
                        'level': row.get('level', ''), 'source': row.get('source', ''),
                        'query': query['query'], 'query_campaign': campaign, 'query_ad_group': group})
    return out


def _read_csv(path):
    import csv
    with open(path, newline='', encoding='utf-8-sig') as fh:
        reader = csv.DictReader(fh, strict=True)
        headers = [re.sub(r'\s+', '_', k.strip().lower()) for k in (reader.fieldnames or [])]
        if not headers or any(not k for k in headers) or len(set(headers)) != len(headers):
            raise ValueError(f'{path}: needs nonempty, unique CSV column names')
        rows = []
        for number, row in enumerate(reader, start=2):
            if None in row or any(v is None for v in row.values()):
                raise ValueError(f'{path}: row {number} does not match the header width')
            rows.append(dict(zip(headers, (v.strip() for v in row.values()))))
    return set(headers), rows


def _alias(row, *names):
    values = {row[name] for name in names if row.get(name)}
    if len(values) > 1:
        raise ValueError(f'Conflicting values for {" / ".join(names)}')
    return next(iter(values), '')


def read_negative_rows(path):
    headers, rows = _read_csv(path)
    if (not headers.intersection({'text', 'keyword'}) or 'match_type' not in headers
            or not headers.intersection({'campaign', 'scope'})):
        raise ValueError(f'{path}: expected text (or keyword), match_type and campaign (or scope) columns')
    out = []
    for number, row in enumerate(rows, start=2):
        text, campaign = _alias(row, 'text', 'keyword'), _alias(row, 'campaign', 'scope')
        if not text or not campaign:
            raise ValueError(f'{path}: row {number} needs negative text and campaign/scope')
        group = row.get('ad_group', '')
        level = row.get('level', '').lower().replace('_', ' ')
        level = level or ('account' if campaign == 'ACCOUNT' else 'ad group' if group else 'campaign')
        if level not in ('account', 'campaign', 'shared list', 'ad group'):
            raise ValueError(f'{path}: row {number} has unknown negative level {level!r}')
        if ((level == 'account') != (campaign == 'ACCOUNT')
                or (level == 'ad group') != bool(group)):
            raise ValueError(f'{path}: row {number} has inconsistent campaign, ad_group or level')
        out.append({'text': text, 'match_type': match_type(row['match_type']),
                    'campaign': campaign, 'ad_group': group, 'level': level,
                    'source': row.get('source', '')})
    return out


def read_query_rows(path, scope=None, ad_group=None):
    from pathlib import Path
    if Path(path).suffix.lower() == '.csv':
        if scope is not None or ad_group is not None:
            raise ValueError('CSV queries carry their own destination; --scope/--ad-group are for text files')
        headers, rows = _read_csv(path)
        if not headers.intersection({'query', 'text', 'keyword'}) or 'campaign' not in headers:
            raise ValueError(f'{path}: expected query (or text/keyword), campaign and optional ad_group columns')
        queries = [{'query': _alias(r, 'query', 'text', 'keyword'), 'campaign': r['campaign'],
                    'ad_group': r.get('ad_group', '')} for r in rows]
    else:
        if not scope or not scope.strip():
            raise ValueError('Plain-text queries need --scope CAMPAIGN; use a query CSV for multiple destinations')
        with open(path, encoding='utf-8-sig') as fh:
            queries = [{'query': line.strip(), 'campaign': scope.strip(), 'ad_group': (ad_group or '').strip()}
                       for line in fh if line.strip()]
    if not queries:
        raise ValueError(f'{path}: no queries found; no protected demand was checked')
    if any(not q['query'] or not q['campaign'] or q['campaign'] == 'ACCOUNT' for q in queries):
        raise ValueError(f'{path}: every query needs text and its actual destination campaign')
    return queries


def main(argv=None):
    import argparse
    import csv
    ap = argparse.ArgumentParser(description='Check which queries negative keywords block.')
    ap.add_argument('negative', nargs='?', help='one negative keyword')
    ap.add_argument('match', nargs='?', help='exact, phrase or broad')
    ap.add_argument('queries', nargs='*', help='queries to test')
    ap.add_argument('--negatives', help='CSV with text (or keyword), match_type and campaign or scope')
    ap.add_argument('--queries', dest='query_file', help='query CSV with destinations, or text file with --scope')
    ap.add_argument('--scope', help='destination campaign for plain-text queries')
    ap.add_argument('--ad-group', help='destination ad group for plain-text queries')
    a = ap.parse_args(argv)
    if a.negatives:
        if not a.query_file:
            ap.error('--negatives needs --queries')
        if a.negative or a.match or a.queries:
            ap.error('give either NEGATIVE MATCH QUERY ... or --negatives/--queries, not both')
        try:
            rows = read_negative_rows(a.negatives)
            queries = read_query_rows(a.query_file, a.scope, a.ad_group)
            found = scoped_conflicts(rows, queries)
        except (OSError, UnicodeError, csv.Error, ValueError) as exc:
            ap.error(str(exc))
        for c in found:
            destination = f"{c['query_campaign']} / {c['query_ad_group']}"
            negative_scope = c['scope'] + (f" / {c['ad_group']}" if c['ad_group'] else '')
            print(f"BLOCKED: {c['query']!r} at {destination} by {c['negative']!r} "
                  f"({c['match_type']}, {negative_scope}, {c['source'] or c['level']})")
        print(f'{len(found)} conflicts across {len(rows)} negatives and {len(queries)} queries')
        return 1 if found else 0
    if a.query_file or a.scope is not None or a.ad_group is not None:
        ap.error('--queries/--scope/--ad-group need --negatives')
    if not (a.negative and a.match and a.queries):
        ap.error('give NEGATIVE MATCH QUERY [QUERY ...], or --negatives and --queries')
    try:
        for q in a.queries:
            print(f'{q!r}: {"BLOCKED" if blocks(a.negative, a.match, q) else "eligible"}')
    except ValueError as exc:
        ap.error(str(exc))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
