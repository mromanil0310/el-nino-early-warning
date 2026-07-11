import { createClient, SupabaseClient } from '@supabase/supabase-js'

// Dashboard uses the anon key — read-only access
// Service role key NEVER appears in dashboard code (security constraint)
export const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL ?? ''
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? ''

// Missing env must degrade to a visible configuration message, not a module-load
// crash (white screen). Queries throw ConfigurationError instead.
export const isConfigured = Boolean(supabaseUrl && supabaseAnonKey)

export const supabase: SupabaseClient | null = isConfigured
  ? createClient(supabaseUrl, supabaseAnonKey)
  : null

export class ConfigurationError extends Error {
  constructor() {
    super(
      'Dashboard is not configured: NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY must be set at build time.'
    )
    this.name = 'ConfigurationError'
  }
}

function client(): SupabaseClient {
  if (!supabase) throw new ConfigurationError()
  return supabase
}

// ─── Types ────────────────────────────────────────────────────────────────────

export interface Province {
  id: number
  name: string
  region_code: string
  pagasa_zone: string
  lat: number
  lon: number
}

export interface RiskScore {
  province_id: number
  crop: string
  season: string
  week_of: string
  crop_stage: string
  vulnerability_index: number
  rainfall_severity_weight: number
  seasonal_outlook: string
  rainfall_anomaly_pct: number | null
  risk_score: number
  risk_level: 'High' | 'Medium' | 'Low'
  trend: 'increasing' | 'decreasing' | 'stable' | 'new'
  prior_week_score: number | null
  provinces?: Province
}

export interface WeeklyDigest {
  id: number
  province_id: number
  crop: string
  week_of: string
  advisory_en: string
  advisory_tl: string
  sms_text: string
}

// ─── Queries ──────────────────────────────────────────────────────────────────

// Fetch failures THROW so the page can show a real error + retry — a silent []
// would render as "no data this week", hiding outages from LGU users. Only a
// genuinely empty table resolves to [].
export async function getLatestRiskScores(): Promise<RiskScore[]> {
  const { data: latestWeek, error: weekError } = await client()
    .from('risk_scores')
    .select('week_of')
    .order('week_of', { ascending: false })
    .limit(1)
    .maybeSingle()

  if (weekError) throw new Error(`Could not reach the risk database (${weekError.message}).`)
  if (!latestWeek) return [] // table empty — a real "no data yet" state

  const { data, error } = await client()
    .from('risk_scores')
    .select('*, provinces(id, name, region_code, pagasa_zone, lat, lon)')
    .eq('week_of', latestWeek.week_of)
    .order('risk_score', { ascending: false })

  if (error) throw new Error(`Could not load risk scores (${error.message}).`)
  return (data as RiskScore[]) || []
}

export async function getDigestForProvince(
  provinceId: number,
  crop: string,
  weekOf: string
): Promise<WeeklyDigest | null> {
  const { data, error } = await client()
    .from('weekly_digests')
    .select('*')
    .eq('province_id', provinceId)
    .eq('crop', crop)
    .eq('week_of', weekOf)
    .maybeSingle()

  if (error || !data) return null
  return data as WeeklyDigest
}

export async function getHistoricalScores(
  provinceId: number,
  crop: string,
  weeks = 8
): Promise<RiskScore[]> {
  const { data, error } = await client()
    .from('risk_scores')
    .select('week_of, risk_score, risk_level, crop_stage, seasonal_outlook')
    .eq('province_id', provinceId)
    .eq('crop', crop)
    .order('week_of', { ascending: false })
    .limit(weeks)

  if (error) return []
  return (data as RiskScore[]) || []
}

export interface FeedbackTotals {
  acted: number
  not_acted: number
  need_help: number
  unknown: number
  total: number
}

interface FeedbackSummaryRow {
  week_of: string
  response_code: 'acted' | 'not_acted' | 'need_help' | 'unknown'
  responses: number
}

// ELN-021: reads the anon-safe `feedback_summary` view (counts only, no PII) and
// aggregates the latest week's cooperative replies into headline totals.
export async function getFeedbackTotals(): Promise<FeedbackTotals | null> {
  const { data, error } = await client()
    .from('feedback_summary')
    .select('week_of, response_code, responses')
    .order('week_of', { ascending: false })

  if (error || !data || data.length === 0) return null

  const rows = data as FeedbackSummaryRow[]
  const latestWeek = rows[0].week_of
  const totals: FeedbackTotals = { acted: 0, not_acted: 0, need_help: 0, unknown: 0, total: 0 }
  for (const row of rows) {
    if (row.week_of !== latestWeek) continue
    const n = Number(row.responses) || 0
    if (row.response_code in totals) totals[row.response_code] += n
    totals.total += n
  }
  return totals.total > 0 ? totals : null
}
