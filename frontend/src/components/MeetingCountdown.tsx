import { useState, useEffect, useRef } from 'react'
import { fetchNextMeeting } from '../api'
import type { NextMeeting } from '../types'

interface Props {
  contactEmail: string
  advisor: string
}

function formatCountdown(startIso: string): string {
  const now = new Date()
  const start = new Date(startIso)
  const diffMs = start.getTime() - now.getTime()

  if (diffMs <= 0) return 'Now'

  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMins / 60)
  const diffDays = Math.floor(diffHours / 24)

  const remHours = diffHours % 24
  const remMins = diffMins % 60

  if (diffDays > 0) {
    return `in ${diffDays}d ${remHours}h ${remMins}m`
  }
  if (diffHours > 0) {
    return `in ${diffHours}h ${remMins}m`
  }
  return `in ${remMins}m`
}

function isToday(startIso: string): boolean {
  const now = new Date()
  const start = new Date(startIso)
  return (
    start.getFullYear() === now.getFullYear() &&
    start.getMonth() === now.getMonth() &&
    start.getDate() === now.getDate()
  )
}

function formatTime(startIso: string): string {
  const start = new Date(startIso)
  return start.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
}

// Check if this advisor has connected Google Calendar
function isCalendarConnected(advisor: string): boolean {
  return localStorage.getItem(`google_connected_${advisor}`) === 'true'
}

export default function MeetingCountdown({ contactEmail, advisor }: Props) {
  const [connected] = useState(() => isCalendarConnected(advisor))
  const [meeting, setMeeting] = useState<NextMeeting | null>(null)
  const [loaded, setLoaded] = useState(false)
  const [countdown, setCountdown] = useState('')
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    if (!connected) return

    fetchNextMeeting(advisor, contactEmail)
      .then((data) => {
        if (data.meeting) {
          setMeeting(data.meeting)
          setCountdown(formatCountdown(data.meeting.start))
        }
        setLoaded(true)
      })
      .catch(() => setLoaded(true))
  }, [advisor, contactEmail, connected])

  useEffect(() => {
    if (!meeting) return

    intervalRef.current = setInterval(() => {
      setCountdown(formatCountdown(meeting.start))
    }, 60000)

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [meeting])

  // Not connected or no meeting — render nothing
  if (!connected || !loaded || !meeting) return null

  const today = isToday(meeting.start)

  return (
    <div className="meeting-countdown">
      <span className={`meeting-pill${today ? ' meeting-pill--today' : ''}`}>
        📅{' '}
        {today
          ? `Meeting today at ${formatTime(meeting.start)}`
          : `Next meeting ${countdown}`}
      </span>
    </div>
  )
}
