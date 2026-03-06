"""Google Calendar service — finds the next upcoming meeting with a given investor."""

import asyncio
from datetime import datetime, timezone, timedelta
from functools import partial
from typing import Optional

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
from googleapiclient.discovery import build

from config import settings

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


def _build_credentials(access_token: str, refresh_token: str, token_expiry: datetime) -> Credentials:
    # Google's Credentials expects a naive UTC datetime for expiry
    expiry = token_expiry.replace(tzinfo=None) if token_expiry.tzinfo else token_expiry
    return Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        scopes=SCOPES,
        expiry=expiry,
    )


def _find_next_meeting_sync(
    access_token: str,
    refresh_token: str,
    token_expiry: datetime,
    investor_email: str,
) -> Optional[dict]:
    """Synchronous Google API call — run via run_in_executor."""
    creds = _build_credentials(access_token, refresh_token, token_expiry)

    # Auto-refresh if token is expired
    if creds.expired and creds.refresh_token:
        creds.refresh(GoogleRequest())

    service = build("calendar", "v3", credentials=creds, cache_discovery=False)

    now_iso = datetime.now(timezone.utc).isoformat()
    events_result = service.events().list(
        calendarId="primary",
        timeMin=now_iso,
        maxResults=20,
        singleEvents=True,
        orderBy="startTime",
    ).execute()

    events = events_result.get("items", [])
    email_lower = investor_email.lower()

    for event in events:
        attendees = event.get("attendees", [])
        attendee_emails = {a.get("email", "").lower() for a in attendees}
        organizer_email = event.get("organizer", {}).get("email", "").lower()

        if email_lower in attendee_emails or email_lower == organizer_email:
            start = event["start"].get("dateTime") or event["start"].get("date")
            return {
                "start": start,
                "summary": event.get("summary", "Meeting"),
                # Return new token if it was refreshed
                "new_access_token": creds.token if creds.token != access_token else None,
                "new_expiry": (
                    creds.expiry.replace(tzinfo=timezone.utc).isoformat()
                    if creds.expiry else None
                ),
            }

    return None


async def get_next_meeting(
    access_token: str,
    refresh_token: str,
    token_expiry: datetime,
    investor_email: str,
) -> Optional[dict]:
    """Async wrapper — delegates sync Google API call to a thread pool."""
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        partial(_find_next_meeting_sync, access_token, refresh_token, token_expiry, investor_email),
    )
    return result
