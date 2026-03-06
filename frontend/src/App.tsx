import { useState, useEffect } from 'react'
import LoginScreen from './components/LoginScreen'
import LeadList from './components/LeadList'

const STORAGE_KEY = 'advisor_name'

export default function App() {
  const [advisor, setAdvisor] = useState<string | null>(
    () => localStorage.getItem(STORAGE_KEY),
  )

  useEffect(() => {
    if (advisor) {
      localStorage.setItem(STORAGE_KEY, advisor)
    } else {
      localStorage.removeItem(STORAGE_KEY)
    }
  }, [advisor])

  if (!advisor) {
    return <LoginScreen onLogin={setAdvisor} />
  }

  return (
    <LeadList
      advisor={advisor}
      onLogout={() => setAdvisor(null)}
    />
  )
}
