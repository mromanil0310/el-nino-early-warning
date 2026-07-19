import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Head from 'next/head'
import { getLatestRiskScores, isConfigured, RiskScore } from '../lib/supabase'
import { downloadCsv, formatWeekOf, scoresToCsv } from '../lib/format'
import { useLanguage } from '../lib/i18n'
import ProvinceCard from '../components/ProvinceCard'
import ProvinceMap from '../components/ProvinceMap'
import RiskSummaryBar from '../components/RiskSummaryBar'
import FeedbackSummary from '../components/FeedbackSummary'
import LanguageToggle from '../components/LanguageToggle'

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
  const { t } = useLanguage()
  const [scores, setScores] = useState<RiskScore[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filterLevel, setFilterLevel] = useState<FilterLevel>('All')
  const [filterCrop, setFilterCrop] = useState<FilterCrop>('All')
  const [search, setSearch] = useState('')
  const [pendingScroll, setPendingScroll] = useState(false)
  // Map is collapsed by default on phones so the actionable summary + cards surface
  // first; on desktop (sm+) it always shows regardless of this flag.
  const [mapOpen, setMapOpen] = useState(false)
  const [locating, setLocating] = useState(false)
  const [locateMsg, setLocateMsg] = useState<string | null>(null)
  const resultsRef = useRef<HTMLDivElement>(null)

  // Selecting a province (map dot or "find my province") filters the card list — but
  // on mobile that list sits well below, so without scrolling the action looks like a
  // no-op. Defer the scroll to an effect (below) so it runs AFTER the filtered,
  // now-shorter list has committed — scrolling during that DOM shrink cancels it.
  const handleProvinceSelect = useCallback((name: string) => {
    setSearch(name)
    setPendingScroll(true)
  }, [])

  useEffect(() => {
    if (!pendingScroll) return
    // Instant (not smooth) so it lands reliably: a "jump to my result" is clearer
    // than a long scroll animation, and smooth-scroll is a no-op under reduced-motion.
    resultsRef.current?.scrollIntoView({ behavior: 'auto', block: 'start' })
    setPendingScroll(false)
  }, [pendingScroll])

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

  // "Find my province": geolocate, then jump to the nearest monitored province.
  // Euclidean distance on lat/lon is fine for nearest-neighbour ranking at this scale.
  const handleLocate = () => {
    setLocateMsg(null)
    if (typeof navigator === 'undefined' || !navigator.geolocation) {
      setLocateMsg(t('locate.unavailable'))
      return
    }
    setLocating(true)
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLocating(false)
        const { latitude, longitude } = pos.coords
        let best: string | null = null
        let bestD = Infinity
        const seen = new Set<string>()
        for (const s of scores) {
          const p = s.provinces
          if (!p || p.lat == null || p.lon == null || seen.has(p.name)) continue
          seen.add(p.name)
          const dLat = p.lat - latitude
          const dLon = p.lon - longitude
          const d = dLat * dLat + dLon * dLon
          if (d < bestD) {
            bestD = d
            best = p.name
          }
        }
        if (!best) {
          setLocateMsg(t('locate.noNearby'))
          return
        }
        setLocateMsg(t('locate.found', { name: best }))
        handleProvinceSelect(best)
      },
      (err) => {
        setLocating(false)
        setLocateMsg(
          err.code === err.PERMISSION_DENIED ? t('locate.denied') : t('locate.unavailable')
        )
      },
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 600000 }
    )
  }

  const hasData = !loading && !error && scores.length > 0

  return (
    <>
      <Head>
        <title>El Niño Early Warning — Philippine Agriculture Dashboard</title>
        <meta
          name="description"
          content="Weekly El Niño agricultural risk scores for Philippine provinces — an experimental decision-support prototype built on PAGASA rainfall outlooks and crop growth-stage sensitivity. Indicative, not an official or validated risk methodology."
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
                  {t('header.subtitle')}
                  {provinceCount > 0 && ` · ${t('header.provincesMonitored', { n: provinceCount })}`}
                </p>
              </div>
              <div className="flex flex-col items-end gap-2 shrink-0">
                <LanguageToggle />
                {weekOf && (
                  <div className="text-right">
                    <div className="text-xs text-gray-500">{t('header.weekOf')}</div>
                    <div className="text-sm font-medium text-gray-700">
                      <time dateTime={weekOf}>{formatWeekOf(weekOf)}</time>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </header>

        {/* Disclaimer banner */}
        <div className="bg-amber-50 border-b border-amber-200">
          <div className="max-w-4xl mx-auto px-4 py-2">
            <p className="text-xs text-amber-800">{t('disclaimer')}</p>
          </div>
        </div>

        <main className="max-w-4xl mx-auto px-4 py-6 space-y-6">
          {/* Loading skeletons */}
          {loading && (
            <div aria-busy="true">
              <p className="sr-only" role="status">{t('state.loading')}</p>
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
              <p className="text-sm font-medium text-red-800">{t('error.title')}</p>
              <p className="mt-1 text-xs text-red-700">{error}</p>
              {isConfigured && (
                <button
                  onClick={load}
                  className="mt-3 rounded-md border border-red-300 bg-white px-3 py-1.5 text-xs font-medium text-red-700 hover:bg-red-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
                >
                  {t('error.retry')}
                </button>
              )}
            </div>
          )}

          {!loading && !error && scores.length === 0 && (
            <div className="rounded-lg border border-gray-200 bg-white p-8 text-center text-sm text-gray-500">
              <p className="font-medium text-gray-600">{t('empty.title')}</p>
              <p className="mt-1">{t('empty.body')}</p>
            </div>
          )}

          {/* Summary bar */}
          {hasData && <RiskSummaryBar scores={scores} />}

          {/* Risk map. Collapsed behind a toggle on phones (actionable content first),
              always visible on desktop. */}
          {hasData && (
            <div>
              <button
                onClick={() => setMapOpen((v) => !v)}
                aria-expanded={mapOpen}
                aria-controls="risk-map-panel"
                className="sm:hidden w-full mb-2 flex items-center justify-between rounded-lg border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-green-600"
              >
                <span>🗺️ {mapOpen ? t('map.toggleHide') : t('map.toggleShow')}</span>
                <span aria-hidden="true">{mapOpen ? '▲' : '▼'}</span>
              </button>
              <div id="risk-map-panel" className={`${mapOpen ? '' : 'hidden'} sm:block`}>
                <ProvinceMap scores={scores} onSelect={handleProvinceSelect} />
              </div>
            </div>
          )}

          {/* Find my province */}
          {hasData && (
            <div>
              <button
                onClick={handleLocate}
                disabled={locating}
                className="inline-flex items-center gap-1 rounded-lg border border-green-300 bg-white px-4 py-2 text-sm font-medium text-green-800 shadow-sm hover:bg-green-50 disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-green-600"
              >
                {locating ? t('locate.locating') : t('locate.button')}
              </button>
              {locateMsg && (
                <p className="mt-2 text-xs text-gray-600" role="status" aria-live="polite">
                  {locateMsg}
                </p>
              )}
            </div>
          )}

          {/* Filters */}
          {hasData && (
            <div ref={resultsRef} className="flex flex-wrap gap-3 items-center scroll-mt-4">
              <div className="relative">
                <input
                  type="search"
                  aria-label={t('search.label')}
                  placeholder={t('search.placeholder')}
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="border border-gray-300 rounded-md px-3 py-1.5 pr-8 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                {search && (
                  <button
                    onClick={() => setSearch('')}
                    aria-label={t('search.clear')}
                    className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded px-1 text-gray-400 hover:text-gray-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
                  >
                    ✕
                  </button>
                )}
              </div>

              <div className="flex gap-1" role="group" aria-label={t('filter.levelLabel')}>
                {(['All', 'High', 'Medium', 'Low'] as FilterLevel[]).map((l) => (
                  <button
                    key={l}
                    onClick={() => setFilterLevel(l)}
                    aria-pressed={filterLevel === l}
                    className={`${CHIP_BASE} ${filterLevel === l ? LEVEL_ACTIVE[l] : CHIP_INACTIVE}`}
                  >
                    {t('level.' + l)}
                  </button>
                ))}
              </div>

              <div className="flex gap-1" role="group" aria-label={t('filter.cropLabel')}>
                {(['All', 'palay', 'corn'] as FilterCrop[]).map((c) => (
                  <button
                    key={c}
                    onClick={() => setFilterCrop(c)}
                    aria-pressed={filterCrop === c}
                    className={`${CHIP_BASE} ${
                      filterCrop === c ? 'bg-blue-600 border-blue-600 text-white' : CHIP_INACTIVE
                    }`}
                  >
                    {t('crop.' + c)}
                  </button>
                ))}
              </div>

              <span className="text-xs text-gray-500 ml-auto" aria-live="polite">
                {t('filter.shown', { shown: filtered.length, total: scores.length })}
              </span>

              <button
                onClick={handleExport}
                disabled={filtered.length === 0}
                className={`${CHIP_BASE} ${CHIP_INACTIVE} disabled:opacity-40 disabled:cursor-not-allowed`}
                title={t('export.title')}
              >
                {t('export.csv')}
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
              <p>{t('filter.noMatch')}</p>
              <button
                onClick={() => {
                  setSearch('')
                  setFilterLevel('All')
                  setFilterCrop('All')
                }}
                className="mt-2 text-blue-600 hover:text-blue-800 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded"
              >
                {t('filter.clearAll')}
              </button>
            </div>
          )}

          {/* Cooperative feedback impact (self-hides until there is feedback) */}
          {hasData && <FeedbackSummary />}
        </main>

        {/* Footer */}
        <footer className="border-t border-gray-200 bg-white mt-12">
          <div className="max-w-4xl mx-auto px-4 py-4 text-xs text-gray-500 text-center space-y-1">
            <p>{t('footer.dataSources')}</p>
            <p>{t('footer.formula')}</p>
            <p>
              <a href="/USER_GUIDE/" className="text-blue-700 hover:underline">
                {t('footer.guide')}
              </a>
            </p>
            <p>{t('footer.built')}</p>
          </div>
        </footer>
      </div>
    </>
  )
}
