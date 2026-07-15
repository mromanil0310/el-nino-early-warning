import React from 'react'

interface TrendIconProps {
  trend: 'increasing' | 'decreasing' | 'stable' | 'new'
  priorScore?: number | null
}

// Trend is conveyed by glyph + color, both of which are lost to screen-reader and
// colorblind users. role="img" + aria-label gives the element a real accessible
// name (a bare `title` on a <span> is announced inconsistently), while the glyph
// itself stays aria-hidden so it isn't read as a stray character.
export default function TrendIcon({ trend, priorScore }: TrendIconProps) {
  const prior = priorScore?.toFixed(0) ?? '?'

  if (trend === 'increasing') {
    const label = `Risk increasing, up from ${prior} last week`
    return (
      <span role="img" aria-label={label} title={label} className="text-red-500 font-bold">
        <span aria-hidden="true">↑</span>
      </span>
    )
  }
  if (trend === 'decreasing') {
    const label = `Risk decreasing, down from ${prior} last week`
    return (
      <span role="img" aria-label={label} title={label} className="text-green-500 font-bold">
        <span aria-hidden="true">↓</span>
      </span>
    )
  }
  if (trend === 'new') {
    return (
      <span title="New this week" className="text-blue-500 text-xs font-medium">
        NEW
      </span>
    )
  }
  const label = `Risk stable versus ${prior} last week`
  return (
    <span role="img" aria-label={label} title={label} className="text-gray-400">
      <span aria-hidden="true">→</span>
    </span>
  )
}
