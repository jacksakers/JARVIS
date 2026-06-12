import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { BookOpen, Plus, Trash2, RefreshCw, Settings2, ChevronDown, ChevronUp, Eye, EyeOff, Edit3, Unlock } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import { GlassPanel, Button, Badge, EmptyState, Spinner, SectionHeader, Textarea, Toggle } from '../components/ui'
import useStore from '../store'
import * as API from '../api'
import clsx from 'clsx'

// ── EntrySettings (inline expandable panel) ──────────────────────────────

function EntrySettings({ entry, onChange, onClose }) {
  const [form, setForm] = useState({
    title:        entry.title        ?? '',
    llm_readable: entry.llm_readable ?? true,
    llm_editable: entry.llm_editable ?? false,
  })
  const [saving, setSaving] = useState(false)

  const save = async () => {
    setSaving(true)
    try {
      const updated = await API.updateJournal(entry.id, form)
      onChange(updated)
      onClose()
    } finally {
      setSaving(false)
    }
  }

  return (
    <motion.div
      initial={{ height: 0, opacity: 0 }}
      animate={{ height: 'auto', opacity: 1 }}
      exit={{ height: 0, opacity: 0 }}
      className="overflow-hidden border-t border-jarvis-border"
    >
      <div className="px-4 py-3 space-y-3 bg-jarvis-surface/30">
        <div>
          <label className="text-[10px] font-medium text-jarvis-muted uppercase tracking-wider block mb-1">Title (optional)</label>
          <input
            value={form.title}
            onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
            placeholder="e.g. Shopping List, Project Ideas…"
            className="glass w-full rounded-lg px-3 py-2 text-sm text-jarvis-text outline-none focus:border-jarvis-cyan/50"
          />
        </div>
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-jarvis-text flex items-center gap-1.5"><Eye size={13} className="text-jarvis-cyan" /> AI can read</p>
              <p className="text-[10px] text-jarvis-muted">Allow routines to read this entry for analysis and context.</p>
            </div>
            <Toggle checked={form.llm_readable} onChange={v => setForm(f => ({ ...f, llm_readable: v }))} />
          </div>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-jarvis-text flex items-center gap-1.5"><Edit3 size={13} className="text-jarvis-amber" /> AI can edit</p>
              <p className="text-[10px] text-jarvis-muted">Allow JARVIS to update this entry (e.g. shopping lists, living docs).</p>
            </div>
            <Toggle checked={form.llm_editable} onChange={v => setForm(f => ({ ...f, llm_editable: v }))} />
          </div>
        </div>
        <div className="flex justify-end gap-2">
          <Button variant="ghost" size="sm" onClick={onClose}>Cancel</Button>
          <Button variant="solid" size="sm" onClick={save} disabled={saving}>{saving ? <Spinner size={12} /> : null} Save</Button>
        </div>
      </div>
    </motion.div>
  )
}

// ── JournalEntryCard ──────────────────────────────────────────────────────

