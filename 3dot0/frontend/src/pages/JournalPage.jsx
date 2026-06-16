import { useState, useEffect, useRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  BookOpen, Plus, Trash2, RefreshCw, Settings2, ChevronDown, ChevronUp,
  Eye, EyeOff, Edit3, Unlock, Search, X, Pin, PinOff, Tag, Palette,
  SortAsc, SortDesc, ArrowUpDown, CheckSquare, FolderPlus, Pencil,
} from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
const parseUTC = s => s ? new Date(s.endsWith('Z') || s.includes('+') ? s : s + 'Z') : null

import { GlassPanel, Button, Badge, EmptyState, Spinner, SectionHeader, Textarea, Toggle } from '../components/ui'
import useStore from '../store'
import * as API from '../api'
import clsx from 'clsx'

//  Helpers 

const SORT_OPTIONS = [
  { value: 'newest',  label: 'Newest first' },
  { value: 'oldest',  label: 'Oldest first' },
  { value: 'updated', label: 'Recently edited' },
  { value: 'title',   label: 'Title Aâ€“Z' },
]

const PRESET_COLORS = [
  '#06b6d4', '#22c55e', '#f59e0b', '#a855f7',
  '#ef4444', '#ec4899', '#3b82f6', '#f97316',
]

//  CategoryBadge 

function CategoryBadge({ name, color, icon, className }) {
  return (
    <span
      className={clsx('inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium', className)}
      style={{ background: color + '22', color, border: `1px solid ${color}44` }}
    >
      {icon} {name}
    </span>
  )
}

//  CategoryManagerModal 

function CategoryManagerModal({ categories, onClose, onChange, mockMode }) {
  const [form,    setForm]    = useState({ name: '', color: PRESET_COLORS[0], icon: 'ðŸ“', description: '' })
  const [editing, setEditing] = useState(null)
  const [saving,  setSaving]  = useState(false)
  const [deleting, setDeleting] = useState(null)

  const startEdit = (cat) => {
    setEditing(cat.id)
    setForm({ name: cat.name, color: cat.color, icon: cat.icon, description: cat.description })
  }

  const saveEdit = async () => {
    setSaving(true)
    try {
      const updated = await API.updateJournalCategory(editing, form, mockMode)
      onChange('update', updated)
      setEditing(null)
      setForm({ name: '', color: PRESET_COLORS[0], icon: 'ðŸ“', description: '' })
    } finally { setSaving(false) }
  }

  const saveNew = async () => {
    if (!form.name.trim()) return
    setSaving(true)
    try {
      const created = await API.createJournalCategory(form, mockMode)
      onChange('create', created)
      setForm({ name: '', color: PRESET_COLORS[0], icon: 'ðŸ“', description: '' })
    } finally { setSaving(false) }
  }

  const del = async (id) => {
    setDeleting(id)
    try {
      await API.deleteJournalCategory(id, mockMode)
      onChange('delete', { id })
    } finally { setDeleting(null) }
  }

  const isEditingThis = (id) => editing === id

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
        className="glass rounded-2xl w-full max-w-md max-h-[80vh] flex flex-col overflow-hidden"
      >
        <div className="flex items-center justify-between p-4 border-b border-jarvis-border">
          <h2 className="font-semibold text-jarvis-text flex items-center gap-2"><Tag size={16} className="text-jarvis-cyan" /> Manage Categories</h2>
          <button onClick={onClose} className="text-jarvis-muted hover:text-white"><X size={16} /></button>
        </div>

        <div className="overflow-y-auto flex-1 p-4 space-y-2">
          {categories.map(cat => (
            <GlassPanel key={cat.id} className="p-3">
              {isEditingThis(cat.id) ? (
                <div className="space-y-2">
                  <CategoryFormFields form={form} setForm={setForm} />
                  <div className="flex gap-2 justify-end">
                    <Button variant="ghost" size="sm" onClick={() => setEditing(null)}>Cancel</Button>
                    <Button variant="solid" size="sm" onClick={saveEdit} disabled={saving}>{saving ? <Spinner size={12} /> : null} Save</Button>
                  </div>
                </div>
              ) : (
                <div className="flex items-center gap-3">
                  <span className="text-lg">{cat.icon}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-jarvis-text">{cat.name}</span>
                      <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: cat.color }} />
                      <span className="text-[10px] text-jarvis-muted">{cat.entry_count} entries</span>
                    </div>
                    {cat.description && <p className="text-[11px] text-jarvis-muted truncate">{cat.description}</p>}
                  </div>
                  <div className="flex gap-1 shrink-0">
                    <button onClick={() => startEdit(cat)} className="p-1 text-jarvis-muted hover:text-jarvis-cyan"><Pencil size={13} /></button>
                    <button onClick={() => del(cat.id)} className="p-1 text-jarvis-muted hover:text-jarvis-red" disabled={deleting === cat.id}>
                      {deleting === cat.id ? <Spinner size={12} /> : <Trash2 size={13} />}
                    </button>
                  </div>
                </div>
              )}
            </GlassPanel>
          ))}
        </div>

        {/* New category form */}
        <div className="border-t border-jarvis-border p-4 space-y-3">
          <p className="text-xs font-semibold text-jarvis-muted uppercase tracking-wider">New Category</p>
          <CategoryFormFields form={form} setForm={setForm} />
          <Button variant="solid" size="sm" onClick={saveNew} disabled={saving || !form.name.trim()} className="w-full justify-center">
            {saving ? <Spinner size={12} /> : <Plus size={14} />} Create Category
          </Button>
        </div>
      </motion.div>
    </div>
  )
}

