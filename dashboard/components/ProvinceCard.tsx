import React, { useState } from 'react'
import { RiskScore, WeeklyDigest, getDigestForProvince, getHistoricalScores } from '../lib/supabase'
import RiskBadge from './RiskBadge'
import TrendIcon from './TrendIcon'
import Sparkline from './Sparkline'

interface ProvinceCardProps {
  score: RiskScore
}

export default function ProvinceCard({ score }: ProvinceCardProps) {
  const [digest, setDigest] = useState<WeeklyDigest | null>(null)
  const [history, setHistory] = useState<number[]>([])
  const [loading, setLoading] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const [lang, setLang] = useState<'en' | 'tl'>('en')

  const provinceName = score.provinces?.name ?? `Province ${score.province_id}`
  const regionCode = score.provinces?.region_code ?? ''

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
          <p className="text-xs text-gray-500">Region {regionCode} · {score.crop.charAt(0).toUpperCase() + score.crop.slice(1)} ({score.season})</p>
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
        <span>Rainfall: <strong>{score.rainfall_anomaly_pct > 0 ? '+' : ''}{score.rainfall_anomaly_pct.toFixed(0)}%</strong></span>
        <span>Week: <strong>{score.week_of}</strong></span>
      </div>

      {/* Expand button */}
      <button
        onClick={handleExpand}
        className="mt-3 text-xs text-blue-600 hover:text-blue-800 underline-offset-2 hover:underline"
      >
        {expanded ? 'Hide advisory ▲' : 'Show advisory ▼'}
      </button>

      {/* Advisory */}
      {expanded && (
        <div className="mt-3 rounded border border-gray-200 bg-white p-3">
          {loading && <p className="text-xs text-gray-400">Loading advisory…</p>}

          {!loading && history.length >= 2 && (
            <div className="mb-3">
              <p className="text-xs font-medium text-gray-500 mb-1">
                Risk trend · last {history.length} weeks
              </p>
              <Sparkline values={history} />
            </div>
          )}
          {!loading && !digest && (
            <p className="text-xs text-gray-400 italic">No advisory generated for this province yet.</p>
          )}
          {!loading && digest && (
            <>
              <div className="mb-2 flex gap-2">
                <button
                  onClick={() => setLang('en')}
                  className={`text-xs px-2 py-0.5 rounded ${lang === 'en' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-700'}`}
                >
                  English
                </button>
                <button
                  onClick={() => setLang('tl')}
                  className={`text-xs px-2 py-0.5 rounded ${lang === 'tl' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-700'}`}
                >
                  Filipino
                </button>
              </div>
              <p className="text-xs text-gray-700 leading-relaxed">
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
