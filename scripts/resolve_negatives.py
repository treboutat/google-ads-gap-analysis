"""Resolve current negatives from GAQL CSVs or English Google Ads UI exports.

    python3 resolve_negatives.py --out negatives_resolved.csv
        [--campaign CAMPAIGN_NEG.csv] [--shared SHARED.csv --attachments ATTACHMENTS.csv]
        [--ad-group AD_GROUP_NEG.csv] [--account ACCOUNT_NEG.csv [--account-attachments CUSTOMER_NEG.csv]]

--campaign, --ad-group and --account accept dedicated negative reports. Mixed
criterion inventories must include a negative boolean, so positives are filtered.
Every report needs a match-type column: CSV parsing strips the quotes of "phrase"
notation, so the type cannot be read back from the text. A report with a Level column
must match the input it is given; a mixed-level report is split first, never widened.
Shared lists require their enabled campaign attachments. An account-level list
applies only when attached to the customer (customer_negative_criterion): a GAQL
account export carries shared_set.id and then needs --account-attachments; rows from a
list that is not attached are reported and left out. Ad-group identity stays explicit in the output.
Rows with removed campaigns or ad groups are omitted when parent statuses are
present. Paused parents are retained for reactivation planning.
"""
import argparse
import csv
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from load_ads_export import _read, load  # noqa: E402
from negative_match import match_type  # noqa: E402


def _rows(path, required):
    df, _ = load(path)
    missing = set(required) - set(df.columns)
    if missing:
        hint = ('; add the Match type column to the export (phrase quotes do not survive CSV parsing)'
                if 'match_type' in missing else '')
        raise ValueError(f'{path}: missing columns: {", ".join(sorted(missing))}{hint}')
    return df.to_dict('records')


def _required(row, name, path):
    value = str(row.get(name, '')).strip()
    if not value:
        raise ValueError(f'{path}: blank {name}; cannot establish negative scope')
    return value


def _negative(row, path):
    if 'negative' not in row:
        return True  # Dedicated negative report supplied to an explicit negative input.
    value = str(row['negative']).strip().lower()
    if value not in ('true', 'false'):
        raise ValueError(f'{path}: invalid negative boolean {value!r}')
    return value == 'true'


def _negative_row(row, path, level, source, campaign=None):
    text = _required(row, 'keyword', path)
    row_level = str(row.get('level', '')).strip().lower()
    if row_level and level != 'shared list' and row_level != level:
        raise ValueError(f'{path}: a {row_level!r} row was supplied as {level} negatives; '
                         'split the report by level')
    kind = match_type(_required(row, 'match_type', path)).upper()
    return {'text': text, 'match_type': kind,
            'campaign': campaign if campaign is not None else _required(row, 'campaign', path),
            'ad_group': _required(row, 'ad_group', path) if level == 'ad group' else '',
            'level': level, 'source': source}


ACCOUNT_LINK = 'customer_negative_criterion.negative_keyword_list.shared_set'


def _account_lists(path):
    """Shared-set IDs attached to the customer, from customer_negative_criterion."""
    ids = set()
    text = _read(path)  # one GAQL column, so load()'s two-known-header detection does not apply
    sep = '\t' if '\t' in text.split('\n', 1)[0] else ','
    rows = [{k.strip().lower(): v for k, v in r.items()}
            for r in csv.DictReader(io.StringIO(text), delimiter=sep)]
    for row in rows:
        row['shared_set_id'] = row.get('shared_set.id', '')
        value = str(row.get(ACCOUNT_LINK) or row.get('shared_set_id') or '').strip()
        if not value:
            raise ValueError(f'{path}: needs {ACCOUNT_LINK} or shared_set.id')
        ids.add(value.rsplit('/', 1)[-1])  # customers/1/sharedSets/42 -> 42
    return ids


