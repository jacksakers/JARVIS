import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { BookOpen, Plus, Trash2, RefreshCw, Sparkles } from 'lucide-react'
import { formatDistanceToNow, format } from 'date-fns'
import { GlassPanel, Button, Badge, EmptyState, Spinner, SectionHeader, Textarea } from '../components/ui'
import useStore from '../store'
import * as API from '../api'
import clsx from 'clsx'

function JournalEntryCard({ entry, onDelete }) {
  return (
    <motion.div layout initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
      <GlassPanel className="p-4 group glow-border">
        <div className="flex items-start justify-between gap-3">
          <p className="text-sm text-jarvis-text whitespace-pre-wrap flex-1 leading-relaxed">{entry.content}</p>
          <button
            onClick={() => onDelete(entry.id)}
            className="opacity-0 group-hover:opacity-100 transition-opacity p-1 text-jarvis-muted hover:text-jarvis-red shrink-0"
          >
            <Trash2 size={13} />
          </button>
        </div>
        <div className="flex items-center gap-3 mt-2">
          <span className="text-[10px] text-jarvis-muted">
            {entry.created_at ? formatDistanceToNow(new Date(entry.created_at), { addSuffix: true }) : ''}
          </span>
          {entry.processed && (
            <Badge type="done" className="text-[10px]">processed</Badge>
          )}
        </div>
      </GlassPanel>
    </motion.div>
  )
}

export default function JournalPage() {
  const mockMode = useStore(s => s.mockMode)
  const [entries, setEntries] = useState([])
  const [loading, setLoading] = useState(true)
  const [input,   setInput]   = useState('')
  const [saving,  setSaving]  = useState(false)
  const inputRef = useRef(null)

  const load = async () => {
    setLoading(true)
    const data = await API.getJournal(mockMode)
    setEntries(data)
    setLoading(false)
  }
  useEffect(() => { load() }, [mockMode])

  const save = async () => {
    const text = input.trim()
    if (!text || saving) return
    setSaving(true)
    try {
      const entry = await API.createJournal({ content: text }, mockMode)
      setEntries(prev => [entry, ...prev])
      setInput('')
      inputRef.current?.focus()
    } finally {
      setSaving(false)
    }
  }

  const del = async (id) => {
    await API.deleteJournal(id, mockMode)
    setEntries(prev => prev.filter(e => e.id !== id))
  }

  const unprocessed = entries.filter(e => !e.processed).length

  return (
    <div className="max-w-3xl mx-auto px-4 py-6">
      <SectionHeader
        title="Journal"
        subtitle="Quick capture for thoughts, notes, and reminders JARVIS can reference."
        actions={
          <div className="flex items-center gap-2">
            {unprocessed > 0 && (
              <span className="text-xs text-jarvis-amber">{unprocessed} unprocessed</span>
            )}
            <Button variant="ghost" size="sm" onClick={load}><RefreshCw size={14} /></Button>
          </div>
        }
      />

      {/* Quick capture */}
      <GlassPanel className="p-4 mb-6 glow-border">
        <Textarea
          ref={inputRef}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) save() }}
          placeholder="Capture a thought, reminder, or note… (Ctrl+Enter to save)"
          className="min-h-[80px] mb-3"
        />
        <div className="flex justify-end gap-2">
          {input.trim() && (
            <Button variant="ghost" size="sm" onClick={() => setInput('')}>Clear</Button>
          )}
          <Button variant="solid" size="sm" onClick={save} disabled={!input.trim() || saving}>
            {saving ? <Spinner size={12} /> : <Plus size={14} />}
            Capture
          </Button>
        </div>
      </GlassPanel>

      {/* Entries */}
      {loading ? (
        <div className="flex justify-center py-20"><Spinner size={24} /></div>
      ) : entries.length === 0 ? (
        <EmptyState
          icon={BookOpen}
          title="Journal is empty"
          description="Capture thoughts above. JARVIS will reference them during routines."
        />
      ) : (
        <div className="space-y-3">
          <AnimatePresence mode="popLayout">
            {entries.map(e => <JournalEntryCard key={e.id} entry={e} onDelete={del} />)}
          </AnimatePresence>
        </div>
      )}
    </div>
  )
}
