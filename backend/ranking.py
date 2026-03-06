from datetime import datetime, timezone
from typing import Any, Optional

MMFC_SCORES: dict[str, int] = {
    "Reached - f/u scheduled": 20,
    "High Priority to Follow": 19,
    "Missed follow up (keep trying)": 18,
    "Reached - f/u not scheduled, but has interest": 15,
    "Have not reached yet": 12,
    "Pitched - confirmed 2nd f/u": 10,
    "Pitched - unconfirmed 2nd f/u": 8,
    "Follow up complete - order not started": 6,
    "Potentially in the future": 4,
    "Pitched - not interested": 2,
    "Declined a meeting": 2,
    "Reached - not interested": 2,
    "Order Complete": 0,
    "Unreachable - 10+ attempts": 0,
    "Unreachable - failing": 0,
    "Reason not to contact": 0,
}

ADVISER_SCORES: dict[str, int] = {
    "Pitched Offering - Follow up within 14 Days": 20,
    "Missed Follow Up": 18,
    "No Show": 15,
    "Pitched Offering - Follow up after 30 days": 10,
    "Shares Reserved": 8,
    "Potentially in the future": 5,
    "Not Interested to Invest More": 2,
    "Pitched Bundle Follow Up - Declined": 1,
    "Order Completed": 0,
}

TIER_ORDER: dict[str, int] = {"Platinum": 0, "Gold": 1, "Silver": 2, "Bronze": 3}
PERF_ORDER: dict[str, int] = {"Strong": 0, "Moderate": 1, "Weak": 2}


def _portfolio_score(value: Optional[Any]) -> float:
    if value is None:
        return 0.0
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 0.0
    if v <= 0:
        return 0.0
    elif v < 500_000:
        return 0.0
    elif v < 1_000_000:
        return 20.0 * (v - 500_000) / 500_000
    elif v < 5_000_000:
        return 20.0 + 40.0 * (v - 1_000_000) / 4_000_000
    elif v < 20_000_000:
        return 60.0 + 30.0 * (v - 5_000_000) / 15_000_000
    else:
        return 100.0


def _recency_score(last_seen_ms: Optional[Any]) -> float:
    if last_seen_ms is None or last_seen_ms == "":
        return 100.0
    try:
        ts = int(last_seen_ms) / 1000.0
        seen_dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        days_ago = (datetime.now(timezone.utc) - seen_dt).days
    except (TypeError, ValueError, OSError):
        return 100.0

    if days_ago > 365:
        return 90.0
    elif days_ago > 180:
        return 75.0
    elif days_ago > 90:
        return 55.0
    elif days_ago > 30:
        return 30.0
    else:
        return 10.0


def compute_score(props: dict[str, Any]) -> float:
    portfolio = _portfolio_score(props.get("total_investment_portfolio"))
    recency = _recency_score(props.get("admin_time_last_seen"))
    mmfc_raw = MMFC_SCORES.get(props.get("mmfc_outcome", ""), 12)
    adviser_raw = ADVISER_SCORES.get(props.get("existing_adviser_status", ""), 0)

    mmfc = mmfc_raw * 5.0       # scale 0-20 → 0-100
    adviser = adviser_raw * 5.0  # scale 0-20 → 0-100

    return round(
        portfolio * 0.35 + recency * 0.25 + mmfc * 0.20 + adviser * 0.20,
        2,
    )


def should_exclude(props: dict[str, Any]) -> bool:
    """Exclude contacts where both MMFC and adviser status indicate a terminal/closed state."""
    mmfc_raw = MMFC_SCORES.get(props.get("mmfc_outcome", ""), 12)
    adviser_raw = ADVISER_SCORES.get(props.get("existing_adviser_status", ""), 0)
    return mmfc_raw == 0 and adviser_raw == 0


def sort_key(contact: dict[str, Any]):
    props = contact.get("properties", {})
    return (
        -contact.get("score", 0.0),
        TIER_ORDER.get(props.get("investor_tier", ""), 99),
        PERF_ORDER.get(props.get("performance_status", ""), 99),
    )


def rank_contacts(contacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Score, filter terminal contacts, and sort. Returns enriched contact dicts."""
    scored = []
    for contact in contacts:
        props = contact.get("properties", {})
        if should_exclude(props):
            continue
        contact["score"] = compute_score(props)
        scored.append(contact)

    scored.sort(key=sort_key)
    for i, contact in enumerate(scored):
        contact["rank"] = i + 1
    return scored
