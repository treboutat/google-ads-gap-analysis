"""Offline regressions for the gap-analysis skill scripts (fictional fixtures only)."""
import csv
import importlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
load_ads_export = importlib.import_module("load_ads_export")
negative_match = importlib.import_module("negative_match")
validate_rsa = importlib.import_module("validate_rsa")
resolve_negatives = importlib.import_module("resolve_negatives")
gap_candidates = importlib.import_module("gap_candidates")
join_conversion_actions = importlib.import_module("join_conversion_actions")
export_negative_verdicts = importlib.import_module("export_negative_verdicts")
import pandas as pd

UI_STR = "\n".join([
    "Search terms report",
    '"July 27, 2026 - October 24, 2026"',
    "Search term\tMatch type\tAdded/Excluded\tCampaign\tAd group\tKeyword\tImpr.\tClicks\tCost\tConversions\tConv. value",
    "acme pricing\tExact match (close variant)\tNone\tNB - Pricing\tPricing\t[acme price]\t120\t14\t1,210.50\t2.00\t500.00",
    "Acme  Pricing\tPhrase match\tNone\tNB - Generic\tGeneric\t\"acme\"\t10\t1\t80.00\t0.00\t0.00",
    "acme alternatives\tBroad match\tNone\tNB - Comp\tComp\tacme competitor\t300\t20\t2,000.00\t0.00\t--",
    "how much does acme cost\tPhrase match\tNone\tNB - Pricing\tPricing\t\"acme cost\"\t50\t5\t400.00\t1.00\t250.00",
    "Total: Account\t\t\t\t\t\t480\t40\t3,690.50\t3.00\t750.00",
]) + "\n"
UI_KW = "\n".join([
    "Search keyword report",
    '"July 27, 2026 - October 24, 2026"',
    "Keyword status\tKeyword\tMatch type\tCampaign\tCampaign status\tAd group\tAd group status\t"
    "Impr.\tClicks\tCost\tConversions\tConv. value",
    "Enabled\t[acme price]\tExact match\tNB - Pricing\tEnabled\tPricing\tEnabled\t1\t1\t1\t1\t1",
    "Paused\tacme alternatives\tBroad match\tNB - Comp\tEnabled\tComp\tEnabled\t0\t0\t0\t0\t0",
    "Enabled\t\"acme cost\"\tPhrase match\tNB - Pricing\tEnabled\tPricing\tEnabled\t1\t1\t1\t1\t1",
]) + "\n"
GAQL_STR = (
    "search_term_view.search_term,search_term_view.status,segments.search_term_match_type,"
    "segments.keyword.info.text,segments.keyword.info.match_type,campaign.id,campaign.name,"
    "ad_group.id,ad_group.name,metrics.impressions,metrics.clicks,metrics.cost_micros,"
    "metrics.conversions,metrics.conversions_value\n"
    "acme pricing,NONE,NEAR_EXACT,acme price,EXACT,1,NB - Pricing,11,Pricing,120,14,1210500000,2,500\n"
    "acme login,EXCLUDED,PHRASE,acme,PHRASE,1,NB - Pricing,11,Pricing,30,3,90000000,0,0\n"
)


class LoaderTest(unittest.TestCase):
    def write(self, text, encoding="utf-16"):
        path = Path(self.tmp.name) / "file.csv"
        path.write_text(text, encoding=encoding)
        return str(path)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_ui_export_metrics_numeric_and_none_kept(self):
        df, window = load_ads_export.load(self.write(UI_STR))
        self.assertIn("July 27, 2026", window)
        self.assertEqual(len(df), 4)  # Total row dropped
        self.assertAlmostEqual(df["cost"].sum(), 3690.5)
        self.assertEqual(df["conv_value"].sum(), 750.0)  # '--' counted as 0, column stays numeric
        self.assertEqual(set(df["added_excluded"]), {"None"})  # not swallowed as NaN
        self.assertEqual(df["search_term_norm"].nunique(), 3)  # case and spacing merged

    def test_gaql_csv_cost_micros(self):
        df, _ = load_ads_export.load(self.write(GAQL_STR, "utf-8"))
        self.assertAlmostEqual(df["cost"].sum(), 1300.5)
        self.assertEqual(list(df["added_excluded"]), ["NONE", "EXCLUDED"])
        self.assertEqual(df.loc[0, "keyword"], "acme price")
        # Both match-type dimensions survive under their own names.
        self.assertEqual(list(df["search_term_match_type"]), ["NEAR_EXACT", "PHRASE"])
        self.assertEqual(list(df["keyword_match_type"]), ["EXACT", "PHRASE"])

    def test_total_footer_only_and_all_conv_value(self):
        text = ("Campaign\tConversion action\tAll conv.\tAll conv. value\tConv. value\n"
                "Total Care - Search\tLead\t2\t200\t100\n"
                "Total: Account\t\t2\t200\t100\n")
        df, _ = load_ads_export.load(self.write(text))
        self.assertEqual(list(df["campaign"]), ["Total Care - Search"])  # a real name starting 'Total'
        self.assertEqual(df["all_conv_value"].sum(), 200)
        self.assertEqual(df["conv_value"].sum(), 100)

    def test_colliding_headers_keep_both_columns(self):
        df, _ = load_ads_export.load(self.write("Keyword status\tStatus\tKeyword\nEnabled\tCampaign paused\tacme\n"))
        self.assertEqual(df.loc[0, "status"], "Enabled")
        self.assertEqual(df.loc[0, "Status"], "Campaign paused")

    def test_keyword_text_normalized(self):
        self.assertEqual(load_ads_export.normalize_text('[Acme  Price]'), "acme price")
        self.assertEqual(load_ads_export.normalize_text('"acme cost"'), "acme cost")
        self.assertEqual(load_ads_export.normalize_text("+acme +cost"), "acme cost")
        self.assertEqual(load_ads_export.normalize_text("C++ Developer"), "c++ developer")
        self.assertEqual(load_ads_export.normalize_text('"acme help\''), "acme help")  # malformed keyword


class NegativeMatchTest(unittest.TestCase):
    def test_rules(self):
        b = negative_match.blocks
        self.assertTrue(b("acme login", "EXACT", "Acme Login"))
        self.assertFalse(b("acme login", "exact", "acme login help"))
        self.assertTrue(b("acme login", "phrase", "acme login help"))
        self.assertFalse(b("acme login", "phrase", "login acme"))
        self.assertTrue(b("acme login", "broad", "login to acme"))
        self.assertFalse(b("c++", "broad", "c developer"))
        self.assertFalse(b("acme logins", "broad", "acme login"))  # no plural expansion
        self.assertTrue(b("hotline", "Campaign Negative Phrase", "crisis hotline"))

    def test_index_matches_slow_path_and_scope(self):
        rows = [{"text": "free", "match_type": "BROAD", "scope": "A"},
                {"text": "acme jobs", "match_type": "PHRASE", "scope": "ACCOUNT"},
                {"text": "acme pricing", "match_type": "EXACT", "scope": "B"}]
        index = negative_match.NegativeIndex(rows)
        queries = ["free acme trial", "acme jobs near me", "acme pricing", "acme pricing plans"]
        for q in queries:
            slow = [r for r in rows if negative_match.blocks(r["text"], r["match_type"], q)]
            self.assertEqual(sorted(map(id, index.hits(q))), sorted(map(id, slow)), q)
        self.assertEqual(index.hits("free acme trial", {"B", "ACCOUNT"}), [])
        self.assertEqual(len(index.hits("acme pricing", {"B"})), 1)

    def test_campaign_key_works_as_scope(self):
        rows = [{"text": "acme jobs", "match_type": "EXACT", "campaign": "A"}]
        self.assertEqual(len(negative_match.conflicts(rows, ["acme jobs"], scope="A")), 1)
        self.assertEqual(negative_match.conflicts(rows, ["acme jobs"], scope="B"), [])

    def test_unknown_match_type_fails_loudly(self):
        with self.assertRaises(ValueError):
            negative_match.blocks("acme", "fuzzy", "acme")


