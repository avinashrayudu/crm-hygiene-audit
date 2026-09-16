from datetime import date
from pathlib import Path

import pandas as pd

from crmaudit import checks
from crmaudit.audit import load, run_audit
from crmaudit.normalize import company_name, domain, email_problem
from crmaudit.report import write

ROOT = Path(__file__).resolve().parents[1]
TODAY = date(2026, 9, 15)
ROLE = ["info", "hello", "orders"]


def df(rows):
    return pd.DataFrame(rows).astype(object)


def test_normalizers():
    assert domain("https://www.cornermarket.com/") == "cornermarket.com"
    assert company_name("CORNER  MARKET Co") == "corner market"
    assert email_problem("info@shop.com", ROLE) == "role inbox"
    assert email_problem("ana.shop.com", ROLE) == "malformed email"
    assert email_problem("ana@gmail.com", ROLE) == "personal email"
    assert email_problem("ana@shop.com", ROLE) == ""


def test_company_dupes_by_domain_and_by_name():
    companies = df([
        {"company_id": "1", "name": "Corner Market", "domain": "cornermarket.com", "state": "NY"},
        {"company_id": "2", "name": "Corner Market Inc.", "domain": "https://www.cornermarket.com/", "state": "NY"},
        {"company_id": "3", "name": "CORNER MARKET Co", "domain": "", "state": "NY"},
        {"company_id": "4", "name": "Corner Market", "domain": "", "state": "NJ"},
        {"company_id": "5", "name": "Hudson Deli", "domain": "hudsondeli.com", "state": "NY"},
    ])
    issues, clusters = checks.company_duplicates(companies, 92)
    assert clusters == [["1", "2", "3"]]
    assert {i["record_id"] for i in issues} == {"2", "3"}


def test_two_different_domains_are_never_merged_on_name():
    companies = df([
        {"company_id": "1", "name": "Union Market", "domain": "unionmarket.com", "state": "NY"},
        {"company_id": "2", "name": "Union Market", "domain": "unionmarketdc.com", "state": "NY"},
    ])
    _, clusters = checks.company_duplicates(companies, 92)
    assert clusters == []


def test_contact_quality_flags_dupes_case_insensitive():
    contacts = df([
        {"contact_id": "1", "email": "ana@shop.com"},
        {"contact_id": "2", "email": "ANA@shop.com"},
        {"contact_id": "3", "email": "hello@shop.com"},
    ])
    found = {(i["record_id"], i["check"]) for i in checks.contact_quality(contacts, ROLE)}
    assert ("2", "duplicate contact") in found
    assert ("3", "role inbox") in found


def test_deal_timing():
    deals = df([
        {"deal_id": "1", "dealstage": "sampled", "stage_entered_at": "2026-08-01", "closedate": "2026-10-01"},
        {"deal_id": "2", "dealstage": "contacted", "stage_entered_at": "2026-09-10", "closedate": "2026-09-01"},
        {"deal_id": "3", "dealstage": "closed_won", "stage_entered_at": "2026-01-01", "closedate": "2026-01-01"},
    ])
    found = {(i["record_id"], i["check"]) for i in checks.deal_timing(deals, ["sampled", "contacted"], 14, TODAY)}
    assert found == {("1", "stuck deal"), ("2", "close date in the past")}


def test_funnel_counts_lost_deals_at_the_stage_they_reached():
    order = ["target", "contacted", "sampled", "closed_won"]
    deals = df([
        {"dealstage": "closed_won", "lost_at_stage": None, "stage_entered_at": "2026-09-01"},
        {"dealstage": "closed_lost", "lost_at_stage": "sampled", "stage_entered_at": "2026-09-01"},
        {"dealstage": "target", "lost_at_stage": None, "stage_entered_at": "2026-09-10"},
    ])
    f = checks.funnel(deals, order, TODAY, ["target", "contacted", "sampled"])
    assert f["reached"].tolist() == [3, 2, 2, 1]
    assert f.loc[3, "step_conversion"] == 0.5


def test_sample_audit_end_to_end(tmp_path):
    companies, contacts, deals = load(ROOT / "data")
    result = run_audit(companies, contacts, deals, today=TODAY)
    assert 0 < result.health["overall"] < 100
    assert len(result.company_clusters) >= 10
    assert set(result.issues["severity"]) <= {"high", "medium", "low"}
    assert result.issues["severity"].iloc[0] == "high"
    report = write(result, tmp_path)
    text = report.read_text()
    assert "Overall health" in text and "Pipeline funnel" in text
    assert (tmp_path / "issues.csv").exists()


def test_thresholds_can_be_overridden():
    companies, contacts, deals = load(ROOT / "data")
    strict = run_audit(companies, contacts, deals, {"stuck_days": 3}, TODAY)
    loose = run_audit(companies, contacts, deals, {"stuck_days": 90}, TODAY)
    assert (strict.issues["check"] == "stuck deal").sum() > (loose.issues["check"] == "stuck deal").sum()
