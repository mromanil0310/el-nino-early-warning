import React from 'react'
import { Lang, useLanguage } from '../lib/i18n'

// Compact EN / FIL segmented control. Drives the entire interface AND the advisory
// text via the shared language context.
export default function LanguageToggle() {
  const { lang, setLang, t } = useLanguage()

  const opt = (value: Lang, label: string) => (
    <button
      onClick={() => setLang(value)}
      aria-pressed={lang === value}
      className={`px-2.5 py-1 text-xs font-medium rounded-md focus:outline-none focus-visible:ring-2 focus-visible:ring-green-600 ${
        lang === value ? 'bg-green-700 text-white' : 'text-gray-600 hover:bg-gray-100'
      }`}
    >
      {label}
    </button>
  )

  return (
    <div
      className="inline-flex items-center gap-0.5 rounded-lg border border-gray-200 bg-white p-0.5"
      role="group"
      aria-label={t('lang.label')}
    >
      {opt('en', t('lang.en'))}
      {opt('fil', t('lang.fil'))}
    </div>
  )
}
