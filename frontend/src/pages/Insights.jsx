import { useState, useEffect } from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { api } from '../lib/api'
import { riskColor, debtColor, timeAgo, truncate } from '../lib/utils'

export default function Insights() {
  const [repos, setRepos] = useState([])
  const [selected, setSelected] = useState(null)
  const [prs, setPRs] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function load() {
      try {
        const repoData = await api.getRepos()
        setRepos(repoData)
        if (repoData.length) {
          setSelected(repoData[0])
          const prData = await api.getPRs({ repo_id: repoData[0].id, limit: 200 })
          setPRs(prData)
        }
      } catch (e) {
        console.error(e)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  // Build file frequency map from PR data
  const fileFrequency = {}
  const fileDebt = {}
  const authorActivity = {}

  prs.forEach((pr) => {
    const risk = pr.risk_level || 'MEDIUM'
    const debt = pr.debt_score || 0;
    (pr.analysis_json?.affected_modules || []).forEach((mod) => {
      fileFrequency[mod] = (fileFrequency[mod] || 0) + 1
      fileDebt[mod] = Math.max(fileDebt[mod] || 0, debt)
    })
    if (pr.author) {
      authorActivity[pr.author] = authorActivity[pr.author] || { prs: 0, high_risk: 0 }
      authorActivity[pr.author].prs++
      if (['HIGH', 'CRITICAL'].includes(risk)) authorActivity[pr.author].high_risk++
    }
  })

  const topFiles = Object.entries(fileFrequency)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 15)
    .map(([file, count]) => ({ file: truncate(file, 35), fullFile: file, count, debt: fileDebt[file] || 0 }))

  const debtHotspots = Object.entries(fileDebt)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10)
    .map(([file, debt]) => ({ file: truncate(file, 40), debt }))

  const engineers = Object.entries(authorActivity)
    .sort((a, b) => b[1].prs - a[1].prs)
    .slice(0, 10)

  const riskDist = { LOW: 0, MEDIUM: 0, HIGH: 0, CRITICAL: 0 }
  prs.forEach((pr) => { if (pr.risk_level) riskDist[pr.risk_level]++ })
  const riskChartData = Object.entries(riskDist).map(([risk, count]) => ({ risk, count }))

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h2 className="text-2xl font-bold text-white">Repository Insights</h2>
          <p className="text-slate-500 text-sm mt-0.5">File hotspots, debt accumulation, and engineer activity</p>
        </div>
        {repos.length > 1 && (
          <select
            className="bg-bg-secondary border border-bg-tertiary text-slate-300 rounded-lg px-3 py-2 text-sm"
            onChange={async (e) => {
              const repo = repos.find((r) => r.id === +e.target.value)
              setSelected(repo)
              const prData = await api.getPRs({ repo_id: repo.id, limit: 200 })
              setPRs(prData)
            }}
          >
            {repos.map((r) => <option key={r.id} value={r.id}>{r.owner}/{r.name}</option>)}
          </select>
        )}
      </div>

      {loading ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {[...Array(4)].map((_, i) => <div key={i} className="skeleton h-64 rounded-xl" />)}
        </div>
      ) : prs.length === 0 ? (
        <div className="card flex flex-col items-center py-16 text-center">
          <span className="text-5xl mb-4">📊</span>
          <p className="text-slate-400 font-medium">No PR data yet</p>
          <p className="text-slate-600 text-sm mt-1">Insights appear once PRs are analyzed</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* File change frequency heatmap */}
          <div className="card">
            <h3 className="font-semibold text-white text-sm mb-4">Most Changed Modules</h3>
            {topFiles.length ? (
              <div className="space-y-2">
                {topFiles.map(({ file, count, debt }) => (
                  <div key={file} className="flex items-center gap-2">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs font-mono text-slate-300 truncate">{file}</span>
                        <span className="text-xs text-slate-500 ml-2">{count}×</span>
                      </div>
                      <div className="h-1.5 bg-bg-tertiary rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all"
                          style={{
                            width: `${(count / topFiles[0].count) * 100}%`,
                            backgroundColor: debtColor(debt),
                          }}
                        />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : <p className="text-slate-600 text-sm">No module data yet</p>}
          </div>

          {/* Risk distribution chart */}
          <div className="card">
            <h3 className="font-semibold text-white text-sm mb-4">Risk Distribution</h3>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={riskChartData} margin={{ top: 5, right: 10, bottom: 5, left: -10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="risk" tick={{ fill: '#475569', fontSize: 11 }} />
                <YAxis tick={{ fill: '#475569', fontSize: 11 }} />
                <Tooltip
                  contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8 }}
                  labelStyle={{ color: '#94a3b8' }}
                />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {riskChartData.map(({ risk }) => (
                    <Cell key={risk} fill={riskColor(risk)} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Tech debt hotspots */}
          <div className="card">
            <h3 className="font-semibold text-white text-sm mb-4">Technical Debt Hotspots</h3>
            {debtHotspots.length ? (
              <div className="space-y-2">
                {debtHotspots.map(({ file, debt }) => (
                  <div key={file} className="flex items-center justify-between gap-3">
                    <span className="text-xs font-mono text-slate-400 truncate flex-1">{file}</span>
                    <div className="flex items-center gap-2">
                      <div className="h-1.5 w-20 bg-bg-tertiary rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full"
                          style={{ width: `${debt}%`, backgroundColor: debtColor(debt) }}
                        />
                      </div>
                      <span className="text-xs font-mono w-10 text-right" style={{ color: debtColor(debt) }}>
                        {debt.toFixed(0)}/100
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : <p className="text-slate-600 text-sm">No debt data yet</p>}
          </div>

          {/* Engineer activity */}
          <div className="card">
            <h3 className="font-semibold text-white text-sm mb-4">Engineer Activity</h3>
            {engineers.length ? (
              <div className="space-y-3">
                {engineers.map(([author, data]) => (
                  <div key={author} className="flex items-center gap-3">
                    <img
                      src={`https://github.com/${author}.png`}
                      alt={author}
                      className="w-7 h-7 rounded-full flex-shrink-0"
                      onError={(e) => { e.target.src = `https://ui-avatars.com/api/?name=${author}&background=334155&color=e2e8f0&size=28` }}
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium text-slate-200">@{author}</span>
                        <span className="text-xs text-slate-500">{data.prs} PRs</span>
                      </div>
                      <div className="flex gap-2 mt-0.5">
                        <div className="h-1 flex-1 bg-bg-tertiary rounded-full overflow-hidden">
                          <div className="h-full bg-accent rounded-full" style={{ width: `${(data.prs / engineers[0][1].prs) * 100}%` }} />
                        </div>
                      </div>
                    </div>
                    {data.high_risk > 0 && (
                      <span className="text-xs text-risk-high">🔴 {data.high_risk}</span>
                    )}
                  </div>
                ))}
              </div>
            ) : <p className="text-slate-600 text-sm">No engineer data yet</p>}
          </div>
        </div>
      )}
    </div>
  )
}
