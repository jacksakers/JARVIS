/**
 * Shared UI primitives: GlassPanel, Button, Badge, Modal, StatusDot, EmptyState
 */
import { motion, AnimatePresence } from 'framer-motion'
import { X } from 'lucide-react'
import clsx from 'clsx'

// ── GlassPanel ────────────────────────────────────────────────────────────

export function GlassPanel({ children, className, hover = false, ...props }) {
  return (
    <div
      className={clsx('glass rounded-xl', hover && 'glow-border cursor-pointer', className)}
      {...props}
    >
      {children}
    </div>
  )
}

// ── Button ────────────────────────────────────────────────────────────────

const btnBase = 'inline-flex items-center gap-2 rounded-lg font-medium text-sm transition-all duration-150 disabled:opacity-40 disabled:cursor-not-allowed select-none'
const btnVariants = {
  primary:  'bg-jarvis-cyan/10 border border-jarvis-cyan/40 text-jarvis-cyan hover:bg-jarvis-cyan/20 hover:border-jarvis-cyan active:scale-95',
  ghost:    'border border-jarvis-border text-jarvis-muted hover:text-jarvis-text hover:border-jarvis-cyan/30 hover:bg-white/5 active:scale-95',
  danger:   'bg-jarvis-red/10 border border-jarvis-red/30 text-jarvis-red hover:bg-jarvis-red/20 active:scale-95',
  success:  'bg-jarvis-green/10 border border-jarvis-green/30 text-jarvis-green hover:bg-jarvis-green/20 active:scale-95',
  amber:    'bg-jarvis-amber/10 border border-jarvis-amber/30 text-jarvis-amber hover:bg-jarvis-amber/20 active:scale-95',
  solid:    'bg-jarvis-cyan text-jarvis-bg font-semibold hover:bg-jarvis-cyan-bright active:scale-95',
}
const btnSizes = {
  xs: 'px-2 py-1 text-xs',
  sm: 'px-3 py-1.5 text-xs',
  md: 'px-4 py-2 text-sm',
  lg: 'px-5 py-2.5 text-base',
}

export function Button({ variant = 'ghost', size = 'md', className, children, ...props }) {
  return (
    <button className={clsx(btnBase, btnVariants[variant], btnSizes[size], className)} {...props}>
      {children}
    </button>
  )
}

// ── IconButton ────────────────────────────────────────────────────────────

export function IconButton({ icon: Icon, label, variant = 'ghost', size = 16, className, ...props }) {
  return (
    <button
      title={label}
      aria-label={label}
      className={clsx(
        'p-2 rounded-lg transition-all duration-150 active:scale-90',
        variant === 'ghost' && 'text-jarvis-muted hover:text-jarvis-text hover:bg-white/5',
        variant === 'danger' && 'text-jarvis-red/70 hover:text-jarvis-red hover:bg-jarvis-red/10',
        variant === 'cyan'  && 'text-jarvis-cyan/70 hover:text-jarvis-cyan hover:bg-jarvis-cyan/10',
        className
      )}
      {...props}
    >
      <Icon size={size} />
    </button>
  )
}

// ── Badge ─────────────────────────────────────────────────────────────────

const badgeMap = {
  briefing:       'bg-jarvis-cyan/10   text-jarvis-cyan   border-jarvis-cyan/25',
  report:         'bg-purple-500/10    text-purple-400    border-purple-400/25',
  reflection:     'bg-jarvis-purple/10 text-jarvis-purple border-jarvis-purple/25',
  journal_analysis:'bg-jarvis-purple/10 text-jarvis-purple border-jarvis-purple/25',
  question:       'bg-jarvis-amber/10  text-jarvis-amber  border-jarvis-amber/25',
  action:         'bg-jarvis-green/10  text-jarvis-green  border-jarvis-green/25',
  error:          'bg-jarvis-red/10    text-jarvis-red    border-jarvis-red/25',
  queued:         'bg-jarvis-muted/10  text-jarvis-muted  border-jarvis-muted/25',
  running:        'bg-jarvis-cyan/10   text-jarvis-cyan   border-jarvis-cyan/25',
  done:           'bg-jarvis-green/10  text-jarvis-green  border-jarvis-green/25',
  failed:         'bg-jarvis-red/10    text-jarvis-red    border-jarvis-red/25',
  active:         'bg-jarvis-green/10  text-jarvis-green  border-jarvis-green/25',
  inactive:       'bg-jarvis-muted/10  text-jarvis-muted  border-jarvis-muted/25',
  cron:           'bg-jarvis-cyan/10   text-jarvis-cyan   border-jarvis-cyan/25',
  manual:         'bg-jarvis-muted/10  text-jarvis-muted  border-jarvis-muted/25',
}

export function Badge({ type, children, className }) {
  return (
    <span className={clsx('inline-flex items-center gap-1 text-[10px] font-mono font-semibold uppercase tracking-wider px-2 py-0.5 rounded border', badgeMap[type] ?? badgeMap.report, className)}>
      {children}
    </span>
  )
}

// ── StatusDot ─────────────────────────────────────────────────────────────

