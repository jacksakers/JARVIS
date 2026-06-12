import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Zap, Plus, Play, Pause, Trash2, Edit3, RefreshCw,
  Upload, Download, FileJson, Copy, Check, ChevronDown, ChevronRight
} from 'lucide-react'
import { GlassPanel, Button, Badge, StatusDot, Modal, Textarea, Input, Toggle, EmptyState, Spinner, SectionHeader, IconButton } from '../components/ui'
import CronBuilder, { humanReadable } from '../components/CronBuilder'
import useStore from '../store'
import * as API from '../api'
import clsx from 'clsx'

// ── JSON Schema for AI Agent ─────────────────────────────────────────────

const ROUTINE_SCHEMA = {
  $schema: 'jarvis-routine-v1',
  description: 'Schema for JARVIS v3.0 routine. Use this to create a routine JSON that can be imported.',
  type: 'object',
  required: ['name', 'trigger', 'system_prompt'],
  properties: {
    name:          { type: 'string', description: 'Short descriptive name for the routine.' },
    description:   { type: 'string', description: 'What this routine does.' },
    trigger: {
      type: 'object',
      properties: {
        type:  { type: 'string', enum: ['cron', 'manual'], description: "Use 'cron' for scheduled, 'manual' for on-demand only." },
        cron:  { type: 'string', description: 'Standard 5-field cron expression. e.g. "0 6 * * *" = 6 AM daily.' },
      },
      required: ['type'],
    },
    system_prompt: { type: 'string', description: 'The full instructions JARVIS will follow when running this routine.' },
    allowed_skills:{ type: 'array',  items: { type: 'string' }, description: 'Skill names JARVIS can use. Empty array = no tools. To grant all skills, list them all.' },
    active:        { type: 'boolean', default: true },
  },
}

const EXAMPLE_ROUTINE = {
  $schema: 'jarvis-routine-v1',
  name: 'Morning Briefing',
  description: 'Daily 6 AM summary of priorities and reminders.',
  trigger: { type: 'cron', cron: '0 6 * * *' },
  system_prompt: 'You are JARVIS morning briefer. Start with the current time from get_system_time, then search memory for any reminders or priorities the user has saved. Format your response as a clean morning briefing with sections: Time, Priorities, Reminders.',
  allowed_skills: ['get_system_time', 'search_memory'],
  active: true,
}

const PROMPT_TEMPLATES = [
  { label: 'Morning Briefing',     value: 'You are JARVIS morning briefer. Call get_system_time, then search_memory for reminders and priorities. Produce a clean morning briefing: current time, today\'s priorities, reminders.' },
  { label: 'Evening Reflection',   value: 'You are a thoughtful philosophical analyst. Review recent journal entries from memory. Connect recurring themes, gently challenge assumptions, and offer fresh perspectives in a Reflection Report.' },
  { label: 'Hourly Digest',        value: 'You are JARVIS news desk. Call get_system_time. Produce a very brief bullet-point digest. Be concise — maximum 5 bullet points.' },
  { label: 'Weekly Strategy',      value: 'You are JARVIS weekly strategist. Summarise last week\'s progress using search_memory, then propose a focused plan for the week ahead with clear priorities.' },
  { label: 'Task Researcher',      value: 'You are an expert researcher. Thoroughly investigate the given topic, use all available tools, and produce a well-structured Markdown report with sources, pros/cons, and a clear recommendation.' },
  { label: 'Devil\'s Advocate',    value: 'You are a critical thinking assistant. Read the user\'s position carefully, then systematically challenge every assumption. The goal is to stress-test ideas, not to agree.' },
]

// ── RoutineEditor Modal ───────────────────────────────────────────────────

