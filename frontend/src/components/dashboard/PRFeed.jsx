import { Link } from 'react-router-dom'
import { riskBadgeClass, riskEmoji, timeAgo, truncate } from '../../lib/utils'

export default function PRFeed({ prs = [], loading }) {
  if (loading) {
    return (
      <div className="space-y-3">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="card flex items-center gap-3 animate-pulse">
            <div className="skeleton w-8 h-8 rounded-full" />
            <div className="flex-1 space-y-2">
              <div className="skeleton h-4 w-3/4" />
              <div className="skeleton h-3 w-1/2" />
            </div>
          </div>
        ))}
      </div>
    )
  }

  if (!prs.length) {
    return (
      <div className="card flex flex-col items-center py-12 text-center">
        <span className="text-4xl mb-3">🔍</span>
        <p className="text-slate-400 font-medium">No PRs analyzed yet</p>
        <p className="text-slate-600 text-sm mt-1">Add a repository and configure webhooks to start</p>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {prs.map((pr) => (
        <Link
          key={pr.id}
          to={`/pr/${pr.id}`}
          className="card flex items-start gap-3 hover:border-accent/30 transition-all duration-150 group cursor-pointer block"
        >
          <img
            src={pr.author_avatar_url || `https://github.com/${pr.author}.png`}
            alt={pr.author}
            className="w-8 h-8 rounded-full mt-0.5 flex-shrink-0"
            onError={(e) => { e.target.src = `https://ui-avatars.com/api/?name=${pr.author}&background=334155&color=e2e8f0` }}
          />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-white font-medium text-sm group-hover:text-accent transition-colors truncate">
                {truncate(pr.title, 70)}
              </span>
              {pr.risk_level && <span className={riskBadgeClass(pr.risk_level)}>{riskEmoji(pr.risk_level)} {pr.risk_level}</span>}
            </div>
            <div className="flex items-center gap-3 mt-1 text-xs text-slate-500">
              <span>#{pr.github_pr_number}</span>
              <span>@{pr.author}</span>
              <span>💥 {pr.blast_radius_count} modules</span>
              <span>🏚️ {pr.debt_score?.toFixed(0) ?? 0}/100 debt</span>
              <span>{timeAgo(pr.created_at)}</span>
            </div>
          </div>
        </Link>
      ))}
    </div>
  )
}
