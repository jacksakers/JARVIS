import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ListTodo, X, RefreshCw, Clock, Wrench, AlertCircle, CheckCircle2, CircleDot, Loader2, Ban, Trash2, Coins } from 'lucide-react'
import { formatDistanceToNow, format } from 'date-fns'
const parseUTC = s => s ? new Date(s.endsWith('Z') || s.includes('+') ? s : s + 'Z') : null

import { GlassPanel, Button, Badge, StatusDot, EmptyState, Spinner, SectionHeader, IconButton } from '../components/ui'
import useStore from '../store'
import * as API from '../api'
import clsx from 'clsx'

const TABS = ['all', 'queued', 'running', 'done', 'failed']

const STATUS_ICON = {
  queued:  <CircleDot    size={13} className="text-jarvis-amber" />,
  running: <Loader2      size={13} className="text-jarvis-cyan animate-spin" />,
  done:    <CheckCircle2 size={13} className="text-jarvis-green" />,
  failed:  <AlertCircle  size={13} className="text-jarvis-red" />,
}

// Pricing: USD per 1M tokens (input / output). Keep in sync with model_registry.py.
const MODEL_PRICING = {
  "gemini-2.5-flash": {"input": 0.30, "output": 2.50},
  "gemini-2.5-pro":   {"input": 1.25, "output": 10.00},
  "gemini-3-flash-preview": {"input": 0.50, "output": 3.00},
  "gemini-3.1-flash-lite": {"input": 0.25, "output": 1.50},
  "gemini-3.5-flash":      {"input": 1.50, "output": 9.00},
}

function computeCost(modelId, promptTokens, completionTokens, thinkingTokens) {
  const pricing = MODEL_PRICING[modelId]
  if (!pricing) return null
  const inCost  = (promptTokens  / 1_000_000) * pricing.input
  const outCost = ((completionTokens + thinkingTokens) / 1_000_000) * pricing.output
  return inCost + outCost
}

function fmtTokens(n) {
  if (n >= 1000) return (n / 1000).toFixed(1) + 'k'
  return String(n)
}

function fmtCost(usd) {
  if (usd < 0.0001) return '<$0.0001'
  if (usd < 0.01)   return '$' + usd.toFixed(4)
  return '$' + usd.toFixed(3)
}

