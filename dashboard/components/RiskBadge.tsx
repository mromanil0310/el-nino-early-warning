import React from 'react'

interface RiskBadgeProps {
  level: 'High' | 'Medium' | 'Low'
  score?: number
  size?: 'sm' | 'md' | 'lg'
}

const LEVEL_STYLES: Record<string, string> = {
  High: 'bg-red-100 text-red-800 border border-red-300',
  Medium: 'bg-yellow-100 text-yellow-800 border border-yellow-300',
  Low: 'bg-green-100 text-green-800 border border-green-300',
}

const SIZE_STYLES: Record<string, string> = {
  sm: 'text-xs px-2 py-0.5 rounded',
  md: 'text-sm px-3 py-1 rounded-md font-medium',
  lg: 'text-base px-4 py-2 rounded-lg font-semibold',
}

export default function RiskBadge({ level, score, size = 'md' }: RiskBadgeProps) {
  return (
    <span className={`inline-flex items-center gap-1 ${LEVEL_STYLES[level]} ${SIZE_STYLES[size]}`}>
      <span>{level}</span>
      {score !== undefined && (
        <span className="opacity-70">({score.toFixed(0)})</span>
      )}
    </span>
  )
}
