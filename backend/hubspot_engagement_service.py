"""Fetch HubSpot engagements (notes, emails) for a contact."""

import html
import re
import httpx
from typing import Any
from config import settings

BASE_URL = "https://api.hubapi.com"


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.HUBSPOT_TOKEN}",
        "Content-Type": "application/json",
    }


def _date(timestamp: str) -> str:
    """Return YYYY-MM-DD from an ISO timestamp string."""
    return timestamp[:10] if timestamp else ""


def _strip_html(text: str) -> str:
    """Remove HTML tags and decode entities from HubSpot rich-text fields."""
    text = html.unescape(text)
    # Replace block-level tags with newlines so paragraphs stay readable
    text = re.sub(r'<(br|p|div|li)[^>]*>', '\n', text, flags=re.IGNORECASE)
    # Strip all remaining tags
    text = re.sub(r'<[^>]+>', '', text)
    # Collapse runs of whitespace / blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


async def get_contact_notes(contact_id: str, limit: int = 5) -> list[str]:
    """Return the most recent HubSpot notes for a contact as formatted strings."""
    async with httpx.AsyncClient(base_url=BASE_URL, headers=_headers(), timeout=30) as client:
        body: dict[str, Any] = {
            "filterGroups": [{
                "filters": [{
                    "propertyName": "associations.contact",
                    "operator": "EQ",
                    "value": contact_id,
                }]
            }],
            "properties": ["hs_note_body", "hs_timestamp"],
            "sorts": [{"propertyName": "hs_timestamp", "direction": "DESCENDING"}],
            "limit": limit,
        }
        try:
            response = await client.post("/crm/v3/objects/notes/search", json=body)
            response.raise_for_status()
        except Exception:
            return []

        results: list[str] = []
        for note in response.json().get("results", []):
            props = note.get("properties", {})
            body_text = _strip_html(props.get("hs_note_body") or "")
            date = _date(props.get("hs_timestamp", ""))
            if body_text:
                results.append(f"[Note {date}]: {body_text[:800]}")
        return results


async def get_contact_emails(contact_id: str, limit: int = 5) -> list[str]:
    """Return the most recent HubSpot emails for a contact as formatted strings."""
    async with httpx.AsyncClient(base_url=BASE_URL, headers=_headers(), timeout=30) as client:
        body: dict[str, Any] = {
            "filterGroups": [{
                "filters": [{
                    "propertyName": "associations.contact",
                    "operator": "EQ",
                    "value": contact_id,
                }]
            }],
            "properties": ["hs_email_subject", "hs_email_text", "hs_timestamp", "hs_email_direction"],
            "sorts": [{"propertyName": "hs_timestamp", "direction": "DESCENDING"}],
            "limit": limit,
        }
        try:
            response = await client.post("/crm/v3/objects/emails/search", json=body)
            response.raise_for_status()
        except Exception:
            return []

        results: list[str] = []
        for email in response.json().get("results", []):
            props = email.get("properties", {})
            subject = (props.get("hs_email_subject") or "No subject").strip()
            text = (props.get("hs_email_text") or "").strip()[:600]
            date = _date(props.get("hs_timestamp", ""))
            direction = props.get("hs_email_direction", "")
            label = "Inbound" if "INBOUND" in direction.upper() else "Outbound"
            if subject or text:
                results.append(f"[Email {date} — {label}] Subject: {subject}\n{text}")
        return results
