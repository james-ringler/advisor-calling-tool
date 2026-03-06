import anthropic
from config import settings


async def generate_investor_status(investor_name: str, transcripts: list[str]) -> str:
    if not transcripts:
        return "No recent call transcripts found for this investor."

    combined = "\n\n---\n\n".join(transcripts)
    prompt = (
        f"You are reviewing call transcripts for Masterworks, an art investment platform. "
        f"Based on the following call transcripts involving {investor_name}, write a 2-3 sentence "
        f"summary of the investor's current status, interest level, and any key next steps or "
        f"concerns. Be concise and factual.\n\nTranscripts:\n{combined}\n\nSummary:"
    )

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text.strip()
