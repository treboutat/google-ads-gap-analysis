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
    python3 negative_match.py --negatives NEG.csv --queries QUERIES.txt [--scope CAMPAIGN]

The second form checks every negative in NEG.csv (text, match_type, campaign or
scope; resolve_negatives.py output plus your proposed rows) against every query in
QUERIES.txt (one per line: enabled keywords, GAP keywords, protected queries) and
prints each conflict. It exits 1 when a conflict exists.

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


def main(argv=None):
    import argparse
    import csv
    ap = argparse.ArgumentParser(description='Check which queries negative keywords block.')
    ap.add_argument('negative', nargs='?', help='one negative keyword')
    ap.add_argument('match', nargs='?', help='exact, phrase or broad')
    ap.add_argument('queries', nargs='*', help='queries to test')
    ap.add_argument('--negatives', help='CSV with text (or keyword), match_type and campaign or scope')
    ap.add_argument('--queries', dest='query_file', help='text file, one query per line')
    ap.add_argument('--scope', help='only negatives for this campaign or ACCOUNT count')
    a = ap.parse_args(argv)
    if a.negatives:
        if not a.query_file:
            ap.error('--negatives needs --queries')
        with open(a.negatives, newline='', encoding='utf-8-sig') as fh:
            rows = []
            for r in csv.DictReader(fh):
                r = {k.strip().lower(): v for k, v in r.items()}
                r['text'] = r.get('text') or r.get('keyword') or ''
                rows.append(r)
        with open(a.query_file, encoding='utf-8-sig') as fh:
            queries = [line.strip() for line in fh if line.strip()]
        try:
            found = conflicts(rows, queries, a.scope)
        except (KeyError, ValueError) as exc:
            ap.error(str(exc))
        for c in found:
            print(f"BLOCKED: {c['query']!r} by {c['negative']!r} ({c['match_type']}, {c['scope']})")
        print(f'{len(found)} conflicts across {len(rows)} negatives and {len(queries)} queries')
        return 1 if found else 0
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
