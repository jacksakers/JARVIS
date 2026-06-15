import { NavLink, useLocation } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Inbox, Bot, Zap, List, BookOpen, Terminal, Settings,
  Cpu, Wifi, WifiOff, AlertCircle, TestTube2, X, Code2
} from 'lucide-react'
import useStore from '../store'
import clsx from 'clsx'

const NAV = [
  { to: '/',            icon: Inbox,    label: 'Feed',        badge: 'unread' },
  { to: '/chat',        icon: Bot,      label: 'Chat',        badge: null },
  { to: '/routines',    icon: Zap,      label: 'Automations', badge: null },
  { to: '/tasks',       icon: List,     label: 'Task Queue',  badge: null },
  { to: '/journal',     icon: BookOpen, label: 'Journal',     badge: null },
  { to: '/development', icon: Code2,    label: 'Development', badge: null },
  { to: '/debug',       icon: Terminal, label: 'Debug',       badge: null },
  { to: '/settings',    icon: Settings, label: 'Settings',    badge: null },
]

function WsIndicator() {
  const status = useStore(s => s.wsStatus)
  const mock   = useStore(s => s.mockMode)
  const map = {
    connected:    { icon: Wifi,        color: 'text-jarvis-green',  label: 'Connected' },
    mock:         { icon: TestTube2,   color: 'text-jarvis-amber',  label: 'Mock Mode' },
    disconnected: { icon: WifiOff,     color: 'text-jarvis-muted',  label: 'Offline' },
    connecting:   { icon: Wifi,        color: 'text-jarvis-cyan animate-pulse', label: 'Connecting' },
    error:        { icon: AlertCircle, color: 'text-jarvis-red',    label: 'Error' },
  }
  const { icon: Icon, color, label } = map[status] ?? map.disconnected
  return (
    <div className={clsx('flex items-center gap-2 text-xs font-mono', color)}>
      <Icon size={14} />
      <span className="hidden md:inline">{label}</span>
    </div>
  )
}

// ── Desktop sidebar ───────────────────────────────────────────────────────

export function Sidebar({ onClose }) {
  const unread = useStore(s => s.unreadCount)
  const mock   = useStore(s => s.mockMode)

  return (
    <nav className="flex flex-col h-full py-4 px-3 gap-1">
      {/* Logo */}
      <div className="flex items-center gap-3 px-2 py-3 mb-4">
        <div className="relative">
          <Cpu size={22} className="text-jarvis-cyan animate-pulse-glow" />
        </div>
        <div>
          <div className="text-sm font-semibold tracking-widest text-jarvis-cyan-bright text-glow">
            J.A.R.V.I.S
          </div>
          <div className="text-[10px] text-jarvis-muted font-mono">v3.0 COMMAND CENTER</div>
        </div>
        {onClose && (
          <button onClick={onClose} className="ml-auto p-1 text-jarvis-muted hover:text-jarvis-text">
            <X size={16} />
          </button>
        )}
      </div>

      {/* Nav items */}
      {NAV.map(({ to, icon: Icon, label, badge }) => (
        <NavLink
          key={to}
          to={to}
          end={to === '/'}
          onClick={onClose}
          className={({ isActive }) => clsx(
            'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all duration-150 group relative',
            isActive
              ? 'bg-jarvis-cyan/10 text-jarvis-cyan-bright border border-jarvis-border-bright'
              : 'text-jarvis-muted hover:text-jarvis-text hover:bg-white/5 border border-transparent'
          )}
        >
          {({ isActive }) => (
            <>
              <Icon size={17} className={clsx('shrink-0', isActive && 'text-jarvis-cyan')} />
              <span className="flex-1">{label}</span>
              {badge === 'unread' && unread > 0 && (
                <span className="text-[10px] font-bold bg-jarvis-cyan text-jarvis-bg px-1.5 py-0.5 rounded-full min-w-[18px] text-center">
                  {unread > 99 ? '99+' : unread}
                </span>
              )}
              {isActive && (
                <motion.div
                  layoutId="nav-indicator"
                  className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 bg-jarvis-cyan rounded-full"
                />
              )}
            </>
          )}
        </NavLink>
      ))}

      {/* Bottom status */}
      <div className="mt-auto px-3 pt-4 border-t border-jarvis-border">
        <WsIndicator />
        {mock && (
          <div className="mt-2 text-[10px] font-mono text-jarvis-amber bg-jarvis-amber/10 border border-jarvis-amber/20 rounded px-2 py-1">
            ⚠ MOCK MODE ACTIVE
          </div>
        )}
      </div>
    </nav>
  )
}