function RoutineEditor({ routine, skills, onSave, onClose }) {
  const [form, setForm] = useState({
    name:               routine?.name               ?? '',
    description:        routine?.description        ?? '',
    trigger_type:       routine?.trigger_type       ?? 'cron',
    trigger_value:      routine?.trigger_value      ?? '0 9 * * *',
    system_prompt:      routine?.system_prompt      ?? '',
    allowed_skill_names:routine?.allowed_skill_names ?? '[]',
    active:             routine?.active              ?? true,
  })
  const [saving, setSaving] = useState(false)
  const [tab, setTab]       = useState('schedule')

  const allowedSkills = (() => { try { return JSON.parse(form.allowed_skill_names) } catch { return [] } })()
  const toggleSkill = (name) => {
    const cur = allowedSkills
    const next = cur.includes(name) ? cur.filter(s => s !== name) : [...cur, name]
    setForm(f => ({ ...f, allowed_skill_names: JSON.stringify(next) }))
  }

  const set = (k) => (v) => setForm(f => ({ ...f, [k]: v }))

  const save = async () => {
    if (!form.name.trim()) return
    setSaving(true)
    try {
      await onSave(form)
      onClose()
    } catch (e) {
      console.error(e)
    } finally {
      setSaving(false)
    }
  }

  const TABS = ['schedule', 'instructions', 'skills', 'advanced']

  return (
    <div className="flex flex-col h-full">
      {/* Tab bar */}
      <div className="flex border-b border-jarvis-border shrink-0 px-5 pt-2">
        {TABS.map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={clsx(
              'px-4 py-2 text-xs font-medium capitalize transition-colors border-b-2 -mb-px',
              tab === t
                ? 'border-jarvis-cyan text-jarvis-cyan'
                : 'border-transparent text-jarvis-muted hover:text-jarvis-text'
            )}
          >
            {t}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto p-5 space-y-5">

        {/* ── Schedule tab ── */}
        {tab === 'schedule' && (
          <>
            <Input label="Name" value={form.name} onChange={e => set('name')(e.target.value)} placeholder="e.g. Morning Briefing" />
            <Input label="Description (optional)" value={form.description} onChange={e => set('description')(e.target.value)} placeholder="What does this routine do?" />

            <div>
              <label className="text-xs font-medium text-jarvis-muted uppercase tracking-wider block mb-3">Trigger type</label>
              <div className="flex gap-2">
                {[['cron', '⏰ Scheduled'], ['manual', '🖱 Manual only']].map(([v, l]) => (
                  <button
                    key={v}
                    type="button"
                    onClick={() => set('trigger_type')(v)}
                    className={clsx(
                      'flex-1 px-4 py-2.5 rounded-lg text-sm border transition-all',
                      form.trigger_type === v
                        ? 'bg-jarvis-cyan/15 border-jarvis-cyan/40 text-jarvis-cyan'
                        : 'border-jarvis-border text-jarvis-muted hover:text-jarvis-text'
                    )}
                  >
                    {l}
                  </button>
                ))}
              </div>
            </div>

            {form.trigger_type === 'cron' && (
              <CronBuilder value={form.trigger_value} onChange={set('trigger_value')} />
            )}
          </>
        )}

        {/* ── Instructions tab ── */}
        {tab === 'instructions' && (
          <>
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-xs font-medium text-jarvis-muted uppercase tracking-wider">System Prompt</label>
                <select
                  onChange={e => { if (e.target.value) set('system_prompt')(e.target.value) }}
                  className="text-xs bg-transparent text-jarvis-cyan border border-jarvis-cyan/20 rounded px-2 py-1 outline-none cursor-pointer"
                  defaultValue=""
                >
                  <option value="" disabled>Use template…</option>
                  {PROMPT_TEMPLATES.map(t => (
                    <option key={t.label} value={t.value}>{t.label}</option>
                  ))}
                </select>
              </div>
              <Textarea
                value={form.system_prompt}
                onChange={e => set('system_prompt')(e.target.value)}
                placeholder="Instructions for JARVIS when this routine runs. Be specific about the output format, tone, and which tools to use."
                className="min-h-[180px] font-mono text-xs leading-relaxed"
              />
            </div>
            <div className="glass rounded-lg p-3 text-xs text-jarvis-muted space-y-1 border-jarvis-cyan/10">
              <p className="text-jarvis-cyan/70 font-medium mb-2">💡 Tips</p>
              <p>• Tell JARVIS which tools to call and in what order.</p>
              <p>• Specify the output format (Markdown headings, bullet points, etc.).</p>
              <p>• Reference allowed skills by name: <code className="text-jarvis-cyan/70">get_system_time</code>, <code className="text-jarvis-cyan/70">search_memory</code>.</p>
            </div>
          </>
        )}

        {/* ── Skills tab ── */}
        {tab === 'skills' && (
          <>
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs text-jarvis-muted">Select which skills this routine can use. <strong className="text-jarvis-amber">Nothing checked = no tools available.</strong></p>
              <div className="flex gap-2">
                <button
                  onClick={() => setForm(f => ({ ...f, allowed_skill_names: JSON.stringify(skills.map(s => s.name)) }))}
                  className="text-[10px] text-jarvis-cyan hover:text-jarvis-cyan-bright border border-jarvis-cyan/20 px-2 py-1 rounded transition-colors"
                >
                  Select all
                </button>
                <button
                  onClick={() => setForm(f => ({ ...f, allowed_skill_names: '[]' }))}
                  className="text-[10px] text-jarvis-muted hover:text-jarvis-text border border-jarvis-border px-2 py-1 rounded transition-colors"
                >
                  Clear
                </button>
              </div>
            </div>
            <div className="space-y-2">
              {skills.map(skill => (
                <label key={skill.name} className="flex items-start gap-3 glass rounded-lg p-3 cursor-pointer hover:border-jarvis-cyan/25 glow-border">
                  <input
                    type="checkbox"
                    checked={allowedSkills.includes(skill.name)}
                    onChange={() => toggleSkill(skill.name)}
                    className="mt-0.5 accent-cyan-400"
                  />
                  <div>
                    <p className="text-sm font-mono text-jarvis-text">{skill.name}</p>
                    <p className="text-xs text-jarvis-muted">{skill.description}</p>
                  </div>
                </label>
              ))}
              {skills.length === 0 && <p className="text-jarvis-muted text-sm">No skills loaded.</p>}
            </div>
            <p className="text-xs text-jarvis-muted">
              {allowedSkills.length === 0 ? '⛔ No skills selected — routine will run without tools' : `✓ ${allowedSkills.length} skill${allowedSkills.length > 1 ? 's' : ''} selected`}
            </p>
          </>
        )}

        {/* ── Advanced tab ── */}
        {tab === 'advanced' && (
          <Toggle
            checked={form.active}
            onChange={set('active')}
            label="Routine is active"
          />
        )}
      </div>

      {/* Footer */}
      <div className="shrink-0 flex items-center justify-end gap-3 px-5 py-4 border-t border-jarvis-border">
        <Button variant="ghost" onClick={onClose}>Cancel</Button>
        <Button variant="solid" onClick={save} disabled={saving || !form.name.trim()}>
          {saving ? <Spinner size={14} /> : null}
          {routine ? 'Save Changes' : 'Create Routine'}
        </Button>
      </div>
    </div>
  )
}

// ── RoutineCard ───────────────────────────────────────────────────────────

function RoutineCard({ routine, onEdit, onToggle, onDelete, onRun }) {
  const [running, setRunning] = useState(false)

  const run = async () => {
    setRunning(true)
    try { await onRun(routine.id) } finally { setTimeout(() => setRunning(false), 4000) }
  }

  return (
    <motion.div layout initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
      <GlassPanel className="p-4 glow-border">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-3 min-w-0 flex-1">
            <StatusDot status={routine.active ? 'active' : 'inactive'} className="mt-1.5 shrink-0" />
            <div className="min-w-0">
              <p className="text-sm font-semibold text-jarvis-text truncate">{routine.name}</p>
              {routine.description && (
                <p className="text-xs text-jarvis-muted mt-0.5 line-clamp-1">{routine.description}</p>
              )}
              <div className="flex items-center gap-2 mt-2 flex-wrap">
                <Badge type={routine.trigger_type}>{routine.trigger_type}</Badge>
                {routine.trigger_type === 'cron' && routine.trigger_value && (
                  <span className="text-[11px] text-jarvis-cyan/80 font-mono">
                    {humanReadable(routine.trigger_value)}
                  </span>
                )}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-1 shrink-0">
            <IconButton icon={running ? Spinner : Play} label="Run now"  variant="cyan"  onClick={run}        size={15} />
            <IconButton icon={Edit3}                    label="Edit"     variant="ghost" onClick={() => onEdit(routine)} size={15} />
            <IconButton icon={routine.active ? Pause : Play} label={routine.active ? 'Pause' : 'Resume'} variant="ghost" onClick={() => onToggle(routine)} size={15} />
            <IconButton icon={Trash2}                   label="Delete"   variant="danger" onClick={() => onDelete(routine.id)} size={15} />
          </div>
        </div>
      </GlassPanel>
    </motion.div>
  )
}

// ── Import / Export modal ─────────────────────────────────────────────────

function ImportExportModal({ open, onClose, onImport, skills }) {
  const [tab, setTab]     = useState('export_schema')
  const [json, setJson]   = useState('')
  const [error, setError] = useState('')
  const [copied, setCopied] = useState(false)

  const schemaStr   = JSON.stringify(ROUTINE_SCHEMA, null, 2)
  const exampleStr  = JSON.stringify(EXAMPLE_ROUTINE, null, 2)

  const copy = (text) => {
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const importJson = () => {
    try {
      const obj = JSON.parse(json)
      const payload = {
        name:               obj.name,
        description:        obj.description ?? '',
        trigger_type:       obj.trigger?.type ?? 'manual',
        trigger_value:      obj.trigger?.cron ?? '',
        system_prompt:      obj.system_prompt ?? '',
        allowed_skill_names:JSON.stringify(obj.allowed_skills ?? []),
        active:             obj.active ?? true,
      }
      onImport(payload)
      onClose()
    } catch (e) {
      setError('Invalid JSON: ' + e.message)
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Import / Export Routines" wide>
      <div className="flex border-b border-jarvis-border px-5 pt-2">
        {[['export_schema', 'AI Schema'], ['export_example', 'Example JSON'], ['import', 'Import']].map(([v, l]) => (
          <button key={v} onClick={() => setTab(v)} className={clsx('px-4 py-2 text-xs font-medium transition-colors border-b-2 -mb-px', tab === v ? 'border-jarvis-cyan text-jarvis-cyan' : 'border-transparent text-jarvis-muted hover:text-jarvis-text')}>
            {l}
          </button>
        ))}
      </div>

      <div className="p-5 space-y-4">
        {tab === 'export_schema' && (
          <>
            <p className="text-xs text-jarvis-muted">Copy this schema and give it to an AI assistant to generate a routine JSON for you.</p>
            <div className="relative">
              <pre className="font-mono text-[11px] text-jarvis-text bg-jarvis-surface/80 rounded-lg p-4 overflow-x-auto border border-jarvis-border max-h-80 overflow-y-auto leading-relaxed">{schemaStr}</pre>
              <button onClick={() => copy(schemaStr)} className="absolute top-2 right-2 p-1.5 glass rounded text-jarvis-muted hover:text-jarvis-cyan">
                {copied ? <Check size={13} /> : <Copy size={13} />}
              </button>
            </div>
          </>
        )}
        {tab === 'export_example' && (
          <>
            <p className="text-xs text-jarvis-muted">A complete example you can give to an AI to show the expected format.</p>
            <div className="relative">
              <pre className="font-mono text-[11px] text-jarvis-text bg-jarvis-surface/80 rounded-lg p-4 overflow-x-auto border border-jarvis-border max-h-80 overflow-y-auto leading-relaxed">{exampleStr}</pre>
              <button onClick={() => copy(exampleStr)} className="absolute top-2 right-2 p-1.5 glass rounded text-jarvis-muted hover:text-jarvis-cyan">
                {copied ? <Check size={13} /> : <Copy size={13} />}
              </button>
            </div>
          </>
        )}
        {tab === 'import' && (
          <>
            <p className="text-xs text-jarvis-muted">Paste a routine JSON (matching the schema above) to import it.</p>
            <Textarea
              value={json}
              onChange={e => { setJson(e.target.value); setError('') }}
              placeholder={exampleStr}
              className="min-h-[200px] font-mono text-xs"
            />
            {error && <p className="text-xs text-jarvis-red">{error}</p>}
            <Button variant="solid" onClick={importJson} disabled={!json.trim()}>
              <Upload size={14} /> Import Routine
            </Button>
          </>
        )}
      </div>
    </Modal>
  )
}

// ── RoutinesPage ──────────────────────────────────────────────────────────

export default function RoutinesPage() {
  const mockMode = useStore(s => s.mockMode)
  const [routines, setRoutines] = useState([])
  const [skills,   setSkills]   = useState([])
  const [loading,  setLoading]  = useState(true)
  const [editing,  setEditing]  = useState(null)       // null = closed, false = new, obj = existing
  const [showImport, setShowImport] = useState(false)

  const load = async () => {
    setLoading(true)
    const [r, s] = await Promise.all([API.getRoutines(mockMode), API.getSkills(mockMode)])
    setRoutines(r)
    setSkills(s)
    setLoading(false)
  }
  useEffect(() => { load() }, [mockMode])

  const saveRoutine = async (form) => {
    if (editing && editing.id) {
      const updated = await API.updateRoutine(editing.id, form, mockMode)
      setRoutines(prev => prev.map(r => r.id === updated.id ? updated : r))
    } else {
      const created = await API.createRoutine(form, mockMode)
      setRoutines(prev => [created, ...prev])
    }
  }

  const toggleRoutine = async (routine) => {
    const updated = await API.updateRoutine(routine.id, { active: !routine.active }, mockMode)
    setRoutines(prev => prev.map(r => r.id === updated.id ? updated : r))
  }

  const deleteRoutine = async (id) => {
    if (!confirm('Delete this routine?')) return
    await API.deleteRoutine(id, mockMode)
    setRoutines(prev => prev.filter(r => r.id !== id))
  }

  const runRoutine = async (id) => {
    await API.runRoutine(id, mockMode)
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-6">
      <SectionHeader
        title="Automations"
        subtitle="Scheduled routines and on-demand tasks. Zero Python required."
        actions={
          <div className="flex gap-2">
            <Button variant="ghost" size="sm" onClick={() => setShowImport(true)}>
              <FileJson size={14} /> Import / Schema
            </Button>
            <Button variant="primary" size="sm" onClick={() => setEditing(false)}>
              <Plus size={14} /> New Routine
            </Button>
          </div>
        }
      />

      {loading ? (
        <div className="flex justify-center py-20"><Spinner size={24} /></div>
      ) : routines.length === 0 ? (
        <EmptyState
          icon={Zap}
          title="No automations yet"
          description="Create a routine to have JARVIS run tasks on a schedule automatically."
          action={<Button variant="primary" onClick={() => setEditing(false)}><Plus size={14} /> Create your first routine</Button>}
        />
      ) : (
        <div className="space-y-3">
          <AnimatePresence mode="popLayout">
            {routines.map(r => (
              <RoutineCard
                key={r.id}
                routine={r}
                onEdit={setEditing}
                onToggle={toggleRoutine}
                onDelete={deleteRoutine}
                onRun={runRoutine}
              />
            ))}
          </AnimatePresence>
        </div>
      )}

      {/* Routine editor modal */}
      <Modal
        open={editing !== null}
        onClose={() => setEditing(null)}
        title={editing?.id ? `Edit: ${editing.name}` : 'New Routine'}
        wide
      >
        {editing !== null && (
          <RoutineEditor
            routine={editing || null}
            skills={skills}
            onSave={saveRoutine}
            onClose={() => setEditing(null)}
          />
        )}
      </Modal>

      {/* Import/Export modal */}
      <ImportExportModal
        open={showImport}
        onClose={() => setShowImport(false)}
        onImport={async (payload) => {
          const created = await API.createRoutine(payload, mockMode)
          setRoutines(prev => [created, ...prev])
        }}
        skills={skills}
      />
    </div>
  )
}
