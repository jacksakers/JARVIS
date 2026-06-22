/**
 * ModelPicker — dropdown to select an LLM for a conversation / routine / dev task.
 * Shows provider badges (Local, Free, Paid) and a description tooltip.
 */
import { useState, useEffect, useRef } from 'react'
import { ChevronDown, Cpu, Cloud, Check, Zap } from 'lucide-react'
import clsx from 'clsx'
import * as API from '../api'

// Static fallback so the picker renders even before the API responds
const DEFAULT_MODELS = [
  { id: 'gemma4:e4b',        name: 'Gemma 4 (Local)',        provider: 'ollama', free: true,  thinking: false, badge: 'Local' },
  { id: 'gemini-2.0-flash',  name: 'Gemini 2.0 Flash',       provider: 'gemini', free: true,  thinking: false, badge: 'Free'  },
  { id: 'gemini-2.5-flash',  name: 'Gemini 2.5 Flash',       provider: 'gemini', free: false, thinking: true,  badge: 'Paid'  },
  { id: 'gemini-2.5-pro',    name: 'Gemini 2.5 Pro',         provider: 'gemini', free: false, thinking: true,  badge: 'Paid'  },
]

const BADGE_STYLES = {
  Local: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
  Free:  'bg-blue-500/15    text-blue-400    border-blue-500/30',
  Paid:  'bg-amber-500/15   text-amber-400   border-amber-500/30',
}

function ModelIcon({ provider }) {
  return provider === 'ollama'
    ? <Cpu size={12} className="text-emerald-400 shrink-0" />
    : <Cloud size={12} className="text-blue-400 shrink-0" />
}

/**
 * @param {string|null}  value       — currently selected model_id (null = config default)
 * @param {function}     onChange    — called with new model_id string or null
 * @param {string}       [placeholder] — text shown when null/"default" is selected
 * @param {string}       [className]
 * @param {boolean}      [compact]   — true = icon-only trigger with tooltip
 * @param {boolean}      [up]        — true = open dropdown upwards
 */
export default function ModelPicker({ value, onChange, placeholder = 'Default model', className, compact = false, up = false }) {
  const [models, setModels]     = useState(DEFAULT_MODELS)
  const [open,   setOpen]       = useState(false)
  const ref                     = useRef(null)

  useEffect(() => {
    API.getModels().then(setModels).catch(() => {})
  }, [])

  // Close on outside click
  useEffect(() => {
    if (!open) return
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  const selected = models.find(m => m.id === value) ?? null

  return (
    <div ref={ref} className={clsx('relative', className)}>
      {/* Trigger */}
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className={clsx(
          'flex items-center gap-1.5 rounded-lg border transition-all text-xs font-medium',
          'border-jarvis-border hover:border-jarvis-cyan/40 bg-jarvis-surface/50 hover:bg-jarvis-surface',
          compact ? 'px-2 py-1.5' : 'px-3 py-2',
        )}
        title={selected ? `${selected.name} — ${selected.description ?? ''}` : placeholder}
      >
        {selected ? (
          <>
            <ModelIcon provider={selected.provider} />
            {!compact && <span className="text-jarvis-text">{selected.name}</span>}
            {selected.thinking && <Zap size={10} className="text-amber-400" title="Thinking model" />}
          </>
        ) : (
          <>
            <Cpu size={12} className="text-jarvis-muted shrink-0" />
            {!compact && <span className="text-jarvis-muted">{placeholder}</span>}
          </>
        )}
        <ChevronDown size={12} className={clsx('text-jarvis-muted transition-transform', open && 'rotate-180')} />
      </button>

      {/* Dropdown */}
      {open && (
        <div className={clsx(
          "absolute z-50 left-0 min-w-[260px] glass rounded-xl border border-jarvis-border shadow-xl overflow-hidden",
          up ? "bottom-full mb-1" : "top-full mt-1"
        )}>
          {/* Default option */}
          <button
            type="button"
            onClick={() => { onChange(null); setOpen(false) }}
            className={clsx(
              'w-full flex items-center gap-2 px-3 py-2.5 text-left text-xs hover:bg-jarvis-surface/60 transition-colors border-b border-jarvis-border',
              !value && 'bg-jarvis-cyan/5',
            )}
          >
            <Cpu size={12} className="text-jarvis-muted shrink-0" />
            <div className="flex-1 min-w-0">
              <div className="text-jarvis-muted font-medium">{placeholder}</div>
              <div className="text-jarvis-muted/50 text-[10px]">Uses your configured default</div>
            </div>
            {!value && <Check size={12} className="text-jarvis-cyan shrink-0" />}
          </button>

          {/* Separator headers */}
          {['ollama', 'gemini'].map(provider => {
            const group = models.filter(m => m.provider === provider)
            if (!group.length) return null
            return (
              <div key={provider}>
                <div className="px-3 py-1.5 text-[10px] font-semibold text-jarvis-muted/50 uppercase tracking-wider bg-jarvis-bg/30">
                  {provider === 'ollama' ? 'Local (Ollama)' : 'Google Gemini'}
                </div>
                {group.map(model => (
                  <button
                    key={model.id}
                    type="button"
                    onClick={() => { onChange(model.id); setOpen(false) }}
                    className={clsx(
                      'w-full flex items-center gap-2 px-3 py-2.5 text-left text-xs hover:bg-jarvis-surface/60 transition-colors',
                      value === model.id && 'bg-jarvis-cyan/5',
                    )}
                  >
                    <ModelIcon provider={model.provider} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5">
                        <span className="text-jarvis-text font-medium">{model.name}</span>
                        {model.thinking && (
                          <Zap size={10} className="text-amber-400" title="Extended thinking" />
                        )}
                      </div>
                      {model.description && (
                        <div className="text-jarvis-muted/60 text-[10px] leading-tight mt-0.5 line-clamp-1">
                          {model.description}
                        </div>
                      )}
                    </div>
                    <span className={clsx(
                      'text-[9px] px-1.5 py-0.5 rounded-full border font-semibold shrink-0',
                      BADGE_STYLES[model.badge] ?? BADGE_STYLES.Free,
                    )}>
                      {model.badge}
                    </span>
                    {value === model.id && <Check size={12} className="text-jarvis-cyan shrink-0" />}
                  </button>
                ))}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
