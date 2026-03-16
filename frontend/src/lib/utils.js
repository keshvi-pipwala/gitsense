import { formatDistanceToNow, format } from 'date-fns'

export function riskBadgeClass(risk) {
  const map = {
    LOW: 'badge-risk-low',
    MEDIUM: 'badge-risk-medium',
    HIGH: 'badge-risk-high',
    CRITICAL: 'badge-risk-critical',
  }
  return map[risk] || 'badge-risk-medium'
}

export function riskColor(risk) {
  const map = {
    LOW: '#22c55e',
    MEDIUM: '#eab308',
    HIGH: '#ef4444',
    CRITICAL: '#dc2626',
  }
  return map[risk] || '#6b7280'
}

export function riskEmoji(risk) {
  const map = { LOW: '🟢', MEDIUM: '🟡', HIGH: '🔴', CRITICAL: '🚨' }
  return map[risk] || '⚪'
}

export function healthColor(score) {
  if (score >= 80) return '#22c55e'
  if (score >= 60) return '#eab308'
  if (score >= 40) return '#ef4444'
  return '#dc2626'
}

export function timeAgo(date) {
  if (!date) return 'N/A'
  try { return formatDistanceToNow(new Date(date), { addSuffix: true }) }
  catch { return 'N/A' }
}

export function formatDate(date) {
  if (!date) return 'N/A'
  try { return format(new Date(date), 'MMM d, yyyy HH:mm') }
  catch { return 'N/A' }
}

export function debtColor(score) {
  if (score <= 20) return '#22c55e'
  if (score <= 50) return '#eab308'
  return '#ef4444'
}

export function truncate(str, len = 80) {
  if (!str) return ''
  return str.length > len ? str.slice(0, len) + '…' : str
}
