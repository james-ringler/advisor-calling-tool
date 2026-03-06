export interface Lead {
  id: string
  rank: number
  score: number
  first_name: string
  last_name: string
  full_name: string
  email: string | null
  linkedin_url: string | null
  admin_time_last_seen: string | null
  investor_tier: string | null
  performance_status: string | null
  mmfc_outcome: string | null
  existing_adviser_status: string | null
  total_amount_purchased: number | null
  total_investment_portfolio: number | null
  hubspot_url: string
}

export type DiscardDuration = 'today' | '30days' | 'forever'
