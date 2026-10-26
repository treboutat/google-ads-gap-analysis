"""Validate RSA field limits and uniqueness.

    python3 validate_rsa.py rsa_upload.csv     # Editor layout: Headline 1-15, Description 1-4, Path 1, Path 2

    from validate_rsa import validate, display_len
    problems = validate(headlines, descriptions, path1, path2)   # [] when clean

The command checks every row, prints each problem with its row, campaign and ad
group, and exits 1 when any row has a problem. Malformed CSV, duplicate or empty
column names, unrecognized asset columns, missing upload columns (Campaign, Ad
group, Ad type, Headline 1-3, Description 1-2, Final URL, Status) and inconsistent
row widths are input errors (exit 2). Each row must be a Paused "Responsive search
ad" with a final URL.

Keyword insertion ({KeyWord:Fallback}) is measured on its fallback text, wherever it
sits in the asset. Double-width characters count twice, as Google counts them. Other
dynamic tokens ({LOCATION(City)}, {CUSTOMIZER...}, {COUNTDOWN...}) cannot be measured
here and are reported for a manual check.
"""
import re
import unicodedata

_DKI = re.compile(r'\{keyword:([^}]*)\}', re.I)
_ASSET = re.compile(r'^(headline|description|path)\b', re.I)
ASSET_COLUMNS = ({f'Headline {n}' for n in range(1, 16)} | {f'Description {n}' for n in range(1, 5)}
                 | {'Path 1', 'Path 2'})
REQUIRED_COLUMNS = ['Campaign', 'Ad group', 'Ad type', 'Headline 1', 'Headline 2', 'Headline 3',
                    'Description 1', 'Description 2', 'Final URL', 'Status']
_OTHER = re.compile(r'\{(?!keyword:)[^}]*\}', re.I)


def display_len(text):
    text = _DKI.sub(lambda m: m.group(1), str(text))
    return sum(2 if unicodedata.east_asian_width(ch) in ('W', 'F') else 1 for ch in text)


def _blank(x):
    return x is None or x != x or not str(x).strip()  # x != x: NaN from an empty sheet cell


def validate(H, D, p1='', p2=''):
    out = [f'blank {kind}' for kind, xs in (('headline', H), ('description', D))
           for x in xs if _blank(x)]
    H = [str(h) for h in H if not _blank(h)]  # blanks never count toward the minimums
    D = [str(d) for d in D if not _blank(d)]
    p1, p2 = ('' if _blank(p) else str(p) for p in (p1, p2))
    if not 3 <= len(H) <= 15:
        out.append(f'{len(H)} headlines (3-15)')
    if not 2 <= len(D) <= 4:
        out.append(f'{len(D)} descriptions (2-4)')
    if len({h.strip().lower() for h in H}) != len(H):
        out.append('duplicate headline')
    if len({d.strip().lower() for d in D}) != len(D):
        out.append('duplicate description')
    out += [f'headline >30: {h} ({display_len(h)})' for h in H if display_len(h) > 30]
    out += [f'description >90: {d} ({display_len(d)})' for d in D if display_len(d) > 90]
    out += [f'path >15: {p} ({display_len(p)})' for p in (p1, p2) if display_len(p) > 15]
    out += [f'dynamic token needs manual length check: {x}' for x in list(H) + list(D) if _OTHER.search(x)]
    out += [f'empty keyword-insertion fallback: {x}' for x in list(H) + list(D)
            if any(not m.group(1).strip() for m in _DKI.finditer(x))]
    return out


def main(argv=None):
    import argparse
    import csv
    ap = argparse.ArgumentParser(description='Validate RSA rows in an Editor-layout CSV.')
    ap.add_argument('csv_file')
    a = ap.parse_args(argv)
    try:
        with open(a.csv_file, newline='', encoding='utf-8-sig') as fh:
            reader = csv.DictReader(fh, strict=True)
            fields = [f.strip() for f in (reader.fieldnames or [])]
            if (not fields or any(not f for f in fields)
                    or len({f.casefold() for f in fields}) != len(fields)):
                ap.error('expected nonempty, unique CSV column names')
            reader.fieldnames = fields
            rows = list(reader)
    except (OSError, UnicodeError, csv.Error) as exc:
        ap.error(str(exc))
    unknown = [f for f in fields if _ASSET.match(f) and f not in ASSET_COLUMNS]
    if unknown:
        ap.error(f'unrecognized asset columns: {", ".join(unknown)}; use Headline 1-15, '
                 'Description 1-4, Path 1, Path 2')
    if not rows:
        ap.error('no RSA rows found')
    # An unquoted comma shifts every later asset; never validate a shifted row.
    for i, r in enumerate(rows, start=2):
        if None in r or any(v is None for v in r.values()):
            ap.error(f'row {i} does not match the header width; quote fields that contain commas')
    missing = [f for f in REQUIRED_COLUMNS if f not in fields]
    if missing:
        ap.error(f'not an importable RSA upload: missing {", ".join(missing)}')
    bad = 0
    for i, r in enumerate(rows, start=2):
        H = [r.get(f'Headline {n}') for n in range(1, 16)]
        D = [r.get(f'Description {n}') for n in range(1, 5)]
        H = [h for h in H if h is not None and h.strip()]  # unused slots are blank in Editor files
        D = [d for d in D if d is not None and d.strip()]
        problems = validate(H, D, r.get('Path 1', ''), r.get('Path 2', ''))
        problems += [f'blank {f}' for f in ('Campaign', 'Ad group', 'Final URL') if not r[f].strip()]
        if r['Ad type'].strip().casefold() != 'responsive search ad':
            problems.append(f"ad type {r['Ad type']!r} (expected Responsive search ad)")
        if r['Status'].strip().casefold() != 'paused':
            problems.append(f"status {r['Status']!r} (new RSAs upload Paused)")
        where = f"row {i} ({r.get('Campaign', '')} / {r.get('Ad group', '')})"
        for problem in problems:
            print(f'{where}: {problem}')
        bad += bool(problems)
    print(f'{len(rows)} RSAs checked, {bad} with problems')
    return 1 if bad else 0


if __name__ == '__main__':
    raise SystemExit(main())