function TaskRow({ task, onCancel, onRetry }) {
  const [expanded, setExpanded] = useState(false)
  const patchedStatus = useStore(s => s.taskPatches[task.id]?.status ?? task.status)
  const patchedTools  = useStore(s => s.taskPatches[task.id]?.toolCalls ?? [])

  const duration = task.completed_at && task.started_at
    ? ((new Date(task.completed_at) - new Date(task.started_at)) / 1000).toFixed(1) + 's'
    : null

  const hasTokens = patchedStatus === 'done' && task.tokens_prompt > 0
  const estimatedCost = hasTokens
    ? computeCost(task.model_id, task.tokens_prompt, task.tokens_completion, task.tokens_thinking)
    : null

  return (
    <motion.div layout initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
      <GlassPanel className="p-0 overflow-hidden glow-border">
        {/* Header row */}
        <button
          onClick={() => setExpanded(e => !e)}
          className="w-full flex items-start gap-3 p-4 text-left hover:bg-jarvis-surface/30 transition-colors"
        >
          <span className="mt-0.5 shrink-0">{STATUS_ICON[patchedStatus] ?? STATUS_ICON.queued}</span>
          <div className="flex-1 min-w-0">
            <p className="text-sm text-jarvis-text line-clamp-2">{task.prompt}</p>
            <div className="flex items-center gap-3 mt-1 flex-wrap">
              <Badge type={patchedStatus}>{patchedStatus}</Badge>
              {task.routine_id && <span className="text-[10px] text-jarvis-cyan/60 font-mono">routine #{task.routine_id}</span>}
              {duration && <span className="text-[10px] text-jarvis-muted">{duration}</span>}
              {task.created_at && (
                <span className="text-[10px] text-jarvis-muted">
                  {formatDistanceToNow(parseUTC(task.created_at), { addSuffix: true })}
                </span>
              )}
              {hasTokens && (
                <span className="text-[10px] text-jarvis-muted font-mono flex items-center gap-1">
                  <Coins size={9} className="text-jarvis-amber/70" />
                  ↑{fmtTokens(task.tokens_prompt)} ↓{fmtTokens(task.tokens_completion + task.tokens_thinking)}
                  {estimatedCost != null && <span className="text-jarvis-amber/80 ml-0.5">· {fmtCost(estimatedCost)}</span>}
                </span>
              )}
            </div>
            {/* Live tool calls for running tasks */}
            {patchedStatus === 'running' && patchedTools.length > 0 && (
              <div className="flex items-center gap-1.5 mt-1.5 flex-wrap">
                {patchedTools.slice(-3).map((tc, i) => (
                  <span key={i} className="text-[10px] font-mono text-jarvis-cyan/60 bg-jarvis-cyan/5 px-1.5 py-0.5 rounded border border-jarvis-cyan/15">
                    <Wrench size={9} className="inline mr-1" />{tc.name}
                  </span>
                ))}
              </div>
            )}
          </div>
          <div className="flex items-center gap-1 shrink-0">
            {(patchedStatus === 'queued' || patchedStatus === 'running') && <IconButton icon={X} label="Cancel" variant="danger" onClick={e => { e.stopPropagation(); onCancel(task.id) }} size={14} />}
            {patchedStatus === 'failed'  && <IconButton icon={RefreshCw} label="Retry"  variant="cyan"  onClick={e => { e.stopPropagation(); onRetry(task.id) }}  size={14} />}
          </div>
        </button>

        {/* Expanded detail */}
        <AnimatePresence>
          {expanded && (
            <motion.div
              initial={{ height: 0 }} animate={{ height: 'auto' }} exit={{ height: 0 }}
              className="overflow-hidden border-t border-jarvis-border"
            >
              <div className="px-4 py-3 space-y-2 text-xs text-jarvis-muted font-mono">
                <div className="flex gap-4 flex-wrap">
                  {task.created_at  && <span>Created:   {format(new Date(task.created_at), 'MMM d, HH:mm:ss')}</span>}
                  {task.started_at  && <span>Started:   {format(new Date(task.started_at), 'MMM d, HH:mm:ss')}</span>}
                  {task.completed_at && <span>Completed: {format(new Date(task.completed_at), 'MMM d, HH:mm:ss')}</span>}
                </div>
                {task.model_id && (
                  <div className="text-jarvis-cyan/60">Model: {task.model_id}</div>
                )}
                {hasTokens && (
                  <div className="bg-jarvis-surface/40 rounded p-2 border border-jarvis-border space-y-1">
                    <div className="flex items-center gap-1.5 text-jarvis-amber/80 mb-1">
                      <Coins size={10} /> Token usage
                    </div>
                    <div className="flex gap-4 flex-wrap">
                      <span>Prompt:     {task.tokens_prompt.toLocaleString()}</span>
                      <span>Completion: {task.tokens_completion.toLocaleString()}</span>
                      {task.tokens_thinking > 0 && <span>Thinking: {task.tokens_thinking.toLocaleString()}</span>}
                      <span>Total: {(task.tokens_prompt + task.tokens_completion + task.tokens_thinking).toLocaleString()}</span>
                    </div>
                    {estimatedCost != null && (
                      <div className="text-jarvis-amber/80">Est. cost: {fmtCost(estimatedCost)}</div>
                    )}
                    {estimatedCost == null && task.model_id && (
                      <div className="text-jarvis-muted/60">Cost: free (local model)</div>
                    )}
                  </div>
                )}
                {task.error_message && (
                  <div className="text-jarvis-red bg-jarvis-red/5 rounded p-2 border border-jarvis-red/20">
                    {task.error_message}
                  </div>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </GlassPanel>
    </motion.div>
  )
}

export default function TasksPage() {
  const mockMode = useStore(s => s.mockMode)
  const [tasks,   setTasks]   = useState([])
  const [tab,     setTab]     = useState('all')
  const [loading, setLoading] = useState(true)

  const load = async () => {
    setLoading(true)
    const t = await API.getTasks({}, mockMode)
    setTasks(t)
    setLoading(false)
  }
  useEffect(() => { load() }, [mockMode])

  // Re-poll every 5s while any running/queued tasks exist
  useEffect(() => {
    const hasActive = tasks.some(t => ['running', 'queued'].includes(t.status))
    if (!hasActive) return
    const id = setInterval(load, 5000)
    return () => clearInterval(id)
  }, [tasks])

  const cancel = async (id) => {
    await API.cancelTask(id, mockMode)
    setTasks(prev => prev.filter(t => t.id !== id))
  }

  const retry = async (id) => {
    const newTask = await API.retryTask(id, mockMode)
    setTasks(prev => [newTask, ...prev.filter(t => t.id !== id)])
    setTab('queued')
  }

  const bulkCleanup = async () => {
    await API.bulkDeleteTasks('done,failed', mockMode)
    await load()
  }

  const filtered = tab === 'all' ? tasks : tasks.filter(t => t.status === tab)

  const counts = TABS.reduce((acc, s) => {
    acc[s] = s === 'all' ? tasks.length : tasks.filter(t => t.status === s).length
    return acc
  }, {})

  const canCleanup = tasks.some(t => ['done', 'failed'].includes(t.status))

  return (
    <div className="max-w-3xl mx-auto px-4 py-6">
      <SectionHeader
        title="Task Queue"
        subtitle="All background tasks and their current status."
        actions={
          <div className="flex items-center gap-2">
            {canCleanup && (
              <Button variant="ghost" size="sm" onClick={bulkCleanup} title="Delete all done and failed tasks">
                <Trash2 size={14} /> Clean up
              </Button>
            )}
            <Button variant="ghost" size="sm" onClick={load}><RefreshCw size={14} /></Button>
          </div>
        }
      />

      {/* Tabs */}
      <div className="flex gap-1 mb-5 overflow-x-auto pb-1">
        {TABS.map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={clsx(
              'px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap flex items-center gap-1.5 transition-all',
              tab === t
                ? 'bg-jarvis-cyan/15 text-jarvis-cyan border border-jarvis-cyan/30'
                : 'text-jarvis-muted hover:text-jarvis-text border border-jarvis-border'
            )}
          >
            {t}
            {counts[t] > 0 && (
              <span className={clsx('text-[10px] px-1.5 rounded-full', tab === t ? 'bg-jarvis-cyan/20' : 'bg-jarvis-surface')}>
                {counts[t]}
              </span>
            )}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex justify-center py-20"><Spinner size={24} /></div>
      ) : filtered.length === 0 ? (
        <EmptyState icon={ListTodo} title={`No ${tab === 'all' ? '' : tab} tasks`} description="Tasks appear here when you use Chat or run routines." />
      ) : (
        <div className="space-y-2">
          <AnimatePresence mode="popLayout">
            {filtered.map(t => <TaskRow key={t.id} task={t} onCancel={cancel} onRetry={retry} />)}
          </AnimatePresence>
        </div>
      )}
    </div>
  )
}