class ValidateRsaTest(unittest.TestCase):
    def test_embedded_keyword_insertion_and_wide_chars(self):
        H = ["Get {KeyWord:Acme Pricing} Today", "Plans From $50/Month", "Talk To Sales"]
        self.assertEqual(validate_rsa.validate(H, ["One.", "Two."]), [])
        self.assertEqual(validate_rsa.display_len("価格"), 4)
        problems = validate_rsa.validate(H + ["{LOCATION(City)} Plumbers", "{KeyWord:}"], ["One.", "Two."])
        self.assertTrue(any("manual length check" in p for p in problems))
        self.assertTrue(any("empty keyword-insertion fallback" in p for p in problems))

    def test_blank_assets_do_not_count(self):
        problems = validate_rsa.validate(["Acme Pricing", "Talk To Sales", "  "], ["One.", ""])
        self.assertIn("blank headline", problems)
        self.assertIn("blank description", problems)
        self.assertIn("2 headlines (3-15)", problems)
        self.assertIn("1 descriptions (2-4)", problems)

    def test_case_insensitive_duplicates(self):
        problems = validate_rsa.validate(["Acme Pricing", "acme pricing", "Talk To Sales"], ["One.", "Two."])
        self.assertIn("duplicate headline", problems)


class GapCandidatesCliTest(unittest.TestCase):
    def test_paused_and_blocked_terms_are_not_hidden(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "str.csv").write_text(UI_STR, encoding="utf-16")
            (tmp / "kw.csv").write_text(UI_KW, encoding="utf-16")
            (tmp / "neg.csv").write_text(
                "text,match_type,campaign,level,source\nacme cost,PHRASE,NB - Pricing,campaign,campaign negative\n")
            out = subprocess.run(
                [sys.executable, str(SCRIPTS / "gap_candidates.py"), str(tmp / "str.csv"), str(tmp / "kw.csv"),
                 "--negatives", str(tmp / "neg.csv"), "--out", str(tmp / "out")],
                capture_output=True, text=True, check=True).stdout
            self.assertIn("paused_keyword_only (1 rows)", out)
            self.assertIn("keyword paused: NB - Comp / Comp", (tmp / "out/paused_keyword_only.csv").read_text())
            self.assertIn("blocked_by_negative (1 rows)", out)
            blocked = (tmp / "out/blocked_by_negative.csv").read_text()
            self.assertIn("how much does acme cost", blocked)
            self.assertIn(",all", blocked)
            # The account's own enabled phrase keyword "acme cost" is blocked by the same negative.
            self.assertIn("enabled_keywords_blocked_by_negative (1 rows)", out)

    def test_partial_and_ad_group_only_blocking(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "str.csv").write_text(UI_STR, encoding="utf-16")
            (tmp / "kw.csv").write_text(UI_KW, encoding="utf-16")
            (tmp / "neg.csv").write_text(
                "text,match_type,campaign,level,source\n"
                "pricing,PHRASE,NB - Generic,campaign,campaign negative\n"
                "alternatives,BROAD,NB - Comp,ad group,ad group: Comp\n")
            subprocess.run(
                [sys.executable, str(SCRIPTS / "gap_candidates.py"), str(tmp / "str.csv"), str(tmp / "kw.csv"),
                 "--negatives", str(tmp / "neg.csv"), "--out", str(tmp / "out")],
                capture_output=True, text=True, check=True)
            agg = (tmp / "out/search_terms_aggregated.csv").read_text()
            self.assertIn("some: NB - Generic", agg)  # served in two campaigns, blocked in one
            self.assertIn("ad group only", agg)

    def test_missing_parent_status_or_placement_stops_the_check(self):
        old_kw = "Keyword status\tKeyword\tMatch type\tCampaign\tAd group\nEnabled\tacme\tBroad match\tNB\tG\n"
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "str.csv").write_text(UI_STR, encoding="utf-16")
            (tmp / "kw.csv").write_text(old_kw, encoding="utf-16")
            run = lambda *extra: subprocess.run(
                [sys.executable, str(SCRIPTS / "gap_candidates.py"), str(tmp / "str.csv"), str(tmp / "kw.csv"),
                 *extra], capture_output=True, text=True)
            result = run()
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("campaign_status", result.stderr)
            result = run("--keyword-status-only")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("LIMIT", result.stdout)
            (tmp / "str.csv").write_text("Search term\tImpr.\tClicks\tCost\tConversions\nacme\t1\t1\t1\t0\n",
                                         encoding="utf-16")
            (tmp / "neg.csv").write_text("text,match_type,campaign\nacme,EXACT,NB\n")
            result = run("--keyword-status-only", "--negatives", str(tmp / "neg.csv"))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("no campaign column", result.stderr)

    def test_review_csvs_neutralize_formulas(self):
        st = UI_STR.replace("acme alternatives", "=HYPERLINK(\"x\")")
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "str.csv").write_text(st, encoding="utf-16")
            (tmp / "kw.csv").write_text(UI_KW, encoding="utf-16")
            subprocess.run([sys.executable, str(SCRIPTS / "gap_candidates.py"), str(tmp / "str.csv"),
                            str(tmp / "kw.csv"), "--out", str(tmp / "out")],
                           capture_output=True, text=True, check=True)
            agg = pd.read_csv(tmp / "out/search_terms_aggregated.csv")
            self.assertIn("'=hyperlink(\"x\")", list(agg.search_term))

    def test_resolve_negatives_requires_attachments(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "resolve_negatives.py"), "--shared", "x.csv", "--out", "y.csv"],
            capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("attachments", result.stderr)

    def test_resolve_negatives_expands_lists_per_campaign(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "shared.csv").write_text(
                "shared_set.id,shared_set.name,shared_criterion.keyword.text,shared_criterion.keyword.match_type\n"
                "9,General,jobs,BROAD\n8,Unused,free,BROAD\n")
            (tmp / "att.csv").write_text("campaign.name,shared_set.id,shared_set.name\nA,9,General\nB,9,General\n")
            out = subprocess.run(
                [sys.executable, str(SCRIPTS / "resolve_negatives.py"), "--shared", str(tmp / "shared.csv"),
                 "--attachments", str(tmp / "att.csv"), "--out", str(tmp / "neg.csv")],
                capture_output=True, text=True, check=True).stdout
            self.assertIn("Unused", out)  # unattached list reported, not applied
            rows = (tmp / "neg.csv").read_text().strip().splitlines()
            self.assertEqual(len(rows), 3)  # header + one row per attached campaign