function CategoryFormFields({ form, setForm }) {
  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        <input
          value={form.icon}
          onChange={e => setForm(f => ({ ...f, icon: e.target.value }))}
          className="glass rounded-lg px-2 py-1.5 text-sm text-jarvis-text outline-none w-14 text-center"
          placeholder="ðŸ“"
          maxLength={4}
        />
        <input
          value={form.name}
          onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
          placeholder="Category name"
          className="glass flex-1 rounded-lg px-3 py-1.5 text-sm text-jarvis-text outline-none focus:border-jarvis-cyan/50"
        />
      </div>
      <input
        value={form.description}
        onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
        placeholder="Short description (optional)"
        className="glass w-full rounded-lg px-3 py-1.5 text-sm text-jarvis-text outline-none focus:border-jarvis-cyan/50"
      />
      <div className="flex gap-1.5 flex-wrap">
        {PRESET_COLORS.map(c => (
          <button
            key={c}
            onClick={() => setForm(f => ({ ...f, color: c }))}
            className={clsx('w-5 h-5 rounded-full transition-transform', form.color === c && 'ring-2 ring-white/60 ring-offset-1 ring-offset-transparent scale-110')}
            style={{ background: c }}
          />
        ))}
        <input
          type="color"
          value={form.color}
          onChange={e => setForm(f => ({ ...f, color: e.target.value }))}
          className="w-5 h-5 rounded-full cursor-pointer bg-transparent border-none"
          title="Custom colour"
        />
      </div>
    </div>
  )
}

//  EntrySettings (inline expandable panel) 

