import React from 'react'

interface SparklineProps {
  values: number[] // oldest → newest, risk scores on a 0–100 scale
  width?: number
  height?: number
}

// Tiny dependency-free SVG sparkline of recent weekly risk scores, with a dashed line
// at the High threshold (65) for quick context. Colored by the latest score's level.
export default function Sparkline({ values, width = 132, height = 30 }: SparklineProps) {
  if (!values || values.length < 2) return null

  const MAX = 100
  const stepX = width / (values.length - 1)
  const y = (v: number) => height - (Math.max(0, Math.min(MAX, v)) / MAX) * height
  const points = values.map((v, i) => `${(i * stepX).toFixed(1)},${y(v).toFixed(1)}`).join(' ')

  const last = values[values.length - 1]
  const color = last > 65 ? '#dc2626' : last >= 35 ? '#ca8a04' : '#16a34a'
  const thresholdY = y(65)

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label={`Risk score trend over the last ${values.length} weeks, currently ${Math.round(last)}`}
    >
      <line x1={0} x2={width} y1={thresholdY} y2={thresholdY} stroke="#e5e7eb" strokeWidth={1} strokeDasharray="2 2" />
      <polyline points={points} fill="none" stroke={color} strokeWidth={1.5} strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={(values.length - 1) * stepX} cy={y(last)} r={2.5} fill={color} />
    </svg>
  )
}
