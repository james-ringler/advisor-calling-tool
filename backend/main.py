import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from typing import Optional

import asyncpg
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from config import settings
from database import init_db, upsert_discard, get_active_discards, save_google_token, get_google_token
from hubspot_client import fetch_contacts_for_advisor, get_advisor_names
from hubspot_engagement_service import get_contact_notes, get_contact_emails
from ranking import rank_contacts
from aircall_service import get_investor_transcripts
from claude_service import generate_investor_status
from google_calendar_service import get_next_meeting
from models import DiscardRequest, LeadResponse, AdvisorsResponse, InvestorStatusResponse


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
        mmfc_outcome=props.get("mmfc_outcome"),
        existing_adviser_status=props.get("existing_adviser_status"),
        total_amount_purchased=float(purchased_raw) if purchased_raw else None,
        total_investment_portfolio=float(portfolio_raw) if portfolio_raw else None,
        hubspot_url=HUBSPOT_CONTACT_URL.format(
            account_id=settings.HUBSPOT_ACCOUNT_ID,
            contact_id=contact_id,
        ),
        last_call_date=_format_date(props.get("aircall_last_call_at")),
        last_website_visit=_format_date(props.get("last_seen_timestamp")),
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
    return [_build_lead(c, c["rank"]) for c in ranked[:35]]


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


# ─── Serve React SPA (must come LAST — catches all unmatched routes) ──────────
# In production (Docker), the React build is at ./static/
# In local dev, the Vite dev server handles the frontend separately.
_static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(_static_dir):
    app.mount("/", StaticFiles(directory=_static_dir, html=True), name="static")