function EntrySettings({ entry, categories, onChange, onClose, mockMode }) {
  const [form, setForm] = useState({
    title:        entry.title        ?? '',
    category_id:  entry.category_id  ?? '',
    llm_readable: entry.llm_readable ?? true,
    llm_editable: entry.llm_editable ?? false,
  })
  const [saving, setSaving] = useState(false)

  const save = async () => {
    setSaving(true)
    try {
      const payload = {
        ...form,
        category_id: form.category_id === '' ? null : Number(form.category_id),
      }
      const updated = await API.updateJournal(entry.id, payload, mockMode)
      onChange(updated)
      onClose()
    } finally { setSaving(false) }
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
            placeholder="e.g. Shopping List, Project Ideasâ€¦"
            className="glass w-full rounded-lg px-3 py-2 text-sm text-jarvis-text outline-none focus:border-jarvis-cyan/50"
          />
        </div>
        <div>
          <label className="text-[10px] font-medium text-jarvis-muted uppercase tracking-wider block mb-1">Category</label>
          <select
            value={form.category_id}
            onChange={e => setForm(f => ({ ...f, category_id: e.target.value }))}
            className="glass w-full rounded-lg px-3 py-2 text-sm text-jarvis-text outline-none focus:border-jarvis-cyan/50 bg-jarvis-surface"
          >
            <option value="">â€” No category â€”</option>
            {categories.map(c => (
              <option key={c.id} value={c.id}>{c.icon} {c.name}</option>
            ))}
          </select>
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

//  JournalEntryCard 

function JournalEntryCard({ entry, categories, onDelete, onChange, mockMode }) {
  const [expanded,     setExpanded]     = useState(false)
  const [showSettings, setShowSettings] = useState(false)
  const [editMode,     setEditMode]     = useState(false)
  const [editContent,  setEditContent]  = useState(entry.content)
  const [saving,       setSaving]       = useState(false)
  const [pinning,      setPinning]      = useState(false)

  const saveEdit = async () => {
    if (editContent.trim() === entry.content) { setEditMode(false); return }
    setSaving(true)
    try {
      const updated = await API.updateJournal(entry.id, { content: editContent.trim() }, mockMode)
      onChange(updated)
      setEditMode(false)
    } finally { setSaving(false) }
  }

  const togglePin = async () => {
    setPinning(true)
    try {
      const updated = await API.updateJournal(entry.id, { pinned: !entry.pinned }, mockMode)
      onChange(updated)
    } finally { setPinning(false) }
  }

  const flags = []
  if (!entry.llm_readable) flags.push({ icon: EyeOff,  label: 'Private',  color: 'text-jarvis-muted' })
  if (entry.llm_editable)  flags.push({ icon: Unlock,  label: 'Editable', color: 'text-jarvis-amber' })

  return (
    <motion.div layout initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
      <GlassPanel className={clsx('p-0 overflow-hidden group', entry.pinned && 'glow-border border-jarvis-cyan/30')}>
        <div className="flex items-start gap-3 p-4">
          <button onClick={() => setExpanded(e => !e)} className="mt-0.5 shrink-0 text-jarvis-muted hover:text-jarvis-text">
            {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap mb-1">
              {entry.pinned && <Pin size={11} className="text-jarvis-cyan fill-jarvis-cyan/30" />}
              {entry.title && <p className="text-xs font-semibold text-jarvis-cyan font-mono">{entry.title}</p>}
              {entry.category_name && (
                <CategoryBadge name={entry.category_name} color={entry.category_color} icon={entry.category_icon} />
              )}
            </div>
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
                {entry.created_at ? formatDistanceToNow(parseUTC(entry.created_at), { addSuffix: true }) : ''}
              </span>
              {entry.updated_at && entry.updated_at !== entry.created_at && (
                <span className="text-[10px] text-jarvis-muted/60">Â· edited</span>
              )}
              {entry.processed && <Badge type="done" className="text-[10px]">analysed</Badge>}
              {flags.map(({ icon: Icon, label, color }) => (
                <span key={label} className={clsx('flex items-center gap-0.5 text-[10px]', color)}><Icon size={10} />{label}</span>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-1 shrink-0">
            {expanded && !editMode && (
              <button onClick={() => setEditMode(true)} className="p-1 text-jarvis-muted hover:text-jarvis-cyan transition-opacity" title="Edit content">
                <Edit3 size={13} />
              </button>
            )}
            <button
              onClick={togglePin}
              disabled={pinning}
              className={clsx('p-1 transition-colors', entry.pinned ? 'text-jarvis-cyan' : 'text-jarvis-muted hover:text-jarvis-cyan group-hover:opacity-100')}
              title={entry.pinned ? 'Unpin' : 'Pin to top'}
            >
              {pinning ? <Spinner size={12} /> : entry.pinned ? <PinOff size={13} /> : <Pin size={13} />}
            </button>
            <button
              onClick={() => setShowSettings(s => !s)}
              className={clsx('p-1 transition-opacity', showSettings ? 'text-jarvis-cyan' : 'text-jarvis-muted hover:text-jarvis-text group-hover:opacity-100')}
              title="Settings"
            >
              <Settings2 size={13} />
            </button>
            <button onClick={() => onDelete(entry.id)} className="p-1 text-jarvis-muted hover:text-jarvis-red group-hover:opacity-100 transition-opacity" title="Delete">
              <Trash2 size={13} />
            </button>
          </div>
        </div>
        <AnimatePresence>
          {showSettings && (
            <EntrySettings
              entry={entry}
              categories={categories}
              onChange={onChange}
              onClose={() => setShowSettings(false)}
              mockMode={mockMode}
            />
          )}
        </AnimatePresence>
      </GlassPanel>
    </motion.div>
  )
}

//  CategorySidebar 

function CategorySidebar({ categories, selected, onSelect, entryCounts }) {
  const total = entryCounts.total ?? 0
  const pinned = entryCounts.pinned ?? 0

  const navItem = (id, icon, label, count, color) => {
    const active = selected === id
    return (
      <button
        key={id}
        onClick={() => onSelect(id)}
        className={clsx(
          'w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors text-left',
          active
            ? 'bg-jarvis-cyan/10 border border-jarvis-cyan/30 text-jarvis-cyan'
            : 'text-jarvis-muted hover:text-jarvis-text hover:bg-white/5'
        )}
      >
        <span className="text-base leading-none">{icon}</span>
        <span className="flex-1 truncate">{label}</span>
        <span className={clsx('text-[10px] tabular-nums', active ? 'text-jarvis-cyan/70' : 'text-jarvis-muted/60')}>{count}</span>
      </button>
    )
  }

  return (
    <div className="space-y-1">
      {navItem('all',    'ðŸ“‹', 'All Entries', total,  null)}
      {navItem('pinned', 'ðŸ“Œ', 'Pinned',      pinned, null)}
      {categories.length > 0 && (
        <div className="pt-2 pb-1">
          <p className="text-[9px] font-semibold uppercase tracking-widest text-jarvis-muted/50 px-3 mb-1">Categories</p>
          {categories.map(cat =>
            navItem(cat.id, cat.icon, cat.name, cat.entry_count, cat.color)
          )}
        </div>
      )}
    </div>
  )
}

//  Main Page 

export default function JournalPage() {
  const mockMode = useStore(s => s.mockMode)
  const [entries,      setEntries]      = useState([])
  const [categories,   setCategories]   = useState([])
  const [loading,      setLoading]      = useState(true)
  const [input,        setInput]        = useState('')
  const [title,        setTitle]        = useState('')
  const [selCategory,  setSelCategory]  = useState('')
  const [llmRead,      setLlmRead]      = useState(true)
  const [llmEdit,      setLlmEdit]      = useState(false)
  const [pinNew,       setPinNew]       = useState(false)
  const [showOpts,     setShowOpts]     = useState(false)
  const [saving,       setSaving]       = useState(false)
  const [search,       setSearch]       = useState('')
  const [sort,         setSort]         = useState('newest')
  const [showSort,     setShowSort]     = useState(false)
  const [activeFilter, setActiveFilter] = useState('all')
  const [showCatMgr,   setShowCatMgr]   = useState(false)
  const inputRef = useRef(null)

  // Build query params from current filter state
  const buildParams = useCallback((searchTerm, sortVal, filter) => {
    const params = {}
    if (searchTerm) params.search = searchTerm
    if (sortVal)    params.sort   = sortVal
    if (filter === 'pinned') params.pinned_only = true
    else if (typeof filter === 'number') params.category_id = filter
    return params
  }, [])

  const loadEntries = useCallback(async (searchTerm = '', sortVal = sort, filter = activeFilter) => {
    setLoading(true)
    try {
      const data = await API.getJournal(buildParams(searchTerm, sortVal, filter), mockMode)
      setEntries(data)
    } finally { setLoading(false) }
  }, [sort, activeFilter, mockMode, buildParams])

  const loadCategories = useCallback(async () => {
    const cats = await API.getJournalCategories(mockMode)
    setCategories(cats)
  }, [mockMode])

  useEffect(() => {
    loadCategories()
    loadEntries()
  }, [mockMode])

  // Debounced search
  useEffect(() => {
    const t = setTimeout(() => loadEntries(search, sort, activeFilter), 350)
    return () => clearTimeout(t)
  }, [search])

  const applyFilter = (filter) => {
    setActiveFilter(filter)
    loadEntries(search, sort, filter)
  }

  const applySort = (s) => {
    setSort(s)
    setShowSort(false)
    loadEntries(search, s, activeFilter)
  }

  const save = async () => {
    const text = input.trim()
    if (!text || saving) return
    setSaving(true)
    try {
      const entry = await API.createJournal({
        content: text,
        title: title.trim(),
        category_id: selCategory ? Number(selCategory) : null,
        pinned: pinNew,
        llm_readable: llmRead,
        llm_editable: llmEdit,
      }, mockMode)
      // Prepend if entry matches current filter
      const matchesFilter =
        activeFilter === 'all' ||
        (activeFilter === 'pinned' && entry.pinned) ||
        (typeof activeFilter === 'number' && entry.category_id === activeFilter)
      if (matchesFilter) setEntries(prev => [entry, ...prev])
      setInput('')
      setTitle('')
      setPinNew(false)
      inputRef.current?.focus()
      // Refresh category counts
      loadCategories()
    } finally { setSaving(false) }
  }

  const del = async (id) => {
    await API.deleteJournal(id, mockMode)
    setEntries(prev => prev.filter(e => e.id !== id))
    loadCategories()
  }

  const update = (updated) => {
    setEntries(prev => prev.map(e => e.id === updated.id ? updated : e))
    loadCategories()
  }

  const handleCategoryChange = (action, data) => {
    if (action === 'create') setCategories(prev => [...prev, data])
    else if (action === 'update') setCategories(prev => prev.map(c => c.id === data.id ? data : c))
    else if (action === 'delete') {
      setCategories(prev => prev.filter(c => c.id !== data.id))
      if (activeFilter === data.id) applyFilter('all')
    }
  }

  const unprocessed = entries.filter(e => !e.processed).length
  const entryCounts = {
    total:  categories.reduce((s, c) => s + c.entry_count, 0) + entries.filter(e => !e.category_id).length,
    pinned: entries.filter(e => e.pinned).length,
  }

  // Active filter label
  const activeLabel = activeFilter === 'all' ? 'All Entries'
    : activeFilter === 'pinned' ? 'Pinned'
    : categories.find(c => c.id === activeFilter)?.name ?? ''

  const sortLabel = SORT_OPTIONS.find(o => o.value === sort)?.label ?? 'Sort'

  return (
    <div className="max-w-5xl mx-auto px-4 py-6">
      <SectionHeader
        title="Journal"
        subtitle="Capture thoughts, notes, lists, and living documents JARVIS can reference."
        actions={
          <div className="flex items-center gap-2">
            {unprocessed > 0 && (
              <span className="text-xs text-jarvis-amber">{unprocessed} unanalysed</span>
            )}
            <Button variant="ghost" size="sm" onClick={() => setShowCatMgr(true)} title="Manage categories">
              <Tag size={14} />
            </Button>
            <Button variant="ghost" size="sm" onClick={() => { loadEntries(search, sort, activeFilter); loadCategories() }}>
              <RefreshCw size={14} />
            </Button>
          </div>
        }
      />

      <div className="flex gap-5">
        {/*  Sidebar  */}
        <div className="hidden md:block w-44 shrink-0 space-y-1">
          <CategorySidebar
            categories={categories}
            selected={activeFilter}
            onSelect={applyFilter}
            entryCounts={entryCounts}
          />
          <button
            onClick={() => setShowCatMgr(true)}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-[11px] text-jarvis-muted/60 hover:text-jarvis-muted transition-colors"
          >
            <FolderPlus size={12} /> Manage categories
          </button>
        </div>

        {/*  Main content  */}
        <div className="flex-1 min-w-0 space-y-4">

          {/* Search + sort bar */}
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-jarvis-muted" />
              <input
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder={`Search ${activeLabel.toLowerCase()}â€¦`}
                className="glass w-full rounded-lg pl-9 pr-8 py-2 text-sm text-jarvis-text placeholder:text-jarvis-muted/50 outline-none focus:border-jarvis-cyan/50"
              />
              {search && (
                <button onClick={() => setSearch('')} className="absolute right-3 top-1/2 -translate-y-1/2 text-jarvis-muted hover:text-white">
                  <X size={12} />
                </button>
              )}
            </div>
            {/* Mobile category filter */}
            <div className="md:hidden">
              <select
                value={activeFilter}
                onChange={e => applyFilter(e.target.value === 'all' || e.target.value === 'pinned' ? e.target.value : Number(e.target.value))}
                className="glass rounded-lg px-2 py-2 text-sm text-jarvis-text bg-jarvis-surface outline-none"
              >
                <option value="all">All</option>
                <option value="pinned">Pinned</option>
                {categories.map(c => <option key={c.id} value={c.id}>{c.icon} {c.name}</option>)}
              </select>
            </div>
            {/* Sort dropdown */}
            <div className="relative">
              <Button variant="ghost" size="sm" onClick={() => setShowSort(s => !s)} className="gap-1">
                <ArrowUpDown size={13} />
                <span className="hidden sm:inline text-[11px]">{sortLabel}</span>
              </Button>
              <AnimatePresence>
                {showSort && (
                  <motion.div
                    initial={{ opacity: 0, y: -4 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -4 }}
                    className="absolute right-0 top-full mt-1 glass rounded-xl shadow-xl z-20 min-w-[160px] py-1"
                  >
                    {SORT_OPTIONS.map(o => (
                      <button
                        key={o.value}
                        onClick={() => applySort(o.value)}
                        className={clsx(
                          'w-full text-left px-3 py-2 text-sm transition-colors',
                          sort === o.value ? 'text-jarvis-cyan' : 'text-jarvis-muted hover:text-jarvis-text hover:bg-white/5'
                        )}
                      >
                        {o.label}
                      </button>
                    ))}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>

          {/* Quick capture */}
          <GlassPanel className="p-4 glow-border">
            <div className="flex gap-2 mb-2">
              <input
                value={title}
                onChange={e => setTitle(e.target.value)}
                placeholder="Title (optional)"
                className="glass flex-1 rounded-lg px-3 py-1.5 text-sm text-jarvis-text placeholder:text-jarvis-muted/50 outline-none focus:border-jarvis-cyan/50"
              />
              <select
                value={selCategory}
                onChange={e => setSelCategory(e.target.value)}
                className="glass rounded-lg px-2 py-1.5 text-sm text-jarvis-text bg-jarvis-surface outline-none max-w-[140px]"
              >
                <option value="">No category</option>
                {categories.map(c => <option key={c.id} value={c.id}>{c.icon} {c.name}</option>)}
              </select>
            </div>
            <Textarea
              ref={inputRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) save() }}
              placeholder="Capture a thought, reminder, or noteâ€¦ (Ctrl+Enter to save)"
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
                      <span className="text-xs text-jarvis-text flex items-center gap-1.5"><Pin size={12} className="text-jarvis-cyan" /> Pin to top</span>
                      <Toggle checked={pinNew} onChange={setPinNew} />
                    </div>
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
            <EmptyState icon={BookOpen} title="Nothing here yet" description={
              search ? `No entries matching "${search}".` :
              activeFilter === 'pinned' ? 'Pin important entries to find them quickly.' :
              'Capture thoughts above. JARVIS will reference them during routines.'
            } />
          ) : (
            <div className="space-y-3">
              <AnimatePresence mode="popLayout">
                {entries.map(e => (
                  <JournalEntryCard
                    key={e.id}
                    entry={e}
                    categories={categories}
                    onDelete={del}
                    onChange={update}
                    mockMode={mockMode}
                  />
                ))}
              </AnimatePresence>
            </div>
          )}
        </div>
      </div>

      {/* Category manager modal */}
      <AnimatePresence>
        {showCatMgr && (
          <CategoryManagerModal
            categories={categories}
            onClose={() => setShowCatMgr(false)}
            onChange={handleCategoryChange}
            mockMode={mockMode}
          />
        )}
      </AnimatePresence>
    </div>
  )
}
