import asyncio
import os
import re
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from typing import Optional

import asyncpg
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from config import settings
from database import init_db, upsert_discard, get_active_discards, save_google_token, get_google_token, log_event, get_report
from hubspot_client import fetch_contacts_for_advisor, get_advisor_names
from hubspot_engagement_service import get_contact_notes, get_contact_emails, get_recent_note
from ranking import rank_contacts, sort_key
from aircall_service import get_investor_transcripts
from claude_service import generate_investor_status
from google_calendar_service import get_next_meeting
from models import DiscardRequest, LeadResponse, AdvisorsResponse, InvestorStatusResponse, AnalyticsEvent


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create PostgreSQL connection pool and init schema
    pool = await asyncpg.create_pool(settings.DATABASE_URL, min_size=2, max_size=10)
    await init_db(pool)
    app.state.db = pool
    yield
    await pool.close()


app = FastAPI(title="Advisor Calling Tool", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # safe: Railway serves frontend from same origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

HUBSPOT_CONTACT_URL = "https://app.hubspot.com/contacts/{account_id}/record/0-1/{contact_id}"


def _format_date(ms_value: Optional[str]) -> Optional[str]:
    """Parse either a millisecond epoch string or an ISO 8601 datetime string."""
    if not ms_value:
        return None
    # Try millisecond epoch first (e.g. "1635854840000")
    try:
        ts = int(ms_value) / 1000.0
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
    except (TypeError, ValueError, OSError):
        pass
    # Fall back to ISO 8601 (e.g. "2025-11-02T14:07:20Z")
    try:
        dt = datetime.fromisoformat(ms_value.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return None


def _had_4min_call(contact: dict) -> bool:
    """Return True if HubSpot records a 4+ minute Aircall conversation for this contact.

    Uses two HubSpot properties synced by the Aircall integration:
    - had_call_over_4_minutes: "Yes" if any historical call exceeded 4 min
    - aircall_call_duration: last call duration in milliseconds (>= 240000 = 4 min)
    """
    props = contact.get("properties", {})
    if (props.get("had_call_over_4_minutes") or "").strip().lower() == "yes":
        return True
    duration_raw = props.get("aircall_call_duration")
    if duration_raw:
        try:
            return int(duration_raw) >= 240_000
        except (ValueError, TypeError):
            pass
    return False


# ─── Note sentiment ──────────────────────────────────────────────────────────

_NOTE_NEGATIVE = {
    "not interested", "not looking", "doesn't want", "don't want",
    "no longer interested", "pass", "happy with current", "not allocating",
    "not going to invest", "no interest", "do not call", "dnc", "declined",
    "no thanks", "not ready", "won't be investing", "too risky", "not for me",
}
_NOTE_POSITIVE = {
    "interested", "excited", "looking to", "wants to", "would like",
    "moving forward", "ready to", "schedule a call", "considering",
    "open to it", "more allocation", "wants more", "asked about",
    "like the concept", "love the concept", "great opportunity",
}

# Catches "not interested", "not really interested", "not very interested",
# "not that interested", "not at all interested", etc.
_NOT_INTERESTED_RE = re.compile(r'\bnot\b\s+(?:\w+\s+){0,2}interested\b', re.IGNORECASE)


def _note_sentiment_delta(text: str) -> float:
    """Return -15 (disinterest), +10 (interest), or 0 (neutral) based on note keywords."""
    t = text.lower()
    if any(kw in t for kw in _NOTE_NEGATIVE):
        return -15.0
    if _NOT_INTERESTED_RE.search(t):
        return -15.0
    if any(kw in t for kw in _NOTE_POSITIVE):
        return +10.0
    return 0.0


_CLOSED_ADVISER_ONLY = {"not interested to invest more", "no show"}


def _is_closed(contact: dict) -> bool:
    """Return True if the contact has already been closed or disengaged."""
    props = contact.get("properties", {})
    for field in ("mmfc_outcome", "existing_adviser_status"):
        val = (props.get(field) or "").lower().strip()
        if "order completed" in val:
            return True
    adviser = (props.get("existing_adviser_status") or "").lower().strip()
    if adviser in _CLOSED_ADVISER_ONLY:
        return True
    return False


def _has_scheduled_followup(contact: dict) -> bool:
    """Return True if a future HubSpot activity is already scheduled for this contact."""
    next_date = contact.get("properties", {}).get("notes_next_activity_date")
    if not next_date:
        return False
    try:
        dt = datetime.fromisoformat(next_date.replace("Z", "+00:00"))
        return dt > datetime.now(timezone.utc)
    except (TypeError, ValueError):
        return False


def _build_lead(contact: dict, rank: int) -> LeadResponse:
    props = contact.get("properties", {})
    contact_id = contact["id"]
    first = props.get("firstname") or ""
    last = props.get("lastname") or ""

    portfolio_raw = props.get("total_investment_portfolio")
    purchased_raw = props.get("totalamountpurchased")

    return LeadResponse(
        id=contact_id,
        rank=rank,
        score=contact.get("score", 0.0),
        first_name=first,
        last_name=last,
        full_name=f"{first} {last}".strip(),
        email=props.get("email"),
        linkedin_url=props.get("hs_linkedin_url"),
        admin_time_last_seen=_format_date(props.get("admin_time_last_seen")),
        investor_tier=props.get("investor_tier"),
        performance_status=props.get("performance_status"),
        mmfc_existing_owner=props.get("be_launch_lists___lead_owner"),
        total_amount_purchased=float(purchased_raw) if purchased_raw else None,
        total_investment_portfolio=float(portfolio_raw) if portfolio_raw else None,
        hubspot_url=HUBSPOT_CONTACT_URL.format(
            account_id=settings.HUBSPOT_ACCOUNT_ID,
            contact_id=contact_id,
        ),
        last_call_date=_format_date(props.get("aircall_last_call_at")),
        last_website_visit=_format_date(props.get("last_seen_timestamp")),
        recent_note=contact.get("recent_note"),
        recent_note_date=contact.get("recent_note_date"),
    )


def _create_google_flow():
    """Build a google_auth_oauthlib Flow from settings."""
    from google_auth_oauthlib.flow import Flow
    return Flow.from_client_config(
        {
            "web": {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [settings.GOOGLE_REDIRECT_URI],
            }
        },
        scopes=["https://www.googleapis.com/auth/calendar.readonly"],
        redirect_uri=settings.GOOGLE_REDIRECT_URI,
    )


# ─── API Routes (all prefixed /api/) ─────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/advisors", response_model=AdvisorsResponse)
async def advisors():
    return AdvisorsResponse(advisors=get_advisor_names())


@app.get("/api/leads", response_model=list[LeadResponse])
async def leads(request: Request, advisor: str = Query(..., description="Advisor name")):
    valid = get_advisor_names()
    if advisor not in valid:
        raise HTTPException(status_code=400, detail=f"Unknown advisor: {advisor}")

    pool = request.app.state.db
    contacts = await fetch_contacts_for_advisor(advisor)
    discarded = await get_active_discards(pool, advisor)
    contacts = [c for c in contacts if c["id"] not in discarded]
    contacts = [c for c in contacts if not _is_closed(c)]
    contacts = [c for c in contacts if not _has_scheduled_followup(c)]
    contacts = [c for c in contacts if _had_4min_call(c)]

    ranked = rank_contacts(contacts)

    # ── Phase 2: enrich top 50 with most recent note ──────────────────────────
    candidates = ranked[:50]
    sem = asyncio.Semaphore(10)

    async def _fetch_note(cid: str):
        async with sem:
            return await get_recent_note(cid)

    note_results = await asyncio.gather(
        *[_fetch_note(c["id"]) for c in candidates],
        return_exceptions=True,
    )
    for contact, note in zip(candidates, note_results):
        if isinstance(note, dict):
            contact["recent_note"]      = note["text"]
            contact["recent_note_date"] = note["date"]
            delta = _note_sentiment_delta(note["text"])
            contact["score"] = round(max(0.0, min(100.0, contact["score"] + delta)), 2)
        else:
            contact["recent_note"] = contact["recent_note_date"] = None

    candidates.sort(key=sort_key)
    for i, c in enumerate(candidates):
        c["rank"] = i + 1
    # ──────────────────────────────────────────────────────────────────────────

    return [_build_lead(c, c["rank"]) for c in candidates[:35]]


@app.post("/api/discard")
async def discard(request: Request, req: DiscardRequest):
    valid = get_advisor_names()
    if req.advisor_name not in valid:
        raise HTTPException(status_code=400, detail=f"Unknown advisor: {req.advisor_name}")
    if req.duration not in ("today", "30days", "forever"):
        raise HTTPException(status_code=400, detail="duration must be 'today', '30days', or 'forever'")

    now = datetime.now(timezone.utc)
    if req.duration == "today":
        until: Optional[datetime] = now.replace(hour=23, minute=59, second=59, microsecond=0)
    elif req.duration == "30days":
        until = now + timedelta(days=30)
    else:
        until = None

    pool = request.app.state.db
    await upsert_discard(pool, req.advisor_name, req.contact_id, until)
    return {"ok": True}


@app.get("/api/investor-status", response_model=InvestorStatusResponse)
async def investor_status(
    contact_id: str = Query(...),
    name: str = Query(...),
):
    try:
        # Fetch all three data sources in parallel
        transcripts, notes, emails = await asyncio.gather(
            get_investor_transcripts(name),
            get_contact_notes(contact_id),
            get_contact_emails(contact_id),
            return_exceptions=False,
        )
        status = await generate_investor_status(name, transcripts, notes, emails)
    except Exception as e:
        status = f"Unable to generate status: {str(e)}"

    return InvestorStatusResponse(contact_id=contact_id, status=status)


# ─── Google Calendar OAuth ─────────────────────────────────────────────────────

@app.get("/api/auth/google")
async def google_auth(advisor: str = Query(..., description="Advisor name")):
    """Redirect advisor to Google OAuth consent screen."""
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=503, detail="Google Calendar not configured")
    flow = _create_google_flow()
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        state=advisor,
    )
    return RedirectResponse(auth_url)


