from groq import AsyncGroq
from config import settings


async def generate_investor_status(
    investor_name: str,
    transcripts: list[str],
    notes: list[str],
    emails: list[str],
) -> str:
    sections: list[str] = []

    if transcripts:
        sections.append("## Call Transcripts\n" + "\n\n---\n\n".join(transcripts))
    if notes:
        sections.append("## HubSpot Notes\n" + "\n\n".join(notes))
    if emails:
        sections.append("## Emails\n" + "\n\n".join(emails))

    if not sections:
        return "No recent activity found for this investor (no calls, notes, or emails on record)."

    combined = "\n\n".join(sections)

    prompt = (
        f"You are reviewing recent activity for {investor_name}, an investor at Masterworks "
        f"(an art investment platform). Below are call transcripts, advisor notes, and emails "
        f"logged in HubSpot.\n\n"
        f"{combined}\n\n"
        f"Write exactly 3 sentences:\n"
        f"1. Their level of interest and which specific fund(s) or offering(s) they have shown interest in.\n"
        f"2. A summary of recent touchpoints (calls, emails, notes) — when and what channel.\n"
        f"3. What the investor asked for or expressed concern about, and what follow-up the advisor committed to.\n\n"
        f"Be specific and factual. If information for a sentence is not available, say so briefly. "
        f"Do not use bullet points or headers — output exactly 3 plain sentences."
    )

    client = AsyncGroq(api_key=settings.GROQ_API_KEY)
    completion = await client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    return completion.choices[0].message.content.strip()
