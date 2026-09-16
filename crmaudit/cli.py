from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from .audit import load, run_audit
from .report import write


def _parse_set(pairs: list[str]) -> dict:
    out = {}
    for p in pairs:
        k, v = p.split("=", 1)
        out[k] = int(v) if v.isdigit() else v
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="crmaudit", description="Audit a CRM export for data quality.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("audit", help="audit companies.csv, contacts.csv and deals.csv in a folder")
    a.add_argument("folder", type=Path)
    a.add_argument("--out", type=Path, default=Path("out"))
    a.add_argument("--today", help="YYYY-MM-DD, for reproducible runs")
    a.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                   help="override a threshold, e.g. --set stuck_days=21")

    p = sub.add_parser("pull", help="export the three objects from HubSpot (needs HUBSPOT_TOKEN)")
    p.add_argument("folder", type=Path)

    args = ap.parse_args(argv)
    if args.cmd == "pull":
        from .hubspot import export
        export(args.folder)
        print(f"exported to {args.folder}")
        return 0

    today = date.fromisoformat(args.today) if args.today else date.today()
    companies, contacts, deals = load(args.folder)
    result = run_audit(companies, contacts, deals, _parse_set(args.set), today)
    path = write(result, args.out)
    print(json.dumps({"health": result.health, "issues": len(result.issues), "report": str(path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
