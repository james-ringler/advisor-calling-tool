import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from typing import Optional

import asyncpg
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import settings
from database import init_db, upsert_discard, get_active_discards
from hubspot_client import fetch_contacts_for_advisor, get_advisor_names
from ranking import rank_contacts
from aircall_service import get_investor_transcripts
from claude_service import generate_investor_status
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
    if not ms_value:
        return None
    try:
        ts = int(ms_value) / 1000.0
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
    except (TypeError, ValueError, OSError):
        return None


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

    ranked = rank_contacts(contacts)
    return [_build_lead(c, c["rank"]) for c in ranked]


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
        transcripts = await get_investor_transcripts(name)
        status = await generate_investor_status(name, transcripts)
    except Exception as e:
        status = f"Unable to generate status: {str(e)}"

    return InvestorStatusResponse(contact_id=contact_id, status=status)


# ─── Serve React SPA (must come LAST — catches all unmatched routes) ──────────
# In production (Docker), the React build is at ./static/
# In local dev, the Vite dev server handles the frontend separately.
_static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(_static_dir):
    app.mount("/", StaticFiles(directory=_static_dir, html=True), name="static")
