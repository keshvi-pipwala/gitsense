const BASE = '/api'

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export const api = {
  // Repos
  getRepos: () => request('/repositories'),
  getRepo: (id) => request(`/repositories/${id}`),
  createRepo: (data) => request('/repositories', { method: 'POST', body: JSON.stringify(data) }),
  deleteRepo: (id) => request(`/repositories/${id}`, { method: 'DELETE' }),
  indexRepo: (id) => request(`/repositories/${id}/index`, { method: 'POST' }),
  getIndexStatus: (id) => request(`/repositories/${id}/status`),

  // PRs
  getPRs: (params = {}) => {
    const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v != null))
    return request(`/prs?${qs}`)
  },
  getPR: (id) => request(`/prs/${id}`),

  // Health
  getHealthHistory: (repoId, days = 30) => request(`/health-history/${repoId}?days=${days}`),

  // Events
  getEvents: (params = {}) => {
    const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v != null))
    return request(`/events?${qs}`)
  },

  // Stats
  getStats: (repoId) => request(`/stats${repoId ? `?repo_id=${repoId}` : ''}`),
}

export function createWebSocket(onMessage) {
  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
  const host = window.location.host
  const ws = new WebSocket(`${protocol}://${host}/ws/events`)

  ws.onopen = () => {
    console.log('GitSense WebSocket connected')
    // Heartbeat
    const ping = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) ws.send('ping')
    }, 30000)
    ws._pingInterval = ping
  }
  ws.onmessage = (e) => {
    try { onMessage(JSON.parse(e.data)) } catch (_) {}
  }
  ws.onclose = () => {
    clearInterval(ws._pingInterval)
  }
  return ws
}
