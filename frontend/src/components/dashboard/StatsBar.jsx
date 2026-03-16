export default function StatsBar({ stats, loading }) {
  const items = [
    { label: 'PRs Analyzed', value: stats?.total_prs_analyzed ?? 0, icon: '🔍', color: 'text-accent' },
    { label: 'High Risk Caught', value: stats?.high_risk_caught ?? 0, icon: '🔴', color: 'text-risk-high' },
    { label: 'Conflicts Detected', value: stats?.conflicts_detected ?? 0, icon: '⚡', color: 'text-risk-medium' },
    { label: 'Avg Debt Score', value: stats?.avg_debt_score != null ? `${stats.avg_debt_score}/100` : '—', icon: '🏚️', color: 'text-slate-300' },
    { label: 'Repos Monitored', value: stats?.repositories_monitored ?? 0, icon: '📦', color: 'text-accent' },
    { label: 'PRs This Week', value: stats?.prs_this_week ?? 0, icon: '📅', color: 'text-slate-300' },
  ]

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
      {items.map(({ label, value, icon, color }) => (
        <div key={label} className="card flex flex-col gap-1">
          <div className="flex items-center gap-1.5 text-xs text-slate-500">{icon} {label}</div>
          {loading
            ? <div className="skeleton h-7 w-16 mt-1" />
            : <div className={`text-2xl font-bold ${color}`}>{value}</div>
          }
        </div>
      ))}
    </div>
  )
}
