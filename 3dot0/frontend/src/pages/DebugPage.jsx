import { useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { Terminal, Trash2, Filter, Wifi, WifiOff, Circle } from 'lucide-react'
import { format } from 'date-fns'
import { GlassPanel, Button, Badge, StatusDot, SectionHeader } from '../components/ui'
import useStore from '../store'
import * as API from '../api'
import clsx from 'clsx'

const EVENT_COLORS = {
  task_queued:  'text-jarvis-amber',
  task_started: 'text-jarvis-cyan',
  task_done:    'text-jarvis-green',
  task_failed:  'text-jarvis-red',
  tool_call:    'text-jarvis-purple',
  tool_result:  'text-jarvis-green/70',
  feed_new:     'text-jarvis-cyan/70',
  ambient:      'text-jarvis-muted',
  connected:    'text-jarvis-green',
  disconnected: 'text-jarvis-red',
  reconnecting: 'text-jarvis-amber',
}

const ALL_EVENT_TYPES = [
  'task_queued', 'task_started', 'task_done', 'task_failed',
  'tool_call', 'tool_result', 'feed_new', 'ambient', 'connected'
]

function EventRow({ event, index }) {
  const [expanded, setExpanded] = useState(false)
  const color = EVENT_COLORS[event.event] ?? 'text-jarvis-text'
  const ts = event.ts ? format(new Date(event.ts), 'HH:mm:ss.SSS') : ''
  const hasData = event.data && Object.keys(event.data).length > 0

  return (
    <motion.div
      initial={{ opacity: 0, x: -4 }}
      animate={{ opacity: 1, x: 0 }}
      className={clsx('font-mono text-xs border-b border-jarvis-border/30 last:border-0', index % 2 === 0 ? 'bg-transparent' : 'bg-jarvis-surface/20')}
    >
      <button
        onClick={() => hasData && setExpanded(e => !e)}
        className={clsx('w-full flex items-center gap-3 px-4 py-2 text-left', hasData && 'hover:bg-jarvis-surface/30 cursor-pointer')}
      >
        <span className="text-jarvis-muted/60 shrink-0 w-24">{ts}</span>
        <span className={clsx('shrink-0 w-32 font-semibold', color)}>{event.event}</span>
        <span className="text-jarvis-muted truncate flex-1">
          {event.data
            ? Object.entries(event.data).slice(0, 2).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join('  ')
            : ''}
        </span>
        {hasData && <span className="text-jarvis-muted/40">{expanded ? '▾' : '▸'}</span>}
      </button>
      {expanded && (
        <div className="px-4 pb-3 pt-1">
          <pre className="text-[10px] text-jarvis-muted leading-relaxed overflow-x-auto whitespace-pre-wrap">
            {JSON.stringify(event.data, null, 2)}
          </pre>
        </div>
      )}
    </motion.div>
  )
}

export default function DebugPage() {
  const mockMode  = useStore(s => s.mockMode)
  const wsStatus  = useStore(s => s.wsStatus)
  const wsEvents  = useStore(s => s.wsEvents)
  const clearEvts = useStore(s => s.clearWsEvents)

  const [filterTypes, setFilterTypes] = useState([])
  const [modelInfo,   setModelInfo]   = useState(null)
  const [skills,      setSkills]      = useState([])
  const bottomRef = useRef(null)

  useEffect(() => {
    API.getSkills(mockMode).then(setSkills).catch(() => {})
    // Try to get health / model info
    fetch('/api/v1/users/me').then(r => r.json()).then(u => setModelInfo(u)).catch(() => {})
  }, [mockMode])

  const toggleFilter = (type) => {
    setFilterTypes(prev => prev.includes(type) ? prev.filter(t => t !== type) : [...prev, type])
  }

  const filtered = filterTypes.length === 0
    ? wsEvents
    : wsEvents.filter(e => filterTypes.includes(e.event))

  const WsIcon = wsStatus === 'connected' ? Wifi : wsStatus === 'disconnected' ? WifiOff : Circle

  return (
    <div className="max-w-4xl mx-auto px-4 py-6 flex flex-col h-full">
      <SectionHeader
        title="Debug Console"
        subtitle="Live WebSocket event stream and system info."
        actions={
          <Button variant="ghost" size="sm" onClick={clearEvts}>
            <Trash2 size={14} /> Clear log
          </Button>
        }
      />

      {/* Status cards */}
      <div className="grid grid-cols-2 gap-3 mb-5 sm:grid-cols-3">
        <GlassPanel className="p-3">
          <p className="text-[10px] text-jarvis-muted uppercase tracking-wider mb-1">WebSocket</p>
          <div className="flex items-center gap-2">
            <StatusDot status={wsStatus === 'connected' || wsStatus === 'mock' ? 'active' : 'inactive'} />
            <span className="text-sm font-medium text-jarvis-text capitalize">{wsStatus}</span>
          </div>
          {mockMode && <p className="text-[10px] text-jarvis-amber mt-1">Mock mode active</p>}
        </GlassPanel>

        <GlassPanel className="p-3">
          <p className="text-[10px] text-jarvis-muted uppercase tracking-wider mb-1">Skills loaded</p>
          <p className="text-sm font-medium text-jarvis-cyan">{skills.length}</p>
          <p className="text-[10px] text-jarvis-muted truncate">{skills.map(s => s.name).join(', ') || '—'}</p>
        </GlassPanel>

        <GlassPanel className="p-3">
          <p className="text-[10px] text-jarvis-muted uppercase tracking-wider mb-1">Events logged</p>
          <p className="text-sm font-medium text-jarvis-text">{wsEvents.length}</p>
          {filtered.length !== wsEvents.length && (
            <p className="text-[10px] text-jarvis-amber">{filtered.length} shown (filtered)</p>
          )}
        </GlassPanel>
      </div>

      {/* Filter chips */}
      <div className="flex gap-1.5 flex-wrap mb-3">
        <span className="text-[10px] text-jarvis-muted self-center mr-1">Filter:</span>
        {ALL_EVENT_TYPES.map(type => (
          <button
            key={type}
            onClick={() => toggleFilter(type)}
            className={clsx(
              'text-[10px] font-mono px-2 py-0.5 rounded border transition-all',
              filterTypes.includes(type)
                ? clsx('border-jarvis-cyan/40 bg-jarvis-cyan/10', EVENT_COLORS[type])
                : 'border-jarvis-border text-jarvis-muted hover:text-jarvis-text'
            )}
          >
            {type}
          </button>
        ))}
        {filterTypes.length > 0 && (
          <button onClick={() => setFilterTypes([])} className="text-[10px] text-jarvis-amber hover:text-jarvis-text ml-1">
            clear filters
          </button>
        )}
      </div>

      {/* Event stream */}
      <GlassPanel className="flex-1 overflow-y-auto rounded-xl min-h-[300px] max-h-[500px]">
        {filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full gap-3 text-jarvis-muted">
            <Terminal size={28} className="opacity-30" />
            <p className="text-sm">No events yet.</p>
            {mockMode && <p className="text-xs opacity-60">Ambient mock events fire every ~8s.</p>}
          </div>
        ) : (
          [...filtered].reverse().map((ev, i) => <EventRow key={`${ev.ts}-${i}`} event={ev} index={i} />)
        )}
      </GlassPanel>
    </div>
  )
}
