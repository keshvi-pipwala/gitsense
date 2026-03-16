import { NavLink } from 'react-router-dom'
import clsx from 'clsx'

const NAV = [
  { to: '/', label: 'Overview', icon: '◈' },
  { to: '/prs', label: 'PR Intelligence', icon: '⚡' },
  { to: '/insights', label: 'Repository Insights', icon: '📊' },
  { to: '/events', label: 'Live Events', icon: '📡' },
  { to: '/settings', label: 'Settings', icon: '⚙️' },
]

export default function Sidebar({ wsConnected }) {
  return (
    <aside className="w-60 min-h-screen bg-bg-secondary border-r border-bg-tertiary flex flex-col">
      <div className="px-6 py-5 border-b border-bg-tertiary">
        <div className="flex items-center gap-2.5">
          <span className="text-2xl">🧠</span>
          <div>
            <h1 className="font-bold text-white text-lg leading-tight">GitSense</h1>
            <p className="text-xs text-slate-500 font-mono">Codebase Intelligence</p>
          </div>
        </div>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-0.5">
        {NAV.map(({ to, label, icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) => clsx(
              'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150',
              isActive
                ? 'bg-accent/15 text-accent border border-accent/20'
                : 'text-slate-400 hover:text-white hover:bg-bg-tertiary/50'
            )}
          >
            <span className="text-base w-5 text-center">{icon}</span>
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="px-4 py-4 border-t border-bg-tertiary">
        <div className="flex items-center gap-2 text-xs">
          <span className={clsx(
            'w-2 h-2 rounded-full',
            wsConnected ? 'bg-risk-low animate-pulse' : 'bg-slate-600'
          )} />
          <span className={wsConnected ? 'text-risk-low' : 'text-slate-500'}>
            {wsConnected ? 'Live stream active' : 'Connecting…'}
          </span>
        </div>
      </div>
    </aside>
  )
}
