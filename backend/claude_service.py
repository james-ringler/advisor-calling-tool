"""
Investor status formatter — no external API required.
Structures the most recent call transcript, note, and email into a
readable summary for the advisor.
"""


async def generate_investor_status(
    investor_name: str,
    transcripts: list[str],
    notes: list[str],
    emails: list[str],
) -> str:
    if not transcripts and not notes and not emails:
        return "No recent activity found for this investor (no calls, notes, or emails on record)."

    sections: list[str] = []

    if transcripts:
        # Show up to 12 dialogue lines from the most recent transcript
        lines = [line for line in transcripts[0].split("\n") if line.strip()][:12]
        sections.append("── Most Recent Call ──\n" + "\n".join(lines))

    if notes:
        sections.append("── Latest Note ──\n" + notes[0])

    if emails:
        sections.append("── Latest Email ──\n" + emails[0])

    return "\n\n".join(sections)
