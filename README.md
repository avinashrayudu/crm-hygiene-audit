# crm-hygiene-audit

![tests](https://github.com/avinashrayudu/crm-hygiene-audit/actions/workflows/tests.yml/badge.svg)

A command-line audit for a HubSpot-style CRM. You point it at three exports (companies, contacts, deals). It finds duplicate accounts, unusable contacts, incomplete or stuck deals, and records with no company attached. Then it scores the CRM from 0 to 100 and writes a report a sales lead can act on.

```bash
python -m crmaudit audit data --today 2026-09-15
```

```json
{
  "health": {
    "company_dupes": 90.9,
    "contact_quality": 64.2,
    "deal_completeness": 36.5,
    "stuck_deals": 43.3,
    "orphans": 93.9,
    "overall": 61.6
  },
  "issues": 308,
  "report": "out/report.md"
}
```

Full sample output: [`docs/sample_report.md`](docs/sample_report.md)

## Why

A pipeline review only means something if the CRM underneath it is clean. The failures I kept running into were boring ones:

- the same store imported twice, once as `cornermarket.com` and once as `https://www.cornermarket.com/`
- `info@` and `orders@` inboxes sitting in outbound sequences
- deals with no channel tagged, so nobody could answer which channel was working
- open deals whose close date passed weeks ago, still counted in the forecast

None of these show up on a dashboard. They only show up when someone audits the records. This tool does that audit in a few seconds and tells you what to fix first.

## Checks

| Check | Object | Severity | What it catches |
|---|---|---|---|
| duplicate company | company | high | Same normalized domain, or company names that match at 92% or better (rapidfuzz token sort) in the same state when one side has no domain. Duplicates are clustered with union-find, so A=B and B=C become one merge group |
| duplicate contact | contact | high | Same email, ignoring case |
| role inbox | contact | high | `info@`, `hello@`, `orders@` and similar |
| malformed email | contact | high | Addresses that will bounce |
| personal email | contact | low | Gmail, Yahoo and similar. Often fine for very small shops |
| missing fields | all | high / medium | Required fields per object, set in `crmaudit/rules.py` |
| orphan contact / deal | contact, deal | medium / high | No valid company association |
| stuck deal | deal | medium | Open and unchanged for more than `stuck_days` (14 by default) |
| close date in the past | deal | high | Still open with a close date that has passed |

It also builds:

- **Funnel.** How many deals reached each stage and the conversion between stages. A lost deal counts up to the stage it reached before it was lost.
- **Fill rates.** The share of records that have each required field.
- **Merge list.** `merge_candidates.csv` lists which record to keep and which to merge into it.

## Health score

Each area is the share of records with no issues of that type. The overall score weights them:

| area | weight |
|---|---|
| contact quality | 25 |
| deal completeness | 25 |
| stuck deals | 20 |
| company duplicates | 15 |
| orphans | 15 |

Weights and thresholds live in `crmaudit/rules.py`. You can change any threshold for one run:

```bash
python -m crmaudit audit data --set stuck_days=21 --set fuzzy_name_threshold=88
```

## Using it on a real portal

```bash
export HUBSPOT_TOKEN=pat-xxx   # private app with read scopes on companies, contacts, deals
python -m crmaudit pull export/
python -m crmaudit audit export/
```

`crmaudit/hubspot.py` pages through the CRM v3 objects API and backs off on 429s. It maps properties onto the columns the audit reads. Custom properties such as the deal's sales channel differ from portal to portal, so check `PROPERTY_MAP` against your own portal first.

## What the sample data shows

The sample is a made-up specialty food brand selling into New York retail. The report says:

- **Deal completeness is 36.5%.** That's mostly because 42% of deals have no channel set, which makes any "which channel converts?" question unanswerable. The fix is to make channel required when a deal is created.
- **29 open deals haven't moved in two weeks, and 14 have a close date in the past.** Those 14 still count toward the forecast.
- **11 company records are copies of another account.** Each one pairs with an original, and `merge_candidates.csv` lists them.
- **The two weakest funnel steps are won to reorder (54%) and meeting to quote (61%).** For a consumer brand, the reorder rate matters most, because the first order is a trial.

## Run it

```bash
pip install -e ".[dev]"
python scripts/make_sample_data.py
python -m crmaudit audit data --today 2026-09-15 --out out
pytest -q
```

## Layout

```
crmaudit/checks.py     individual checks, funnel and fill rates
crmaudit/audit.py      runs the checks and computes the health score
crmaudit/report.py     markdown report, issues.csv, merge_candidates.csv
crmaudit/hubspot.py    optional export from a live HubSpot portal
scripts/               fake data generator
tests/                 unit and end-to-end tests
```

All companies and people in `data/` are invented.
