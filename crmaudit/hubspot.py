"""Pull companies, contacts and deals from HubSpot into the CSV shape the audit reads.

Needs a private app token with crm.objects.companies.read,
crm.objects.contacts.read and crm.objects.deals.read, in HUBSPOT_TOKEN.
Stage-entry dates come from the deal's `hs_v2_date_entered_current_stage`
property. Pipelines and custom properties differ per portal, so check
PROPERTY_MAP against your own portal first.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
from pathlib import Path

import pandas as pd

BASE = "https://api.hubapi.com/crm/v3/objects"

PROPERTY_MAP = {
    "companies": {"name": "name", "domain": "domain", "industry": "industry",
                  "state": "state", "lifecyclestage": "lifecyclestage"},
    "contacts": {"email": "email", "firstname": "firstname", "lastname": "lastname",
                 "jobtitle": "jobtitle", "associatedcompanyid": "associated_company_id"},
    "deals": {"dealname": "dealname", "amount": "amount", "closedate": "closedate",
              "dealstage": "dealstage", "hubspot_owner_id": "hubspot_owner_id",
              "channel": "pipeline_channel",
              "hs_v2_date_entered_current_stage": "stage_entered_at"},
}
ID_COL = {"companies": "company_id", "contacts": "contact_id", "deals": "deal_id"}


def _get(url: str, token: str) -> dict:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            if e.code == 429:  # rate limited; back off and retry
                time.sleep(2 ** attempt)
                continue
            raise
    raise RuntimeError("HubSpot kept rate limiting; try again later")


def pull(obj: str, token: str) -> pd.DataFrame:
    props = ",".join(PROPERTY_MAP[obj])
    extra = "&associations=companies" if obj == "deals" else ""
    url = f"{BASE}/{obj}?limit=100&properties={props}{extra}"
    rows = []
    while url:
        data = _get(url, token)
        for rec in data.get("results", []):
            row = {ID_COL[obj]: rec["id"]}
            for src, dst in PROPERTY_MAP[obj].items():
                row[dst] = rec["properties"].get(src)
            if obj == "deals":
                assoc = rec.get("associations", {}).get("companies", {}).get("results", [])
                row["associated_company_id"] = assoc[0]["id"] if assoc else None
            rows.append(row)
        nxt = data.get("paging", {}).get("next", {}).get("link")
        url = nxt
    return pd.DataFrame(rows)


def export(folder: Path) -> None:
    token = os.environ.get("HUBSPOT_TOKEN")
    if not token:
        raise SystemExit("Set HUBSPOT_TOKEN to a private app token first.")
    folder.mkdir(parents=True, exist_ok=True)
    for obj, fname in (("companies", "companies.csv"), ("contacts", "contacts.csv"), ("deals", "deals.csv")):
        pull(obj, token).to_csv(folder / fname, index=False)
