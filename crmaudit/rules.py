"""Default thresholds. Override any of them from the CLI with --set key=value."""

DEFAULTS = {
    "fuzzy_name_threshold": 92,     # rapidfuzz token_sort_ratio for company names
    "stuck_days": 14,               # open deal with no stage change for this long
    "stale_contact_days": 180,      # no activity for this long
    "required_deal_fields": ["amount", "closedate", "dealstage", "hubspot_owner_id", "pipeline_channel"],
    "required_contact_fields": ["email", "firstname", "lastname", "jobtitle", "associated_company_id"],
    "required_company_fields": ["domain", "industry", "state", "lifecyclestage"],
    "open_stages": ["target", "contacted", "sampled", "meeting_held", "quote_sent"],
    "stage_order": ["target", "contacted", "sampled", "meeting_held", "quote_sent", "closed_won", "reordered"],
    "role_inbox_prefixes": ["info", "hello", "sales", "contact", "support", "team", "admin",
                            "orders", "office", "founders", "hey", "hi"],
    # weights for the 0-100 health score; each is the share of records passing
    "weights": {"company_dupes": 15, "contact_quality": 25, "deal_completeness": 25,
                "stuck_deals": 20, "orphans": 15},
}
