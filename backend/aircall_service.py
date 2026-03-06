"""Aircall transcript search service.
AircallClient and RateLimiter are adapted from:
/Users/jamesringler/aircall-mcp-server/src/aircall_mcp/client.py
"""

import asyncio
import time
from collections import deque
from typing import Any, Optional

import httpx
from config import settings


class RateLimiter:
    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.window_seconds = 60
        self.request_times: deque = deque()
        self._lock = asyncio.Lock()

    async def acquire(self):
        async with self._lock:
            now = time.time()
            while self.request_times and self.request_times[0] < now - self.window_seconds:
                self.request_times.popleft()
            if len(self.request_times) >= self.requests_per_minute:
                wait_time = self.request_times[0] + self.window_seconds - now + 0.1
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                    return await self.acquire()
            self.request_times.append(now)


class AircallClient:
    def __init__(self):
        self.api_id = settings.AIRCALL_API_ID
        self.api_token = settings.AIRCALL_API_TOKEN
        self.base_url = "https://api.aircall.io/v1"
        self.timeout = 30
        self.rate_limiter = RateLimiter(60)
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                auth=(self.api_id, self.api_token),
                timeout=self.timeout,
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _request(self, method: str, endpoint: str, **kwargs) -> dict[str, Any]:
        await self.rate_limiter.acquire()
        client = await self._get_client()
        response = await client.request(method, endpoint, **kwargs)
        response.raise_for_status()
        return response.json()

    async def list_calls(self, per_page: int = 50) -> list[dict[str, Any]]:
        data = await self._request("GET", "/calls", params={"per_page": per_page, "order": "desc"})
        return data.get("calls", [])

    async def get_transcript(self, call_id: int) -> Optional[dict[str, Any]]:
        try:
            data = await self._request("GET", f"/calls/{call_id}/transcription")
            return data.get("transcription", data)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise


def _format_transcript(transcript: dict[str, Any]) -> str:
    utterances = transcript.get("utterances", [])
    lines = []
    for u in utterances:
        speaker = u.get("channel_type", "unknown").capitalize()
        text = u.get("transcript", "").strip()
        if text:
            lines.append(f"{speaker}: {text}")
    return "\n".join(lines)


async def get_investor_transcripts(investor_name: str) -> list[str]:
    """Return up to 3 formatted transcript strings for calls mentioning the investor."""
    client = AircallClient()
    try:
        calls = await client.list_calls(per_page=50)
        name_parts = investor_name.lower().split()
        # Need at least first + last name to match
        if len(name_parts) < 2:
            return []

        first, last = name_parts[0], name_parts[-1]
        matched_transcripts: list[str] = []

        for call in calls:
            if len(matched_transcripts) >= 3:
                break
            call_id = call.get("id")
            if not call_id:
                continue
            try:
                transcript = await client.get_transcript(call_id)
            except Exception:
                continue
            if not transcript:
                continue

            raw_text = _format_transcript(transcript).lower()
            if first in raw_text and last in raw_text:
                matched_transcripts.append(_format_transcript(transcript))

        return matched_transcripts
    finally:
        await client.close()
