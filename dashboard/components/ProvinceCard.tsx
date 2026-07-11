import React, { useState } from 'react'
import { RiskScore, WeeklyDigest, getDigestForProvince, getHistoricalScores } from '../lib/supabase'
import { capitalize, formatWeekOf } from '../lib/format'
import RiskBadge from './RiskBadge'
import TrendIcon from './TrendIcon'
import Sparkline from './Sparkline'

interface ProvinceCardProps {
  score: RiskScore
}

type Lang = 'en' | 'tl'
const LANG_KEY = 'elnino.advisoryLang'

// Officers read many advisories in a row — remember the language choice across
// cards and visits instead of resetting to English on every card.
function getPreferredLang(): Lang {
  if (typeof window === 'undefined') return 'en'
  return window.localStorage.getItem(LANG_KEY) === 'tl' ? 'tl' : 'en'
}

export default function ProvinceCard({ score }: ProvinceCardProps) {
  const [digest, setDigest] = useState<WeeklyDigest | null>(null)
  const [history, setHistory] = useState<number[]>([])
  const [loading, setLoading] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const [lang, setLangState] = useState<Lang>(getPreferredLang)

  const setLang = (l: Lang) => {
    setLangState(l)
    try {
      window.localStorage.setItem(LANG_KEY, l)
    } catch {
      /* storage unavailable (private mode) — session-only preference */
    }
  }

  const provinceName = score.provinces?.name ?? `Province ${score.province_id}`
  const regionCode = score.provinces?.region_code ?? ''
  const advisoryId = `advisory-${score.province_id}-${score.crop}-${score.season}`

  async function handleExpand() {
    if (!expanded && !digest) {
      setLoading(true)
      const [d, hist] = await Promise.all([
        getDigestForProvince(score.province_id, score.week_of),
        getHistoricalScores(score.province_id, score.crop, 8),
      ])
      setDigest(d)
      setHistory(hist.map((h) => h.risk_score).reverse()) // oldest → newest
      setLoading(false)
    }
    setExpanded((prev) => !prev)
  }

  return (
    <div className={`rounded-lg border p-4 shadow-sm transition-all ${
      score.risk_level === 'High'
        ? 'border-red-200 bg-red-50'
        : score.risk_level === 'Medium'
        ? 'border-yellow-200 bg-yellow-50'
        : 'border-green-200 bg-green-50'
    }`}>
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h3 className="font-semibold text-gray-900">{provinceName}</h3>
          <p className="text-xs text-gray-600">Region {regionCode} · {capitalize(score.crop)} ({score.season})</p>
        </div>
        <div className="flex items-center gap-2">
          <TrendIcon trend={score.trend} priorScore={score.prior_week_score} />
          <RiskBadge level={score.risk_level} score={score.risk_score} />
        </div>
      </div>

      {/* Details */}
      <div className="mt-2 grid grid-cols-2 gap-1 text-xs text-gray-600">
        <span>Stage: <strong>{score.crop_stage}</strong></span>
        <span>Outlook: <strong>{score.seasonal_outlook}</strong></span>
        <span>
          Rainfall:{' '}
          <strong>
            {score.rainfall_anomaly_pct == null
              ? '—'
              : `${score.rainfall_anomaly_pct > 0 ? '+' : ''}${score.rainfall_anomaly_pct.toFixed(0)}%`}
          </strong>
        </span>
        <span>Week: <strong>{formatWeekOf(score.week_of)}</strong></span>
      </div>

      {/* Expand button */}
      <button
        onClick={handleExpand}
        aria-expanded={expanded}
        aria-controls={advisoryId}
        className="mt-3 text-xs text-blue-700 hover:text-blue-900 underline-offset-2 hover:underline rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
      >
        {expanded ? 'Hide advisory ▲' : 'Show advisory ▼'}
      </button>

      {/* Advisory */}
      {expanded && (
        <div id={advisoryId} className="mt-3 rounded border border-gray-200 bg-white p-3">
          {loading && <p className="text-xs text-gray-500" role="status">Loading advisory…</p>}

          {!loading && history.length >= 2 && (
            <div className="mb-3">
              <p className="text-xs font-medium text-gray-500 mb-1">
                Risk trend · last {history.length} weeks
              </p>
              <Sparkline values={history} />
            </div>
          )}
          {!loading && !digest && (
            <p className="text-xs text-gray-500 italic">No advisory generated for this province yet.</p>
          )}
          {!loading && digest && (
            <>
              <div className="mb-2 flex gap-2" role="group" aria-label="Advisory language">
                <button
                  onClick={() => setLang('en')}
                  aria-pressed={lang === 'en'}
                  className={`text-xs px-2 py-0.5 rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${lang === 'en' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'}`}
                >
                  English
                </button>
                <button
                  onClick={() => setLang('tl')}
                  aria-pressed={lang === 'tl'}
                  className={`text-xs px-2 py-0.5 rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${lang === 'tl' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'}`}
                >
                  Filipino
                </button>
              </div>
              <p className="text-xs text-gray-700 leading-relaxed" lang={lang === 'tl' ? 'fil' : 'en'}>
                {lang === 'en' ? digest.advisory_en : digest.advisory_tl}
              </p>
              <div className="mt-2 rounded bg-gray-50 p-2">
                <p className="text-xs font-medium text-gray-500 mb-1">SMS text:</p>
                <p className="text-xs font-mono text-gray-700">{digest.sms_text}</p>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}
