/**
 * CronBuilder — visual cron expression editor.
 * No manual typing required (unless the user wants "Custom" mode).
 */
import { useState, useEffect } from 'react'
import { Clock, Info } from 'lucide-react'
import { Input, Toggle } from './ui'
import clsx from 'clsx'

// ── Cron math ─────────────────────────────────────────────────────────────

const DAYS = [
  { value: '0', label: 'Sun' },
  { value: '1', label: 'Mon' },
  { value: '2', label: 'Tue' },
  { value: '3', label: 'Wed' },
  { value: '4', label: 'Thu' },
  { value: '5', label: 'Fri' },
  { value: '6', label: 'Sat' },
]

export const FREQ_OPTIONS = [
  { value: 'every_minute', label: 'Every minute',  icon: '⚡' },
  { value: 'every_hour',   label: 'Every hour',    icon: '⏱' },
  { value: 'every_n_hours',label: 'Every N hours', icon: '🔄' },
  { value: 'daily',        label: 'Daily',         icon: '☀️' },
  { value: 'weekdays',     label: 'Weekdays',      icon: '🗓' },
  { value: 'weekly',       label: 'Weekly',        icon: '📅' },
  { value: 'monthly',      label: 'Monthly',       icon: '🗃' },
  { value: 'custom',       label: 'Custom cron',   icon: '⚙️' },
]

function buildCron(freq, time, days, nHours, dom) {
  const [h, m] = (time || '09:00').split(':').map(Number)
  switch (freq) {
    case 'every_minute':  return '* * * * *'
    case 'every_hour':    return '0 * * * *'
    case 'every_n_hours': return `0 */${nHours || 2} * * *`
    case 'daily':         return `${m} ${h} * * *`
    case 'weekdays':      return `${m} ${h} * * 1-5`
    case 'weekly': {
      const ds = days.length ? days.join(',') : '1'
      return `${m} ${h} * * ${ds}`
    }
    case 'monthly':       return `${m} ${h} ${dom || 1} * *`
    default:              return ''
  }
}

function parseCron(cron) {
  if (!cron) return { freq: 'daily', time: '09:00', days: ['1'], nHours: 2, dom: 1 }
  const p = cron.trim().split(/\s+/)
  if (p.length !== 5) return { freq: 'custom', time: '09:00', days: ['1'], nHours: 2, dom: 1 }
  const [min, hour, dom, , dow] = p

  if (cron === '* * * * *') return { freq: 'every_minute', time: '09:00', days: ['1'], nHours: 2, dom: 1 }
  if (cron === '0 * * * *') return { freq: 'every_hour',   time: '09:00', days: ['1'], nHours: 2, dom: 1 }

  if (min === '0' && hour.startsWith('*/') && dom === '*')
    return { freq: 'every_n_hours', time: '09:00', nHours: parseInt(hour.slice(2)) || 2, days: ['1'], dom: 1 }

  const time = `${hour.padStart(2,'0')}:${min.padStart(2,'0')}`

  if (dom === '*' && dow === '*')        return { freq: 'daily',    time, days: ['1'], nHours: 2, dom: 1 }
  if (dom === '*' && dow === '1-5')      return { freq: 'weekdays', time, days: ['1'], nHours: 2, dom: 1 }
  if (dom === '*' && /^[\d,]+$/.test(dow)) return { freq: 'weekly', time, days: dow.split(','), nHours: 2, dom: 1 }
  if (/^\d+$/.test(dom) && dow === '*') return { freq: 'monthly', time, days: ['1'], nHours: 2, dom: parseInt(dom) }

  return { freq: 'custom', time, days: ['1'], nHours: 2, dom: 1 }
}

function humanReadable(cron) {
  if (!cron) return '—'
  const { freq, time, days, nHours, dom } = parseCron(cron)
  const dayNames = days.map(d => DAYS.find(x => x.value === d)?.label ?? d).join(', ')
  switch (freq) {
    case 'every_minute':  return 'Every minute'
    case 'every_hour':    return 'Every hour'
    case 'every_n_hours': return `Every ${nHours} hours`
    case 'daily':         return `Every day at ${time}`
    case 'weekdays':      return `Weekdays at ${time}`
    case 'weekly':        return `Every ${dayNames} at ${time}`
    case 'monthly':       return `Monthly on the ${dom}${['th','st','nd','rd'][dom] ?? 'th'} at ${time}`
    default:              return cron
  }
}

// ── CronBuilder component ─────────────────────────────────────────────────

