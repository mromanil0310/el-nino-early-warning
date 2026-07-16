import React, { useState } from 'react'
import { RiskScore, WeeklyDigest, getDigestForProvince, getHistoricalScores } from '../lib/supabase'
import { capitalize, formatWeekOf } from '../lib/format'
import { useLanguage } from '../lib/i18n'
import RiskBadge from './RiskBadge'
import TrendIcon from './TrendIcon'
import Sparkline from './Sparkline'

interface ProvinceCardProps {
  score: RiskScore
}

export default function ProvinceCard({ score }: ProvinceCardProps) {
  const { lang, t } = useLanguage()
  const [digest, setDigest] = useState<WeeklyDigest | null>(null)
  const [history, setHistory] = useState<number[]>([])
  const [loading, setLoading] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const [copied, setCopied] = useState(false)

  const provinceName = score.provinces?.name ?? `Province ${score.province_id}`
  const regionCode = score.provinces?.region_code ?? ''
  const advisoryId = `advisory-${score.province_id}-${score.crop}-${score.season}`

  // Crop names are known values (palay/corn); fall back to a capitalized raw value
  // if an unexpected crop appears rather than leaking the dictionary key.
  const cropTranslation = t('crop.' + score.crop)
  const cropLabel = cropTranslation.startsWith('crop.') ? capitalize(score.crop) : cropTranslation

  // Advisory text follows the global language: Filipino → the Tagalog column.
  const advisoryText = lang === 'fil' ? digest?.advisory_tl : digest?.advisory_en

  // Distribution is the whole point for reach: one dashboard viewer can forward a
  // plain-language advisory to a barangay group chat or SMS. Uses the native share
  // sheet where available (mobile), falling back to clipboard copy on desktop. Shares
  // in the currently-selected language, plus a link so recipients can look up their
  // own province.
  async function shareAdvisory() {
    if (!digest) return
    const body = lang === 'fil' ? digest.advisory_tl : digest.advisory_en
    const heading = t('card.shareHeading', {
      province: provinceName,
      crop: cropLabel,
      level: t('level.' + score.risk_level),
    })
    const origin = typeof window !== 'undefined' ? window.location.origin : ''
    const text = `${heading}\n\n${body}${origin ? `\n\n${origin}` : ''}`

    if (typeof navigator !== 'undefined' && typeof navigator.share === 'function') {
      try {
        await navigator.share({ title: heading, text })
        return
      } catch (err) {
        // User dismissed the share sheet — respect that, don't silently copy instead.
        if (err instanceof DOMException && err.name === 'AbortError') return
        // Any other share failure falls through to the clipboard path below.
      }
    }
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2000)
    } catch {
      /* clipboard blocked (insecure context / denied permission) — nothing else to do */
    }
  }

  async function handleExpand() {
    if (!expanded && !digest) {
      setLoading(true)
      const [d, hist] = await Promise.all([
        getDigestForProvince(score.province_id, score.crop, score.week_of),
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
          <p className="text-xs text-gray-600">
            {t('card.region', { code: regionCode, crop: cropLabel, season: score.season })}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <TrendIcon trend={score.trend} priorScore={score.prior_week_score} />
          <RiskBadge level={score.risk_level} score={score.risk_score} />
        </div>
      </div>

      {/* Details */}
      <div className="mt-2 grid grid-cols-2 gap-1 text-xs text-gray-600">
        <span>{t('card.stage')}: <strong>{score.crop_stage}</strong></span>
        <span>{t('card.outlook')}: <strong>{score.seasonal_outlook}</strong></span>
        <span>
          {t('card.rainfall')}:{' '}
          <strong>
            {score.rainfall_anomaly_pct == null
              ? '—'
              : `${score.rainfall_anomaly_pct > 0 ? '+' : ''}${score.rainfall_anomaly_pct.toFixed(0)}%`}
          </strong>
        </span>
        <span>{t('card.week')}: <strong>{formatWeekOf(score.week_of)}</strong></span>
      </div>

      {/* Expand button */}
      <button
        onClick={handleExpand}
        aria-expanded={expanded}
        aria-controls={advisoryId}
        className="mt-3 text-xs text-blue-700 hover:text-blue-900 underline-offset-2 hover:underline rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
      >
        {expanded ? t('card.hideAdvisory') : t('card.showAdvisory')}
      </button>

      {/* Advisory */}
      {expanded && (
        <div id={advisoryId} className="mt-3 rounded border border-gray-200 bg-white p-3">
          {loading && <p className="text-xs text-gray-500" role="status">{t('card.loadingAdvisory')}</p>}

          {!loading && history.length >= 2 && (
            <div className="mb-3">
              <p className="text-xs font-medium text-gray-500 mb-1">{t('card.trend', { n: history.length })}</p>
              <Sparkline values={history} />
            </div>
          )}
          {!loading && !digest && (
            <p className="text-xs text-gray-500 italic">{t('card.noAdvisory')}</p>
          )}
          {!loading && digest && (
            <>
              <p className="text-xs text-gray-700 leading-relaxed" lang={lang === 'fil' ? 'fil' : 'en'}>
                {advisoryText}
              </p>
              <div className="mt-2 rounded bg-gray-50 p-2">
                <p className="text-xs font-medium text-gray-500 mb-1">{t('card.smsText')}</p>
                <p className="text-xs font-mono text-gray-700">{digest.sms_text}</p>
              </div>
              <button
                onClick={shareAdvisory}
                aria-live="polite"
                className="mt-3 inline-flex items-center gap-1 rounded-md border border-blue-300 bg-white px-3 py-1.5 text-xs font-medium text-blue-700 hover:bg-blue-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
              >
                {copied ? t('card.copied') : t('card.share')}
              </button>
            </>
          )}
        </div>
      )}
    </div>
  )
}