def resolve(campaign=None, shared=None, attachments=None, ad_group=None, account=None,
            account_attachments=None):
    out, unattached = [], []
    for path, level in ((campaign, 'campaign'), (ad_group, 'ad group'), (account, 'account')):
        if not path:
            continue
        rows = _rows(path, ('keyword', 'match_type'))
        linked = None
        if level == 'account' and any(str(r.get('shared_set_id', '')).strip() for r in rows):
            if not account_attachments:
                raise ValueError('--account rows name a shared list; supply --account-attachments '
                                 '(customer_negative_criterion) so an unattached list is not applied')
            linked = _account_lists(account_attachments)
        for row in rows:
            # Query 4 can return an enabled negative under a removed parent.
            # Historical STR placements do not make that exclusion effective.
            if (str(row.get('campaign_status', '')).strip().lower() == 'removed'
                    or (level == 'ad group'
                        and str(row.get('ad_group_status', '')).strip().lower() == 'removed')):
                continue
            if linked is not None and str(row.get('shared_set_id', '')).strip() not in linked:
                unattached.append(str(row.get('shared_set_name') or row.get('shared_set_id')))
                continue
            if _negative(row, path):
                out.append(_negative_row(row, path, level, f'{level} negative',
                                         'ACCOUNT' if level == 'account' else None))
    if shared:
        if not attachments:
            raise ValueError('--shared needs --attachments: list creation does not apply a list')
        links, lists = _rows(attachments, ('campaign',)), _rows(shared, ('keyword', 'match_type'))
        # Join on IDs when both files carry them, on names when neither does. A file
        # with IDs against one without would match nothing and read as "not applied".
        has_id = [any(str(r.get('shared_set_id', '')).strip() for r in rows) for rows in (links, lists)]
        has_name = [any(str(r.get('shared_set_name', '')).strip() for r in rows) for rows in (links, lists)]
        if has_id[0] and has_id[1]:
            field = 'shared_set_id'
        elif all(has_name) or not lists:
            field = 'shared_set_name'  # IDs on one side only: names are the common key
        else:
            raise ValueError('Shared lists and attachments share no list identity: give both '
                             'shared_set.id or both list names')
        attached = {}
        for row in links:
            key = str(row.get(field) or '').strip()
            if not key:
                raise ValueError(f'{attachments}: missing shared-list ID or name')
            attached.setdefault(key, set()).add(_required(row, 'campaign', attachments))
        for row in lists:
            key = str(row.get(field) or '').strip()
            if not key:
                raise ValueError(f'{shared}: missing shared-list ID or name')
            name = row.get('shared_set_name') or key
            # Match by stable ID when provided on both reports. Never broaden an
            # ID mismatch through a coincidentally identical list name.
            campaigns = attached.get(key, set())
            if not campaigns:
                unattached.append(name)
            for dest in sorted(campaigns):
                out.append(_negative_row(row, shared, 'shared list', name, dest))
    return out, sorted(set(unattached))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--campaign')
    ap.add_argument('--shared')
    ap.add_argument('--attachments')
    ap.add_argument('--ad-group')
    ap.add_argument('--account')
    ap.add_argument('--account-attachments')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    if not any((a.campaign, a.shared, a.ad_group, a.account)):
        ap.error('Supply at least one negative report; no input is not a checked empty inventory')
    if a.shared and not a.attachments:
        ap.error('--shared needs --attachments: a list only blocks searches in campaigns it is attached to')
    try:
        rows, unattached = resolve(a.campaign, a.shared, a.attachments, a.ad_group, a.account,
                                   a.account_attachments)
    except ValueError as exc:
        ap.error(str(exc))
    with open(a.out, 'w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=['text', 'match_type', 'campaign', 'ad_group', 'level', 'source'])
        w.writeheader()
        w.writerows(rows)
    by_level = {}
    for row in rows:
        by_level[row['level']] = by_level.get(row['level'], 0) + 1
    print(f'{len(rows)} scoped negative rows written to {a.out}: {by_level}')
    if unattached:
        print('Shared lists with no matching enabled attachment (not applied):', ', '.join(unattached))


if __name__ == '__main__':
    main()
