import { useState, useEffect } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { api } from '../lib/api'
import { healthColor } from '../lib/utils'
import HealthGauge from '../components/dashboard/HealthGauge'
import StatsBar from '../components/dashboard/StatsBar'
import PRFeed from '../components/dashboard/PRFeed'

export default function Overview() {
  const [repos, setRepos] = useState([])
  const [selectedRepo, setSelectedRepo] = useState(null)
  const [stats, setStats] = useState(null)
  const [prs, setPRs] = useState([])
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function load() {
      try {
        const [repoData, statsData, prData] = await Promise.all([
          api.getRepos(),
          api.getStats(),
          api.getPRs({ limit: 10 }),
        ])
        setRepos(repoData)
        setStats(statsData)
        setPRs(prData)
        if (repoData.length) {
          setSelectedRepo(repoData[0])
          const h = await api.getHealthHistory(repoData[0].id, 30)
          setHistory(h)
        }
      } catch (e) {
        console.error(e)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const healthScore = selectedRepo?.health_score ?? 0
  const chartData = history.map((h) => ({
    date: new Date(h.calculated_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
    score: Math.round(h.score),
  }))

  return (
    <div className="p-6 space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-white">Overview</h2>
        <p className="text-slate-500 text-sm mt-0.5">Real-time codebase intelligence dashboard</p>
      </div>

      <StatsBar stats={stats} loading={loading} />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Health gauge */}
        <div className="card flex flex-col items-center justify-center gap-2">
          <div className="text-sm text-slate-500 font-medium mb-2">
            {selectedRepo ? `${selectedRepo.owner}/${selectedRepo.name}` : 'Repository Health'}
          </div>
          {loading ? (
            <div className="skeleton w-40 h-28" />
          ) : (
            <HealthGauge score={healthScore} size={200} />
          )}
          {repos.length > 1 && (
            <select
              className="mt-2 bg-bg-tertiary text-slate-300 text-xs rounded px-2 py-1 border border-bg-tertiary"
              onChange={async (e) => {
                const repo = repos.find((r) => r.id === +e.target.value)
                setSelectedRepo(repo)
                if (repo) {
                  const h = await api.getHealthHistory(repo.id, 30)
                  setHistory(h)
                }
              }}
            >
              {repos.map((r) => (
                <option key={r.id} value={r.id}>{r.owner}/{r.name}</option>
              ))}
            </select>
          )}
        </div>

        {/* Health trend chart */}
        <div className="card col-span-2">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-white text-sm">Health Score Trend (30 days)</h3>
          </div>
          {loading || !chartData.length ? (
            <div className="flex items-center justify-center h-40 text-slate-600 text-sm">
              {loading ? 'Loading…' : 'No health history yet — checks run every 6 hours'}
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={180}>
              <LineChart data={chartData} margin={{ top: 5, right: 10, bottom: 5, left: -10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="date" tick={{ fill: '#475569', fontSize: 11 }} />
                <YAxis domain={[0, 100]} tick={{ fill: '#475569', fontSize: 11 }} />
                <Tooltip
                  contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8 }}
                  labelStyle={{ color: '#94a3b8' }}
                  itemStyle={{ color: '#6366f1' }}
                />
                <Line
                  type="monotone"
                  dataKey="score"
                  stroke="#6366f1"
                  strokeWidth={2.5}
                  dot={{ fill: '#6366f1', r: 3 }}
                  activeDot={{ r: 5, fill: '#818cf8' }}
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* PR Feed */}
      <div>
        <h3 className="font-semibold text-white text-sm mb-3">Recent PR Analysis</h3>
        <PRFeed prs={prs} loading={loading} />
      </div>
    </div>
  )
}