@app.get("/api/auth/google/callback")
async def google_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
):
    """Exchange Google auth code for tokens and store them."""
    advisor_name = state
    valid = get_advisor_names()
    if advisor_name not in valid:
        raise HTTPException(status_code=400, detail="Invalid advisor in OAuth state")

    flow = _create_google_flow()
    flow.fetch_token(code=code)
    creds = flow.credentials

    # Ensure expiry is timezone-aware
    expiry = creds.expiry  # naive UTC from Google
    if expiry:
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
    else:
        expiry = datetime.now(timezone.utc) + timedelta(hours=1)

    pool = request.app.state.db
    await save_google_token(
        pool,
        advisor_name,
        creds.token,
        creds.refresh_token or "",
        expiry,
    )

    return RedirectResponse("/?calendar=connected")


@app.get("/api/calendar/next-meeting")
async def calendar_next_meeting(
    request: Request,
    advisor: str = Query(...),
    contact_email: str = Query(...),
):
    """Return the next upcoming calendar event matching a contact's email."""
    pool = request.app.state.db
    token_data = await get_google_token(pool, advisor)

    if not token_data:
        return {"connected": False, "meeting": None}

    try:
        result = await get_next_meeting(
            token_data["access_token"],
            token_data["refresh_token"],
            token_data["token_expiry"],
            contact_email,
        )
    except Exception:
        # Token may have been revoked or expired beyond refresh — treat as not connected
        return {"connected": False, "meeting": None}

    if result is None:
        return {"connected": True, "meeting": None}

    # Persist refreshed token if Google rotated it
    if result.get("new_access_token"):
        expiry_str = result.get("new_expiry")
        if expiry_str:
            new_expiry = datetime.fromisoformat(expiry_str)
            if new_expiry.tzinfo is None:
                new_expiry = new_expiry.replace(tzinfo=timezone.utc)
        else:
            new_expiry = datetime.now(timezone.utc) + timedelta(hours=1)
        await save_google_token(
            pool,
            advisor,
            result["new_access_token"],
            token_data["refresh_token"],
            new_expiry,
        )

    return {
        "connected": True,
        "meeting": {
            "start": result["start"],
            "summary": result["summary"],
        },
    }


