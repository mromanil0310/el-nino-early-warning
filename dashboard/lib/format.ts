import { RiskScore } from './supabase'

// "2026-06-22" → "Jun 22, 2026". Falls back to the raw string on anything unparseable.
export function formatWeekOf(isoDate: string): string {
  const d = new Date(`${isoDate}T00:00:00`)
  if (isNaN(d.getTime())) return isoDate
  return d.toLocaleDateString('en-PH', { month: 'short', day: 'numeric', year: 'numeric' })
}

export function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1)
}

function csvCell(v: string | number | null | undefined): string {
  const s = v == null ? '' : String(v)
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
}

// Client-side CSV of the currently visible scores — DA/LGU workflows are
// spreadsheet-first, and this works before the Phase 2 export API exists.
export function scoresToCsv(scores: RiskScore[]): string {
  const header = [
    'province', 'region', 'crop', 'season', 'week_of', 'crop_stage',
    'seasonal_outlook', 'rainfall_anomaly_pct', 'risk_score', 'risk_level', 'trend',
  ]
  const lines = scores.map((s) =>
    [
      s.provinces?.name ?? s.province_id,
      s.provinces?.region_code ?? '',
      s.crop,
      s.season,
      s.week_of,
      s.crop_stage,
      s.seasonal_outlook,
      s.rainfall_anomaly_pct,
      s.risk_score,
      s.risk_level,
      s.trend,
    ]
      .map(csvCell)
      .join(',')
  )
  return [header.join(','), ...lines].join('\n')
}

export function downloadCsv(filename: string, csv: string): void {
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
