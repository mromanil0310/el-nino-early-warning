import React, { useCallback, useEffect, useMemo, useState } from 'react'
import Head from 'next/head'
import { getLatestRiskScores, isConfigured, RiskScore } from '../lib/supabase'
import { downloadCsv, formatWeekOf, scoresToCsv } from '../lib/format'
import ProvinceCard from '../components/ProvinceCard'
import ProvinceMap from '../components/ProvinceMap'
import RiskSummaryBar from '../components/RiskSummaryBar'
import FeedbackSummary from '../components/FeedbackSummary'

const DISCLAIMER =
  'DISCLAIMER: This dashboard is a decision-support tool based on public PAGASA seasonal forecasts and PhilRice crop calendars. Risk scores are model estimates. Verify with your local Department of Agriculture or PAGASA office before taking action. Not a substitute for official advisories.'

type FilterLevel = 'All' | 'High' | 'Medium' | 'Low'
type FilterCrop = 'All' | 'palay' | 'corn'

const LEVEL_ACTIVE: Record<FilterLevel, string> = {
  All: 'bg-gray-800 border-gray-800 text-white',
  High: 'bg-red-600 border-red-600 text-white',
  Medium: 'bg-yellow-500 border-yellow-500 text-white',
  Low: 'bg-green-600 border-green-600 text-white',
}

const CHIP_BASE =
  'text-xs px-3 py-1 rounded-full border transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-1'
const CHIP_INACTIVE = 'bg-white border-gray-300 text-gray-600 hover:bg-gray-50'

function SkeletonCard() {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm animate-pulse" aria-hidden="true">
      <div className="flex items-start justify-between">
        <div className="space-y-2">
          <div className="h-4 w-32 rounded bg-gray-200" />
          <div className="h-3 w-44 rounded bg-gray-100" />
        </div>
        <div className="h-6 w-20 rounded-md bg-gray-200" />
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2">
        <div className="h-3 w-24 rounded bg-gray-100" />
        <div className="h-3 w-28 rounded bg-gray-100" />
        <div className="h-3 w-20 rounded bg-gray-100" />
        <div className="h-3 w-24 rounded bg-gray-100" />
      </div>
    </div>
  )
}

