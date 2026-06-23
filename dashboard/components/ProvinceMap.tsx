import React from 'react'
import { RiskScore } from '../lib/supabase'

interface ProvinceMapProps {
  scores: RiskScore[]
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

// Dependency-free positional risk map: each pilot province is plotted by its lat/lon
// (equirectangular) and colored by its WORST crop's risk level. Hover for details; the
// ranked list on the right gives the readable summary. No GeoJSON/heavy map lib needed.
export default function ProvinceMap({ scores }: ProvinceMapProps) {
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

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <h2 className="text-sm font-semibold text-gray-700 mb-3">
        Risk map — {points.length} Luzon pilot provinces
      </h2>
      <div className="flex flex-col sm:flex-row gap-4">
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="w-full sm:w-1/2 max-w-[300px] mx-auto rounded bg-gray-50"
          role="img"
          aria-label="Map of pilot provinces colored by El Niño risk level"
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
            >
              <title>{p.name}: {p.level} ({Math.round(p.score)})</title>
            </circle>
          ))}
        </svg>

        <div className="sm:w-1/2 space-y-2">
          <div className="flex gap-3 text-xs text-gray-600">
            <span className="flex items-center gap-1"><span className="inline-block w-2.5 h-2.5 rounded-full" style={{ background: '#dc2626' }} /> High</span>
            <span className="flex items-center gap-1"><span className="inline-block w-2.5 h-2.5 rounded-full" style={{ background: '#ca8a04' }} /> Medium</span>
            <span className="flex items-center gap-1"><span className="inline-block w-2.5 h-2.5 rounded-full" style={{ background: '#16a34a' }} /> Low</span>
          </div>
          <ul className="text-xs divide-y divide-gray-100">
            {ranked.slice(0, 8).map((p) => (
              <li key={p.id} className="flex items-center justify-between py-1">
                <span className="flex items-center gap-2 text-gray-700">
                  <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ background: levelColor(p.level) }} />
                  {p.name}
                </span>
                <span className="font-medium text-gray-500">{Math.round(p.score)} · {p.level}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  )
}
