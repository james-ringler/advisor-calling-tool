import { useState } from 'react'
import type { Lead, DiscardDuration } from '../types'
import DiscardModal from './DiscardModal'
import InvestorStatus from './InvestorStatus'
import MeetingCountdown from './MeetingCountdown'
import { discardContact, trackEvent } from '../api'

interface Props {
  lead: Lead
  advisor: string
  onDiscard: (id: string) => void
}

function fmt(value: number | null, type: 'currency' | 'number'): string {
  if (value == null) return '—'
  if (type === 'currency') {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(value)
  }
  return value.toLocaleString()
}

function scoreColor(score: number): string {
  if (score >= 70) return 'score-high'
  if (score >= 40) return 'score-mid'
  return 'score-low'
}

// Maps HubSpot tier values like "Tier A", "Tier B: ...", "Tier C: 18 Months+" to a CSS class
function tierClass(tier: string | null): string {
  if (!tier) return ''
  const match = tier.match(/tier\s+([a-zA-Z])/i)
  if (!match) return ''
  const letter = match[1].toUpperCase()
  const map: Record<string, string> = { A: 'a', B: 'b', C: 'c', D: 'd' }
  return `tier-${map[letter] ?? 'other'}`
}

export default function LeadCard({ lead, advisor, onDiscard }: Props) {
  const [showModal, setShowModal] = useState(false)
  const [discarding, setDiscarding] = useState(false)

  async function handleDiscard(duration: DiscardDuration) {
    setDiscarding(true)
    setShowModal(false)
    trackEvent(advisor, 'click_discard')
    try {
      await discardContact(advisor, lead.id, duration)
      onDiscard(lead.id)
    } catch {
      setDiscarding(false)
    }
  }

  return (
    <>
      <div className={`lead-card ${discarding ? 'lead-card--discarding' : ''}`}>
        <div className="lead-card-header">
          <div className="lead-rank">#{lead.rank}</div>
          <div className="lead-name-block">
            <h2 className="lead-name">{lead.full_name || '—'}</h2>
            {lead.email && (
              <a className="lead-email" href={`mailto:${lead.email}`}>{lead.email}</a>
            )}
          </div>
          <div className="lead-header-right">
            <span className={`lead-score ${scoreColor(lead.score)}`}>{lead.score.toFixed(0)}</span>
            <div className="lead-actions">
              <a
                href={lead.hubspot_url}
                target="_blank"
                rel="noopener noreferrer"
                className="btn btn-hubspot"
                onClick={() => trackEvent(advisor, 'click_hubspot')}
              >
                HubSpot
              </a>
              {lead.linkedin_url && (
                <a
                  href={lead.linkedin_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn btn-linkedin"
                  aria-label="LinkedIn"
                  onClick={() => trackEvent(advisor, 'click_linkedin')}
                >
                  <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor">
                    <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
                  </svg>
                </a>
              )}
              <button
                className="btn btn-discard"
                onClick={() => setShowModal(true)}
                disabled={discarding}
              >
                Discard
              </button>
            </div>
          </div>
        </div>

        <div className="lead-fields">
          <div className="lead-field">
            <span className="field-label">Portfolio Size</span>
            <span className="field-value">{fmt(lead.total_investment_portfolio, 'currency')}</span>
          </div>
          <div className="lead-field">
            <span className="field-label">Total Purchased</span>
            <span className="field-value">{fmt(lead.total_amount_purchased, 'currency')}</span>
          </div>
          <div className="lead-field">
            <span className="field-label">Admin Last Seen</span>
            <span className="field-value">{lead.admin_time_last_seen ?? 'Never'}</span>
          </div>
          <div className="lead-field">
            <span className="field-label">Investor Tier</span>
            <span className={`field-value tier-badge ${tierClass(lead.investor_tier)}`}>
              {lead.investor_tier ?? '—'}
            </span>
          </div>
          <div className="lead-field">
            <span className="field-label">Performance</span>
            <span className="field-value">{lead.performance_status ?? '—'}</span>
          </div>
          <div className="lead-field">
            <span className="field-label">MMFC Outcome</span>
            <span className="field-value">{lead.mmfc_outcome ?? '—'}</span>
          </div>
          <div className="lead-field lead-field--wide">
            <span className="field-label">Existing Adviser Status</span>
            <span className="field-value">{lead.existing_adviser_status ?? '—'}</span>
          </div>
          <div className="lead-field">
            <span className="field-label">Last Called</span>
            <span className="field-value">{lead.last_call_date ?? 'Never'}</span>
          </div>
          <div className="lead-field">
            <span className="field-label">Last on Website</span>
            <span className="field-value">{lead.last_website_visit ?? 'Never'}</span>
          </div>
        </div>

        {lead.recent_note && (
          <div className="lead-note">
            <span className="note-meta">📝 Note — {lead.recent_note_date ?? ''}</span>
            <p className="note-text">
              {lead.recent_note.length > 220
                ? lead.recent_note.slice(0, 220) + '…'
                : lead.recent_note}
            </p>
          </div>
        )}

        {lead.email && <MeetingCountdown contactEmail={lead.email} advisor={advisor} />}

        <InvestorStatus contactId={lead.id} investorName={lead.full_name} />
      </div>

      {showModal && (
        <DiscardModal
          leadName={lead.full_name}
          onConfirm={handleDiscard}
          onCancel={() => setShowModal(false)}
        />
      )}
    </>
  )
}
