import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Send, Bot, User, Wrench, Trash2, Cpu, AlertCircle,
  Plus, MessageSquare, Menu, Pencil, Check, X
} from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { formatDistanceToNow } from 'date-fns'

const parseUTC = s => s ? new Date(s.endsWith('Z') || s.includes('+') ? s : s + 'Z') : null
import { Button, EmptyState, Spinner } from '../components/ui'
import useStore from '../store'
import * as API from '../api'
import clsx from 'clsx'

const PERSONAS = [
  { value: '', label: 'Default JARVIS' },
  { value: 'You are a concise analyst. Be direct and data-driven.', label: 'Analyst' },
  { value: 'You are a creative brainstorming partner. Be expansive and imaginative.', label: 'Creative' },
  { value: 'You are a friendly assistant who explains things simply.', label: 'Simple Mode' },
  { value: "You are a critical thinker who challenges assumptions. Play devil's advocate.", label: "Devil's Advocate" },
]

// ── Sub-components ────────────────────────────────────────────────────────

function TypingIndicator() {
  return (
    <div className="flex items-center gap-1 py-1">
      <span className="typing-dot" /><span className="typing-dot" /><span className="typing-dot" />
    </div>
  )
}

function ToolCallLine({ data }) {
  return (
    <div className="flex items-center gap-2 text-xs font-mono text-jarvis-cyan/70 py-1">
      <Wrench size={11} />
      <span className="text-jarvis-muted">Calling</span>
      <span className="text-jarvis-cyan">{data.name}</span>
      {data.arguments && Object.keys(data.arguments).length > 0 && (
        <span className="text-jarvis-muted truncate max-w-[180px]">
          ({JSON.stringify(data.arguments).slice(0, 60)})
        </span>
      )}
    </div>
  )
}

function ToolResultLine({ data }) {
  return (
    <div className="flex items-center gap-2 text-xs font-mono text-green-400/70 py-0.5">
      <span className="text-green-400">✓</span>
      <span className="text-jarvis-muted">{data.name}:</span>
      <span className="text-green-400/80 truncate max-w-[220px]">{String(data.result ?? '').slice(0, 80)}</span>
    </div>
  )
}

function Message({ msg }) {
  const isUser = msg.role === 'user'
  if (msg.role === 'system') {
    return (
      <div className="flex justify-center my-2">
        <span className="text-[11px] text-jarvis-muted font-mono bg-jarvis-surface/50 px-3 py-1 rounded-full border border-jarvis-border">
          {msg.content}
        </span>
      </div>
    )
  }
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className={clsx('flex gap-3', isUser ? 'flex-row-reverse' : 'flex-row')}
    >
      <div className={clsx(
        'w-7 h-7 rounded-lg flex items-center justify-center shrink-0 mt-1',
        isUser ? 'bg-purple-500/20 border border-purple-500/30' : 'bg-jarvis-cyan/10 border border-jarvis-cyan/25'
      )}>
        {isUser
          ? <User size={14} className="text-purple-400" />
          : <Cpu size={14} className="text-jarvis-cyan" />}
      </div>
      <div className={clsx('flex flex-col gap-1 max-w-[78%]', isUser && 'items-end')}>
        {!isUser && msg.toolEvents?.length > 0 && (
          <div className="glass rounded-lg px-3 py-2 text-xs mb-1 border border-jarvis-border">
            {msg.toolEvents.map((ev, i) => (
              ev.type === 'tool_call'
                ? <ToolCallLine key={i} data={ev.data} />
                : <ToolResultLine key={i} data={ev.data} />
            ))}
          </div>
        )}
        <div className={clsx(
          'rounded-xl px-4 py-3 text-sm',
          isUser
            ? 'bg-purple-500/15 border border-purple-500/25 text-jarvis-text'
            : 'glass border-jarvis-border text-jarvis-text'
        )}>
          {msg.status === 'thinking' && <TypingIndicator />}
          {msg.status === 'error' && (
            <div className="flex items-center gap-2 text-red-400 text-xs">
              <AlertCircle size={14} /> {msg.content || 'An error occurred.'}
            </div>
          )}
          {(msg.status === 'done' || msg.status === 'streaming' || !msg.status) && msg.content && (
            msg.content_html
              ? <div className="prose prose-sm prose-jarvis max-w-none" dangerouslySetInnerHTML={{ __html: msg.content_html }} />
              : <ReactMarkdown remarkPlugins={[remarkGfm]} className="prose prose-sm prose-jarvis max-w-none">
                  {msg.content}
                </ReactMarkdown>
          )}
        </div>
        <span className="text-[10px] text-jarvis-muted/60 px-1">
          {msg.created_at ? formatDistanceToNow(parseUTC(msg.created_at), { addSuffix: true }) : ''}
        </span>
      </div>
    </motion.div>
  )
}

