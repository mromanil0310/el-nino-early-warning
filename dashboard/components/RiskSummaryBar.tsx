import React from 'react'
import { RiskScore } from '../lib/supabase'
import { useLanguage } from '../lib/i18n'

interface RiskSummaryBarProps {
  scores: RiskScore[]
}

export default function RiskSummaryBar({ scores }: RiskSummaryBarProps) {
  const { t } = useLanguage()
  const high = scores.filter((s) => s.risk_level === 'High').length
  const medium = scores.filter((s) => s.risk_level === 'Medium').length
  const low = scores.filter((s) => s.risk_level === 'Low').length
  const total = scores.length

  if (total === 0) return null

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <h2 className="text-sm font-semibold text-gray-700 mb-3">{t('summary.heading', { n: total })}</h2>
      <div className="flex gap-4">
        <div className="flex-1 text-center">
          <div className="text-2xl font-bold text-red-600">{high}</div>
          <div className="text-xs text-gray-500">{t('summary.high')}</div>
        </div>
        <div className="flex-1 text-center">
          <div className="text-2xl font-bold text-yellow-600">{medium}</div>
          <div className="text-xs text-gray-500">{t('summary.medium')}</div>
        </div>
        <div className="flex-1 text-center">
          <div className="text-2xl font-bold text-green-600">{low}</div>
          <div className="text-xs text-gray-500">{t('summary.low')}</div>
        </div>
      </div>

      {/* Visual bar — decorative; the counts above carry the information */}
      <div className="mt-3 flex h-2 rounded-full overflow-hidden" aria-hidden="true">
        {high > 0 && (
          <div
            className="bg-red-500"
            style={{ width: `${(high / total) * 100}%` }}
          />
        )}
        {medium > 0 && (
          <div
            className="bg-yellow-400"
            style={{ width: `${(medium / total) * 100}%` }}
          />
        )}
        {low > 0 && (
          <div
            className="bg-green-500"
            style={{ width: `${(low / total) * 100}%` }}
          />
        )}
      </div>
    </div>
  )
}
