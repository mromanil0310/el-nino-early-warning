import React, { useEffect, useState } from 'react'
import Head from 'next/head'
import { getLatestRiskScores, RiskScore } from '../lib/supabase'
import ProvinceCard from '../components/ProvinceCard'
import ProvinceMap from '../components/ProvinceMap'
import RiskSummaryBar from '../components/RiskSummaryBar'
import FeedbackSummary from '../components/FeedbackSummary'

const DISCLAIMER =
  'DISCLAIMER: This dashboard is a decision-support tool based on public PAGASA seasonal forecasts and PhilRice crop calendars. Risk scores are model estimates. Verify with your local Department of Agriculture or PAGASA office before taking action. Not a substitute for official advisories.'

type FilterLevel = 'All' | 'High' | 'Medium' | 'Low'
type FilterCrop = 'All' | 'palay' | 'corn'

export default function Home() {
  const [scores, setScores] = useState<RiskScore[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filterLevel, setFilterLevel] = useState<FilterLevel>('All')
  const [filterCrop, setFilterCrop] = useState<FilterCrop>('All')
  const [search, setSearch] = useState('')

  useEffect(() => {
    getLatestRiskScores()
      .then(setScores)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false))
  }, [])

  const weekOf = scores[0]?.week_of ?? null

  const filtered = scores.filter((s) => {
    if (filterLevel !== 'All' && s.risk_level !== filterLevel) return false
    if (filterCrop !== 'All' && s.crop !== filterCrop) return false
    if (search) {
      const name = s.provinces?.name?.toLowerCase() ?? ''
      if (!name.includes(search.toLowerCase())) return false
    }
    return true
  })

  return (
    <>
      <Head>
        <title>El Niño Early Warning — Philippine Agriculture Dashboard</title>
        <meta
          name="description"
          content="Weekly El Niño agricultural risk scores for 15 Luzon pilot provinces. Based on PAGASA seasonal forecasts and PhilRice crop calendar data."
        />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href="/favicon.ico" />
      </Head>

      <div className="min-h-screen bg-gray-50">
        {/* Header */}
        <header className="bg-white border-b border-gray-200 shadow-sm">
          <div className="max-w-4xl mx-auto px-4 py-4">
            <div className="flex items-start justify-between">
              <div>
                <h1 className="text-xl font-bold text-gray-900">
                  🌾 El Niño Early Warning
                </h1>
                <p className="text-sm text-gray-500">
                  Philippine Agricultural Risk Dashboard · 15 Luzon Pilot Provinces
                </p>
              </div>
              {weekOf && (
                <div className="text-right">
                  <div className="text-xs text-gray-400">Week of</div>
                  <div className="text-sm font-medium text-gray-700">{weekOf}</div>
                </div>
              )}
            </div>
          </div>
        </header>

        {/* Disclaimer banner */}
        <div className="bg-amber-50 border-b border-amber-200">
          <div className="max-w-4xl mx-auto px-4 py-2">
            <p className="text-xs text-amber-800">{DISCLAIMER}</p>
          </div>
        </div>

        <main className="max-w-4xl mx-auto px-4 py-6 space-y-6">
          {/* Loading / error state */}
          {loading && (
            <div className="text-center py-12 text-gray-400">
              Loading risk scores…
            </div>
          )}
          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
              Failed to load data: {error}
            </div>
          )}

          {!loading && !error && scores.length === 0 && (
            <div className="rounded-lg border border-gray-200 bg-white p-8 text-center text-gray-400 text-sm">
              No risk scores available yet. The pipeline runs every Monday morning.
            </div>
          )}

          {/* Summary bar */}
          {!loading && scores.length > 0 && (
            <RiskSummaryBar scores={scores} />
          )}

          {/* Risk map overview */}
          {!loading && scores.length > 0 && (
            <ProvinceMap scores={scores} />
          )}

          {/* Filters */}
          {!loading && scores.length > 0 && (
            <div className="flex flex-wrap gap-3 items-center">
              <input
                type="text"
                placeholder="Search province…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="border border-gray-300 rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />

              <div className="flex gap-1">
                {(['All', 'High', 'Medium', 'Low'] as FilterLevel[]).map((l) => (
                  <button
                    key={l}
                    onClick={() => setFilterLevel(l)}
                    className={`text-xs px-3 py-1 rounded-full border transition-colors ${
                      filterLevel === l
                        ? l === 'High'
                          ? 'bg-red-600 border-red-600 text-white'
                          : l === 'Medium'
                          ? 'bg-yellow-500 border-yellow-500 text-white'
                          : l === 'Low'
                          ? 'bg-green-600 border-green-600 text-white'
                          : 'bg-gray-800 border-gray-800 text-white'
                        : 'bg-white border-gray-300 text-gray-600 hover:bg-gray-50'
                    }`}
                  >
                    {l}
                  </button>
                ))}
              </div>

              <div className="flex gap-1">
                {(['All', 'palay', 'corn'] as FilterCrop[]).map((c) => (
                  <button
                    key={c}
                    onClick={() => setFilterCrop(c)}
                    className={`text-xs px-3 py-1 rounded-full border transition-colors ${
                      filterCrop === c
                        ? 'bg-blue-600 border-blue-600 text-white'
                        : 'bg-white border-gray-300 text-gray-600 hover:bg-gray-50'
                    }`}
                  >
                    {c === 'All' ? 'All Crops' : c.charAt(0).toUpperCase() + c.slice(1)}
                  </button>
                ))}
              </div>

              <span className="text-xs text-gray-400 ml-auto">
                {filtered.length} of {scores.length} shown
              </span>
            </div>
          )}

          {/* Province cards */}
          {!loading && filtered.length > 0 && (
            <div className="grid gap-4 sm:grid-cols-2">
              {filtered.map((s) => (
                <ProvinceCard
                  key={`${s.province_id}-${s.crop}-${s.season}`}
                  score={s}
                />
              ))}
            </div>
          )}

          {!loading && filtered.length === 0 && scores.length > 0 && (
            <div className="text-center py-8 text-gray-400 text-sm">
              No provinces match the current filter.
            </div>
          )}

          {/* Cooperative feedback impact (self-hides until there is feedback) */}
          {!loading && scores.length > 0 && <FeedbackSummary />}
        </main>

        {/* Footer */}
        <footer className="border-t border-gray-200 bg-white mt-12">
          <div className="max-w-4xl mx-auto px-4 py-4 text-xs text-gray-400 text-center space-y-1">
            <p>Data sources: PAGASA Seasonal Climate Outlook · PhilRice El Niño Crop Calendar</p>
            <p>Risk formula: rainfall_severity_weight × crop_stage_vulnerability_index × 100 (PhilRice methodology)</p>
            <p>Built by Biboy Labs · For pilot use by LGU agricultural offices only</p>
          </div>
        </footer>
      </div>
    </>
  )
}
