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

export default function LeadList({ advisor, onLogout }: Props) {
  const [leads, setLeads] = useState<Lead[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [refreshing, setRefreshing] = useState(false)
  const [calendarConnected, setCalendarConnected] = useState(
    () => localStorage.getItem(calendarKey(advisor)) === 'true'
  )

  // On mount: check if returning from Google OAuth callback
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    if (params.get('calendar') === 'connected') {
      localStorage.setItem(calendarKey(advisor), 'true')
      setCalendarConnected(true)
      // Clean the URL without reloading
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
    <div className="app-container">
      <header className="app-header">
        <div className="header-left">
          <img src="https://www.masterworks.com/mwlogo-400x100.png" className="header-logo-img" alt="Masterworks" />
          <div>
            <h1 className="header-title">Calling List</h1>
            <p className="header-advisor">{advisor}</p>
          </div>
        </div>
        <div className="header-right">
          {!loading && (
            <span className="lead-count">{leads.length} lead{leads.length !== 1 ? 's' : ''}</span>
          )}
          {calendarConnected ? (
            <span className="btn btn-calendar-connected">📅 Calendar Connected</span>
          ) : (
            <button className="btn btn-calendar" onClick={handleConnectCalendar}>
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
      </header>

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
  )
}
