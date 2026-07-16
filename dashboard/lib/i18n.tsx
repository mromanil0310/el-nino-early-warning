import React, { createContext, useContext, useEffect, useState } from 'react'

// Bilingual (English / Filipino) UI layer. The whole point is reach: the advisories
// have always been bilingual, but the surrounding chrome was English-only, which
// shuts out the farmers and barangay officials this is ultimately meant to serve.
// One global toggle now drives BOTH the interface and the advisory text.

export type Lang = 'en' | 'fil'

// Single source of truth for the preference. Replaces ProvinceCard's old
// 'elnino.advisoryLang' (en|tl) key — the migration below maps the legacy value.
const LANG_KEY = 'elnino.lang'

export function readStoredLang(): Lang {
  if (typeof window === 'undefined') return 'en'
  try {
    const v = window.localStorage.getItem(LANG_KEY)
    if (v === 'fil' || v === 'en') return v
    // Migrate the legacy advisory-language key ('tl' → Filipino).
    const legacy = window.localStorage.getItem('elnino.advisoryLang')
    if (legacy === 'tl') return 'fil'
  } catch {
    /* storage unavailable (private mode) — fall through to default */
  }
  return 'en'
}

type Params = Record<string, string | number>
type Entry = string | ((p: Params) => string)

// Keep proper nouns (PAGASA, PhilRice, El Niño, palay/mais, crop stages, PAGASA
// outlook labels) intact — translating technical data values would misrepresent
// the source. Only interface copy is localized.
const DICT: Record<Lang, Record<string, Entry>> = {
  en: {
    'header.subtitle': 'Philippine Agricultural Risk Dashboard',
    'header.provincesMonitored': (p) => `${p.n} provinces monitored`,
    'header.weekOf': 'Week of',
    'lang.label': 'Language',
    'lang.en': 'English',
    'lang.fil': 'Filipino',
    disclaimer:
      'DISCLAIMER: This dashboard is a decision-support tool based on public PAGASA seasonal forecasts and PhilRice crop calendars. Risk scores are model estimates. Verify with your local Department of Agriculture or PAGASA office before taking action. Not a substitute for official advisories.',
    'state.loading': 'Loading risk scores…',
    'error.title': "Could not load this week's risk data",
    'error.retry': 'Try again',
    'empty.title': 'No risk scores available yet.',
    'empty.body': 'The pipeline runs every Monday at 6:00 AM (PHT). Check back after the next run.',
    'search.placeholder': 'Search province…',
    'search.label': 'Search province',
    'search.clear': 'Clear search',
    'filter.levelLabel': 'Filter by risk level',
    'filter.cropLabel': 'Filter by crop',
    'level.All': 'All',
    'level.High': 'High',
    'level.Medium': 'Medium',
    'level.Low': 'Low',
    'crop.All': 'All Crops',
    'crop.palay': 'Palay',
    'crop.corn': 'Corn',
    'filter.shown': (p) => `${p.shown} of ${p.total} shown`,
    'export.csv': '⬇ Export CSV',
    'export.title': 'Download the rows currently shown as a CSV spreadsheet',
    'filter.noMatch': 'No provinces match the current filter.',
    'filter.clearAll': 'Clear all filters',
    'locate.button': '📍 Find my province',
    'locate.locating': 'Locating…',
    'locate.denied': 'Location permission denied. Search for your province instead.',
    'locate.unavailable': 'Location is not available on this device. Search for your province instead.',
    'locate.noNearby': 'No monitored province is near your location yet.',
    'locate.found': (p) => `Nearest monitored province: ${p.name}`,
    'map.toggleShow': 'Show risk map',
    'map.toggleHide': 'Hide risk map',
    'map.heading': (p) => `Risk map — ${p.n} ${Number(p.n) === 1 ? 'province' : 'provinces'} scored`,
    'map.hint': 'Tap a province to see its details below.',
    'map.aria': 'Map of provinces colored by El Niño risk level',
    'summary.heading': (p) =>
      `Risk summary — ${p.n} crop ${Number(p.n) === 1 ? 'assessment' : 'assessments'} this week`,
    'summary.high': 'High Risk (>65)',
    'summary.medium': 'Medium (35–65)',
    'summary.low': 'Low (<35)',
    'card.region': (p) => `Region ${p.code} · ${p.crop} (${p.season})`,
    'card.stage': 'Stage',
    'card.outlook': 'Outlook',
    'card.rainfall': 'Rainfall',
    'card.week': 'Week',
    'card.showAdvisory': 'Show advisory ▼',
    'card.hideAdvisory': 'Hide advisory ▲',
    'card.trend': (p) => `Risk trend · last ${p.n} weeks`,
    'card.noAdvisory': 'No advisory generated for this province yet.',
    'card.loadingAdvisory': 'Loading advisory…',
    'card.smsText': 'SMS text:',
    'card.share': '↗ Share this advisory',
    'card.copied': '✓ Copied to clipboard',
    'card.shareHeading': (p) => `${p.province} — ${p.crop}: ${p.level} El Niño risk`,
    'feedback.heading': (p) => `Cooperative feedback — this week (${p.n} replies)`,
    'feedback.acted': 'Acted on advisory',
    'feedback.notYet': 'Not yet',
    'feedback.needHelp': 'Need help',
    'footer.dataSources': 'Data sources: PAGASA Seasonal Climate Outlook · PhilRice El Niño Crop Calendar',
    'footer.formula':
      'Risk formula: rainfall_severity_weight × crop_stage_vulnerability_index × 100 (PhilRice methodology)',
    'footer.guide': 'How to use this dashboard',
    'footer.built': 'Built by Biboy Labs · For pilot use by LGU agricultural offices only',
  },
  fil: {
    'header.subtitle': 'Dashboard ng Panganib sa Agrikultura ng Pilipinas',
    'header.provincesMonitored': (p) => `${p.n} lalawigang binabantayan`,
    'header.weekOf': 'Linggo ng',
    'lang.label': 'Wika',
    'lang.en': 'English',
    'lang.fil': 'Filipino',
    disclaimer:
      'PAALALA: Ang dashboard na ito ay kasangkapan sa paggawa ng desisyon batay sa pampublikong seasonal forecast ng PAGASA at crop calendar ng PhilRice. Ang mga marka ng panganib ay tantiya lamang ng modelo. Kumpirmahin muna sa inyong lokal na tanggapan ng Department of Agriculture o PAGASA bago kumilos. Hindi ito kapalit ng opisyal na abiso.',
    'state.loading': 'Kinukuha ang mga marka ng panganib…',
    'error.title': 'Hindi ma-load ang datos ng panganib ngayong linggo',
    'error.retry': 'Subukan muli',
    'empty.title': 'Wala pang marka ng panganib.',
    'empty.body':
      'Tumatakbo ang sistema tuwing Lunes ng 6:00 AM (PHT). Balikan pagkatapos ng susunod na takbo.',
    'search.placeholder': 'Maghanap ng lalawigan…',
    'search.label': 'Maghanap ng lalawigan',
    'search.clear': 'Burahin ang paghahanap',
    'filter.levelLabel': 'Salain ayon sa antas ng panganib',
    'filter.cropLabel': 'Salain ayon sa pananim',
    'level.All': 'Lahat',
    'level.High': 'Mataas',
    'level.Medium': 'Katamtaman',
    'level.Low': 'Mababa',
    'crop.All': 'Lahat ng Pananim',
    'crop.palay': 'Palay',
    'crop.corn': 'Mais',
    'filter.shown': (p) => `${p.shown} sa ${p.total} ipinapakita`,
    'export.csv': '⬇ I-export ang CSV',
    'export.title': 'I-download ang kasalukuyang ipinapakitang datos bilang CSV spreadsheet',
    'filter.noMatch': 'Walang lalawigang tumugma sa salain.',
    'filter.clearAll': 'Burahin lahat ng salain',
    'locate.button': '📍 Hanapin ang aking lalawigan',
    'locate.locating': 'Hinahanap…',
    'locate.denied': 'Hindi pinayagan ang lokasyon. Maghanap na lang ng inyong lalawigan.',
    'locate.unavailable': 'Hindi available ang lokasyon sa device na ito. Maghanap na lang ng inyong lalawigan.',
    'locate.noNearby': 'Wala pang binabantayang lalawigan malapit sa inyong lokasyon.',
    'locate.found': (p) => `Pinakamalapit na binabantayang lalawigan: ${p.name}`,
    'map.toggleShow': 'Ipakita ang mapa ng panganib',
    'map.toggleHide': 'Itago ang mapa ng panganib',
    'map.heading': (p) => `Mapa ng panganib — ${p.n} lalawigang minarkahan`,
    'map.hint': 'I-tap ang lalawigan para makita ang detalye sa ibaba.',
    'map.aria': 'Mapa ng mga lalawigan na kinulayan ayon sa antas ng panganib sa El Niño',
    'summary.heading': (p) => `Buod ng panganib — ${p.n} pagtatasa ng pananim ngayong linggo`,
    'summary.high': 'Mataas (>65)',
    'summary.medium': 'Katamtaman (35–65)',
    'summary.low': 'Mababa (<35)',
    'card.region': (p) => `Rehiyon ${p.code} · ${p.crop} (${p.season})`,
    'card.stage': 'Yugto',
    'card.outlook': 'Pananaw',
    'card.rainfall': 'Ulan',
    'card.week': 'Linggo',
    'card.showAdvisory': 'Ipakita ang payo ▼',
    'card.hideAdvisory': 'Itago ang payo ▲',
    'card.trend': (p) => `Takbo ng panganib · nakaraang ${p.n} linggo`,
    'card.noAdvisory': 'Wala pang payo para sa lalawigang ito.',
    'card.loadingAdvisory': 'Kinukuha ang payo…',
    'card.smsText': 'Tekstong SMS:',
    'card.share': '↗ Ibahagi ang payong ito',
    'card.copied': '✓ Nakopya na',
    'card.shareHeading': (p) => `${p.province} — ${p.crop}: ${p.level} na panganib sa El Niño`,
    'feedback.heading': (p) => `Puna ng kooperatiba — ngayong linggo (${p.n} sagot)`,
    'feedback.acted': 'Kumilos sa payo',
    'feedback.notYet': 'Hindi pa',
    'feedback.needHelp': 'Kailangan ng tulong',
    'footer.dataSources':
      'Pinagkunan ng datos: PAGASA Seasonal Climate Outlook · PhilRice El Niño Crop Calendar',
    'footer.formula':
      'Pormula ng panganib: rainfall_severity_weight × crop_stage_vulnerability_index × 100 (pamamaraan ng PhilRice)',
    'footer.guide': 'Paano gamitin ang dashboard na ito',
    'footer.built': 'Gawa ng Biboy Labs · Para sa pilot na gamit ng mga tanggapang pang-agrikultura ng LGU',
  },
}

