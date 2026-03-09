import type { Lead, DiscardDuration, NextMeeting } from './types'

const BASE = '/api'

export async function fetchAdvisors(): Promise<string[]> {
  const res = await fetch(`${BASE}/advisors`)
  if (!res.ok) throw new Error('Failed to fetch advisors')
  const data = await res.json()
  return data.advisors as string[]
}

export async function fetchLeads(advisor: string): Promise<Lead[]> {
  const res = await fetch(`${BASE}/leads?advisor=${encodeURIComponent(advisor)}`)
  if (!res.ok) throw new Error('Failed to fetch leads')
  return res.json() as Promise<Lead[]>
}

export async function discardContact(
  advisorName: string,
  contactId: string,
  duration: DiscardDuration,
): Promise<void> {
  const res = await fetch(`${BASE}/discard`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ advisor_name: advisorName, contact_id: contactId, duration }),
  })
  if (!res.ok) throw new Error('Failed to discard contact')
}

export async function fetchInvestorStatus(
  contactId: string,
  name: string,
): Promise<string> {
  const res = await fetch(
    `${BASE}/investor-status?contact_id=${encodeURIComponent(contactId)}&name=${encodeURIComponent(name)}`,
  )
  if (!res.ok) throw new Error('Failed to fetch investor status')
  const data = await res.json()
  return data.status as string
}

/** Fire-and-forget analytics event. Never throws — never blocks the UI. */
export function trackEvent(advisor: string, eventType: string): void {
  fetch('/api/analytics', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ advisor_name: advisor, event_type: eventType }),
  }).catch(() => {})
}

export async function fetchNextMeeting(
  advisor: string,
  contactEmail: string,
): Promise<{ connected: boolean; meeting: NextMeeting | null }> {
  const res = await fetch(
    `${BASE}/calendar/next-meeting?advisor=${encodeURIComponent(advisor)}&contact_email=${encodeURIComponent(contactEmail)}`,
  )
  if (!res.ok) throw new Error('Calendar API error')
  return res.json()
}
