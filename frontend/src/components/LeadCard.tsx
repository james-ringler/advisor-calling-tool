import { useState } from 'react'
import type { Lead, DiscardDuration } from '../types'
import DiscardModal from './DiscardModal'
import InvestorStatus from './InvestorStatus'
import MeetingCountdown from './MeetingCountdown'
import { discardContact } from '../api'

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

export default function LeadCard({ lead, advisor, onDiscard }: Props) {
  const [showModal, setShowModal] = useState(false)
  const [discarding, setDiscarding] = useState(false)

  async function handleDiscard(duration: DiscardDuration) {
    setDiscarding(true)
    setShowModal(false)
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
              >
                HubSpot
              </a>
              {lead.linkedin_url && (
                <a
                  href={lead.linkedin_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn btn-linkedin"
                >
                  LinkedIn
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
            <span className={`field-value tier-badge tier-${(lead.investor_tier ?? '').toLowerCase()}`}>
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