export default function Home() {
  const [scores, setScores] = useState<RiskScore[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filterLevel, setFilterLevel] = useState<FilterLevel>('All')
  const [filterCrop, setFilterCrop] = useState<FilterCrop>('All')
  const [search, setSearch] = useState('')

  const load = useCallback(() => {
    setLoading(true)
    setError(null)
    getLatestRiskScores()
      .then(setScores)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const weekOf = scores[0]?.week_of ?? null
  const provinceCount = useMemo(
    () => new Set(scores.map((s) => s.province_id)).size,
    [scores]
  )

  const filtered = scores.filter((s) => {
    if (filterLevel !== 'All' && s.risk_level !== filterLevel) return false
    if (filterCrop !== 'All' && s.crop !== filterCrop) return false
    if (search) {
      const name = s.provinces?.name?.toLowerCase() ?? ''
      if (!name.includes(search.toLowerCase())) return false
    }
    return true
  })

  const handleExport = () => {
    const suffix = weekOf ? `-${weekOf}` : ''
    downloadCsv(`elnino-risk-scores${suffix}.csv`, scoresToCsv(filtered))
  }

  return (
    <>
      <Head>
        <title>El Niño Early Warning — Philippine Agriculture Dashboard</title>
        <meta
          name="description"
          content="Weekly El Niño agricultural risk scores for Philippine provinces. Based on PAGASA seasonal forecasts and PhilRice crop calendar data."
        />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </Head>

      <div className="min-h-screen bg-gray-50">
        {/* Header */}
        <header className="bg-white border-b border-gray-200 shadow-sm">
          <div className="max-w-4xl mx-auto px-4 py-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h1 className="text-xl font-bold text-gray-900">
                  <span aria-hidden="true">🌾</span> El Niño Early Warning
                </h1>
                <p className="text-sm text-gray-500">
                  Philippine Agricultural Risk Dashboard
                  {provinceCount > 0 && ` · ${provinceCount} provinces monitored`}
                </p>
              </div>
              {weekOf && (
                <div className="text-right shrink-0">
                  <div className="text-xs text-gray-500">Week of</div>
                  <div className="text-sm font-medium text-gray-700">
                    <time dateTime={weekOf}>{formatWeekOf(weekOf)}</time>
                  </div>
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
          {/* Loading skeletons */}
          {loading && (
            <div aria-busy="true">
              <p className="sr-only" role="status">Loading risk scores…</p>
              <div className="grid gap-4 sm:grid-cols-2">
                <SkeletonCard />
                <SkeletonCard />
                <SkeletonCard />
                <SkeletonCard />
              </div>
            </div>
          )}

          {/* Configuration / fetch errors — distinct from the empty state */}
          {!loading && error && (
            <div className="rounded-lg border border-red-200 bg-red-50 p-4" role="alert">
              <p className="text-sm font-medium text-red-800">Could not load this week&apos;s risk data</p>
              <p className="mt-1 text-xs text-red-700">{error}</p>
              {isConfigured && (
                <button
                  onClick={load}
                  className="mt-3 rounded-md border border-red-300 bg-white px-3 py-1.5 text-xs font-medium text-red-700 hover:bg-red-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
                >
                  Try again
                </button>
              )}
            </div>
          )}

          {!loading && !error && scores.length === 0 && (
            <div className="rounded-lg border border-gray-200 bg-white p-8 text-center text-sm text-gray-500">
              <p className="font-medium text-gray-600">No risk scores available yet.</p>
              <p className="mt-1">The pipeline runs every Monday at 6:00 AM (PHT). Check back after the next run.</p>
            </div>
          )}

          {/* Summary bar */}
          {!loading && !error && scores.length > 0 && <RiskSummaryBar scores={scores} />}

          {/* Risk map overview — clicking a province filters the list below */}
          {!loading && !error && scores.length > 0 && (
            <ProvinceMap scores={scores} onSelect={(name) => setSearch(name)} />
          )}

          {/* Filters */}
          {!loading && !error && scores.length > 0 && (
            <div className="flex flex-wrap gap-3 items-center">
              <div className="relative">
                <input
                  type="search"
                  aria-label="Search province"
                  placeholder="Search province…"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="border border-gray-300 rounded-md px-3 py-1.5 pr-8 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                {search && (
                  <button
                    onClick={() => setSearch('')}
                    aria-label="Clear search"
                    className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded px-1 text-gray-400 hover:text-gray-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
                  >
                    ✕
                  </button>
                )}
              </div>

              <div className="flex gap-1" role="group" aria-label="Filter by risk level">
                {(['All', 'High', 'Medium', 'Low'] as FilterLevel[]).map((l) => (
                  <button
                    key={l}
                    onClick={() => setFilterLevel(l)}
                    aria-pressed={filterLevel === l}
                    className={`${CHIP_BASE} ${filterLevel === l ? LEVEL_ACTIVE[l] : CHIP_INACTIVE}`}
                  >
                    {l}
                  </button>
                ))}
              </div>

              <div className="flex gap-1" role="group" aria-label="Filter by crop">
                {(['All', 'palay', 'corn'] as FilterCrop[]).map((c) => (
                  <button
                    key={c}
                    onClick={() => setFilterCrop(c)}
                    aria-pressed={filterCrop === c}
                    className={`${CHIP_BASE} ${
                      filterCrop === c ? 'bg-blue-600 border-blue-600 text-white' : CHIP_INACTIVE
                    }`}
                  >
                    {c === 'All' ? 'All Crops' : c.charAt(0).toUpperCase() + c.slice(1)}
                  </button>
                ))}
              </div>

              <span className="text-xs text-gray-500 ml-auto" aria-live="polite">
                {filtered.length} of {scores.length} shown
              </span>

              <button
                onClick={handleExport}
                disabled={filtered.length === 0}
                className={`${CHIP_BASE} ${CHIP_INACTIVE} disabled:opacity-40 disabled:cursor-not-allowed`}
                title="Download the rows currently shown as a CSV spreadsheet"
              >
                ⬇ Export CSV
              </button>
            </div>
          )}

          {/* Province cards */}
          {!loading && !error && filtered.length > 0 && (
            <div className="grid gap-4 sm:grid-cols-2">
              {filtered.map((s) => (
                <ProvinceCard key={`${s.province_id}-${s.crop}-${s.season}`} score={s} />
              ))}
            </div>
          )}

          {!loading && !error && filtered.length === 0 && scores.length > 0 && (
            <div className="rounded-lg border border-gray-200 bg-white p-6 text-center text-sm text-gray-500">
              <p>No provinces match the current filter.</p>
              <button
                onClick={() => {
                  setSearch('')
                  setFilterLevel('All')
                  setFilterCrop('All')
                }}
                className="mt-2 text-blue-600 hover:text-blue-800 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded"
              >
                Clear all filters
              </button>
            </div>
          )}

          {/* Cooperative feedback impact (self-hides until there is feedback) */}
          {!loading && !error && scores.length > 0 && <FeedbackSummary />}
        </main>

        {/* Footer */}
        <footer className="border-t border-gray-200 bg-white mt-12">
          <div className="max-w-4xl mx-auto px-4 py-4 text-xs text-gray-500 text-center space-y-1">
            <p>Data sources: PAGASA Seasonal Climate Outlook · PhilRice El Niño Crop Calendar</p>
            <p>Risk formula: rainfall_severity_weight × crop_stage_vulnerability_index × 100 (PhilRice methodology)</p>
            <p>Built by Biboy Labs · For pilot use by LGU agricultural offices only</p>
          </div>
        </footer>
      </div>
    </>
  )
}
