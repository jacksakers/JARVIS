import { useState, useEffect } from 'react'
import { Settings, Save, ExternalLink, Shield, Cpu, Wifi, User, Lock, LogOut, Users } from 'lucide-react'
import { GlassPanel, Button, Toggle, SectionHeader, Spinner } from '../components/ui'
import useStore from '../store'
import { API_BASE, WS_URL } from '../config'
import * as API from '../api'
import clsx from 'clsx'

export default function SettingsPage() {
  const mockMode        = useStore(s => s.mockMode)
  const toggleMock      = useStore(s => s.toggleMock)
  const wsStatus        = useStore(s => s.wsStatus)
  const authToken       = useStore(s => s.authToken)
  const currentUser     = useStore(s => s.currentUser)
  const updateCurrentUser = useStore(s => s.updateCurrentUser)
  const clearAuth       = useStore(s => s.clearAuth)

  // Profile form
  const [name,       setName]       = useState(currentUser?.name ?? '')
  const [bio,        setBio]        = useState(currentUser?.bio ?? '')
  const [password,   setPassword]   = useState('')
  const [pwConfirm,  setPwConfirm]  = useState('')
  const [savingProfile, setSavingProfile] = useState(false)
  const [profileMsg, setProfileMsg] = useState('')

  // Preferences JSON (parsed from currentUser.preferences)
  const [timezone, setTimezone] = useState(() => {
    try { return JSON.parse(currentUser?.preferences || '{}').timezone ?? 'America/New_York' }
    catch { return 'America/New_York' }
  })
  const [savingPrefs, setSavingPrefs] = useState(false)

  // All users list
  const [users, setUsers] = useState([])
  useEffect(() => {
    if (!mockMode) API.getUsers(mockMode).then(setUsers).catch(() => {})
  }, [mockMode])

  const saveProfile = async () => {
    if (password && password !== pwConfirm) { setProfileMsg('Passwords do not match.'); return }
    setSavingProfile(true)
    setProfileMsg('')
    try {
      const payload = { name, bio }
      if (password) payload.password = password
      const updated = authToken
        ? await API.updateAuthMe(authToken, payload)
        : await API.updateMe(payload, mockMode)
      updateCurrentUser(updated)
      setPassword(''); setPwConfirm('')
      setProfileMsg('Saved!')
      setTimeout(() => setProfileMsg(''), 2500)
    } catch (err) {
      setProfileMsg(err.message || 'Failed to save.')
    } finally {
      setSavingProfile(false)
    }
  }

  const savePrefs = async () => {
    setSavingPrefs(true)
    try {
      let existingPrefs = {}
      try { existingPrefs = JSON.parse(currentUser?.preferences || '{}') } catch {}
      const newPrefs = { ...existingPrefs, timezone }
      const payload = { preferences: JSON.stringify(newPrefs) }
      const updated = authToken
        ? await API.updateAuthMe(authToken, payload)
        : await API.updateMe(payload, mockMode)
      updateCurrentUser(updated)
    } catch (err) { console.error(err) }
    finally { setSavingPrefs(false) }
  }

  const handleLogout = async () => {
    if (authToken) {
      try { await API.logoutAuth(authToken) } catch {}
    }
    clearAuth()
    window.location.href = '/login'
  }

  return (
    <div className="max-w-2xl mx-auto px-4 py-6 space-y-6">
      <SectionHeader title="Settings" subtitle="Account, preferences, and connections." />

      {/* Profile */}
      <GlassPanel className="p-5">
        <div className="flex items-center gap-3 mb-4">
          <User size={16} className="text-jarvis-cyan" />
          <h3 className="text-sm font-semibold text-jarvis-text">Profile</h3>
          {currentUser && (
            <span className="ml-auto text-xs text-jarvis-muted">#{currentUser.id} · {currentUser.is_primary ? 'Primary' : 'User'}</span>
          )}
        </div>
        <div className="space-y-3">
          <div>
            <label className="text-xs text-jarvis-muted block mb-1">Display Name</label>
            <input
              value={name}
              onChange={e => setName(e.target.value)}
              className="glass w-full rounded-lg px-3 py-2 text-sm text-jarvis-text outline-none focus:border-jarvis-cyan/50"
            />
          </div>
          <div>
            <label className="text-xs text-jarvis-muted block mb-1">Bio <span className="text-jarvis-muted/50">(JARVIS uses this for context)</span></label>
            <textarea
              value={bio}
              onChange={e => setBio(e.target.value)}
              rows={3}
              placeholder="Tell JARVIS about yourself: role, interests, how you like responses formatted, etc."
              className="glass w-full rounded-lg px-3 py-2 text-sm text-jarvis-text outline-none focus:border-jarvis-cyan/50 resize-none"
            />
          </div>
        </div>
        <div className="mt-4 border-t border-jarvis-border pt-4">
          <div className="flex items-center gap-3 mb-3">
            <Lock size={13} className="text-jarvis-muted" />
            <span className="text-xs text-jarvis-muted">Change Password (leave blank to keep current)</span>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-jarvis-muted block mb-1">New Password</label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                className="glass w-full rounded-lg px-3 py-2 text-sm text-jarvis-text outline-none focus:border-jarvis-cyan/50"
              />
            </div>
            <div>
              <label className="text-xs text-jarvis-muted block mb-1">Confirm</label>
              <input
                type="password"
                value={pwConfirm}
                onChange={e => setPwConfirm(e.target.value)}
                className="glass w-full rounded-lg px-3 py-2 text-sm text-jarvis-text outline-none focus:border-jarvis-cyan/50"
              />
            </div>
          </div>
        </div>
        <div className="flex items-center justify-between mt-4">
          {profileMsg && (
            <span className={clsx('text-xs', profileMsg === 'Saved!' ? 'text-green-400' : 'text-red-400')}>
              {profileMsg}
            </span>
          )}
          <div className="ml-auto flex gap-2">
            <Button variant="ghost" size="sm" onClick={handleLogout}>
              <LogOut size={13} /> Sign out
            </Button>
            <Button variant="solid" size="sm" onClick={saveProfile} disabled={savingProfile}>
              {savingProfile ? <Spinner size={12} /> : <Save size={13} />} Save Profile
            </Button>
          </div>
        </div>
      </GlassPanel>

      {/* Preferences */}
      <GlassPanel className="p-5">
        <div className="flex items-center gap-3 mb-4">
          <Cpu size={16} className="text-jarvis-cyan" />
          <h3 className="text-sm font-semibold text-jarvis-text">Preferences</h3>
        </div>
        <div className="space-y-3">
          <div>
            <label className="text-xs text-jarvis-muted block mb-1">Timezone</label>
            <input
              value={timezone}
              onChange={e => setTimezone(e.target.value)}
              placeholder="e.g. America/New_York, Europe/London"
              className="glass w-full rounded-lg px-3 py-2 text-sm text-jarvis-text font-mono outline-none focus:border-jarvis-cyan/50"
            />
            <p className="text-[10px] text-jarvis-muted mt-1">Used for scheduling reminders and time-aware tasks.</p>
          </div>
        </div>
        <div className="flex justify-end mt-4">
          <Button variant="solid" size="sm" onClick={savePrefs} disabled={savingPrefs}>
            {savingPrefs ? <Spinner size={12} /> : <Save size={13} />} Save Preferences
          </Button>
        </div>
      </GlassPanel>

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
              Runs the UI without a backend. Simulated events for testing or demos.
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
            wsStatus === 'connected' ? 'text-green-400 border-green-400/30 bg-green-400/5' :
            wsStatus === 'mock'      ? 'text-yellow-400 border-yellow-400/30 bg-yellow-400/5' :
                                      'text-red-400 border-red-400/30 bg-red-400/5'
          )}>
            {wsStatus}
          </div>
        </div>
        <div className="space-y-1 text-xs font-mono text-jarvis-muted">
          <div>API: <span className="text-jarvis-text">{API_BASE || '(same origin)'}</span></div>
          <div>WS: <span className="text-jarvis-text">{WS_URL}</span></div>
          <p className="text-[10px] mt-2">Configure via <code className="text-jarvis-cyan/70">VITE_API_BASE</code> / <code className="text-jarvis-cyan/70">VITE_WS_URL</code> env vars at build time.</p>
        </div>
      </GlassPanel>

      {/* All users */}
      {users.length > 1 && (
        <GlassPanel className="p-5">
          <div className="flex items-center gap-3 mb-4">
            <Users size={16} className="text-jarvis-cyan" />
            <h3 className="text-sm font-semibold text-jarvis-text">Users</h3>
          </div>
          <div className="space-y-2">
            {users.map(u => (
              <div key={u.id} className="flex items-center justify-between py-1.5 border-b border-jarvis-border last:border-0">
                <div>
                  <span className="text-sm text-jarvis-text">{u.name}</span>
                  {u.is_primary && <span className="ml-2 text-[10px] text-jarvis-cyan border border-jarvis-cyan/20 px-1.5 rounded">primary</span>}
                </div>
                <span className="text-xs text-jarvis-muted">{u.has_password ? '🔒' : 'no password'}</span>
              </div>
            ))}
          </div>
        </GlassPanel>
      )}

      {/* Backend links */}
      <GlassPanel className="p-5">
        <h3 className="text-sm font-semibold text-jarvis-text mb-3">Backend API</h3>
        <div className="flex gap-2 flex-wrap">
          <a
            href="/docs"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 text-xs text-jarvis-cyan border border-jarvis-cyan/20 px-3 py-1.5 rounded-lg hover:border-jarvis-cyan/40 transition-all"
          >
            <ExternalLink size={12} /> Swagger UI
          </a>
          <a
            href="/redoc"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 text-xs text-jarvis-cyan border border-jarvis-cyan/20 px-3 py-1.5 rounded-lg hover:border-jarvis-cyan/40 transition-all"
          >
            <ExternalLink size={12} /> ReDoc
          </a>
        </div>
      </GlassPanel>
    </div>
  )
}
