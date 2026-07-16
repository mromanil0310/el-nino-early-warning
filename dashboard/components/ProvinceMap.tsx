import React from 'react'
import { RiskScore } from '../lib/supabase'
import { useLanguage } from '../lib/i18n'

interface ProvinceMapProps {
  scores: RiskScore[]
  /** Called with the province name when a dot or ranked row is activated. */
  onSelect?: (name: string) => void
}

interface ProvincePoint {
  id: number
  name: string
  lat: number
  lon: number
  score: number
  level: 'High' | 'Medium' | 'Low'
  crops: number
}

const levelColor = (lvl: string) =>
  lvl === 'High' ? '#dc2626' : lvl === 'Medium' ? '#ca8a04' : '#16a34a'

// Dependency-free positional risk map: each province is plotted by its lat/lon
// (equirectangular) and colored by its WORST crop's risk level. Dots and ranked rows
// are focusable buttons that filter the card list. No GeoJSON/heavy map lib needed.
export default function ProvinceMap({ scores, onSelect }: ProvinceMapProps) {
  const { t } = useLanguage()
  const byProvince = new Map<number, ProvincePoint>()
  for (const s of scores) {
    const p = s.provinces
    if (!p || p.lat == null || p.lon == null) continue
    const cur = byProvince.get(s.province_id)
    if (!cur) {
      byProvince.set(s.province_id, {
        id: s.province_id, name: p.name, lat: p.lat, lon: p.lon,
        score: s.risk_score, level: s.risk_level, crops: 1,
      })
    } else {
      cur.crops += 1
      if (s.risk_score > cur.score) {
        cur.score = s.risk_score
        cur.level = s.risk_level
      }
    }
  }

  const points = Array.from(byProvince.values())
  if (points.length === 0) return null

  const lats = points.map((p) => p.lat)
  const lons = points.map((p) => p.lon)
  const minLat = Math.min(...lats), maxLat = Math.max(...lats)
  const minLon = Math.min(...lons), maxLon = Math.max(...lons)
  const W = 300, H = 380, pad = 28
  const x = (lon: number) => pad + ((lon - minLon) / ((maxLon - minLon) || 1)) * (W - 2 * pad)
  const y = (lat: number) => pad + ((maxLat - lat) / ((maxLat - minLat) || 1)) * (H - 2 * pad)

  const ranked = [...points].sort((a, b) => b.score - a.score)
  const select = (name: string) => onSelect?.(name)

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <h2 className="text-sm font-semibold text-gray-700 mb-1">{t('map.heading', { n: points.length })}</h2>
      {onSelect && <p className="text-xs text-gray-500 mb-3">{t('map.hint')}</p>}
      <div className="flex flex-col sm:flex-row gap-4">
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="w-full sm:w-1/2 max-w-[300px] mx-auto rounded bg-gray-50"
          role="img"
          aria-label={t('map.aria')}
        >
          {points.map((p) => (
            <circle
              key={p.id}
              cx={x(p.lon)}
              cy={y(p.lat)}
              r={7}
              fill={levelColor(p.level)}
              fillOpacity={0.85}
              stroke="#fff"
              strokeWidth={1.5}
              tabIndex={onSelect ? 0 : undefined}
              role={onSelect ? 'button' : undefined}
              aria-label={`${p.name}: ${t('level.' + p.level)}, ${Math.round(p.score)}`}
              className={onSelect ? 'cursor-pointer focus:outline-none focus-visible:stroke-blue-600' : undefined}
              onClick={onSelect ? () => select(p.name) : undefined}
              onKeyDown={
                onSelect
                  ? (e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        select(p.name)
                      }
                    }
                  : undefined
              }
            >
              <title>{p.name}: {t('level.' + p.level)} ({Math.round(p.score)})</title>
            </circle>
          ))}
        </svg>

        <div className="sm:w-1/2 space-y-2">
          <div className="flex gap-3 text-xs text-gray-600" aria-hidden="true">
            <span className="flex items-center gap-1"><span className="inline-block w-2.5 h-2.5 rounded-full" style={{ background: '#dc2626' }} /> {t('level.High')}</span>
            <span className="flex items-center gap-1"><span className="inline-block w-2.5 h-2.5 rounded-full" style={{ background: '#ca8a04' }} /> {t('level.Medium')}</span>
            <span className="flex items-center gap-1"><span className="inline-block w-2.5 h-2.5 rounded-full" style={{ background: '#16a34a' }} /> {t('level.Low')}</span>
          </div>
          <ul className="text-xs divide-y divide-gray-100">
            {ranked.slice(0, 8).map((p) => (
              <li key={p.id} className="flex items-center justify-between py-1">
                {onSelect ? (
                  <button
                    onClick={() => select(p.name)}
                    className="flex items-center gap-2 text-gray-700 hover:text-blue-700 rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
                  >
                    <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ background: levelColor(p.level) }} aria-hidden="true" />
                    {p.name}
                  </button>
                ) : (
                  <span className="flex items-center gap-2 text-gray-700">
                    <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ background: levelColor(p.level) }} aria-hidden="true" />
                    {p.name}
                  </span>
                )}
                <span className="font-medium text-gray-500">{Math.round(p.score)} · {t('level.' + p.level)}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  )
}
