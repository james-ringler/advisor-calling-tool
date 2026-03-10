from pydantic import BaseModel
from typing import Optional


class DiscardRequest(BaseModel):
    advisor_name: str
    contact_id: str
    duration: str  # "today" | "30days" | "forever"


class LeadResponse(BaseModel):
    id: str
    rank: int
    score: float
    first_name: str
    last_name: str
    full_name: str
    email: Optional[str] = None
    linkedin_url: Optional[str] = None
    admin_time_last_seen: Optional[str] = None
    investor_tier: Optional[str] = None
    performance_status: Optional[str] = None
    mmfc_outcome: Optional[str] = None
    existing_adviser_status: Optional[str] = None
    total_amount_purchased: Optional[float] = None
    total_investment_portfolio: Optional[float] = None
    hubspot_url: str
    last_call_date: Optional[str] = None
    last_website_visit: Optional[str] = None
    recent_note: Optional[str] = None
    recent_note_date: Optional[str] = None


class AnalyticsEvent(BaseModel):
    advisor_name: str
    event_type: str


class AdvisorsResponse(BaseModel):
    advisors: list[str]


class InvestorStatusResponse(BaseModel):
    contact_id: str
    status: str
