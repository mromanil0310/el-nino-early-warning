import { createClient } from '@supabase/supabase-js'

// Dashboard uses the anon key — read-only access
// Service role key NEVER appears in dashboard code (security constraint)
const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!

export const supabase = createClient(supabaseUrl, supabaseAnonKey)

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
  rainfall_anomaly_pct: number
  risk_score: number
  risk_level: 'High' | 'Medium' | 'Low'
  trend: 'increasing' | 'decreasing' | 'stable' | 'new'
  prior_week_score: number | null
  provinces?: Province
}

export interface WeeklyDigest {
  id: number
  province_id: number
  week_of: string
  advisory_en: string
  advisory_tl: string
  sms_text: string
}

// ─── Queries ──────────────────────────────────────────────────────────────────

export async function getLatestRiskScores(): Promise<RiskScore[]> {
  try {
    // Get the most recent week_of available
    const { data: latestWeek } = await supabase
      .from('risk_scores')
      .select('week_of')
      .order('week_of', { ascending: false })
      .limit(1)
      .single()

    if (!latestWeek) return []

    const { data, error } = await supabase
      .from('risk_scores')
      .select('*, provinces(id, name, region_code, pagasa_zone, lat, lon)')
      .eq('week_of', latestWeek.week_of)
      .order('risk_score', { ascending: false })

    if (error) {
      console.error('Error fetching risk scores:', error)
      return []
    }

    return (data as RiskScore[]) || []
  } catch (e) {
    console.error('Supabase connection error:', e)
    return []
  }
}

export async function getDigestForProvince(
  provinceId: number,
  weekOf: string
): Promise<WeeklyDigest | null> {
  const { data, error } = await supabase
    .from('weekly_digests')
    .select('*')
    .eq('province_id', provinceId)
    .eq('week_of', weekOf)
    .single()

  if (error || !data) return null
  return data as WeeklyDigest
}

export async function getHistoricalScores(
  provinceId: number,
  crop: string,
  weeks = 8
): Promise<RiskScore[]> {
  const { data, error } = await supabase
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

// ELN-021: reads the anon-safe `feedback_summary` view (counts only, no PII) and
// aggregates the latest week's cooperative replies into headline totals.
export async function getFeedbackTotals(): Promise<FeedbackTotals | null> {
  const { data, error } = await supabase
    .from('feedback_summary')
    .select('week_of, response_code, responses')
    .order('week_of', { ascending: false })

  if (error || !data || data.length === 0) return null

  const latestWeek = (data[0] as any).week_of
  const totals: FeedbackTotals = { acted: 0, not_acted: 0, need_help: 0, unknown: 0, total: 0 }
  for (const row of data as any[]) {
    if (row.week_of !== latestWeek) continue
    const n = Number(row.responses) || 0
    if (row.response_code in totals) (totals as any)[row.response_code] += n
    totals.total += n
  }
  return totals.total > 0 ? totals : null
}
