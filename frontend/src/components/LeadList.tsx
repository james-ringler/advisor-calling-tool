import { useState, useEffect, useCallback } from 'react'
import type { Lead } from '../types'
import { fetchLeads } from '../api'
import LeadCard from './LeadCard'

interface Props {
  advisor: string
  onLogout: () => void
}

function calendarKey(advisor: string) {
  return `google_connected_${advisor}`
}

function getGreeting(): string {
  const h = new Date().getHours()
  if (h < 12) return 'Good morning'
  if (h < 17) return 'Good afternoon'
  return 'Good evening'
}

export default function LeadList({ advisor, onLogout }: Props) {
  const [leads, setLeads] = useState<Lead[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [refreshing, setRefreshing] = useState(false)
  const [calendarConnected, setCalendarConnected] = useState(
    () => localStorage.getItem(calendarKey(advisor)) === 'true'
  )

  const firstName = advisor.split(' ')[0]

  // On mount: check if returning from Google OAuth callback
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    if (params.get('calendar') === 'connected') {
      localStorage.setItem(calendarKey(advisor), 'true')
      setCalendarConnected(true)
      window.history.replaceState({}, '', window.location.pathname)
    }
  }, [advisor])

  const load = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true)
    else setLoading(true)
    setError('')
    try {
      const data = await fetchLeads(advisor)
      setLeads(data)
    } catch {
      setError('Failed to load leads. Check your connection and try again.')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [advisor])

  useEffect(() => { load() }, [load])

  function handleDiscard(id: string) {
    setLeads((prev) => prev.filter((l) => l.id !== id))
  }

  function handleConnectCalendar() {
    window.location.href = `/api/auth/google?advisor=${encodeURIComponent(advisor)}`
  }

  return (
    <div className="app-wrapper">

      {/* ── Sticky Navbar ── */}
      <nav className="app-navbar">
        <div className="navbar-inner">
          <img
            src="https://www.masterworks.com/mwlogo-400x100.png"
            className="nav-logo"
            alt="Masterworks"
          />
          <div className="nav-actions">
            {calendarConnected ? (
              <span className="btn btn-calendar-connected-nav">📅 Calendar Connected</span>
            ) : (
              <button className="btn btn-calendar-nav" onClick={handleConnectCalendar}>
                Connect Calendar
              </button>
            )}
            <button
              className="btn btn-refresh"
              onClick={() => load(true)}
              disabled={refreshing || loading}
            >
              {refreshing ? 'Refreshing…' : '↻ Refresh'}
            </button>
            <button className="btn btn-logout" onClick={onLogout}>
              Switch Advisor
            </button>
          </div>
        </div>
      </nav>

      {/* ── Hero ── */}
      <div className="app-hero">
        <div className="hero-inner">
          <h1 className="hero-greeting">{getGreeting()}, {firstName}</h1>
          {!loading && !error && (
            <p className="hero-subhead">
              Leads to call ({leads.length})
            </p>
          )}
        </div>
      </div>

      {/* ── Lead Cards ── */}
      <div className="app-container">
        <main className="lead-list-container">
          {loading && (
            <div className="state-message">
              <div className="big-spinner" />
              <p>Loading your call list…</p>
            </div>
          )}

          {error && !loading && (
            <div className="state-message state-message--error">
              <p>{error}</p>
              <button className="btn btn-refresh" onClick={() => load()}>Try Again</button>
            </div>
          )}

          {!loading && !error && leads.length === 0 && (
            <div className="state-message">
              <p>No leads to show right now.</p>
            </div>
          )}

          {!loading && !error && leads.map((lead) => (
            <LeadCard
              key={lead.id}
              lead={lead}
              advisor={advisor}
              onDiscard={handleDiscard}
            />
          ))}
        </main>
      </div>

    </div>
  )
}