// ── Mobile bottom navigation ──────────────────────────────────────────────

export function MobileNav() {
  const unread = useStore(s => s.unreadCount)
  const mobile = NAV.slice(0, 5) // Show first 5 on mobile

  return (
    <nav className="flex items-center justify-around px-2 py-2 glass border-t border-jarvis-border safe-area-bottom md:hidden">
      {mobile.map(({ to, icon: Icon, label, badge }) => (
        <NavLink
          key={to}
          to={to}
          end={to === '/'}
          className={({ isActive }) => clsx(
            'flex flex-col items-center gap-1 px-3 py-1.5 rounded-lg relative',
            isActive ? 'text-jarvis-cyan' : 'text-jarvis-muted'
          )}
        >
          {({ isActive }) => (
            <>
              <Icon size={20} />
              <span className="text-[10px]">{label}</span>
              {badge === 'unread' && unread > 0 && (
                <span className="absolute -top-1 -right-1 text-[9px] font-bold bg-jarvis-cyan text-jarvis-bg w-4 h-4 rounded-full flex items-center justify-center">
                  {unread > 9 ? '9+' : unread}
                </span>
              )}
            </>
          )}
        </NavLink>
      ))}
    </nav>
  )
}

// ── Top bar (mobile) ───────────────────────────────────────────────────────

export function TopBar({ onMenuOpen }) {
  const location = useLocation()
  const mockMode = useStore(s => s.mockMode)
  const toggle   = useStore(s => s.toggleMock)
  const title = NAV.find(n => n.to === location.pathname)?.label ?? 'JARVIS'

  return (
    <header className="flex items-center gap-3 px-4 py-3 glass border-b border-jarvis-border md:hidden">
      <button onClick={onMenuOpen} className="p-1">
        <Cpu size={20} className="text-jarvis-cyan" />
      </button>
      <span className="font-semibold text-jarvis-cyan-bright tracking-wide flex-1">{title}</span>
      <WsIndicator />
      <button
        onClick={toggle}
        className={clsx(
          'text-[10px] font-mono px-2 py-1 rounded border transition-colors',
          mockMode
            ? 'border-jarvis-amber/40 text-jarvis-amber bg-jarvis-amber/10'
            : 'border-jarvis-border text-jarvis-muted hover:text-jarvis-text'
        )}
      >
        {mockMode ? 'MOCK' : 'LIVE'}
      </button>
    </header>
  )
}

// ── Desktop header bar ────────────────────────────────────────────────────

export function DesktopTopBar() {
  const location = useLocation()
  const mockMode = useStore(s => s.mockMode)
  const toggle   = useStore(s => s.toggleMock)
  const title = NAV.find(n =>
    n.to === '/' ? location.pathname === '/' : location.pathname.startsWith(n.to)
  )?.label ?? 'JARVIS'

  return (
    <header className="hidden md:flex items-center gap-4 px-6 py-3 border-b border-jarvis-border bg-jarvis-surface/50">
      <h1 className="text-sm font-semibold text-jarvis-text tracking-wide">{title}</h1>
      <div className="flex-1" />
      <WsIndicator />
      <button
        onClick={toggle}
        className={clsx(
          'flex items-center gap-2 text-xs font-mono px-3 py-1.5 rounded-lg border transition-all',
          mockMode
            ? 'border-jarvis-amber/40 text-jarvis-amber bg-jarvis-amber/10 hover:bg-jarvis-amber/20'
            : 'border-jarvis-border text-jarvis-muted hover:text-jarvis-text hover:border-jarvis-cyan/30'
        )}
      >
        <TestTube2 size={13} />
        {mockMode ? 'Mock Mode ON' : 'Mock Mode OFF'}
      </button>
    </header>
  )
}
