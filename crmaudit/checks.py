"""Each check takes dataframes and returns a list of issue dicts.

An issue always has: object, record_id, check, detail, severity.
Severity is "high" when the problem breaks reporting or routing,
"medium" when it makes a rep's life harder, "low" otherwise.
"""
from __future__ import annotations

from datetime import date, datetime

import pandas as pd
from rapidfuzz import fuzz

from .normalize import company_name, domain, email_problem


def _issue(obj, rid, check, detail, severity):
    return {"object": obj, "record_id": str(rid), "check": check, "detail": detail, "severity": severity}


def _blank(v) -> bool:
    if v is None:
        return True
    try:
        if pd.isna(v):
            return True
    except (TypeError, ValueError):
        pass
    return str(v).strip() in ("", "nan", "NaT", "<NA>")


def company_duplicates(companies: pd.DataFrame, threshold: int) -> tuple[list[dict], list[list[str]]]:
    """Group companies that are the same account.

    Pass 1: identical normalized domain.
    Pass 2: company names above the fuzzy threshold within the same state,
    for records where at least one side has no domain.
    Returns issues plus the clusters (lists of record ids) for merge work.
    """
    df = companies.copy()
    df["_dom"] = df["domain"].map(domain)
    df["_name"] = df["name"].map(company_name)
    parent = {rid: rid for rid in df["company_id"].astype(str)}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    reasons: dict[tuple[str, str], str] = {}
    for dom, grp in df[df["_dom"] != ""].groupby("_dom"):
        ids = grp["company_id"].astype(str).tolist()
        for other in ids[1:]:
            union(ids[0], other)
            reasons[(ids[0], other)] = f"same domain {dom}"

    rows = df[["company_id", "_name", "_dom", "state"]].astype(str).values.tolist()
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            a, b = rows[i], rows[j]
            if a[2] and b[2] and a[2] not in ("", "nan") and b[2] not in ("", "nan"):
                continue  # both have domains; pass 1 already decided
            if a[3] != b[3]:
                continue
            score = fuzz.token_sort_ratio(a[1], b[1])
            if score >= threshold:
                union(a[0], b[0])
                reasons[(a[0], b[0])] = f"name match {score:.0f}% in {a[3]}"

    clusters: dict[str, list[str]] = {}
    for rid in parent:
        clusters.setdefault(find(rid), []).append(rid)
    groups = [sorted(v, key=lambda x: int(x) if x.isdigit() else x) for v in clusters.values() if len(v) > 1]

    issues = []
    for g in groups:
        why = sorted({r for (x, y), r in reasons.items() if x in g and y in g})
        for rid in g[1:]:
            issues.append(_issue("company", rid, "duplicate company",
                                 f"same account as {g[0]} ({'; '.join(why)})", "high"))
    return issues, groups


def missing_fields(df: pd.DataFrame, obj: str, id_col: str, fields: list[str]) -> list[dict]:
    issues = []
    for _, row in df.iterrows():
        gaps = [f for f in fields if f in df.columns and _blank(row[f])]
        if gaps:
            sev = "high" if any(f in ("amount", "closedate", "email", "domain", "pipeline_channel") for f in gaps) else "medium"
            issues.append(_issue(obj, row[id_col], "missing fields", ", ".join(gaps), sev))
    return issues


def contact_quality(contacts: pd.DataFrame, role_prefixes: list[str]) -> list[dict]:
    issues = []
    seen: dict[str, str] = {}
    for _, row in contacts.iterrows():
        rid = row["contact_id"]
        problem = email_problem(row.get("email"), role_prefixes)
        if problem and problem != "missing email":
            sev = "high" if problem in ("malformed email", "role inbox") else "low"
            issues.append(_issue("contact", rid, problem, str(row.get("email")), sev))
        email = str(row.get("email") or "").strip().lower()
        if email and email != "nan":
            if email in seen:
                issues.append(_issue("contact", rid, "duplicate contact", f"same email as {seen[email]}", "high"))
            else:
                seen[email] = str(rid)
    return issues


def orphans(contacts: pd.DataFrame, deals: pd.DataFrame, companies: pd.DataFrame) -> list[dict]:
    known = set(companies["company_id"].astype(str))
    issues = []
    for _, row in contacts.iterrows():
        cid = str(row.get("associated_company_id") or "").split(".")[0]
        if cid in ("", "nan") or cid not in known:
            issues.append(_issue("contact", row["contact_id"], "orphan contact", "no valid company association", "medium"))
    for _, row in deals.iterrows():
        cid = str(row.get("associated_company_id") or "").split(".")[0]
        if cid in ("", "nan") or cid not in known:
            issues.append(_issue("deal", row["deal_id"], "orphan deal", "no valid company association", "high"))
    return issues


def _to_date(v):
    if _blank(v):
        return None
    if isinstance(v, (date, datetime)):
        return v if isinstance(v, date) and not isinstance(v, datetime) else v.date()
    return pd.to_datetime(v).date()


def deal_timing(deals: pd.DataFrame, open_stages: list[str], stuck_days: int, today: date) -> list[dict]:
    issues = []
    for _, row in deals.iterrows():
        stage = str(row.get("dealstage"))
        if stage not in open_stages:
            continue
        entered = _to_date(row.get("stage_entered_at"))
        if entered and (today - entered).days > stuck_days:
            issues.append(_issue("deal", row["deal_id"], "stuck deal",
                                 f"{(today - entered).days} days in {stage}", "medium"))
        close = _to_date(row.get("closedate"))
        if close and close < today:
            issues.append(_issue("deal", row["deal_id"], "close date in the past",
                                 f"open in {stage}, close date {close}", "high"))
    return issues


def funnel(deals: pd.DataFrame, stage_order: list[str], today: date,
           open_stages: list[str] | None = None) -> pd.DataFrame:
    """How many deals reached each stage, and step conversion.

    A deal 'reached' a stage if its current stage is that stage or later.
    closed_lost deals count as reaching the stage recorded in lost_at_stage.
    """
    idx = {s: i for i, s in enumerate(stage_order)}
    reached_level = []
    for _, row in deals.iterrows():
        stage = str(row.get("dealstage"))
        if stage == "closed_lost":
            stage = str(row.get("lost_at_stage") or stage_order[0])
        reached_level.append(idx.get(stage, 0))
    s = pd.Series(reached_level)
    counts = [int((s >= i).sum()) for i in range(len(stage_order))]
    out = pd.DataFrame({"stage": stage_order, "reached": counts})
    out["step_conversion"] = (out["reached"] / out["reached"].shift(1)).round(3)
    out.loc[0, "step_conversion"] = None

    open_deals = deals[deals["dealstage"].isin(open_stages or stage_order)].copy()
    open_deals["days_in_stage"] = [
        (today - d).days if d else None for d in open_deals["stage_entered_at"].map(_to_date)
    ]
    med = open_deals.groupby("dealstage")["days_in_stage"].median()
    out["median_days_in_stage_now"] = out["stage"].map(med)
    return out


def fill_rates(df: pd.DataFrame, fields: list[str]) -> dict[str, float]:
    total = len(df) or 1
    return {f: round(1 - df[f].map(_blank).sum() / total, 3) for f in fields if f in df.columns}
