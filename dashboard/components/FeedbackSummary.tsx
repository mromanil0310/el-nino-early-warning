import React, { useEffect, useState } from 'react'
import { getFeedbackTotals, FeedbackTotals } from '../lib/supabase'
import { useLanguage } from '../lib/i18n'

// ELN-021 impact view: this week's cooperative reply totals from the anon-safe
// `feedback_summary` view. Self-hides until there is feedback to show.
export default function FeedbackSummary() {
  const { t } = useLanguage()
  const [totals, setTotals] = useState<FeedbackTotals | null>(null)
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    getFeedbackTotals().then(setTotals).finally(() => setLoaded(true))
  }, [])

  if (!loaded || !totals) return null

  const items = [
    { label: t('feedback.acted'), value: totals.acted, color: '#16a34a' },
    { label: t('feedback.notYet'), value: totals.not_acted, color: '#ca8a04' },
    { label: t('feedback.needHelp'), value: totals.need_help, color: '#dc2626' },
  ]

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <h2 className="text-sm font-semibold text-gray-700 mb-3">{t('feedback.heading', { n: totals.total })}</h2>
      <div className="flex gap-4">
        {items.map((it) => (
          <div key={it.label} className="flex-1 text-center">
            <div className="text-2xl font-bold" style={{ color: it.color }}>{it.value}</div>
            <div className="text-xs text-gray-500">{it.label}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