export type TFunc = (key: string, params?: Params) => string

interface LanguageContextValue {
  lang: Lang
  setLang: (l: Lang) => void
  t: TFunc
}

const LanguageContext = createContext<LanguageContextValue | null>(null)

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  // Always start from 'en' so the server-rendered static export and the first client
  // render agree (no hydration mismatch); a layout effect then applies the stored
  // preference before paint.
  const [lang, setLangState] = useState<Lang>('en')

  useEffect(() => {
    const stored = readStoredLang()
    if (stored !== 'en') setLangState(stored)
  }, [])

  useEffect(() => {
    if (typeof document !== 'undefined') {
      document.documentElement.lang = lang === 'fil' ? 'fil' : 'en'
    }
  }, [lang])

  const setLang = (l: Lang) => {
    setLangState(l)
    try {
      window.localStorage.setItem(LANG_KEY, l)
    } catch {
      /* storage unavailable — session-only preference */
    }
  }

  const t: TFunc = (key, params = {}) => {
    const entry = DICT[lang][key] ?? DICT.en[key]
    if (entry == null) return key
    return typeof entry === 'function' ? entry(params) : entry
  }

  return <LanguageContext.Provider value={{ lang, setLang, t }}>{children}</LanguageContext.Provider>
}

export function useLanguage(): LanguageContextValue {
  const ctx = useContext(LanguageContext)
  if (!ctx) throw new Error('useLanguage must be used within a LanguageProvider')
  return ctx
}
