import { useState } from 'react'
import { fetchInvestorStatus } from '../api'

interface Props {
  contactId: string
  investorName: string
}

type State = 'idle' | 'loading' | 'loaded' | 'error'

export default function InvestorStatus({ contactId, investorName }: Props) {
  const [state, setState] = useState<State>('idle')
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')

  async function load() {
    setState('loading')
    setError('')
    try {
      const result = await fetchInvestorStatus(contactId, investorName)
      setStatus(result)
      setState('loaded')
    } catch {
      setError('Failed to load status. Try again.')
      setState('error')
    }
  }

  if (state === 'idle') {
    return (
      <div className="investor-status investor-status--idle">
        <button className="status-load-btn" onClick={load}>
          ✦ Load Investor Status
        </button>
      </div>
    )
  }

  if (state === 'loading') {
    return (
      <div className="investor-status investor-status--loading">
        <span className="spinner" /> Analyzing call history…
      </div>
    )
  }

  if (state === 'error') {
    return (
      <div className="investor-status investor-status--error">
        <span>{error}</span>
        <button className="status-retry-btn" onClick={load}>Retry</button>
      </div>
    )
  }

  return (
    <div className="investor-status investor-status--loaded">
      <p className="status-label">Investor Status</p>
      <p className="status-text">{status}</p>
    </div>
  )
}
