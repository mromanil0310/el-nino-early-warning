import React from 'react'

interface TrendIconProps {
  trend: 'increasing' | 'decreasing' | 'stable' | 'new'
  priorScore?: number | null
}

export default function TrendIcon({ trend, priorScore }: TrendIconProps) {
  if (trend === 'increasing') {
    return (
      <span title={`Up from ${priorScore?.toFixed(0) ?? '?'} last week`} className="text-red-500 font-bold">
        ↑
      </span>
    )
  }
  if (trend === 'decreasing') {
    return (
      <span title={`Down from ${priorScore?.toFixed(0) ?? '?'} last week`} className="text-green-500 font-bold">
        ↓
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
  return (
    <span title={`Stable vs ${priorScore?.toFixed(0) ?? '?'} last week`} className="text-gray-400">
      →
    </span>
  )
}
