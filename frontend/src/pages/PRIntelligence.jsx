import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import { riskBadgeClass, riskEmoji, debtColor, timeAgo, truncate } from '../lib/utils'
import clsx from 'clsx'

const RISK_OPTIONS = ['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW']

export default function PRIntelligence() {
  const [prs, setPRs] = useState([])
  const [loading, setLoading] = useState(true)
  const [riskFilter, setRiskFilter] = useState('ALL')
  const [authorFilter, setAuthorFilter] = useState('')
  const [repos, setRepos] = useState([])
  const [repoFilter, setRepoFilter] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params = { limit: 100 }
      if (riskFilter !== 'ALL') params.risk_level = riskFilter
      if (authorFilter) params.author = authorFilter
      if (repoFilter) params.repo_id = repoFilter
      const data = await api.getPRs(params)
      setPRs(data)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }, [riskFilter, authorFilter, repoFilter])

  useEffect(() => {
    api.getRepos().then(setRepos).catch(() => {})
    load()
  }, [load])

  return (
    <div className="p-6 space-y-5">
      <div>
        <h2 className="text-2xl font-bold text-white">PR Intelligence</h2>
        <p className="text-slate-500 text-sm mt-0.5">Every analyzed pull request — filterable and searchable</p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-center">
        <div className="flex gap-1">
          {RISK_OPTIONS.map((r) => (
            <button
              key={r}
              onClick={() => setRiskFilter(r)}
              className={clsx(
                'text-xs px-3 py-1.5 rounded-lg font-semibold transition-all',
                riskFilter === r
                  ? 'bg-accent text-white'
                  : 'bg-bg-secondary border border-bg-tertiary text-slate-400 hover:text-white'
              )}
            >
              {r === 'ALL' ? 'All' : `${riskEmoji(r)} ${r}`}
            </button>
          ))}
        </div>
        <input
          type="text"
          placeholder="Filter by author…"
          value={authorFilter}
          onChange={(e) => setAuthorFilter(e.target.value)}
          className="bg-bg-secondary border border-bg-tertiary text-slate-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-accent/50 w-44"
        />
        {repos.length > 0 && (
          <select
            value={repoFilter}
            onChange={(e) => setRepoFilter(e.target.value)}
            className="bg-bg-secondary border border-bg-tertiary text-slate-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-accent/50"
          >
            <option value="">All Repos</option>
            {repos.map((r) => (
              <option key={r.id} value={r.id}>{r.owner}/{r.name}</option>
            ))}
          </select>
        )}
        <span className="text-slate-500 text-xs ml-auto">{prs.length} PRs</span>
      </div>

      {/* PR List */}
      {loading ? (
        <div className="space-y-3">
          {[...Array(8)].map((_, i) => (
            <div key={i} className="card animate-pulse flex gap-4 items-center">
              <div className="skeleton w-10 h-10 rounded-full" />
              <div className="flex-1 space-y-2">
                <div className="skeleton h-4 w-2/3" />
                <div className="skeleton h-3 w-1/3" />
              </div>
            </div>
          ))}
        </div>
      ) : prs.length === 0 ? (
        <div className="card flex flex-col items-center py-16 text-center">
          <span className="text-5xl mb-4">⚡</span>
          <p className="text-slate-400 font-medium">No PRs match your filters</p>
        </div>
      ) : (
        <div className="space-y-2">
          {prs.map((pr) => (
            <Link
              key={pr.id}
              to={`/pr/${pr.id}`}
              className="card flex items-start gap-4 hover:border-accent/30 transition-all group cursor-pointer block"
            >
              <img
                src={pr.author_avatar_url || `https://github.com/${pr.author}.png`}
                alt={pr.author}
                className="w-10 h-10 rounded-full flex-shrink-0"
                onError={(e) => { e.target.src = `https://ui-avatars.com/api/?name=${pr.author}&background=334155&color=e2e8f0` }}
              />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-white font-semibold text-sm group-hover:text-accent transition-colors">
                    {truncate(pr.title, 80)}
                  </span>
                  {pr.risk_level && (
                    <span className={riskBadgeClass(pr.risk_level)}>
                      {riskEmoji(pr.risk_level)} {pr.risk_level}
                    </span>
                  )}
                  {pr.is_stale && <span className="text-xs bg-slate-700 text-slate-400 px-2 py-0.5 rounded-full">STALE</span>}
                </div>

                <p className="text-xs text-slate-500 mt-1 leading-relaxed line-clamp-1">
                  {pr.analysis_json?.summary || 'Analysis pending…'}
                </p>

                <div className="flex gap-4 mt-2 text-xs text-slate-500 flex-wrap">
                  <span>#{pr.github_pr_number}</span>
                  <span>@{pr.author}</span>
                  <span style={{ color: debtColor(pr.debt_score ?? 0) }}>🏚️ {pr.debt_score?.toFixed(0) ?? 0}/100</span>
                  <span>💥 {pr.blast_radius_count} modules</span>
                  <span>±{(pr.lines_added ?? 0) + (pr.lines_removed ?? 0)} lines</span>
                  <span>{timeAgo(pr.created_at)}</span>
                </div>

                {pr.analysis_json?.recommendations?.length > 0 && (
                  <p className="text-xs text-accent/70 mt-1.5">
                    → {pr.analysis_json.recommendations[0]}
                  </p>
                )}
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
