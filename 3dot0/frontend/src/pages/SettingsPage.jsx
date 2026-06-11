import { useState, useEffect } from 'react'
import { Settings, Save, RotateCcw, ExternalLink, Shield, Cpu, Wifi } from 'lucide-react'
import { GlassPanel, Button, Input, Toggle, SectionHeader } from '../components/ui'
import useStore from '../store'
import { API_BASE, WS_URL } from '../config'
import clsx from 'clsx'

export default function SettingsPage() {
  const mockMode   = useStore(s => s.mockMode)
  const toggleMock = useStore(s => s.toggleMock)
  const wsStatus   = useStore(s => s.wsStatus)

  const [apiUrl,  setApiUrl]  = useState(API_BASE)
  const [wsUrl,   setWsUrl]   = useState(WS_URL)
  const [saved,   setSaved]   = useState(false)
  const [me,      setMe]      = useState(null)

  useEffect(() => {
    if (!mockMode) {
      fetch('/api/v1/users/me').then(r => r.json()).then(setMe).catch(() => {})
    }
  }, [mockMode])

  const save = () => {
    // Settings are read from env at build time; these are just display + future localStorage override
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  return (
    <div className="max-w-2xl mx-auto px-4 py-6 space-y-6">
      <SectionHeader title="Settings" subtitle="Runtime configuration and connections." />

      {/* Mock Mode */}
      <GlassPanel className="p-5">
        <div className="flex items-center gap-3 mb-4">
          <Shield size={16} className="text-jarvis-amber" />
          <h3 className="text-sm font-semibold text-jarvis-text">Mock Mode</h3>
        </div>
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-sm text-jarvis-text">Enable mock mode</p>
            <p className="text-xs text-jarvis-muted mt-0.5">
              Runs the entire UI without a backend. Simulated events, routines, and tasks for testing or demos.
            </p>
          </div>
          <Toggle checked={mockMode} onChange={toggleMock} />
        </div>
        {mockMode && (
          <div className="mt-3 text-xs text-jarvis-amber bg-jarvis-amber/5 border border-jarvis-amber/20 rounded-lg px-3 py-2">
            Mock mode is active — no real API calls are being made.
          </div>
        )}
      </GlassPanel>

      {/* Connection */}
      <GlassPanel className="p-5">
        <div className="flex items-center gap-3 mb-4">
          <Wifi size={16} className="text-jarvis-cyan" />
          <h3 className="text-sm font-semibold text-jarvis-text">Connection</h3>
          <div className={clsx(
            'ml-auto text-xs px-2 py-0.5 rounded-full border',
            wsStatus === 'connected' ? 'text-jarvis-green border-jarvis-green/30 bg-jarvis-green/5' :
            wsStatus === 'mock'      ? 'text-jarvis-amber border-jarvis-amber/30 bg-jarvis-amber/5' :
                                      'text-jarvis-red border-jarvis-red/30 bg-jarvis-red/5'
          )}>
            {wsStatus}
          </div>
        </div>
        <div className="space-y-4">
          <div>
            <label className="text-xs font-medium text-jarvis-muted uppercase tracking-wider block mb-1.5">API Base URL</label>
            <input
              value={apiUrl}
              onChange={e => setApiUrl(e.target.value)}
              className="glass w-full rounded-lg px-3 py-2.5 text-sm text-jarvis-text outline-none focus:border-jarvis-cyan/50 font-mono"
            />
            <p className="text-[10px] text-jarvis-muted mt-1">Set via <code className="text-jarvis-cyan/70">VITE_API_BASE</code> env var at build time.</p>
          </div>
          <div>
            <label className="text-xs font-medium text-jarvis-muted uppercase tracking-wider block mb-1.5">WebSocket URL</label>
            <input
              value={wsUrl}
              onChange={e => setWsUrl(e.target.value)}
              className="glass w-full rounded-lg px-3 py-2.5 text-sm text-jarvis-text outline-none focus:border-jarvis-cyan/50 font-mono"
            />
            <p className="text-[10px] text-jarvis-muted mt-1">Set via <code className="text-jarvis-cyan/70">VITE_WS_URL</code> env var at build time.</p>
          </div>
        </div>
      </GlassPanel>

      {/* User info */}
      {me && !mockMode && (
        <GlassPanel className="p-5">
          <div className="flex items-center gap-3 mb-4">
            <Cpu size={16} className="text-jarvis-cyan" />
            <h3 className="text-sm font-semibold text-jarvis-text">User</h3>
          </div>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-jarvis-muted">Name</span>
              <span className="text-jarvis-text">{me.name}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-jarvis-muted">ID</span>
              <span className="text-jarvis-text font-mono">#{me.id}</span>
            </div>
          </div>
        </GlassPanel>
      )}

      {/* Backend links */}
      <GlassPanel className="p-5">
        <h3 className="text-sm font-semibold text-jarvis-text mb-3">Backend</h3>
        <div className="flex gap-2 flex-wrap">
          <a
            href="/docs"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 text-xs text-jarvis-cyan hover:text-jarvis-cyan-bright border border-jarvis-cyan/20 px-3 py-1.5 rounded-lg hover:border-jarvis-cyan/40 transition-all"
          >
            <ExternalLink size={12} /> Swagger UI (/docs)
          </a>
          <a
            href="/redoc"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 text-xs text-jarvis-cyan hover:text-jarvis-cyan-bright border border-jarvis-cyan/20 px-3 py-1.5 rounded-lg hover:border-jarvis-cyan/40 transition-all"
          >
            <ExternalLink size={12} /> ReDoc (/redoc)
          </a>
        </div>
      </GlassPanel>
    </div>
  )
}
