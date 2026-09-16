from __future__ import annotations

from pathlib import Path

from .audit import AuditResult

FIXES = {
    "duplicate company": "Merge into the lowest record id. Check which record owns the open deals first.",
    "duplicate contact": "Merge; keep the record with the most recent activity.",
    "missing fields": "Make the field required at the stage where it becomes known, not at create.",
    "role inbox": "Find a named person. A shared inbox can't be personalized or reliably tracked.",
    "malformed email": "Fix or clear. These bounce and hurt sender reputation.",
    "personal email": "Fine for founders of very small brands; otherwise look for a work address.",
    "orphan contact": "Associate to a company so the contact shows up in account views.",
    "orphan deal": "Associate to a company; unassociated deals disappear from account rollups.",
    "stuck deal": "Ask the owner for a next step and a date, or close it lost.",
    "close date in the past": "Move the close date or close the deal. These inflate the forecast.",
}


def _table(rows: list[list], header: list[str]) -> str:
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    for r in rows:
        out.append("| " + " | ".join("" if v is None else str(v) for v in r) + " |")
    return "\n".join(out)


def _pct(v) -> str:
    return "" if v is None or v != v else f"{v:.0%}"


def write(result: AuditResult, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    result.issues.to_csv(out_dir / "issues.csv", index=False)
    with open(out_dir / "merge_candidates.csv", "w") as fh:
        fh.write("keep_id,merge_ids\n")
        for g in result.company_clusters:
            fh.write(f"{g[0]},{' '.join(g[1:])}\n")

    h = result.health
    c = result.counts
    lines = [
        "# CRM health report",
        "",
        f"**Overall health: {h['overall']} / 100**  ",
        f"{c['companies']} companies · {c['contacts']} contacts · {c['deals']} deals ({c['open_deals']} open)",
        "",
        "## Score breakdown",
        "",
        _table([[k.replace('_', ' '), f"{v}%"] for k, v in h.items() if k != "overall"],
               ["area", "records passing"]),
        "",
        "## Issues by check",
        "",
    ]
    if result.issues.empty:
        lines.append("No issues found.")
    else:
        summary = (result.issues.groupby(["check", "severity"]).size()
                   .reset_index(name="count").sort_values("count", ascending=False))
        lines.append(_table([[r.check, r.severity, r.count, FIXES.get(r.check, "")]
                             for r in summary.itertuples()],
                            ["check", "severity", "records", "what to do"]))
    lines += ["", "## Pipeline funnel", ""]
    f = result.funnel
    lines.append(_table([[r.stage, r.reached, _pct(r.step_conversion),
                          "" if r.median_days_in_stage_now != r.median_days_in_stage_now else int(r.median_days_in_stage_now)]
                         for r in f.itertuples()],
                        ["stage", "deals reached", "from previous stage", "median days sitting there now"]))
    lines += ["", "## Field fill rates", ""]
    for obj, rates in result.fill_rates.items():
        lines.append(f"**{obj}**: " + ", ".join(f"{k} {v:.0%}" for k, v in rates.items()))
        lines.append("")
    if result.company_clusters:
        lines += ["## Largest duplicate clusters", ""]
        top = sorted(result.company_clusters, key=len, reverse=True)[:5]
        lines.append(_table([[g[0], ", ".join(g[1:])] for g in top], ["keep", "merge"]))
    path = out_dir / "report.md"
    path.write_text("\n".join(lines) + "\n")
    return path