export default function CronBuilder({ value, onChange }) {
  const parsed   = parseCron(value)
  const [freq,   setFreq]   = useState(parsed.freq)
  const [time,   setTime]   = useState(parsed.time)
  const [days,   setDays]   = useState(parsed.days)
  const [nHours, setNHours] = useState(parsed.nHours)
  const [dom,    setDom]    = useState(parsed.dom)
  const [custom, setCustom] = useState(value || '')
  const [showRaw,setShowRaw]= useState(false)

  // When any control changes, recompute and bubble up
  useEffect(() => {
    const cron = freq === 'custom' ? custom : buildCron(freq, time, days, nHours, dom)
    onChange?.(cron)
  }, [freq, time, days, nHours, dom, custom])

  const currentCron = freq === 'custom' ? custom : buildCron(freq, time, days, nHours, dom)

  const toggleDay = (d) => setDays(prev => prev.includes(d) ? prev.filter(x => x !== d) : [...prev, d])

  return (
    <div className="space-y-4">
      {/* Frequency selector */}
      <div>
        <label className="text-xs font-medium text-jarvis-muted uppercase tracking-wider block mb-2">Frequency</label>
        <div className="grid grid-cols-2 gap-1.5 sm:grid-cols-4">
          {FREQ_OPTIONS.map(opt => (
            <button
              key={opt.value}
              type="button"
              onClick={() => setFreq(opt.value)}
              className={clsx(
                'flex items-center gap-2 px-3 py-2 rounded-lg text-xs border transition-all text-left',
                freq === opt.value
                  ? 'bg-jarvis-cyan/15 border-jarvis-cyan/40 text-jarvis-cyan'
                  : 'border-jarvis-border text-jarvis-muted hover:border-jarvis-cyan/25 hover:text-jarvis-text'
              )}
            >
              <span>{opt.icon}</span>
              <span>{opt.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Every N hours input */}
      {freq === 'every_n_hours' && (
        <div>
          <label className="text-xs font-medium text-jarvis-muted uppercase tracking-wider block mb-2">Interval (hours)</label>
          <div className="flex items-center gap-2">
            {[2, 3, 4, 6, 8, 12].map(n => (
              <button
                key={n}
                type="button"
                onClick={() => setNHours(n)}
                className={clsx(
                  'px-3 py-1.5 rounded-lg text-xs border transition-all',
                  nHours === n
                    ? 'bg-jarvis-cyan/15 border-jarvis-cyan/40 text-jarvis-cyan'
                    : 'border-jarvis-border text-jarvis-muted hover:text-jarvis-text'
                )}
              >
                {n}h
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Time picker */}
      {['daily', 'weekdays', 'weekly', 'monthly'].includes(freq) && (
        <div>
          <label className="text-xs font-medium text-jarvis-muted uppercase tracking-wider block mb-2">
            <Clock size={11} className="inline mr-1" />Time
          </label>
          <input
            type="time"
            value={time}
            onChange={e => setTime(e.target.value)}
            className="glass rounded-lg px-3 py-2.5 text-sm text-jarvis-text outline-none focus:border-jarvis-cyan/50 font-mono"
          />
        </div>
      )}

      {/* Day selector for weekly */}
      {freq === 'weekly' && (
        <div>
          <label className="text-xs font-medium text-jarvis-muted uppercase tracking-wider block mb-2">Days</label>
          <div className="flex gap-1.5">
            {DAYS.map(d => (
              <button
                key={d.value}
                type="button"
                onClick={() => toggleDay(d.value)}
                className={clsx(
                  'w-9 h-9 rounded-lg text-xs border transition-all',
                  days.includes(d.value)
                    ? 'bg-jarvis-cyan/15 border-jarvis-cyan/40 text-jarvis-cyan font-semibold'
                    : 'border-jarvis-border text-jarvis-muted hover:text-jarvis-text'
                )}
              >
                {d.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Day of month for monthly */}
      {freq === 'monthly' && (
        <div>
          <label className="text-xs font-medium text-jarvis-muted uppercase tracking-wider block mb-2">Day of month</label>
          <div className="flex flex-wrap gap-1">
            {Array.from({ length: 28 }, (_, i) => i + 1).map(d => (
              <button
                key={d}
                type="button"
                onClick={() => setDom(d)}
                className={clsx(
                  'w-8 h-8 rounded text-xs border transition-all',
                  dom === d
                    ? 'bg-jarvis-cyan/15 border-jarvis-cyan/40 text-jarvis-cyan font-semibold'
                    : 'border-jarvis-border text-jarvis-muted hover:text-jarvis-text'
                )}
              >
                {d}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Custom cron input */}
      {freq === 'custom' && (
        <Input
          label="Cron expression"
          value={custom}
          onChange={e => setCustom(e.target.value)}
          placeholder="* * * * * (min hr day month weekday)"
          className="font-mono"
          hint="Five fields: minute hour day-of-month month day-of-week"
        />
      )}

      {/* Human-readable preview */}
      <div className="flex items-center justify-between">
        <div className="glass rounded-lg px-3 py-2 flex-1 mr-2">
          <p className="text-xs text-jarvis-muted mb-0.5">Schedule</p>
          <p className="text-sm text-jarvis-cyan font-medium">{humanReadable(currentCron)}</p>
        </div>
        <button
          type="button"
          onClick={() => setShowRaw(s => !s)}
          className="text-[10px] text-jarvis-muted hover:text-jarvis-text font-mono px-2 py-1 rounded border border-jarvis-border"
        >
          {showRaw ? 'Hide' : 'Raw'}
        </button>
      </div>
      {showRaw && (
        <div className="font-mono text-xs text-jarvis-muted bg-jarvis-surface/50 rounded px-3 py-2 border border-jarvis-border">
          {currentCron || '—'}
        </div>
      )}
    </div>
  )
}

export { humanReadable, parseCron, buildCron }