# ─── Analytics ───────────────────────────────────────────────────────────────

@app.post("/api/analytics", status_code=204)
async def track(request: Request, event: AnalyticsEvent):
    """Fire-and-forget event logger. Never raises to the client."""
    try:
        await log_event(request.app.state.db, event.advisor_name, event.event_type)
    except Exception:
        pass  # never block the UI


@app.get("/report", response_class=HTMLResponse)
async def report_page(request: Request, days: int = 7):
    """Bookmarkable admin report: daily usage by advisor."""
    rows = await get_report(request.app.state.db, days)

    if rows:
        row_html = "\n".join(
            f"<tr>"
            f"<td>{r['day']}</td>"
            f"<td>{r['advisor_name']}</td>"
            f"<td class='num'>{r['page_loads']}</td>"
            f"<td class='num'>{r['refreshes']}</td>"
            f"<td class='num'>{r['clicks']}</td>"
            f"</tr>"
            for r in rows
        )
    else:
        row_html = "<tr><td colspan='5' class='empty'>No events recorded yet.</td></tr>"

    active7  = 'class="active"' if days == 7  else ''
    active30 = 'class="active"' if days == 30 else ''

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Usage Report</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            background: #f5f5f5; color: #111827; padding: 40px 32px; margin: 0; }}
    h1   {{ font-size: 22px; font-weight: 700; margin: 0 0 4px; }}
    .sub {{ color: #6b7280; font-size: 13px; margin: 0 0 24px; }}
    .toggle {{ margin-bottom: 20px; display: flex; gap: 8px; }}
    .toggle a {{ padding: 6px 16px; border-radius: 6px; background: #e5e7eb;
                 color: #374151; text-decoration: none; font-size: 13px;
                 font-weight: 500; transition: background .15s; }}
    .toggle a:hover {{ background: #d1d5db; }}
    .toggle a.active {{ background: #495DE5; color: #fff; }}
    table  {{ width: 100%; border-collapse: collapse; background: #fff;
              border-radius: 10px; overflow: hidden;
              box-shadow: 0 1px 4px rgba(0,0,0,.08); }}
    th     {{ padding: 11px 16px; text-align: left; font-size: 11px;
              text-transform: uppercase; letter-spacing: .06em;
              color: #9ca3af; background: #fafafa;
              border-bottom: 1px solid #e5e7eb; }}
    th.num {{ text-align: right; }}
    td     {{ padding: 12px 16px; font-size: 14px;
              border-bottom: 1px solid #f3f4f6; }}
    tr:last-child td {{ border-bottom: none; }}
    tr:hover td {{ background: #fafafa; }}
    .num   {{ text-align: right; font-variant-numeric: tabular-nums; }}
    .empty {{ text-align: center; color: #9ca3af; padding: 48px !important; }}
  </style>
</head>
<body>
  <h1>Usage Report</h1>
  <p class="sub">Advisor activity — last {days} days (ET)</p>
  <div class="toggle">
    <a href="/report?days=7"  {active7}>Last 7 days</a>
    <a href="/report?days=30" {active30}>Last 30 days</a>
  </div>
  <table>
    <thead>
      <tr>
        <th>Date</th>
        <th>Advisor</th>
        <th class="num">Page Loads</th>
        <th class="num">Refreshes</th>
        <th class="num">Clicks</th>
      </tr>
    </thead>
    <tbody>
      {row_html}
    </tbody>
  </table>
</body>
</html>"""
    return HTMLResponse(content=html)


# ─── Serve React SPA (must come LAST — catches all unmatched routes) ──────────
# In production (Docker), the React build is at ./static/
# In local dev, the Vite dev server handles the frontend separately.
_static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(_static_dir):
    app.mount("/", StaticFiles(directory=_static_dir, html=True), name="static")
