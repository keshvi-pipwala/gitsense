import { useRef, useEffect } from 'react'
import { formatDate } from '../../lib/utils'
import clsx from 'clsx'

const STATUS_STYLES = {
  processing: 'text-accent',
  done: 'text-risk-low',
  complete: 'text-risk-low',
  queued: 'text-risk-medium',
  error: 'text-risk-high',
  received: 'text-slate-400',
  info: 'text-slate-400',
}

const STATUS_ICONS = {
  processing: '⟳',
  done: '✓',
  complete: '✓',
  queued: '◌',
  error: '✗',
  received: '→',
  info: '·',
}

function EventRow({ event }) {
  const statusColor = STATUS_STYLES[event.status] || 'text-slate-400'
  const icon = STATUS_ICONS[event.status] || '·'

  return (
    <div className={clsx('flex items-start gap-3 py-2.5 border-b border-bg-tertiary/50 animate-slide-in', {
      'bg-red-950/10': event.status === 'error',
      'bg-green-950/10': event.status === 'complete' || event.status === 'done',
    })}>
      <span className={clsx('font-mono text-sm font-bold w-4 flex-shrink-0 mt-0.5', statusColor)}>{icon}</span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          {event.pr_number && (
            <span className="text-xs bg-accent/10 text-accent px-1.5 py-0.5 rounded font-mono">PR #{event.pr_number}</span>
          )}
          {event.event_type && (
            <span className="text-xs bg-bg-tertiary text-slate-400 px-1.5 py-0.5 rounded font-mono">{event.event_type}</span>
          )}
          {event.step && (
            <span className="text-xs text-slate-500 font-mono">{event.step}</span>
          )}
        </div>
        <p className={clsx('text-sm mt-0.5', statusColor === 'text-slate-400' ? 'text-slate-300' : statusColor)}>
          {event.detail || event.data?.action || JSON.stringify(event.data || {}).slice(0, 100)}
        </p>
      </div>
      <span className="text-xs text-slate-600 flex-shrink-0 font-mono mt-0.5">
        {event.timestamp ? new Date(event.timestamp).toLocaleTimeString() : ''}
      </span>
    </div>
  )
}

export default function EventStream({ events = [], connected }) {
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [events.length])

  return (
    <div className="card flex flex-col h-[600px]">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-white">Live Agent Events</h3>
        <div className="flex items-center gap-2 text-xs">
          <span className={clsx('w-2 h-2 rounded-full', connected ? 'bg-risk-low animate-pulse' : 'bg-slate-600')} />
          <span className={connected ? 'text-risk-low' : 'text-slate-500'}>
            {connected ? 'LIVE' : 'Reconnecting…'}
          </span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto font-mono text-xs pr-1">
        {events.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <span className="text-4xl mb-3">📡</span>
            <p className="text-slate-400">Waiting for GitHub events…</p>
            <p className="text-slate-600 text-xs mt-1">Events appear here in real-time as the agent processes PRs</p>
          </div>
        ) : (
          events.map((event, i) => <EventRow key={i} event={event} />)
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
