import { useState, useCallback } from 'react'
import { useWebSocket } from '../hooks/useWebSocket'
import EventStream from '../components/events/EventStream'

const MAX_EVENTS = 200

export default function Events() {
  const [events, setEvents] = useState([])

  const onMessage = useCallback((msg) => {
    if (msg.type === 'connected') return
    setEvents((prev) => {
      const next = [...prev, { ...msg, timestamp: msg.timestamp || new Date().toISOString() }]
      return next.slice(-MAX_EVENTS)
    })
  }, [])

  const { connected } = useWebSocket(onMessage)

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white">Live Event Stream</h2>
          <p className="text-slate-500 text-sm mt-0.5">Watch the AI agent process PRs in real-time</p>
        </div>
        <button
          onClick={() => setEvents([])}
          className="btn-ghost text-sm"
        >
          Clear
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        <div className="card text-center">
          <div className="text-3xl font-bold text-accent">{events.length}</div>
          <div className="text-xs text-slate-500 mt-1">Total Events</div>
        </div>
        <div className="card text-center">
          <div className="text-3xl font-bold text-risk-low">
            {events.filter(e => e.status === 'complete' || e.status === 'done').length}
          </div>
          <div className="text-xs text-slate-500 mt-1">Completed</div>
        </div>
        <div className="card text-center">
          <div className="text-3xl font-bold text-accent">
            {events.filter(e => e.status === 'processing').length}
          </div>
          <div className="text-xs text-slate-500 mt-1">Processing</div>
        </div>
        <div className="card text-center">
          <div className="text-3xl font-bold text-risk-high">
            {events.filter(e => e.status === 'error').length}
          </div>
          <div className="text-xs text-slate-500 mt-1">Errors</div>
        </div>
      </div>

      <EventStream events={events} connected={connected} />
    </div>
  )
}
