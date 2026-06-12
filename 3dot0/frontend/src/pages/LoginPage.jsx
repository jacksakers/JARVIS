import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { login, register } from '../api'
import useStore from '../store'

export default function LoginPage() {
  const [tab, setTab] = useState('login')   // 'login' | 'register'
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm]   = useState('')
  const [error, setError]       = useState('')
  const [loading, setLoading]   = useState(false)
  const { setAuth } = useStore()
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    if (tab === 'register' && password !== confirm) {
      setError('Passwords do not match.')
      return
    }
    if (!username.trim()) {
      setError('Username is required.')
      return
    }
    setLoading(true)
    try {
      const fn = tab === 'login' ? login : register
      const res = await fn(username.trim(), password)
      setAuth(res.user, res.token)
      navigate('/', { replace: true })
    } catch (err) {
      setError(err.message || 'Authentication failed.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-jarvis-bg px-4">
      <div className="w-full max-w-sm">
        {/* Logo / title */}
        <div className="text-center mb-8">
          <div className="text-4xl font-bold text-jarvis-cyan tracking-widest">JARVIS</div>
          <div className="text-jarvis-muted text-sm mt-1">Personal AI Assistant</div>
        </div>

        {/* Card */}
        <div className="bg-jarvis-surface border border-jarvis-border rounded-2xl p-6 shadow-xl">
          {/* Tabs */}
          <div className="flex mb-6 rounded-lg overflow-hidden border border-jarvis-border">
            {['login', 'register'].map(t => (
              <button
                key={t}
                onClick={() => { setTab(t); setError('') }}
                className={`flex-1 py-2 text-sm font-medium transition-colors ${
                  tab === t
                    ? 'bg-jarvis-cyan text-black'
                    : 'text-jarvis-muted hover:text-white'
                }`}
              >
                {t === 'login' ? 'Sign In' : 'Register'}
              </button>
            ))}
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs text-jarvis-muted mb-1">Username</label>
              <input
                type="text"
                autoFocus
                autoComplete="username"
                value={username}
                onChange={e => setUsername(e.target.value)}
                className="w-full bg-jarvis-bg border border-jarvis-border rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-jarvis-cyan"
                placeholder="e.g. jarvis"
              />
            </div>
            <div>
              <label className="block text-xs text-jarvis-muted mb-1">Password</label>
              <input
                type="password"
                autoComplete={tab === 'login' ? 'current-password' : 'new-password'}
                value={password}
                onChange={e => setPassword(e.target.value)}
                className="w-full bg-jarvis-bg border border-jarvis-border rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-jarvis-cyan"
                placeholder={tab === 'login' ? 'Your password (leave blank if none set)' : 'Choose a password'}
              />
            </div>
            {tab === 'register' && (
              <div>
                <label className="block text-xs text-jarvis-muted mb-1">Confirm Password</label>
                <input
                  type="password"
                  autoComplete="new-password"
                  value={confirm}
                  onChange={e => setConfirm(e.target.value)}
                  className="w-full bg-jarvis-bg border border-jarvis-border rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-jarvis-cyan"
                  placeholder="Repeat password"
                />
              </div>
            )}

            {error && (
              <p className="text-red-400 text-xs">{error}</p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2 rounded-lg bg-jarvis-cyan text-black font-semibold text-sm hover:bg-opacity-80 transition-all disabled:opacity-50"
            >
              {loading ? 'Please wait…' : tab === 'login' ? 'Sign In' : 'Create Account'}
            </button>
          </form>

          {tab === 'login' && (
            <p className="text-jarvis-muted text-xs text-center mt-4">
              First time? Use any username with a blank password<br />to log in as the primary user.
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
