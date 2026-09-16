from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from . import checks
from .rules import DEFAULTS


@dataclass
class AuditResult:
    issues: pd.DataFrame
    company_clusters: list[list[str]]
    funnel: pd.DataFrame
    fill_rates: dict[str, dict[str, float]]
    health: dict[str, float]
    counts: dict[str, int]


def load(folder: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    read = lambda n: pd.read_csv(folder / n, dtype=str)  # blanks come back as NaN
    return read("companies.csv"), read("contacts.csv"), read("deals.csv")


SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}


def _sorted(df: pd.DataFrame) -> pd.DataFrame:
    out = df.assign(_rank=df["severity"].map(SEVERITY_RANK))
    return out.sort_values(["_rank", "object", "check", "record_id"]).drop(columns="_rank").reset_index(drop=True)


def _share_clean(total: int, bad_ids: set) -> float:
    return 1.0 if total == 0 else max(0.0, 1 - len(bad_ids) / total)


def run_audit(companies: pd.DataFrame, contacts: pd.DataFrame, deals: pd.DataFrame,
              rules: dict | None = None, today: date | None = None) -> AuditResult:
    r = {**DEFAULTS, **(rules or {})}
    today = today or date.today()
    deals = deals.copy()
    deals["amount"] = pd.to_numeric(deals["amount"], errors="coerce")

    issues: list[dict] = []
    dup_issues, clusters = checks.company_duplicates(companies, int(r["fuzzy_name_threshold"]))
    issues += dup_issues
    issues += checks.missing_fields(companies, "company", "company_id", r["required_company_fields"])
    issues += checks.missing_fields(contacts, "contact", "contact_id", r["required_contact_fields"])
    issues += checks.missing_fields(deals, "deal", "deal_id", r["required_deal_fields"])
    issues += checks.contact_quality(contacts, r["role_inbox_prefixes"])
    issues += checks.orphans(contacts, deals, companies)
    issues += checks.deal_timing(deals, r["open_stages"], int(r["stuck_days"]), today)

    df = pd.DataFrame(issues, columns=["object", "record_id", "check", "detail", "severity"])

    def ids(obj, *names):
        sel = df[(df["object"] == obj) & df["check"].isin(names)]
        return set(sel["record_id"])

    open_deals = deals[deals["dealstage"].isin(r["open_stages"])]
    parts = {
        "company_dupes": _share_clean(len(companies), ids("company", "duplicate company")),
        "contact_quality": _share_clean(len(contacts), ids("contact", "malformed email", "role inbox",
                                                           "duplicate contact", "missing fields")),
        "deal_completeness": _share_clean(len(deals), ids("deal", "missing fields")),
        "stuck_deals": _share_clean(len(open_deals), ids("deal", "stuck deal", "close date in the past")),
        "orphans": _share_clean(len(contacts) + len(deals),
                                ids("contact", "orphan contact") | ids("deal", "orphan deal")),
    }
    w = r["weights"]
    score = sum(parts[k] * w[k] for k in parts) / sum(w.values()) * 100
    health = {k: round(v * 100, 1) for k, v in parts.items()}
    health["overall"] = round(score, 1)

    return AuditResult(
        issues=_sorted(df),
        company_clusters=clusters,
        funnel=checks.funnel(deals, r["stage_order"], today, r["open_stages"]),
        fill_rates={
            "companies": checks.fill_rates(companies, r["required_company_fields"]),
            "contacts": checks.fill_rates(contacts, r["required_contact_fields"]),
            "deals": checks.fill_rates(deals, r["required_deal_fields"]),
        },
        health=health,
        counts={"companies": len(companies), "contacts": len(contacts), "deals": len(deals),
                "open_deals": len(open_deals)},
    )
