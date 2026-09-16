from __future__ import annotations

import re

FREE_MAIL = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com", "aol.com"}
EMAIL_RE = re.compile(r"^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}$")
SUFFIX_RE = re.compile(r"\b(inc|llc|ltd|co|corp|corporation|company)\b\.?", re.I)


def _text(value) -> str:
    """str() that treats None, NaN and pandas NA as empty."""
    try:
        if value is None or value != value:
            return ""
    except TypeError:  # pandas NA refuses to be used as a bool
        return ""
    return str(value)


def domain(value) -> str:
    v = _text(value).strip().lower()
    if v in ("", "nan", "none", "<na>"):
        return ""
    v = re.sub(r"^[a-z]+://", "", v)
    v = v.split("/")[0]
    return v[4:] if v.startswith("www.") else v


def company_name(value) -> str:
    v = _text(value).lower()
    v = SUFFIX_RE.sub(" ", v)
    v = re.sub(r"[^a-z0-9 ]", " ", v)
    return re.sub(r"\s+", " ", v).strip()


def email_problem(value, role_prefixes: list[str]) -> str:
    v = _text(value).strip().lower()
    if v in ("", "nan", "<na>"):
        return "missing email"
    if not EMAIL_RE.match(v):
        return "malformed email"
    local, dom = v.split("@", 1)
    if local.split("+")[0] in role_prefixes:
        return "role inbox"
    if dom in FREE_MAIL:
        return "personal email"
    return ""