// ── Conversation list item ────────────────────────────────────────────────

function ConvItem({ conv, active, onSelect, onDelete, onRename }) {
  const [editing, setEditing] = useState(false)
  const [title, setTitle] = useState(conv.title || 'New chat')
  const inputRef = useRef(null)
  useEffect(() => { if (editing) inputRef.current?.focus() }, [editing])

  const save = () => {
    if (title.trim()) onRename(conv.id, title.trim())
    setEditing(false)
  }

  return (
    <div
      onClick={() => !editing && onSelect(conv.id)}
      className={clsx(
        'group flex items-center gap-2 px-3 py-2.5 rounded-lg cursor-pointer transition-colors text-sm',
        active
          ? 'bg-jarvis-cyan/10 border border-jarvis-cyan/20 text-white'
          : 'hover:bg-jarvis-surface text-jarvis-muted hover:text-white'
      )}
    >
      <MessageSquare size={13} className="shrink-0" />
      {editing ? (
        <input
          ref={inputRef}
          value={title}
          onChange={e => setTitle(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') save(); if (e.key === 'Escape') setEditing(false) }}
          onClick={e => e.stopPropagation()}
          className="flex-1 bg-jarvis-bg border border-jarvis-cyan/40 rounded px-2 py-0.5 text-xs text-white outline-none"
        />
      ) : (
        <span className="flex-1 truncate text-xs">{conv.title || 'New chat'}</span>
      )}
      <div
        className="flex gap-1 group-hover:opacity-100 transition-opacity"
        onClick={e => e.stopPropagation()}
      >
        {editing ? (
          <>
            <button onClick={save} className="text-green-400 hover:text-green-300"><Check size={12} /></button>
            <button onClick={() => setEditing(false)} className="text-jarvis-muted hover:text-white"><X size={12} /></button>
          </>
        ) : (
          <>
            <button onClick={() => setEditing(true)} className="text-jarvis-muted hover:text-jarvis-cyan"><Pencil size={11} /></button>
            <button onClick={() => onDelete(conv.id)} className="text-jarvis-muted hover:text-red-400"><Trash2 size={11} /></button>
          </>
        )}
      </div>
    </div>
  )
}

// ── Main ChatPage ─────────────────────────────────────────────────────────

export default function ChatPage() {
  const mockMode    = useStore(s => s.mockMode)
  const wsEvents    = useStore(s => s.wsEvents)

  const [conversations, setConversations] = useState([])
  const [activeConvId, setActiveConvId]   = useState(null)
  const [messages, setMessages]           = useState([])
  const [sidebarOpen, setSidebarOpen]     = useState(false)
  const [loadingConvs, setLoadingConvs]   = useState(true)
  const [loadingMsgs, setLoadingMsgs]     = useState(false)

  const [input, setInput]         = useState('')
  const [persona, setPersona]     = useState('')
  const [sending, setSending]     = useState(false)
  const [activeTaskId, setActiveTaskId] = useState(null)

  const bottomRef      = useRef(null)
  const inputRef       = useRef(null)
  const pendingIdRef   = useRef(null)
  const activeConvIdRef = useRef(null)

  useEffect(() => { activeConvIdRef.current = activeConvId }, [activeConvId])

  // Load conversations on mount
  useEffect(() => { loadConversations() }, [mockMode])

  const loadConversations = async () => {
    setLoadingConvs(true)
    try {
      const convs = await API.getConversations(mockMode)
      setConversations(convs)
      if (convs.length > 0) selectConversation(convs[0].id)
    } catch (e) { console.error(e) }
    finally { setLoadingConvs(false) }
  }

  const selectConversation = async (convId) => {
    setActiveConvId(convId)
    setSidebarOpen(false)
    setLoadingMsgs(true)
    try {
      const msgs = await API.getConversationMessages(convId, mockMode)
      setMessages(msgs.map(m => ({ ...m, toolEvents: tryParseJson(m.tool_events) })))
    } catch (e) { console.error(e); setMessages([]) }
    finally { setLoadingMsgs(false) }
  }

  const newConversation = async () => {
    try {
      const conv = await API.createConversation({ title: 'New chat' }, mockMode)
      setConversations(prev => [conv, ...prev])
      setActiveConvId(conv.id)
      setMessages([])
    } catch (e) { console.error(e) }
  }

  const deleteConversation = async (convId) => {
    try {
      await API.deleteConversation(convId, mockMode)
      const rest = conversations.filter(c => c.id !== convId)
      setConversations(rest)
      if (convId === activeConvId) {
        if (rest.length > 0) selectConversation(rest[0].id)
        else { setActiveConvId(null); setMessages([]) }
      }
    } catch (e) { console.error(e) }
  }

  const renameConversation = async (convId, title) => {
    try {
      await API.updateConversation(convId, { title }, mockMode)
      setConversations(prev => prev.map(c => c.id === convId ? { ...c, title } : c))
    } catch (e) { console.error(e) }
  }

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // WS listener for the active task
  useEffect(() => {
    if (!activeTaskId) return
    const latest = wsEvents[0]
    if (!latest || latest.data?.task_id !== activeTaskId) return
    const { event, data } = latest

    if (event === 'tool_call' || event === 'tool_result') {
      setMessages(prev => prev.map(m =>
        m.id === pendingIdRef.current
          ? { ...m, toolEvents: [...(m.toolEvents ?? []), { type: event, data }] }
          : m
      ))
    }
    if (event === 'task_done') {
      API.getFeed({}, mockMode).then(items => {
        const fi = items.find(i => i.task_id === activeTaskId)
        setMessages(prev => prev.map(m =>
          m.id === pendingIdRef.current
            ? { ...m, status: 'done', content: fi?.content_markdown ?? 'Done.', content_html: fi?.content_html ?? '' }
            : m
        ))
        setSending(false); setActiveTaskId(null); pendingIdRef.current = null
        const cid = activeConvIdRef.current
        if (cid) {
          API.getConversationMessages(cid, mockMode)
            .then(msgs => setMessages(msgs.map(m => ({ ...m, toolEvents: tryParseJson(m.tool_events) }))))
            .catch(() => {})
        }
      })
    }
    if (event === 'task_failed') {
      setMessages(prev => prev.map(m =>
        m.id === pendingIdRef.current
          ? { ...m, status: 'error', content: data.error ?? 'Task failed.' }
          : m
      ))
      setSending(false); setActiveTaskId(null); pendingIdRef.current = null
    }
  }, [wsEvents])

  const send = async () => {
    const text = input.trim()
    if (!text || sending) return
    setInput('')
    setSending(true)

    let convId = activeConvId
    if (!convId) {
      try {
        const conv = await API.createConversation({ title: text.slice(0, 50) }, mockMode)
        convId = conv.id
        setConversations(prev => [conv, ...prev])
        setActiveConvId(conv.id)
      } catch { setSending(false); return }
    }

    const tempId = `tmp-${Date.now()}`
    setMessages(prev => [...prev, { id: tempId, role: 'user', content: text, created_at: new Date().toISOString() }])

    try {
      const res = await API.sendConversationMessage(convId, text, mockMode)
      const asstId = res?.assistant_message?.id ?? `asst-${Date.now()}`
      pendingIdRef.current = asstId
      setMessages(prev => [
        ...prev.filter(m => m.id !== tempId),
        res?.user_message ?? { id: tempId, role: 'user', content: text, created_at: new Date().toISOString() },
        { id: asstId, role: 'assistant', status: 'thinking', content: '', toolEvents: [], created_at: new Date().toISOString() },
      ])
      const taskId = res?.task_id
      if (taskId) {
        setActiveTaskId(taskId)
        const isNewChat = conversations.find(c => c.id === convId)?.title === 'New chat'
        if (isNewChat) renameConversation(convId, text.length > 50 ? text.slice(0, 47) + '…' : text)
        if (!mockMode) {
          const poll = setInterval(async () => {
            try {
              const tasks = await API.getTasks({ status: 'done' }, false)
              if (tasks.find(t => t.id === taskId)) {
                clearInterval(poll)
                const items = await API.getFeed({}, false)
                const fi = items.find(i => i.task_id === taskId)
                setMessages(prev => prev.map(m =>
                  m.id === pendingIdRef.current
                    ? { ...m, status: 'done', content: fi?.content_markdown ?? 'Done.', content_html: fi?.content_html ?? '' }
                    : m
                ))
                setSending(false); setActiveTaskId(null); pendingIdRef.current = null
              }
            } catch {}
          }, 3000)
          setTimeout(() => clearInterval(poll), 120000)
        }
      } else {
        setSending(false)
      }
    } catch (err) {
      setMessages(prev => [...prev.filter(m => m.id !== tempId), {
        id: `err-${Date.now()}`, role: 'assistant', status: 'error',
        content: err.message, created_at: new Date().toISOString()
      }])
      setSending(false)
    }
  }

  function tryParseJson(str) {
    if (!str) return []
    try { return JSON.parse(str) } catch { return [] }
  }

  const activeConv = conversations.find(c => c.id === activeConvId)

  return (
    <div className="flex h-full overflow-hidden">
      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div className="fixed inset-0 bg-black/60 z-30 md:hidden" onClick={() => setSidebarOpen(false)} />
      )}

      {/* Sidebar */}
      <div className={clsx(
        'flex flex-col w-64 border-r border-jarvis-border bg-jarvis-bg shrink-0 z-40',
        sidebarOpen ? 'fixed inset-y-0 left-0' : 'hidden md:flex'
      )}>
        <div className="flex items-center justify-between px-4 py-3 border-b border-jarvis-border">
          <span className="text-sm font-medium text-white">Chats</span>
          <button
            onClick={newConversation}
            className="p-1.5 rounded-lg hover:bg-jarvis-surface transition-colors text-jarvis-muted hover:text-jarvis-cyan"
          ><Plus size={15} /></button>
        </div>
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {loadingConvs ? (
            <div className="flex justify-center py-6"><Spinner /></div>
          ) : conversations.length === 0 ? (
            <p className="text-center text-jarvis-muted text-xs py-6">No conversations yet.</p>
          ) : conversations.map(conv => (
            <ConvItem
              key={conv.id}
              conv={conv}
              active={conv.id === activeConvId}
              onSelect={selectConversation}
              onDelete={deleteConversation}
              onRename={renameConversation}
            />
          ))}
        </div>
      </div>

      {/* Main */}
      <div className="flex flex-col flex-1 min-w-0 h-full">
        {/* Top bar */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-jarvis-border shrink-0">
          <button className="md:hidden text-jarvis-muted hover:text-white" onClick={() => setSidebarOpen(true)}>
            <Menu size={16} />
          </button>
          <Cpu size={13} className="text-jarvis-cyan shrink-0" />
          <span className="text-xs text-jarvis-muted shrink-0">Persona:</span>
          <select
            value={persona}
            onChange={e => setPersona(e.target.value)}
            className="bg-transparent text-xs text-jarvis-text outline-none cursor-pointer flex-1 min-w-0"
          >
            {PERSONAS.map(p => <option key={p.value} value={p.value}>{p.label}</option>)}
          </select>
          {activeConv && (
            <span className="text-xs text-jarvis-muted truncate max-w-[160px] hidden sm:block">
              {activeConv.title}
            </span>
          )}
          <button onClick={newConversation} className="text-jarvis-muted hover:text-jarvis-cyan transition-colors" title="New chat">
            <Plus size={14} />
          </button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-4 flex flex-col gap-4">
          {!activeConvId && !loadingConvs && (
            <EmptyState icon={Bot} title="JARVIS is ready" description="Start a new chat or pick one from the sidebar." />
          )}
          {loadingMsgs && <div className="flex justify-center py-8"><Spinner /></div>}
          <AnimatePresence>
            {messages.map(msg => <Message key={msg.id} msg={msg} />)}
          </AnimatePresence>
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="shrink-0 px-4 py-3 border-t border-jarvis-border">
          <div className="flex items-end gap-2">
            <div className="flex-1 glass rounded-xl border-jarvis-border focus-within:border-jarvis-cyan/50 transition-colors">
              <textarea
                ref={inputRef}
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
                placeholder={activeConvId ? 'Message JARVIS… (Enter to send)' : 'Start a new conversation…'}
                rows={1}
                disabled={sending}
                className="w-full bg-transparent px-4 py-3 text-sm text-jarvis-text placeholder:text-jarvis-muted/50 outline-none resize-none max-h-32 overflow-y-auto"
                style={{ fieldSizing: 'content' }}
              />
            </div>
            <button
              onClick={send}
              disabled={!input.trim() || sending}
              className="p-3 rounded-xl bg-jarvis-cyan text-black hover:bg-jarvis-cyan/80 transition-all disabled:opacity-40 disabled:cursor-not-allowed shrink-0"
            >
              {sending ? <Spinner size="sm" /> : <Send size={16} />}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}