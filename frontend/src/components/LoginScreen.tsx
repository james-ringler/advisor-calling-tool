import { useState, useEffect } from 'react'
import { fetchAdvisors } from '../api'

interface Props {
  onLogin: (advisor: string) => void
}

export default function LoginScreen({ onLogin }: Props) {
  const [advisors, setAdvisors] = useState<string[]>([])
  const [selected, setSelected] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    fetchAdvisors()
      .then(setAdvisors)
      .catch(() => setError('Could not load advisor list. Is the backend running?'))
      .finally(() => setLoading(false))
  }, [])

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (selected) onLogin(selected)
  }

  return (
    <div className="login-container">
      <div className="login-card">
        <div className="login-logo">MW</div>
        <h1 className="login-title">Advisor Calling Tool</h1>
        <p className="login-subtitle">Select your name to see your call list</p>

        {loading && <p className="login-loading">Loading…</p>}
        {error && <p className="login-error">{error}</p>}

        {!loading && !error && (
          <form onSubmit={handleSubmit} className="login-form">
            <select
              className="login-select"
              value={selected}
              onChange={(e) => setSelected(e.target.value)}
            >
              <option value="">— Select your name —</option>
              {advisors.map((name) => (
                <option key={name} value={name}>{name}</option>
              ))}
            </select>
            <button
              type="submit"
              className="login-button"
              disabled={!selected}
            >
              View My Call List
            </button>
          </form>
        )}
      </div>
    </div>
  )
}
