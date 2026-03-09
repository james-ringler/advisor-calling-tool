"""PostgreSQL-backed discard storage using asyncpg.
Railway provides DATABASE_URL automatically when the PostgreSQL plugin is added.
"""

from datetime import datetime, timezone
from typing import Optional

import asyncpg


async def init_db(pool: asyncpg.Pool) -> None:
    """Create all tables if they don't exist."""
    await pool.execute("""
        CREATE TABLE IF NOT EXISTS discards (
            id SERIAL PRIMARY KEY,
            advisor_name TEXT NOT NULL,
            contact_id TEXT NOT NULL,
            discard_until TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(advisor_name, contact_id)
        )
    """)
    await pool.execute("""
        CREATE TABLE IF NOT EXISTS google_tokens (
            advisor_name TEXT PRIMARY KEY,
            access_token TEXT NOT NULL,
            refresh_token TEXT NOT NULL,
            token_expiry TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    await pool.execute("""
        CREATE TABLE IF NOT EXISTS analytics_events (
            id           SERIAL PRIMARY KEY,
            advisor_name TEXT NOT NULL,
            event_type   TEXT NOT NULL,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    await pool.execute("""
        CREATE INDEX IF NOT EXISTS idx_analytics_advisor_date
            ON analytics_events (advisor_name, created_at DESC)
    """)


async def upsert_discard(
    pool: asyncpg.Pool,
    advisor_name: str,
    contact_id: str,
    discard_until: Optional[datetime],
) -> None:
    """Insert or update a discard record for a contact."""
    await pool.execute("""
        INSERT INTO discards (advisor_name, contact_id, discard_until)
        VALUES ($1, $2, $3)
        ON CONFLICT (advisor_name, contact_id)
        DO UPDATE SET
            discard_until = EXCLUDED.discard_until,
            created_at = NOW()
    """, advisor_name, contact_id, discard_until)


async def get_active_discards(pool: asyncpg.Pool, advisor_name: str) -> set[str]:
    """Return contact IDs that are still discarded (today, 30-day, or forever)."""
    now = datetime.now(timezone.utc)
    rows = await pool.fetch("""
        SELECT contact_id FROM discards
        WHERE advisor_name = $1
          AND (discard_until IS NULL OR discard_until > $2)
    """, advisor_name, now)
    return {row["contact_id"] for row in rows}


async def save_google_token(
    pool: asyncpg.Pool,
    advisor_name: str,
    access_token: str,
    refresh_token: str,
    token_expiry: datetime,
) -> None:
    """Insert or update Google OAuth tokens for an advisor."""
    await pool.execute("""
        INSERT INTO google_tokens (advisor_name, access_token, refresh_token, token_expiry, updated_at)
        VALUES ($1, $2, $3, $4, NOW())
        ON CONFLICT (advisor_name)
        DO UPDATE SET
            access_token = EXCLUDED.access_token,
            refresh_token = EXCLUDED.refresh_token,
            token_expiry = EXCLUDED.token_expiry,
            updated_at = NOW()
    """, advisor_name, access_token, refresh_token, token_expiry)


async def log_event(pool: asyncpg.Pool, advisor_name: str, event_type: str) -> None:
    """Insert a single analytics event row."""
    await pool.execute(
        "INSERT INTO analytics_events (advisor_name, event_type) VALUES ($1, $2)",
        advisor_name, event_type,
    )


async def get_report(pool: asyncpg.Pool, days: int = 7):
    """Return daily usage counts per advisor for the last N days (ET timezone)."""
    return await pool.fetch("""
        SELECT
            (created_at AT TIME ZONE 'America/New_York')::date AS day,
            advisor_name,
            SUM(CASE WHEN event_type = 'page_load'  THEN 1 ELSE 0 END) AS page_loads,
            SUM(CASE WHEN event_type = 'refresh'    THEN 1 ELSE 0 END) AS refreshes,
            SUM(CASE WHEN event_type LIKE 'click_%' THEN 1 ELSE 0 END) AS clicks
        FROM analytics_events
        WHERE created_at >= NOW() - ($1 || ' days')::interval
        GROUP BY day, advisor_name
        ORDER BY day DESC, advisor_name
    """, str(days))


async def get_google_token(pool: asyncpg.Pool, advisor_name: str) -> Optional[dict]:
    """Return stored Google tokens for an advisor, or None if not connected."""
    row = await pool.fetchrow("""
        SELECT access_token, refresh_token, token_expiry
        FROM google_tokens WHERE advisor_name = $1
    """, advisor_name)
    if not row:
        return None
    return {
        "access_token": row["access_token"],
        "refresh_token": row["refresh_token"],
        "token_expiry": row["token_expiry"],
    }
