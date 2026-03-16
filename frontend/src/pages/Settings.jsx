import { useState, useEffect } from 'react'
import { api } from '../lib/api'
import { timeAgo } from '../lib/utils'
import clsx from 'clsx'

function StatusDot({ status }) {
  const colors = {
    complete: 'bg-risk-low',
    indexing: 'bg-accent animate-pulse',
    pending: 'bg-risk-medium',
    failed: 'bg-risk-high',
  }
  return <span className={clsx('inline-block w-2 h-2 rounded-full', colors[status] || 'bg-slate-600')} />
}

export default function Settings() {
  const [repos, setRepos] = useState([])
  const [newUrl, setNewUrl] = useState('')
  const [adding, setAdding] = useState(false)
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(null)
  const [indexingId, setIndexingId] = useState(null)

  const loadRepos = () => api.getRepos().then(setRepos).catch(console.error)

  useEffect(() => {
    loadRepos()
    const interval = setInterval(loadRepos, 5000)
    return () => clearInterval(interval)
  }, [])

  async function addRepo(e) {
    e.preventDefault()
    if (!newUrl.trim()) return
    setAdding(true)
    setError(null)
    try {
      await api.createRepo({ github_url: newUrl.trim() })
      setSuccess('Repository added successfully!')
      setNewUrl('')
      loadRepos()
      setTimeout(() => setSuccess(null), 3000)
    } catch (err) {
      setError(err.message)
    } finally {
      setAdding(false)
    }
  }

  async function triggerIndex(repoId) {
    setIndexingId(repoId)
    try {
      await api.indexRepo(repoId)
      setSuccess('Indexing started!')
      setTimeout(() => setSuccess(null), 3000)
      loadRepos()
    } catch (err) {
      setError(err.message)
    } finally {
      setTimeout(() => setIndexingId(null), 2000)
    }
  }

  async function deleteRepo(repoId, name) {
    if (!confirm(`Delete ${name} from GitSense? This removes all indexed data.`)) return
    try {
      await api.deleteRepo(repoId)
      loadRepos()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="p-6 space-y-6 max-w-3xl">
      <div>
        <h2 className="text-2xl font-bold text-white">Settings</h2>
        <p className="text-slate-500 text-sm mt-0.5">Manage repositories and configuration</p>
      </div>

      {/* Add Repository */}
      <div className="card space-y-4">
        <h3 className="font-semibold text-white">Add Repository</h3>
        <form onSubmit={addRepo} className="flex gap-3">
          <input
            type="url"
            value={newUrl}
            onChange={(e) => setNewUrl(e.target.value)}
            placeholder="https://github.com/owner/repo"
            className="flex-1 bg-bg-tertiary border border-bg-tertiary text-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-accent/50"
            required
          />
          <button type="submit" disabled={adding} className="btn-primary">
            {adding ? 'Adding…' : 'Add Repo'}
          </button>
        </form>
        {error && <p className="text-risk-high text-sm">⚠️ {error}</p>}
        {success && <p className="text-risk-low text-sm">✓ {success}</p>}
        <div className="text-xs text-slate-500 bg-bg-primary/50 rounded-lg p-3 space-y-1">
          <p className="font-medium text-slate-400">After adding a repository:</p>
          <p>1. Configure a GitHub webhook pointing to <code className="font-mono text-accent">YOUR_URL/webhook/github</code></p>
          <p>2. Set Content-Type to <code className="font-mono text-accent">application/json</code></p>
          <p>3. Select events: Pull requests, Pushes, Issues</p>
          <p>4. Set the secret to your <code className="font-mono text-accent">GITHUB_WEBHOOK_SECRET</code></p>
          <p>5. Click "Index Now" to index the codebase for semantic search</p>
        </div>
      </div>

      {/* Repositories */}
      <div className="card space-y-3">
        <h3 className="font-semibold text-white">Monitored Repositories</h3>
        {repos.length === 0 ? (
          <p className="text-slate-500 text-sm">No repositories added yet</p>
        ) : (
          <div className="space-y-3">
            {repos.map((repo) => (
              <div key={repo.id} className="flex items-center justify-between gap-4 p-3 bg-bg-primary/40 rounded-lg border border-bg-tertiary">
                <div className="flex items-center gap-3 min-w-0">
                  <StatusDot status={repo.indexing_status} />
                  <div className="min-w-0">
                    <a
                      href={repo.github_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm font-medium text-white hover:text-accent transition-colors"
                    >
                      {repo.owner}/{repo.name}
                    </a>
                    <div className="text-xs text-slate-500 mt-0.5 flex gap-3 flex-wrap">
                      <span>Status: <span className="text-slate-300">{repo.indexing_status}</span></span>
                      <span>{repo.total_files_indexed} files indexed</span>
                      <span>Health: <span className="text-accent">{repo.health_score?.toFixed(0) ?? '—'}/100</span></span>
                      {repo.indexed_at && <span>Last indexed {timeAgo(repo.indexed_at)}</span>}
                    </div>
                  </div>
                </div>
                <div className="flex gap-2 flex-shrink-0">
                  <button
                    onClick={() => triggerIndex(repo.id)}
                    disabled={repo.indexing_status === 'indexing' || indexingId === repo.id}
                    className="text-xs btn-ghost py-1"
                  >
                    {repo.indexing_status === 'indexing' ? '⟳ Indexing…' : 'Index Now'}
                  </button>
                  <button
                    onClick={() => deleteRepo(repo.id, `${repo.owner}/${repo.name}`)}
                    className="text-xs text-risk-high hover:bg-red-950/30 border border-red-900/30 hover:border-risk-high/30 px-2 py-1 rounded-lg transition-all"
                  >
                    Remove
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Environment info */}
      <div className="card space-y-3">
        <h3 className="font-semibold text-white">Configuration Reference</h3>
        <div className="text-xs font-mono space-y-1.5 text-slate-400">
          {[
            ['GITHUB_TOKEN', 'GitHub personal access token (repo scope)'],
            ['GITHUB_WEBHOOK_SECRET', 'Webhook HMAC secret — set same in GitHub'],
            ['ANTHROPIC_API_KEY', 'Claude API key from console.anthropic.com'],
            ['SLACK_WEBHOOK_URL', 'Slack incoming webhook URL (optional)'],
            ['SMTP_HOST / SMTP_USER', 'Email server credentials (optional)'],
            ['DATABASE_URL', 'PostgreSQL connection string'],
            ['REDIS_URL', 'Redis connection string for Celery'],
          ].map(([key, desc]) => (
            <div key={key} className="flex gap-3">
              <span className="text-accent w-48 flex-shrink-0">{key}</span>
              <span className="text-slate-500">{desc}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
