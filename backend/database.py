"""PostgreSQL-backed discard storage using asyncpg.
Railway provides DATABASE_URL automatically when the PostgreSQL plugin is added.
"""

from datetime import datetime, timezone
from typing import Optional

import asyncpg


async def init_db(pool: asyncpg.Pool) -> None:
    """Create the discards table if it doesn't exist."""
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
