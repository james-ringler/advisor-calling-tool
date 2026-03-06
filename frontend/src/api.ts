import type { Lead, DiscardDuration } from './types'

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
