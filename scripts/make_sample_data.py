"""Build a fake HubSpot-style export with realistic mess planted in it.

Everything is invented. The as-of date is fixed so the report is reproducible:
    python -m crmaudit audit data --today 2026-09-15
"""
from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from pathlib import Path

random.seed(11)
OUT = Path(__file__).resolve().parents[1] / "data"
AS_OF = date(2026, 9, 15)

A = ["Corner", "Brooklyn", "Hudson", "Garden", "Village", "Harbor", "Park Slope", "Union",
     "Maple", "Juniper", "Olive", "Sunrise", "Parkside", "Riverside", "Main Street", "Elm"]
B = ["Market", "Grocer", "Pantry", "Cafe", "Provisions", "Bodega", "Gift Shop", "Foods",
     "Co-op", "Deli", "Cheese Shop", "Bakery"]
INDUSTRIES = ["Grocery", "Specialty Food", "Cafe", "Gift & Home", "Hospitality", "Corporate"]
STATES = ["NY", "NY", "NY", "NJ", "CT", "MA", "PA"]
LIFECYCLE = ["lead", "opportunity", "customer", "customer", ""]
FIRST = ["Ana", "Ben", "Chloe", "Dev", "Eli", "Fatima", "Gus", "Hana", "Ivan", "Jo", "Kira", "Leo",
         "Mina", "Nate", "Ola", "Pia", "Raj", "Sofia", "Tom", "Uma", "Vic", "Wen", "Yara", "Zed"]
LAST = ["Adler", "Baptiste", "Cruz", "Dunn", "Ekwueme", "Fischer", "Gomez", "Haddad", "Iqbal",
        "Jensen", "Khan", "Liang", "Murphy", "Novak", "Osei", "Patel", "Quinn", "Rossi"]
TITLES = ["Store Manager", "Owner", "Buyer", "General Manager", "Purchasing Manager",
          "Category Manager", "Office Manager", "", "Assistant Manager"]
STAGES = ["target", "contacted", "sampled", "meeting_held", "quote_sent", "closed_won", "reordered", "closed_lost"]
STAGE_WEIGHTS = [18, 22, 14, 10, 8, 12, 6, 10]
OWNERS = ["101", "102", "103", ""]
CHANNELS = ["retail", "wholesale", "corporate", "hospitality", "", ""]


def slug(s):
    return "".join(ch for ch in s.lower() if ch.isalnum())


companies = []
used = set()
cid = 1000
while len(companies) < 110:
    name = f"{random.choice(A)} {random.choice(B)}"
    if name in used:
        continue
    used.add(name)
    cid += 1
    companies.append({
        "company_id": str(cid), "name": name,
        "domain": slug(name) + random.choice([".com", ".nyc", ".co"]) if random.random() > 0.15 else "",
        "industry": random.choice(INDUSTRIES) if random.random() > 0.2 else "",
        "state": random.choice(STATES),
        "lifecyclestage": random.choice(LIFECYCLE),
    })

# Planted duplicates: the same shop imported again with a different spelling or a www domain.
for src in random.sample([c for c in companies if c["domain"]], 6):
    cid += 1
    companies.append({**src, "company_id": str(cid),
                      "name": src["name"] + random.choice([" Inc.", " LLC", ""]),
                      "domain": "https://www." + src["domain"] + "/"})
for src in random.sample(companies[:100], 5):
    cid += 1
    companies.append({**src, "company_id": str(cid),
                      "name": src["name"].replace(" ", "  ").upper() + " Co", "domain": ""})

contacts = []
ctid = 5000
for c in companies:
    for _ in range(random.choice([1, 2, 2, 3])):
        ctid += 1
        fn, ln = random.choice(FIRST), random.choice(LAST)
        dom = c["domain"].replace("https://www.", "").strip("/") or slug(c["name"]) + ".com"
        roll = random.random()
        if roll < 0.08:
            email = random.choice(["info", "hello", "orders", "hey"]) + "@" + dom
        elif roll < 0.11:
            email = f"{fn.lower()}.{ln.lower()}@{dom}".replace("@", "")  # malformed
        elif roll < 0.16:
            email = f"{fn.lower()}{ln.lower()}@gmail.com"
        elif roll < 0.20:
            email = ""
        else:
            email = f"{fn.lower()}@{dom}"
        contacts.append({
            "contact_id": str(ctid), "email": email, "firstname": fn,
            "lastname": ln if random.random() > 0.05 else "",
            "jobtitle": random.choice(TITLES),
            "associated_company_id": c["company_id"] if random.random() > 0.07 else "",
        })
for src in random.sample([x for x in contacts if "@" in x["email"]], 7):
    ctid += 1
    contacts.append({**src, "contact_id": str(ctid), "email": src["email"].upper()})
# normalize the uppercase copies so the dedupe check (case-insensitive) sees them
for x in contacts:
    x["email"] = x["email"].lower()

deals = []
did = 9000
for c in random.sample(companies, 85):
    did += 1
    stage = random.choices(STAGES, STAGE_WEIGHTS)[0]
    entered = AS_OF - timedelta(days=random.choice([1, 3, 5, 8, 12, 16, 22, 35, 60]))
    close = AS_OF + timedelta(days=random.randint(-40, 75))
    deals.append({
        "deal_id": str(did), "dealname": f"{c['name']} opening order",
        "amount": "" if random.random() < 0.15 else str(random.choice([180, 240, 360, 480, 720, 1200])),
        "closedate": "" if random.random() < 0.08 else close.isoformat(),
        "dealstage": stage,
        "lost_at_stage": random.choice(STAGES[:5]) if stage == "closed_lost" else "",
        "stage_entered_at": entered.isoformat(),
        "hubspot_owner_id": random.choice(OWNERS),
        "pipeline_channel": random.choice(CHANNELS),
        "associated_company_id": c["company_id"] if random.random() > 0.05 else "",
    })

OUT.mkdir(exist_ok=True)
for name, rows in (("companies.csv", companies), ("contacts.csv", contacts), ("deals.csv", deals)):
    with open(OUT / name, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
print(f"{len(companies)} companies, {len(contacts)} contacts, {len(deals)} deals -> {OUT}")