class ScopeAndJoinRegressionTest(unittest.TestCase):
    def test_same_ad_group_conflict_without_sibling_false_positive(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "neg.csv"
            path.write_text("text,match_type,campaign,ad_group,level,source\n"
                            "acme cost,EXACT,NB,Costs,ad group,local\n"
                            "acme pricing,EXACT,NB,Other,ad group,sibling\n")
            negatives = gap_candidates.read_negatives(path)
            kw = pd.DataFrame([
                {"campaign": "NB", "ad_group": "Costs", "keyword": term,
                 "keyword_norm": term, "match_type": "EXACT", "status": "ENABLED"}
                for term in ("acme cost", "acme pricing")])
            found = gap_candidates.keywords_blocked(kw, negatives)
            self.assertEqual(list(found.blocked_query), ["acme cost"])
            self.assertIn("close variants not assessed", found.iloc[0].coverage)
            self.assertFalse(negative_match.blocks("acme cost", "EXACT", "acme costs"))
            st = kw.rename(columns={"keyword_norm": "search_term_norm"}).assign(
                impressions=1, clicks=1, cost=1, conversions=1, conv_value=1)
            agg = gap_candidates.aggregate(st, set(), {}, 90)
            hits, extent = gap_candidates.blocked_by(agg, negatives)
            self.assertTrue(hits[0])
            self.assertEqual(hits[1], "")
            self.assertEqual(extent, ["ad group only: NB / Costs", ""])

    def test_empty_search_terms_and_explicit_scope(self):
        st = pd.DataFrame(columns=['search_term_norm', 'campaign', 'ad_group', 'match_type',
                                   'impressions', 'clicks', 'cost', 'conversions', 'conv_value'])
        agg = gap_candidates.aggregate(st, set(), {}, 90)
        self.assertTrue(agg.empty)
        with self.assertRaisesRegex(ValueError, "greater than zero"):
            gap_candidates.aggregate(st, set(), {}, 0)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "neg.csv"
            for content in (
                "text,match_type,campaign,level\njobs,BROAD,,campaign\n",
                "text,match_type,level\njobs,BROAD,account\n",
                "text,match_type,campaign,level\njobs,BROAD,ACCOUNT,campaign\n",
                "match_type,campaign,level\nBROAD,NB,campaign\n",
                "text,match_type,campaign,level\n,BROAD,NB,campaign\n",
            ):
                path.write_text(content)
                with self.assertRaises(ValueError, msg=content):
                    gap_candidates.read_negatives(path)
            path.write_text("text,match_type,campaign,level\njobs,BROAD,ACCOUNT,account\n")
            self.assertEqual(gap_candidates.read_negatives(path).iloc[0]['scope'], 'ACCOUNT')

    def test_ignored_periods_match_in_index_and_slow_path(self):
        row = {"text": "fifth ave.", "match_type": "EXACT", "scope": "NB"}
        self.assertTrue(negative_match.blocks(row["text"], "EXACT", "fifth ave"))
        self.assertEqual(len(negative_match.NegativeIndex([row]).hits("fifth ave")), 1)

    def test_export_formats_and_account_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            campaign = tmp / "campaign.csv"
            campaign.write_text('Negative keyword report\n"July 27 - October 24"\n'
                                'Campaign\tNegative keyword\tMatch type\nNB\tjobs\tBroad match\n',
                                encoding="utf-16")
            group = tmp / "group.csv"
            group.write_text("Campaign,Ad group,Keyword,Match type\nNB,Costs,free,Exact\n")
            account = tmp / "account.csv"
            account.write_text("shared_criterion.keyword.text,shared_criterion.keyword.match_type\nlogin,PHRASE\n")
            rows, _ = resolve_negatives.resolve(campaign=str(campaign), ad_group=str(group), account=str(account))
            self.assertEqual(len(rows), 3)
            self.assertEqual(rows[1]["ad_group"], "Costs")
            self.assertEqual(rows[2]["campaign"], "ACCOUNT")
            self.assertEqual(rows[2]["text"], "login")

    def test_mixed_inventory_filters_positives_and_rejects_bad_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mixed.csv"
            path.write_text("campaign.name,ad_group.name,ad_group_criterion.keyword.text,"
                            "ad_group_criterion.keyword.match_type,ad_group_criterion.negative\n"
                            "NB,Costs,jobs,BROAD,true\nNB,Costs,pricing,EXACT,false\n")
            rows, _ = resolve_negatives.resolve(ad_group=str(path))
            self.assertEqual([r["text"] for r in rows], ["jobs"])
            path.write_text("Campaign,Keyword,Match type\nNB,jobs,Broad\n")
            with self.assertRaisesRegex(ValueError, "ad_group"):
                resolve_negatives.resolve(ad_group=str(path))
            path.write_text("Campaign,Keyword,Match type\n,jobs,Broad\n")
            with self.assertRaisesRegex(ValueError, "campaign"):
                resolve_negatives.resolve(campaign=str(path))
            path.write_text("Campaign,Keyword,Match type\nNB,jobs,Fuzzy\n")
            with self.assertRaisesRegex(ValueError, "match type"):
                resolve_negatives.resolve(campaign=str(path))

    def test_empty_reports_are_supported_but_no_inputs_are_not_a_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "empty.csv"
            path.write_text("Campaign,Keyword,Match type\n")
            self.assertEqual(resolve_negatives.resolve(campaign=str(path)), ([], []))
            result = subprocess.run([sys.executable, str(SCRIPTS / "resolve_negatives.py"),
                                     "--out", str(Path(tmp) / "out.csv")], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("at least one negative report", result.stderr)

    def test_conversion_join_preserves_spend_and_each_action_total(self):
        keys = {"search_term": "acme pricing", "campaign_id": "1", "ad_group_id": "11"}
        terms = pd.DataFrame([{**keys, "keyword": kw, "impressions": 10, "clicks": 2,
                               "cost": cost, "conversions": conv, "conv_value": conv * 100}
                              for kw, cost, conv in (("acme", 20, 1), ("acme pricing", 30, 2))])
        actions = pd.DataFrame([{**keys, "conversion_action": name, "all_conversions": count,
                                 "all_conv_value": value}
                                for name, count, value in (("Qualified lead", 3, 300), ("Customer", 1, 500))])
        joined = join_conversion_actions.join_actions(terms, actions)
        self.assertEqual(len(joined), 1)
        self.assertEqual(joined.cost.sum(), 50)
        self.assertEqual(joined["all_conversions: Qualified lead"].sum(), 3)
        self.assertEqual(joined["all_conv_value: Customer"].sum(), 500)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            join_conversion_actions.join_actions(terms, pd.concat([actions, actions]))
        actions.loc[0, "campaign_id"] = "2"
        with self.assertRaisesRegex(ValueError, "absent"):
            join_conversion_actions.join_actions(terms, actions)

    def test_keyword_conversion_join_keeps_match_types_separate(self):
        common = {"keyword": "acme pricing", "campaign_id": "1", "ad_group_id": "11"}
        terms = pd.DataFrame([{**common, "match_type": kind, "impressions": 10, "clicks": 2,
                               "cost": cost, "conversions": 1, "conv_value": 1}
                              for kind, cost in (("EXACT", 20), ("PHRASE", 30))])
        actions = pd.DataFrame([{**common, "match_type": kind, "conversion_action": "Lead",
                                 "all_conversions": count, "all_conv_value": count}
                                for kind, count in (("EXACT", 1), ("PHRASE", 2))])
        result = join_conversion_actions.join_actions(terms, actions, "keyword")
        self.assertEqual(len(result), 2)
        self.assertEqual(result.cost.sum(), 50)
        self.assertEqual(result["all_conversions: Lead"].sum(), 3)

    def test_conversion_join_cli_reads_raw_gaql_headers(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "str.csv").write_text(GAQL_STR)
            (tmp / "actions.csv").write_text(
                "search_term_view.search_term,campaign.id,ad_group.id,segments.conversion_action_name,"
                "metrics.all_conversions,metrics.all_conversions_value\nacme pricing,1,11,Qualified lead,2,500\n")
            subprocess.run([sys.executable, str(SCRIPTS / "join_conversion_actions.py"),
                            str(tmp / "str.csv"), str(tmp / "actions.csv"), "--out", str(tmp / "out.csv")],
                           capture_output=True, text=True, check=True)
            result = pd.read_csv(tmp / "out.csv")
            self.assertEqual(result.cost.sum(), 1300.5)
            self.assertEqual(result["all_conversions: Qualified lead"].sum(), 2)

    def test_negative_export_only_exclude_preserves_match_and_scope(self):
        review = pd.DataFrame([{"text": "jobs", "match_type": "PHRASE", "campaign": "NB", "verdict": v}
                               for v in ("Exclude", "Keep relevant", "Keep unsure", "")])
        rows = export_negative_verdicts.export_rows(review)
        self.assertEqual(rows, [{"Campaign": "NB", "Ad group": "", "Keyword": "jobs",
                                 "Criterion Type": "Campaign Negative Phrase"}])
        self.assertEqual(export_negative_verdicts.export_rows(review.iloc[1:]), [])
        for field, value in (("verdict", "Maybe"), ("ad_group", "Local"), ("campaign", "ACCOUNT"),
                             ("text", ""), ("level", "shared list"), ("match_type", "fuzzy")):
            bad = review.iloc[:1].copy()
            bad[field] = value
            with self.assertRaises(ValueError, msg=field):
                export_negative_verdicts.export_rows(bad)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            export_negative_verdicts.export_rows(pd.concat([review.iloc[:1], review.iloc[:1]]))

    def test_negative_export_cli_pending_creates_header_only_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "review.csv").write_text("text,match_type,campaign,verdict\njobs,EXACT,NB,\n")
            subprocess.run([sys.executable, str(SCRIPTS / "export_negative_verdicts.py"),
                            str(tmp / "review.csv"), "--customer-id", "123-456-7890",
                            "--out", str(tmp / "neg_upload_1234567890.csv")],
                           capture_output=True, text=True, check=True)
            self.assertEqual((tmp / "neg_upload_1234567890.csv").read_text().splitlines(),
                             ["Campaign,Ad group,Keyword,Criterion Type"])


class NegativeScopeRegressionTest(unittest.TestCase):
    def write(self, tmp, name, text, encoding="utf-8"):
        path = Path(tmp) / name
        path.write_text(text, encoding=encoding)
        return str(path)

    def test_serving_status_is_not_paused_and_keyword_status_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            for header, row in (
                ("Status\tKeyword\tCampaign\tCampaign status\tAd group\tAd group status",
                 "Low search volume\tacme pricing\tC1\tEnabled\tAG1\tEnabled"),
                ("Status\tKeyword status\tKeyword\tCampaign\tCampaign status\tAd group\tAd group status",
                 "Campaign paused\tEnabled\tacme pricing\tC1\tEnabled\tAG1\tEnabled"),
            ):
                kw, _ = load_ads_export.load(self.write(tmp, "kw.csv", f"{header}\n{row}\n"))
                active, paused = gap_candidates.keyword_sets(kw)
                self.assertEqual((active, paused), ({"acme pricing"}, {}), header)

    def test_missing_conv_value_is_a_labelled_limit_not_a_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            st = self.write(tmp, "st.csv", "Search term\tCampaign\tClicks\tCost\tConversions\nacme\tC1\t1\t5\t1\n")
            kw = self.write(tmp, "kw.csv", "Keyword status\tKeyword\tCampaign\tCampaign status\tAd group\t"
                                           "Ad group status\nEnabled\tother\tC1\tEnabled\tAG\tEnabled\n")
            result = subprocess.run([sys.executable, str(SCRIPTS / "gap_candidates.py"), st, kw],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("no conv_value", result.stdout)
            self.assertIn("converting_not_keyword (1 rows)", result.stdout)

    def test_keyword_missing_from_one_geo_campaign_is_surfaced(self):
        kw = pd.DataFrame([{"campaign": "NB - East", "ad_group": "G", "keyword_norm": "acme pricing",
                            "status": "ENABLED", "campaign_status": "ENABLED", "ad_group_status": "ENABLED"}])
        st = pd.DataFrame([{"search_term_norm": "acme pricing", "campaign": c, "ad_group": "G", "clicks": 1,
                            "cost": 1, "conversions": 1} for c in ("NB - East", "NB - West")])
        g = gap_candidates.aggregate(st, {"acme pricing"}, {}, 90, gap_candidates.enabled_campaigns(kw))
        self.assertEqual(g.iloc[0].served_without_keyword, "NB - West")

    def test_partial_extent_names_ad_group_blocks(self):
        neg = pd.DataFrame([
            {"text": "acme", "match_type": "BROAD", "scope": "C1", "ad_group": "", "level": "campaign", "source": "x"},
            {"text": "acme", "match_type": "BROAD", "scope": "C2", "ad_group": "G2", "level": "ad group", "source": "y"}])
        st = pd.DataFrame([{"search_term_norm": "acme", "campaign": c, "ad_group": a, "clicks": 1, "cost": 1,
                            "conversions": 0} for c, a in (("C1", "G1"), ("C2", "G2"))])
        _, extent = gap_candidates.blocked_by(gap_candidates.aggregate(st, set(), {}, 90), neg)
        self.assertEqual(extent, ["some: C1; ad group: C2 / G2"])

    def test_sixteen_word_limit(self):
        long_query = " ".join(f"w{i}" for i in range(16)) + " jobs"
        self.assertFalse(negative_match.blocks("jobs", "broad", long_query))
        self.assertEqual(negative_match.NegativeIndex([{"text": "jobs", "match_type": "BROAD"}]).hits(long_query), [])
        self.assertTrue(negative_match.blocks("jobs", "broad", "w1 jobs"))

    def test_resolver_needs_match_type_and_rejects_mixed_levels(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(tmp, "neg.csv", 'Campaign,Negative keyword\nNB,[acme login]\nNB,"acme jobs"\n')
            with self.assertRaisesRegex(ValueError, "Match type column"):
                resolve_negatives.resolve(campaign=path)
            path = self.write(tmp, "mixed.csv", "Level,Campaign,Ad group,Negative keyword,Match type\n"
                                                "Campaign,NB,,free,Broad\nAd group,NB,Costs,jobs,Exact\n")
            with self.assertRaisesRegex(ValueError, "split the report"):
                resolve_negatives.resolve(campaign=path)

    def test_export_strips_sheet_escape_and_checks_customer(self):
        review = pd.DataFrame([{"text": "'+1 acme", "match_type": "BROAD", "campaign": "NB", "verdict": "Exclude"},
                               {"text": "[acme login]", "match_type": "EXACT", "campaign": "NB", "verdict": "Exclude"}])
        rows = export_negative_verdicts.export_rows(review, "1234567890")
        self.assertEqual([r["Keyword"] for r in rows], ["+1 acme", "acme login"])
        review["customer_id"] = "999-999-9999"
        with self.assertRaisesRegex(ValueError, "customer"):
            export_negative_verdicts.export_rows(review, "1234567890")
        result = subprocess.run([sys.executable, str(SCRIPTS / "export_negative_verdicts.py"), "x.csv",
                                 "--out", "y.csv"], capture_output=True, text=True)
        self.assertIn("--customer-id", result.stderr)

    def test_account_list_applies_only_when_attached(self):
        with tempfile.TemporaryDirectory() as tmp:
            acct = self.write(tmp, "acct.csv", "shared_set.id,shared_set.name,shared_criterion.keyword.text,"
                                               "shared_criterion.keyword.match_type\n42,Live,jobs,BROAD\n7,Dormant,free,BROAD\n")
            with self.assertRaisesRegex(ValueError, "account-attachments"):
                resolve_negatives.resolve(account=acct)
            link = self.write(tmp, "link.csv", "customer_negative_criterion.negative_keyword_list.shared_set\n"
                                               "customers/1234567890/sharedSets/42\n")
            rows, unattached = resolve_negatives.resolve(account=acct, account_attachments=link)
            self.assertEqual([(r["text"], r["campaign"]) for r in rows], [("jobs", "ACCOUNT")])
            self.assertEqual(unattached, ["Dormant"])
            Path(link).write_text("customer_negative_criterion.negative_keyword_list.shared_set\n"
                                  "customers/1234567890/sharedSets/42\n", encoding="utf-16")
            self.assertEqual(len(resolve_negatives.resolve(account=acct, account_attachments=link)[0]), 1)

    def test_duplicate_raw_headers_get_suffixes(self):
        with tempfile.TemporaryDirectory() as tmp:
            df, _ = load_ads_export.load(self.write(tmp, "x.csv", "campaign.name,campaign,clicks\nA,B,1\n"))
            self.assertEqual(df.loc[0, "campaign"], "B")  # the plain name is the earlier alias
            self.assertEqual(df.loc[0, "campaign.name"], "A")
            df, _ = load_ads_export.load(self.write(tmp, "y.csv", "Campaign,campaign,clicks\nA,B,1\n"))
            self.assertEqual(list(df.columns[:2]), ["campaign", "campaign__2"])


class ExportAndMatchingRegressionTest(unittest.TestCase):
    def test_paused_copy_in_served_campaign_is_named(self):
        kw = pd.DataFrame([{"campaign": c, "ad_group": "Pricing", "keyword_norm": "acme pricing", "status": s,
                            "campaign_status": "ENABLED", "ad_group_status": "ENABLED"}
                           for c, s in (("NB - A", "ENABLED"), ("NB - B", "PAUSED"))])
        st = pd.DataFrame([{"search_term_norm": "acme pricing", "campaign": "NB - B", "ad_group": "Pricing",
                            "clicks": 1, "cost": 1, "conversions": 1}])
        active, paused = gap_candidates.keyword_sets(kw)
        g = gap_candidates.aggregate(st, active, paused, 90, gap_candidates.enabled_campaigns(kw),
                                     gap_candidates.off_locations(kw))
        self.assertEqual(g.iloc[0].served_without_keyword, "NB - B")
        self.assertEqual(g.iloc[0].paused_in_served_campaign, "keyword paused: NB - B / Pricing")

    def test_pipe_in_campaign_names_keeps_paused_copy_visible(self):
        kw = pd.DataFrame([{"campaign": c, "ad_group": "AG1", "keyword_norm": "acme pricing", "status": s,
                            "campaign_status": "ENABLED", "ad_group_status": "ENABLED"}
                           for c, s in (("NB | Pricing | NJ", "ENABLED"), ("NB | Pricing | TX", "PAUSED"))])
        st = pd.DataFrame([{"search_term_norm": "acme pricing", "campaign": c, "ad_group": "AG1",
                            "clicks": 1, "cost": 1, "conversions": 1} for c in ("NB | Pricing | NJ", "NB | Pricing | TX")])
        active, paused = gap_candidates.keyword_sets(kw)
        g = gap_candidates.aggregate(st, active, paused, 90, gap_candidates.enabled_campaigns(kw),
                                     gap_candidates.off_locations(kw))
        self.assertEqual(g.iloc[0].paused_in_served_campaign, "keyword paused: NB | Pricing | TX / AG1")

    def test_serving_status_naming_a_parent_is_not_a_keyword_pause(self):
        kw = pd.DataFrame([{"campaign": "NB", "ad_group": "G", "keyword_norm": "acme", "status": "Campaign paused"}])
        self.assertEqual(gap_candidates.keyword_sets(kw)[1], {"acme": "campaign paused: NB"})

    def test_shared_list_ids_on_one_side_join_on_names_or_stop(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "shared.csv").write_text("shared_set.id,shared_set.name,shared_criterion.keyword.text,"
                                            "shared_criterion.keyword.match_type\n111,General,teen,BROAD\n")
            (tmp / "att.csv").write_text("Campaign,Negative keyword list\nNB,General\n")
            rows, _ = resolve_negatives.resolve(shared=str(tmp / "shared.csv"), attachments=str(tmp / "att.csv"))
            self.assertEqual([r["campaign"] for r in rows], ["NB"])  # names are the common key
            (tmp / "shared.csv").write_text("shared_set.id,shared_criterion.keyword.text,"
                                            "shared_criterion.keyword.match_type\n111,teen,BROAD\n")
            with self.assertRaisesRegex(ValueError, "no list identity"):
                resolve_negatives.resolve(shared=str(tmp / "shared.csv"), attachments=str(tmp / "att.csv"))
            (tmp / "shared.csv").write_text("Negative keyword list,Keyword,Match type\nGeneral,teen,Broad\n")
            rows, unattached = resolve_negatives.resolve(shared=str(tmp / "shared.csv"),
                                                         attachments=str(tmp / "att.csv"))
            self.assertEqual(([r["campaign"] for r in rows], unattached), (["NB"], []))

    def test_nan_headline_is_blank_and_editor_invalid_text_stops(self):
        problems = validate_rsa.validate(["Acme Pricing", "Talk To Sales", float("nan")], ["One.", "Two."])
        self.assertIn("blank headline", problems)
        for text in ("-free trial", "widget, cheap"):
            review = pd.DataFrame([{"text": text, "match_type": "BROAD", "campaign": "NB", "verdict": "Exclude"}])
            with self.assertRaisesRegex(ValueError, "reject"):
                export_negative_verdicts.export_rows(review)

    def test_export_out_name_must_carry_customer_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "review.csv").write_text("text,match_type,campaign,verdict\njobs,EXACT,NB,Exclude\n")
            result = subprocess.run([sys.executable, str(SCRIPTS / "export_negative_verdicts.py"),
                                     str(tmp / "review.csv"), "--customer-id", "123-456-7890",
                                     "--out", str(tmp / "neg_upload.csv")], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("customer ID", result.stderr)

    def test_helpers_run_in_isolated_mode(self):
        for script in ("export_negative_verdicts.py", "join_conversion_actions.py"):
            result = subprocess.run([sys.executable, "-I", "-c",
                                     f"import runpy; runpy.run_path({str(SCRIPTS / script)!r})"],
                                    capture_output=True, text=True)
            self.assertNotIn("ModuleNotFoundError: No module named 'load_ads_export'", result.stderr, script)


class LateReviewRegressionTest(unittest.TestCase):
    def test_removed_parent_negatives_are_not_effective(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "neg.csv"
            path.write_text(
                "campaign.name,campaign.status,ad_group.name,ad_group.status,"
                "ad_group_criterion.keyword.text,ad_group_criterion.keyword.match_type,"
                "ad_group_criterion.negative,ad_group_criterion.status\n"
                "NB,ENABLED,Removed,REMOVED,retired group,EXACT,true,ENABLED\n"
                "Old,REMOVED,Live,ENABLED,retired campaign,EXACT,true,ENABLED\n"
                "NB,ENABLED,Live,ENABLED,live keyword,EXACT,true,ENABLED\n"
                "NB,ENABLED,Paused,PAUSED,paused keyword,EXACT,true,ENABLED\n"
                "Paused,PAUSED,Live,ENABLED,paused campaign keyword,EXACT,true,ENABLED\n")
            rows, _ = resolve_negatives.resolve(ad_group=str(path))
            self.assertEqual([r['text'] for r in rows],
                             ['live keyword', 'paused keyword', 'paused campaign keyword'])
            # Historical placements must not resurrect an exclusion from a removed parent.
            frame = pd.DataFrame(rows).rename(columns={'campaign': 'scope'})
            st = pd.DataFrame([{'search_term_norm': term, 'campaign': c, 'ad_group': a,
                                'clicks': 1, 'cost': 1, 'conversions': 1}
                               for term, c, a in [('retired group', 'NB', 'Removed'),
                                                  ('retired campaign', 'Old', 'Live'),
                                                  ('live keyword', 'NB', 'Live')]])
            agg = gap_candidates.aggregate(st, set(), {}, 90)
            hits, _ = gap_candidates.blocked_by(agg, frame)
            found = dict(zip(agg.search_term, hits))
            self.assertFalse(found['retired group'])
            self.assertFalse(found['retired campaign'])
            self.assertTrue(found['live keyword'])

    def test_removed_campaign_negatives_are_skipped_in_ui_exports(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "neg.csv"
            path.write_text("Campaign,Campaign status,Negative keyword,Match type\n"
                            "Old,Removed,retired,Exact\nNB,Enabled,current,Exact\n",
                            encoding='utf-16')
            rows, _ = resolve_negatives.resolve(campaign=str(path))
            self.assertEqual([r['text'] for r in rows], ['current'])

    def test_minus_operators_apply_only_to_negative_tokens(self):
        cases = [
            ('dark -chocolate', 'BROAD', 'dark cake', True),
            ('-chocolate dark', 'PHRASE', 'fresh dark cake', True),
            ('dark -chocolate', 'EXACT', 'dark', True),
            ('dark -chocolate', 'EXACT', 'dark cake', False),
            ('dark -chocolate', 'BROAD', 'chocolate cake', False),
            ('sugar-free', 'BROAD', 'sugar-free cake', True),
            ('sugar-free', 'BROAD', 'sugar free cake', False),
            ('-chocolate', 'BROAD', 'dark cake', False),
            ('dark cake', 'PHRASE', 'dark -cake', False),
        ]
        for text, kind, query, expected in cases:
            with self.subTest(text=text, kind=kind, query=query):
                row = {'text': text, 'match_type': kind, 'scope': 'NB'}
                self.assertEqual(negative_match.blocks(text, kind, query), expected)
                self.assertEqual(bool(negative_match.NegativeIndex([row]).hits(query, {'NB'})), expected)
                self.assertEqual(bool(negative_match.conflicts([row], [query], 'NB')), expected)
                self.assertFalse(negative_match.NegativeIndex([row]).hits(query, {'Other'}))


class BulkNegativeCheckTest(unittest.TestCase):
    def check_files(self, negatives, queries, *extra, query_name="q.csv"):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "neg.csv").write_text(negatives)
            (root / query_name).write_text(queries)
            return subprocess.run(
                [sys.executable, str(SCRIPTS / "negative_match.py"), "--negatives", str(root / "neg.csv"),
                 "--queries", str(root / query_name), *extra], capture_output=True, text=True)

    def test_campaign_routing_does_not_block_brand_destination(self):
        result = self.check_files(
            "text,match_type,campaign\nnorthwind,PHRASE,Nonbrand\n",
            "query,campaign,ad_group\nnorthwind pricing,Brand,Pricing\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("0 conflicts", result.stdout)

    def test_ad_group_checks_preserve_actual_and_sibling_destinations(self):
        result = self.check_files(
            "text,match_type,campaign,ad_group,level\nnorthwind pricing,EXACT,NB,Other,ad group\n",
            "query,campaign,ad_group\nnorthwind pricing,NB,Pricing\nnorthwind pricing,NB,Other\n")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("1 conflicts", result.stdout)
        self.assertIn("NB / Other", result.stdout)
        self.assertNotIn("NB / Pricing", result.stdout)

    def test_account_campaign_and_attached_list_inherit_into_destination(self):
        result = self.check_files(
            "text,match_type,campaign,ad_group,level,source\n"
            "jobs,BROAD,ACCOUNT,,account,account negative\n"
            "free,PHRASE,NB,,campaign,campaign negative\n"
            "login,PHRASE,NB,,shared list,General\n",
            "query,campaign,ad_group\nscheduling jobs,Brand,Core\nfree tools,NB,Core\n"
            "northwind login,NB,Core\nnorthwind login,Other,Core\n")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("3 conflicts", result.stdout)
        self.assertNotIn("Other / Core", result.stdout)

    def test_incomplete_negative_rows_do_not_pass(self):
        cases = [
            "negative,match_type,campaign\nnorthwind,EXACT,NB\n",
            "text,match_type,campaign\n,EXACT,NB\n",
            "text,match_type,campaign\nnorthwind,,NB\n",
            "text,match_type,campaign\nnorthwind,BOGUS,NB\n",
            "text,match_type,campaign\nnorthwind,EXACT,\n",
            "text,match_type,campaign,level\nnorthwind,EXACT,NB,ad group\n",
            "text,match_type,campaign,ad_group,level\nnorthwind,EXACT,ACCOUNT,Core,account\n",
            "text,match_type,campaign,scope\nnorthwind,EXACT,NB,Other\n",
        ]
        for negatives in cases:
            with self.subTest(negatives=negatives):
                result = self.check_files(negatives, "query,campaign,ad_group\nnorthwind,NB,Core\n")
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertNotIn("0 conflicts", result.stdout)

    def test_missing_query_scope_and_empty_queries_do_not_pass(self):
        negatives = "text,match_type,campaign\nnorthwind,EXACT,NB\n"
        for queries in ("query\nnorthwind\n", "query,campaign\nnorthwind,\n", "query,campaign\n"):
            with self.subTest(queries=queries):
                result = self.check_files(negatives, queries)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        result = self.check_files(negatives, "northwind\n", query_name="q.txt")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)

    def test_plain_text_requires_ad_group_when_current_inventory_needs_it(self):
        negatives = "text,match_type,campaign,ad_group,level\nnorthwind,EXACT,NB,Other,ad group\n"
        result = self.check_files(negatives, "northwind\n", "--scope", "NB", query_name="q.txt")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        for group, expected in (("Core", 0), ("Other", 1)):
            result = self.check_files(negatives, "northwind\n", "--scope", "NB", "--ad-group", group,
                                      query_name="q.txt")
            self.assertEqual(result.returncode, expected, result.stdout + result.stderr)

    def test_header_only_inventory_is_a_checked_empty_set(self):
        result = self.check_files("text,match_type,campaign\n", "query,campaign,ad_group\nnorthwind,NB,Core\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("0 negatives and 1 queries", result.stdout)

    def test_bulk_check_tokenization_scales_with_inputs_not_cross_product(self):
        from unittest.mock import patch
        negatives = [{"text": f"unrelated{i}", "match_type": "EXACT", "campaign": "NB"} for i in range(1000)]
        queries = [{"query": f"buyer query {i}", "campaign": "NB", "ad_group": "Core"} for i in range(1000)]
        with patch.object(negative_match, "_tokens", wraps=negative_match._tokens) as tokenize:
            found = negative_match.scoped_conflicts(negatives, queries)
            self.assertEqual(found, [])
            self.assertLessEqual(tokenize.call_count, 4000)  # bounded work, not 1,000,000 pairwise checks

    def test_scoped_index_agrees_with_exhaustive_destination_checks(self):
        negatives = []
        for campaign in ('ACCOUNT', 'Brand', 'NB'):
            for group in (('',) if campaign == 'ACCOUNT' else ('', 'Core', 'Other')):
                for kind in ('EXACT', 'PHRASE', 'BROAD'):
                    for text in ('northwind pricing', 'pricing northwind', 'dark -chocolate', 'jobs'):
                        negatives.append({'text': text, 'match_type': kind, 'campaign': campaign,
                                          'ad_group': group})
        queries = [{'query': text, 'campaign': campaign, 'ad_group': group}
                   for campaign in ('Brand', 'NB', 'New') for group in ('Core', 'Other')
                   for text in ('northwind pricing', 'northwind pricing help', 'pricing northwind',
                                'dark cake', 'scheduler jobs', 'unrelated')]
        actual = negative_match.scoped_conflicts(negatives, queries)
        identity = lambda r, q: (r['text'], r['match_type'].lower(), r['campaign'], r.get('ad_group', ''),
                                 q['query'], q['campaign'], q['ad_group'])
        expected = [identity(n, q) for q in queries for n in negatives
                    if n['campaign'] in ('ACCOUNT', q['campaign'])
                    and (not n['ad_group'] or n['ad_group'] == q['ad_group'])
                    and negative_match.blocks(n['text'], n['match_type'], q['query'])]
        observed = [(r['negative'], r['match_type'], r['scope'], r['ad_group'], r['query'],
                     r['query_campaign'], r['query_ad_group']) for r in actual]
        self.assertCountEqual(observed, expected)

    def test_malformed_csv_and_ambiguous_query_modes_are_rejected(self):
        query = "query,campaign,ad_group\nnorthwind,NB,Core\n"
        for negatives in (
                "text,text,match_type,campaign\nnorthwind,other,EXACT,NB\n",
                "text,match_type,campaign\nnorthwind,EXACT,NB,extra\n",
                "text,match_type,campaign\nnorthwind,EXACT\n",
                "text,match_type,campaign,level\nnorthwind,EXACT,NB,unknown\n"):
            with self.subTest(negatives=negatives):
                result = self.check_files(negatives, query)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        result = self.check_files("text,match_type,campaign\nnorthwind,EXACT,NB\n", query, "--scope", "NB")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)

    def test_editor_style_headers_and_bom_keep_matching_values(self):
        result = self.check_files(
            '\ufeffKeyword,Match type,Campaign,Ad group,Level\nnorthwind,Exact match,NB,Core,ad group\n',
            '\ufeffQuery,Campaign,Ad group\nnorthwind,NB,Core\n')
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("1 conflicts", result.stdout)


class CommandLineTest(unittest.TestCase):
    def run_script(self, name, *args):
        return subprocess.run([sys.executable, str(SCRIPTS / name), *args], capture_output=True, text=True)

    def test_negative_match_single_and_file_modes(self):
        single = self.run_script("negative_match.py", "northwind login", "phrase", "northwind login help", "northwind pricing")
        self.assertEqual(single.returncode, 0)
        self.assertIn("'northwind login help': BLOCKED", single.stdout)
        self.assertIn("'northwind pricing': eligible", single.stdout)
        self.assertNotEqual(self.run_script("negative_match.py").returncode, 0)
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "neg.csv").write_text("text,match_type,campaign\nnorthwind login,PHRASE,NB - Core\n"
                                         "jobs,BROAD,ACCOUNT\n")
            (tmp / "q.txt").write_text("northwind pricing\nnorthwind login help\nscheduling jobs\n")
            result = self.run_script("negative_match.py", "--negatives", str(tmp / "neg.csv"),
                                     "--queries", str(tmp / "q.txt"), "--scope", "NB - Core")
            self.assertEqual(result.returncode, 1)
            self.assertIn("2 conflicts", result.stdout)
            self.assertNotIn("'northwind pricing'", result.stdout)

    def test_validate_rsa_cli_reads_editor_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rsa.csv"
            header = ["Campaign", "Ad group"] + [f"Headline {n}" for n in range(1, 16)] + \
                     [f"Description {n}" for n in range(1, 5)] + ["Path 1", "Path 2", "Ad type", "Final URL", "Status"]
            upload = ["Responsive search ad", "https://example.com/pricing", "Paused"]
            good = ["NB - Core", "Pricing", "Northwind Pricing", "Plans For Clinics", "Book A Demo"] + [""] * 12 + \
                   ["Scheduling software for clinics.", "See plans and book a demo today."] + ["", ""] + ["pricing", ""] + upload
            bad = ["NB - Core", "Clinics", "A headline that is far too long to fit", "Two", "Three"] + [""] * 12 + \
                  ["Only one description."] + ["", "", ""] + ["clinics", ""] + upload
            with path.open("w", newline="") as fh:
                writer = csv.writer(fh)
                writer.writerows([header, good, bad])
            result = self.run_script("validate_rsa.py", str(path))
            self.assertEqual(result.returncode, 1)
            self.assertNotIn("row 2", result.stdout)
            self.assertIn("row 3 (NB - Core / Clinics): headline >30", result.stdout)
            self.assertIn("1 descriptions (2-4)", result.stdout)

    def test_export_accepts_comma_verdicts(self):
        review = pd.DataFrame([{"text": "scheduling jobs", "match_type": "EXACT", "campaign": "NB - Core", "verdict": "Exclude"},
                               {"text": "northwind demo", "match_type": "EXACT", "campaign": "NB - Core", "verdict": "Keep, relevant"},
                               {"text": "clinic scheduling", "match_type": "EXACT", "campaign": "NB - Core", "verdict": "Keep, unsure"}])
        rows = export_negative_verdicts.export_rows(review)
        self.assertEqual([r["Keyword"] for r in rows], ["scheduling jobs"])


class InputValidationTest(unittest.TestCase):
    def run_script(self, name, *args):
        return subprocess.run([sys.executable, str(SCRIPTS / name), *args], capture_output=True, text=True)

    def test_validate_rsa_rejects_rows_wider_than_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rsa.csv"
            header = ["Campaign", "Ad group", "Headline 1", "Headline 2", "Headline 3",
                      "Description 1", "Description 2"]
            path.write_text(",".join(header) + "\n"
                            "NB - Core,Pricing,Plans, For Clinics,Book A Demo,See Pricing,"
                            "Clinic scheduling.,Book a demo today.\n")
            result = self.run_script("validate_rsa.py", str(path))
            self.assertEqual(result.returncode, 2)
            self.assertIn("row 2 does not match the header width", result.stderr)

    def test_validate_rsa_rejects_header_only_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rsa.csv"
            path.write_text("Campaign,Ad group,Headline 1,Description 1\n")
            result = self.run_script("validate_rsa.py", str(path))
            self.assertEqual(result.returncode, 2)
            self.assertIn("no RSA rows found", result.stderr)

    def test_negative_match_rejects_mixed_single_and_bulk_arguments(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "neg.csv").write_text("text,match_type,campaign\nnorthwind login,PHRASE,NB - Core\n")
            (tmp / "q.csv").write_text("query,campaign,ad_group\nnorthwind pricing,NB - Core,Pricing\n")
            result = self.run_script("negative_match.py", "blocked", "exact", "blocked",
                                     "--negatives", str(tmp / "neg.csv"), "--queries", str(tmp / "q.csv"))
            self.assertEqual(result.returncode, 2)
            self.assertIn("not both", result.stderr)

    def test_validate_rsa_rejects_duplicate_headers_that_hide_invalid_assets(self):
        for duplicate in ('Headline 1', 'Headline 1 ', 'headline 1'):
            with self.subTest(duplicate=duplicate), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / 'rsa.csv'
                with path.open('w', newline='') as fh:
                    csv.writer(fh).writerows([
                        ['Campaign', 'Ad group', 'Headline 1', duplicate, 'Headline 2', 'Headline 3',
                         'Description 1', 'Description 2'],
                        ['NB', 'Core', 'This headline is too long and must never pass the validator',
                         'Plans', 'For Clinics', 'Book A Demo', 'Scheduling for clinics.', 'Book a demo today.']])
                result = self.run_script('validate_rsa.py', str(path))
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertIn('unique', result.stderr)

    def test_validate_rsa_rejects_malformed_csv_and_short_rows(self):
        for row in ('NB,Core,Plans,For Clinics,Book A Demo,One description.\n',
                    'NB,Core,"Plans"oops,For Clinics,Book A Demo,One description.,Another one.\n'):
            with self.subTest(row=row), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / 'rsa.csv'
                path.write_text('Campaign,Ad group,Headline 1,Headline 2,Headline 3,Description 1,Description 2\n' + row)
                result = self.run_script('validate_rsa.py', str(path))
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'rsa.csv'
            with path.open('w', newline='') as fh:
                csv.writer(fh).writerows([
                    ['Campaign', 'Ad group', 'Ad type', 'Headline 1', 'Headline 2', 'Headline 3',
                     'Description 1', 'Description 2', 'Final URL', 'Status'],
                    ['NB', 'Core', 'Responsive search ad', 'Plans For Clinics', 'Book A Demo', 'See Pricing',
                     'Clinic scheduling, without the paperwork.', 'Book a demo today.',
                     'https://example.com/pricing', 'Paused']])
            result = self.run_script('validate_rsa.py', str(path))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class UploadLayoutAndScopeTest(unittest.TestCase):
    def run_script(self, name, *args):
        return subprocess.run([sys.executable, str(SCRIPTS / name), *args], capture_output=True, text=True)

    def write_rsa(self, tmp, header, row):
        path = Path(tmp) / "rsa.csv"
        with path.open("w", newline="") as fh:
            csv.writer(fh).writerows([header, row])
        return str(path)

    def test_validate_rsa_requires_the_upload_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_rsa(tmp, ["Headline 10", "Headline 2", "Headline 3", "Description 1", "Description 2"],
                                  ["Ten", "Two", "Three", "One.", "Two."])
            result = self.run_script("validate_rsa.py", path)
            self.assertEqual(result.returncode, 2)
            self.assertIn("missing Campaign", result.stderr)
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_rsa(tmp, ["Campaign", "Ad group", "Ad type", "Headline 1", "Headline 16"],
                                  ["NB", "Core", "Responsive search ad", "One", "Sixteen"])
            result = self.run_script("validate_rsa.py", path)
            self.assertEqual(result.returncode, 2)
            self.assertIn("unrecognized asset columns: Headline 16", result.stderr)

    def test_validate_rsa_flags_non_importable_rows(self):
        header = ["Campaign", "Ad group", "Ad type", "Headline 1", "Headline 2", "Headline 3",
                  "Description 1", "Description 2", "Final URL", "Status"]
        row = ["NB", "Core", "Expanded text ad", "Plans For Clinics", "Book A Demo", "See Pricing",
               "Clinic scheduling.", "Book a demo today.", "", "Enabled"]
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_script("validate_rsa.py", self.write_rsa(tmp, header, row))
            self.assertEqual(result.returncode, 1)
            for problem in ("blank Final URL", "ad type 'Expanded text ad'", "status 'Enabled'"):
                self.assertIn(problem, result.stdout)

    def test_campaign_named_account_is_a_campaign(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "neg.csv").write_text("text,match_type,campaign,ad_group,level,source\n"
                                         "login,PHRASE,ACCOUNT,,campaign,campaign negative\n"
                                         "jobs,BROAD,ACCOUNT,,account,account negative\n")
            (tmp / "q.csv").write_text("query,campaign,ad_group\n"
                                       "acme login,ACCOUNT,Core\nacme login,NB,Core\nacme jobs,NB,Core\n")
            result = self.run_script("negative_match.py", "--negatives", str(tmp / "neg.csv"),
                                     "--queries", str(tmp / "q.csv"))
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("'acme login' at ACCOUNT / Core", result.stdout)
            self.assertNotIn("'acme login' at NB / Core", result.stdout)
            self.assertIn("'acme jobs' at NB / Core", result.stdout)


if __name__ == "__main__":
    unittest.main()
