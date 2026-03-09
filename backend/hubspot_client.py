import httpx
from typing import Any
from config import settings

BASE_URL = "https://api.hubapi.com"

PROPERTIES = [
    "firstname",
    "lastname",
    "email",
    "phone",
    "be_launch_lists___lead_owner",
    "total_investment_portfolio",
    "admin_time_last_seen",
    "investor_tier",
    "performance_status",
    "existing_adviser_status",
    "mmfc_outcome",
    "totalamountpurchased",
    "hs_linkedin_url",
    "aircall_last_call_at",
    "last_seen_timestamp",
    "notes_next_activity_date",
]

ADVISOR_NAMES = [
    "Michael Strang",
    "Evan McMann",
    "Brendan Miles",
    "Anthony DeSimone",
    "Jake Maggy",
    "Alec McKenna",
    "Mike DelPozzo",
    "Erik Bringsjord",
    "Candy Light",
    "Kevin Cox",
]


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.HUBSPOT_TOKEN}",
        "Content-Type": "application/json",
    }


async def fetch_contacts_for_advisor(advisor_name: str) -> list[dict[str, Any]]:
    """Fetch all HubSpot contacts assigned to the given advisor via the Search API."""
    contacts = []
    cursor = None

    async with httpx.AsyncClient(base_url=BASE_URL, headers=_headers(), timeout=30) as client:
        while True:
            body: dict[str, Any] = {
                "filterGroups": [{
                    "filters": [{
                        "propertyName": "be_launch_lists___lead_owner",
                        "operator": "EQ",
                        "value": advisor_name,
                    }]
                }],
                "properties": PROPERTIES,
                "limit": 100,
            }
            if cursor:
                body["after"] = cursor

            response = await client.post("/crm/v3/objects/contacts/search", json=body)
            response.raise_for_status()
            data = response.json()

            results = data.get("results", [])
            contacts.extend(results)

            paging = data.get("paging", {})
            next_cursor = paging.get("next", {}).get("after")
            if not next_cursor:
                break
            cursor = next_cursor

    return contacts


def get_advisor_names() -> list[str]:
    return ADVISOR_NAMES
