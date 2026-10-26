"""Export only reviewed Exclude rows to a clean campaign-negative Editor CSV.

    python3 export_negative_verdicts.py REVIEW.csv --customer-id 123-456-7890 --out neg_upload_1234567890.csv

Review columns: text, match_type, campaign, verdict; optional ad_group, level.
Verdicts: Exclude, Keep relevant, Keep unsure, or blank (pending). Explicit negative
match types are preserved. Account/shared-list/ad-group changes need their own
separately scoped upload and are refused here, not widened to campaigns.
Editor rows match campaigns by name in whatever account is open, so the customer ID
is required: it must match any customer_id column in the review and must appear in
the --out file name, and the reviewer confirms Editor's open account before import. Text
Editor would reject as a keyword (a leading '-', or , ! @ % ^ ( ) = { } ; ~ ` < > ? \\ |)
stops the export. Keyword text
loses match notation ([x], "x") and a leading apostrophe added to neutralize a
spreadsheet formula. This produces a file only; it grants no authority to import it.
"""
import argparse
import csv
import re

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # also under python -I
from load_ads_export import load  # noqa: E402
from negative_match import match_type  # noqa: E402

FIELDS = ['Campaign', 'Ad group', 'Keyword', 'Criterion Type']
VERDICTS = {'exclude', 'keep relevant', 'keep unsure', ''}


INVALID = re.compile(r'[,!@%^()={};~`<>?\\|]')


def _clean(text):
    if text[:1] == "'" and text[1:2] in ('=', '+', '-', '@'):
        text = text[1:]
    if len(text) > 1 and (text[0], text[-1]) in (('[', ']'), ('"', '"')):
        text = text[1:-1].strip()
    return text


def export_rows(review, customer_id=None):
    missing = {'text', 'match_type', 'campaign', 'verdict'} - set(review.columns)
    if missing:
        raise ValueError(f'Missing review columns: {", ".join(sorted(missing))}')
    out = []
    for row in review.to_dict('records'):
        verdict = ' '.join(str(row['verdict']).replace(',', ' ').split()).lower()  # 'Keep, unsure' too
        if verdict not in VERDICTS:
            raise ValueError(f'Unknown reviewer verdict: {row["verdict"]!r}')
        if verdict != 'exclude':
            continue
        campaign, text = str(row['campaign']).strip(), _clean(str(row['text']).strip())
        row_cid = re.sub(r'\D', '', str(row.get('customer_id', '')))
        if customer_id and row_cid and row_cid != customer_id:
            raise ValueError(f'Exclude row for customer {row_cid}, export is for {customer_id}')
        if not campaign or not text:
            raise ValueError('An Exclude row needs campaign and text')
        if text.startswith('-') or INVALID.search(text):
            raise ValueError(f'Keyword text Editor would reject: {text!r}')
        level = str(row.get('level') or 'campaign').strip().lower()
        if level != 'campaign' or str(row.get('ad_group', '')).strip() or campaign == 'ACCOUNT':
            raise ValueError('Only campaign negatives supported here; upload narrower or shared-list scope separately')
        kind = match_type(row['match_type']).title()
        out.append({'Campaign': campaign, 'Ad group': '', 'Keyword': text,
                    'Criterion Type': f'Campaign Negative {kind}'})
    identities = [(row['Campaign'], row['Keyword'].lower(), row['Criterion Type']) for row in out]
    if len(set(identities)) != len(identities):
        raise ValueError('Duplicate approved negative operations')
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('review')
    ap.add_argument('--customer-id', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    cid = re.sub(r'\D', '', args.customer_id)
    if len(cid) != 10:
        ap.error('--customer-id must be the 10-digit Google Ads customer ID')
    if cid not in re.sub(r'\D', '', os.path.basename(args.out)):
        ap.error(f'--out file name must carry the customer ID, e.g. neg_upload_{cid}.csv')
    try:
        review, _ = load(args.review)
        rows = export_rows(review, cid)
    except ValueError as exc:
        ap.error(str(exc))
    with open(args.out, 'w', newline='', encoding='utf-8') as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f'{len(rows)} Exclude rows exported for customer {cid[:3]}-{cid[3:6]}-{cid[6:]}; '
          'Keep and pending rows omitted. Confirm Editor has that account open before import.')


if __name__ == '__main__':
    main()
