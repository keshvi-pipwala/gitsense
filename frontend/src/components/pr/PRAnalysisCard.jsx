import { useState } from 'react'
import { riskBadgeClass, riskEmoji, debtColor, timeAgo, formatDate } from '../../lib/utils'

function Section({ title, icon, items, color = 'text-slate-300', defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen)
  if (!items || !items.length) return null
  return (
    <div className="border border-bg-tertiary rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-bg-tertiary/30 transition-colors"
      >
        <span className="text-sm font-semibold text-slate-200">{icon} {title} <span className="text-slate-500 font-normal">({items.length})</span></span>
        <span className="text-slate-500 text-xs">{open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <ul className="px-4 pb-3 space-y-1.5">
          {items.map((item, i) => (
            <li key={i} className={`text-sm ${color} leading-relaxed flex gap-2`}>
              <span className="text-slate-600 mt-0.5 flex-shrink-0">•</span>
              <span>{item}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export default function PRAnalysisCard({ pr }) {
  if (!pr) return null
  const analysis = pr.analysis_json || {}

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Header */}
      <div className="card">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap mb-2">
              {pr.risk_level && <span className={riskBadgeClass(pr.risk_level)}>{riskEmoji(pr.risk_level)} {pr.risk_level} RISK</span>}
              {pr.is_stale && <span className="badge-risk-medium">STALE</span>}
            </div>
            <h2 className="text-xl font-bold text-white leading-snug">{pr.title}</h2>
            <div className="flex items-center gap-3 mt-2 text-sm text-slate-400 flex-wrap">
              <span>PR #{pr.github_pr_number}</span>
              <span>·</span>
              <img
                src={pr.author_avatar_url || `https://github.com/${pr.author}.png`}
                className="w-5 h-5 rounded-full inline"
                alt=""
                onError={(e) => { e.target.style.display = 'none' }}
              />
              <span>@{pr.author}</span>
              <span>·</span>
              <span>{timeAgo(pr.created_at)}</span>
            </div>
          </div>
          <a
            href={pr.github_pr_url}
            target="_blank"
            rel="noopener noreferrer"
            className="btn-ghost text-sm flex-shrink-0"
          >
            View on GitHub ↗
          </a>
        </div>

        {/* Metrics grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-4 pt-4 border-t border-bg-tertiary">
          {[
            { label: 'Debt Score', value: `${pr.debt_score?.toFixed(0) ?? 0}/100`, color: debtColor(pr.debt_score ?? 0) },
            { label: 'Blast Radius', value: `${pr.blast_radius_count ?? 0} modules` },
            { label: 'Files Changed', value: pr.files_changed ?? 0 },
            { label: 'Lines', value: `+${pr.lines_added ?? 0} / -${pr.lines_removed ?? 0}` },
          ].map(({ label, value, color }) => (
            <div key={label} className="text-center">
              <div className="text-xs text-slate-500 mb-1">{label}</div>
              <div className="font-bold text-sm" style={color ? { color } : {}}>{value}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Summary */}
      {analysis.summary && (
        <div className="card border-l-4 border-accent">
          <p className="text-sm text-slate-300 leading-relaxed">{analysis.summary}</p>
        </div>
      )}

      {/* Sections */}
      <div className="space-y-2">
        <Section title="Recommendations" icon="🎯" items={analysis.recommendations} color="text-slate-200" defaultOpen />
        <Section title="Breaking Changes" icon="⚠️" items={analysis.breaking_changes} color="text-risk-high" />
        <Section title="Affected Modules" icon="💥" items={analysis.affected_modules} color="text-risk-medium" />
        <Section title="Conflicts" icon="⚡" items={analysis.conflicts} color="text-risk-medium" />
        <Section title="Technical Debt" icon="🏚️" items={analysis.debt_issues} />
        <Section title="Suggested Reviewers" icon="👥" items={analysis.reviewer_suggestions} />
        <Section title="Similar Past PRs" icon="📚" items={analysis.similar_past_prs} />
      </div>

      {/* Risk reasoning */}
      {analysis.risk_reasoning && (
        <div className="card bg-bg-primary/50">
          <p className="text-xs text-slate-500 font-mono leading-relaxed">
            🧠 <strong className="text-slate-400">Risk reasoning:</strong> {analysis.risk_reasoning}
          </p>
        </div>
      )}

      {/* Labels */}
      {pr.labels_applied?.length > 0 && (
        <div className="flex gap-2 flex-wrap">
          {pr.labels_applied.map((l) => (
            <span key={l} className="text-xs bg-accent/10 text-accent border border-accent/20 px-2 py-0.5 rounded font-mono">{l}</span>
          ))}
        </div>
      )}
    </div>
  )
}