function JournalEntryCard({ entry, onDelete, onChange }) {
  const [expanded,     setExpanded]     = useState(false)
  const [showSettings, setShowSettings] = useState(false)
  const [editMode,     setEditMode]     = useState(false)
  const [editContent,  setEditContent]  = useState(entry.content)
  const [saving,       setSaving]       = useState(false)

  const saveEdit = async () => {
    if (editContent.trim() === entry.content) { setEditMode(false); return }
    setSaving(true)
    try {
      const updated = await API.updateJournal(entry.id, { content: editContent.trim() })
      onChange(updated)
      setEditMode(false)
    } finally {
      setSaving(false)
    }
  }

  const flags = []
  if (!entry.llm_readable) flags.push({ icon: EyeOff,  label: 'Private',  color: 'text-jarvis-muted' })
  if (entry.llm_editable)  flags.push({ icon: Unlock,  label: 'Editable', color: 'text-jarvis-amber' })

  return (
    <motion.div layout initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
      <GlassPanel className="p-0 overflow-hidden glow-border group">
        <div className="flex items-start gap-3 p-4">
          <button onClick={() => setExpanded(e => !e)} className="mt-0.5 shrink-0 text-jarvis-muted hover:text-jarvis-text">
            {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>
          <div className="flex-1 min-w-0">
            {entry.title && <p className="text-xs font-semibold text-jarvis-cyan font-mono mb-1">{entry.title}</p>}
            {!expanded ? (
              <p className="text-sm text-jarvis-text line-clamp-2 leading-relaxed">{entry.content}</p>
            ) : editMode ? (
              <div className="space-y-2">
                <textarea
                  value={editContent}
                  onChange={e => setEditContent(e.target.value)}
                  className="glass w-full rounded-lg px-3 py-2 text-sm text-jarvis-text outline-none focus:border-jarvis-cyan/50 min-h-[80px] resize-y"
                  autoFocus
                />
                <div className="flex gap-2">
                  <Button variant="solid" size="sm" onClick={saveEdit} disabled={saving}>{saving ? <Spinner size={12} /> : null} Save</Button>
                  <Button variant="ghost" size="sm" onClick={() => { setEditMode(false); setEditContent(entry.content) }}>Cancel</Button>
                </div>
              </div>
            ) : (
              <p className="text-sm text-jarvis-text whitespace-pre-wrap leading-relaxed">{entry.content}</p>
            )}
            <div className="flex items-center gap-2 mt-2 flex-wrap">
              <span className="text-[10px] text-jarvis-muted">
                {entry.created_at ? formatDistanceToNow(new Date(entry.created_at), { addSuffix: true }) : ''}
              </span>
              {entry.updated_at && entry.updated_at !== entry.created_at && (
                <span className="text-[10px] text-jarvis-muted/60">· edited</span>
              )}
              {entry.processed && <Badge type="done" className="text-[10px]">analysed</Badge>}
              {flags.map(({ icon: Icon, label, color }) => (
                <span key={label} className={clsx('flex items-center gap-0.5 text-[10px]', color)}><Icon size={10} />{label}</span>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-1 shrink-0">
            {expanded && !editMode && (
              <button onClick={() => setEditMode(true)} className="p-1 text-jarvis-muted hover:text-jarvis-cyan opacity-0 group-hover:opacity-100 transition-opacity" title="Edit content">
                <Edit3 size={13} />
              </button>
            )}
            <button
              onClick={() => setShowSettings(s => !s)}
              className={clsx('p-1 transition-opacity', showSettings ? 'text-jarvis-cyan' : 'text-jarvis-muted hover:text-jarvis-text opacity-0 group-hover:opacity-100')}
              title="Settings"
            >
              <Settings2 size={13} />
            </button>
            <button onClick={() => onDelete(entry.id)} className="p-1 text-jarvis-muted hover:text-jarvis-red opacity-0 group-hover:opacity-100 transition-opacity" title="Delete">
              <Trash2 size={13} />
            </button>
          </div>
        </div>
        <AnimatePresence>
          {showSettings && <EntrySettings entry={entry} onChange={onChange} onClose={() => setShowSettings(false)} />}
        </AnimatePresence>
      </GlassPanel>
    </motion.div>
  )
}

export default function JournalPage() {
  const mockMode = useStore(s => s.mockMode)
  const [entries,  setEntries]  = useState([])
  const [loading,  setLoading]  = useState(true)
  const [input,    setInput]    = useState('')
  const [title,    setTitle]    = useState('')
  const [llmRead,  setLlmRead]  = useState(true)
  const [llmEdit,  setLlmEdit]  = useState(false)
  const [showOpts, setShowOpts] = useState(false)
  const [saving,   setSaving]   = useState(false)
  const inputRef = useRef(null)

  const load = async () => {
    setLoading(true)
    const data = await API.getJournal({}, mockMode)
    setEntries(data)
    setLoading(false)
  }
  useEffect(() => { load() }, [mockMode])

  const save = async () => {
    const text = input.trim()
    if (!text || saving) return
    setSaving(true)
    try {
      const entry = await API.createJournal(
        { content: text, title: title.trim(), llm_readable: llmRead, llm_editable: llmEdit },
        mockMode
      )
      setEntries(prev => [entry, ...prev])
      setInput('')
      setTitle('')
      inputRef.current?.focus()
    } finally {
      setSaving(false)
    }
  }

  const del = async (id) => {
    await API.deleteJournal(id, mockMode)
    setEntries(prev => prev.filter(e => e.id !== id))
  }

  const update = (updated) => {
    setEntries(prev => prev.map(e => e.id === updated.id ? updated : e))
  }

  const unprocessed = entries.filter(e => !e.processed).length

  return (
    <div className="max-w-3xl mx-auto px-4 py-6">
      <SectionHeader
        title="Journal"
        subtitle="Quick capture for thoughts, notes, and living documents JARVIS can reference."
        actions={
          <div className="flex items-center gap-2">
            {unprocessed > 0 && (
              <span className="text-xs text-jarvis-amber">{unprocessed} unanalysed</span>
            )}
            <Button variant="ghost" size="sm" onClick={load}><RefreshCw size={14} /></Button>
          </div>
        }
      />

      {/* Quick capture */}
      <GlassPanel className="p-4 mb-6 glow-border">
        <input
          value={title}
          onChange={e => setTitle(e.target.value)}
          placeholder="Entry title (optional, e.g. Shopping List)"
          className="glass w-full rounded-lg px-3 py-2 text-sm text-jarvis-text placeholder:text-jarvis-muted/50 outline-none focus:border-jarvis-cyan/50 mb-2"
        />
        <Textarea
          ref={inputRef}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) save() }}
          placeholder="Capture a thought, reminder, or note… (Ctrl+Enter to save)"
          className="min-h-[80px] mb-3"
        />
        <button
          onClick={() => setShowOpts(o => !o)}
          className="flex items-center gap-1.5 text-[11px] text-jarvis-muted hover:text-jarvis-text mb-3"
        >
          <Settings2 size={12} /> Entry options {showOpts ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
        </button>
        <AnimatePresence>
          {showOpts && (
            <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden mb-3">
              <div className="space-y-2 py-1">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-jarvis-text flex items-center gap-1.5"><Eye size={12} className="text-jarvis-cyan" /> AI can read</span>
                  <Toggle checked={llmRead} onChange={setLlmRead} />
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-jarvis-text flex items-center gap-1.5"><Edit3 size={12} className="text-jarvis-amber" /> AI can edit</span>
                  <Toggle checked={llmEdit} onChange={setLlmEdit} />
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
        <div className="flex justify-end gap-2">
          {input.trim() && <Button variant="ghost" size="sm" onClick={() => setInput('')}>Clear</Button>}
          <Button variant="solid" size="sm" onClick={save} disabled={!input.trim() || saving}>
            {saving ? <Spinner size={12} /> : <Plus size={14} />} Capture
          </Button>
        </div>
      </GlassPanel>

      {/* Entries */}
      {loading ? (
        <div className="flex justify-center py-20"><Spinner size={24} /></div>
      ) : entries.length === 0 ? (
        <EmptyState icon={BookOpen} title="Journal is empty" description="Capture thoughts above. JARVIS will reference them during routines." />
      ) : (
        <div className="space-y-3">
          <AnimatePresence mode="popLayout">
            {entries.map(e => (
              <JournalEntryCard key={e.id} entry={e} onDelete={del} onChange={update} />
            ))}
          </AnimatePresence>
        </div>
      )}
    </div>
  )
}