export function StatusDot({ status, className }) {
  const colors = {
    running:  'bg-jarvis-cyan animate-pulse',
    queued:   'bg-jarvis-amber',
    done:     'bg-jarvis-green',
    failed:   'bg-jarvis-red',
    active:   'bg-jarvis-green animate-pulse',
    inactive: 'bg-jarvis-muted',
  }
  return <span className={clsx('inline-block w-2 h-2 rounded-full shrink-0', colors[status] ?? 'bg-jarvis-muted', className)} />
}

// ── Modal ─────────────────────────────────────────────────────────────────

export function Modal({ open, onClose, title, children, wide = false }) {
  // Close on Escape
  if (typeof window !== 'undefined') {
    document.onkeydown = (e) => { if (e.key === 'Escape' && open) onClose?.() }
  }

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50 flex items-end md:items-center justify-center p-0 md:p-4">
          {/* Backdrop */}
          <motion.div
            key="backdrop"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="absolute inset-0 bg-black/70 backdrop-blur-sm"
            onClick={onClose}
          />
          {/* Panel */}
          <motion.div
            key="panel"
            initial={{ opacity: 0, y: 40, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.97 }}
            transition={{ type: 'spring', damping: 26, stiffness: 240 }}
            className={clsx(
              'relative glass rounded-t-2xl md:rounded-2xl w-full flex flex-col max-h-[92vh] md:max-h-[88vh] overflow-hidden',
              wide ? 'md:max-w-3xl' : 'md:max-w-lg'
            )}
          >
            {/* Header */}
            {title && (
              <div className="flex items-center justify-between px-5 py-4 border-b border-jarvis-border shrink-0">
                <h2 className="text-sm font-semibold text-jarvis-cyan-bright tracking-wide">{title}</h2>
                <button onClick={onClose} className="p-1 text-jarvis-muted hover:text-jarvis-text rounded-lg hover:bg-white/5">
                  <X size={16} />
                </button>
              </div>
            )}
            <div className="overflow-y-auto flex-1">{children}</div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  )
}

// ── EmptyState ────────────────────────────────────────────────────────────

export function EmptyState({ icon: Icon, title, description, action }) {
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-20 text-center px-6">
      {Icon && (
        <div className="p-4 rounded-full bg-jarvis-cyan/5 border border-jarvis-border animate-float">
          <Icon size={28} className="text-jarvis-cyan/50" />
        </div>
      )}
      <div>
        <p className="text-jarvis-text font-medium">{title}</p>
        {description && <p className="text-jarvis-muted text-sm mt-1">{description}</p>}
      </div>
      {action}
    </div>
  )
}

// ── Spinner ───────────────────────────────────────────────────────────────

export function Spinner({ size = 16 }) {
  return (
    <svg
      width={size} height={size}
      viewBox="0 0 24 24" fill="none"
      className="animate-spin text-jarvis-cyan"
    >
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeOpacity="0.25" />
      <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  )
}

// ── SectionHeader ─────────────────────────────────────────────────────────


export function SectionHeader({ title, subtitle, actions }) {

  return (

    <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4 mb-4">

      <div>

        <h2 className="text-base font-semibold text-jarvis-text">{title}</h2>

        {subtitle && <p className="text-xs text-jarvis-muted mt-0.5">{subtitle}</p>}

      </div>

      {actions && <div className="flex items-center gap-2 flex-wrap sm:justify-end">{actions}</div>}

    </div>

  )

}

// ── Textarea ──────────────────────────────────────────────────────────────

export function Textarea({ label, hint, className, ...props }) {
  return (
    <div className="flex flex-col gap-1.5">
      {label && <label className="text-xs font-medium text-jarvis-muted uppercase tracking-wider">{label}</label>}
      <textarea
        className={clsx(
          'glass rounded-lg px-3 py-2.5 text-sm text-jarvis-text placeholder:text-jarvis-muted/60 outline-none focus:border-jarvis-cyan/50 focus:ring-0 resize-none transition-colors min-h-[80px]',
          className
        )}
        {...props}
      />
      {hint && <p className="text-[11px] text-jarvis-muted">{hint}</p>}
    </div>
  )
}

// ── Input ─────────────────────────────────────────────────────────────────

export function Input({ label, hint, className, ...props }) {
  return (
    <div className="flex flex-col gap-1.5">
      {label && <label className="text-xs font-medium text-jarvis-muted uppercase tracking-wider">{label}</label>}
      <input
        className={clsx(
          'glass rounded-lg px-3 py-2.5 text-sm text-jarvis-text placeholder:text-jarvis-muted/60 outline-none focus:border-jarvis-cyan/50 transition-colors',
          className
        )}
        {...props}
      />
      {hint && <p className="text-[11px] text-jarvis-muted">{hint}</p>}
    </div>
  )
}

// ── Toggle ────────────────────────────────────────────────────────────────

export function Toggle({ checked, onChange, label }) {
  return (
    <label className="flex items-center gap-3 cursor-pointer group">
      <div className="relative">
        <input type="checkbox" className="sr-only" checked={checked} onChange={e => onChange(e.target.checked)} />
        <div className={clsx('w-10 h-5 rounded-full transition-colors', checked ? 'bg-jarvis-cyan' : 'bg-jarvis-dim')} />
        <div className={clsx('absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white transition-transform', checked ? 'translate-x-5' : 'translate-x-0')} />
      </div>
      {label && <span className="text-sm text-jarvis-text">{label}</span>}
    </label>
  )
}
