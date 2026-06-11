import { useState, useEffect, useRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Send, Bot, User, Wrench, ChevronDown, Trash2, Cpu, AlertCircle } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { formatDistanceToNow } from 'date-fns'
import { Button, GlassPanel, Badge, StatusDot, Spinner, EmptyState } from '../components/ui'
import useStore from '../store'
import * as API from '../api'
import clsx from 'clsx'

const PERSONAS = [
  { value: '', label: 'Default JARVIS' },
  { value: 'You are a concise analyst. Be direct and data-driven.', label: 'Analyst' },
  { value: 'You are a creative brainstorming partner. Be expansive and imaginative.', label: 'Creative' },
  { value: 'You are a friendly assistant who explains things simply.', label: 'Simple Mode' },
  { value: 'You are a critical thinker who challenges assumptions. Play devil\'s advocate.', label: 'Devil\'s Advocate' },
]

// ── Message renderers ─────────────────────────────────────────────────────

function ToolCallLine({ data }) {
  return (
    <div className="flex items-center gap-2 text-xs font-mono text-jarvis-cyan/70 py-1">
      <Wrench size={11} />
      <span className="text-jarvis-muted">Calling</span>
      <span className="text-jarvis-cyan">{data.name}</span>
      {data.arguments && Object.keys(data.arguments).length > 0 && (
        <span className="text-jarvis-muted truncate max-w-[200px]">
          ({JSON.stringify(data.arguments).slice(0, 60)})
        </span>
      )}
    </div>
  )
}

function ToolResultLine({ data }) {
  return (
    <div className="flex items-center gap-2 text-xs font-mono text-jarvis-green/70 py-0.5">
      <span className="text-jarvis-green">✓</span>
      <span className="text-jarvis-muted">{data.name}:</span>
      <span className="text-jarvis-green/80 truncate max-w-[260px]">{data.result}</span>
    </div>
  )
}

function TypingIndicator() {
  return (
    <div className="flex items-center gap-1 py-1">
      <span className="typing-dot" />
      <span className="typing-dot" />
      <span className="typing-dot" />
    </div>
  )
}

function Message({ msg }) {
  const isUser = msg.role === 'user'
  const isSystem = msg.role === 'system'

  if (isSystem) {
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
      {/* Avatar */}
      <div className={clsx(
        'w-7 h-7 rounded-lg flex items-center justify-center shrink-0 mt-1',
        isUser ? 'bg-jarvis-purple/20 border border-jarvis-purple/30' : 'bg-jarvis-cyan/10 border border-jarvis-cyan/25'
      )}>
        {isUser ? <User size={14} className="text-jarvis-purple" /> : <Cpu size={14} className="text-jarvis-cyan" />}
      </div>

      {/* Bubble */}
      <div className={clsx('flex flex-col gap-1 max-w-[78%]', isUser && 'items-end')}>
        {/* Tool events above the bubble */}
        {!isUser && msg.toolEvents?.length > 0 && (
          <div className="glass rounded-lg px-3 py-2 text-xs mb-1 border border-jarvis-border">
            {msg.toolEvents.map((ev, i) => (
              ev.type === 'tool_call'
                ? <ToolCallLine key={i} data={ev.data} />
                : <ToolResultLine key={i} data={ev.data} />
            ))}
          </div>
        )}

        {/* Content bubble */}
        <div className={clsx(
          'rounded-xl px-4 py-3 text-sm',
          isUser
            ? 'bg-jarvis-purple/15 border border-jarvis-purple/25 text-jarvis-text'
            : 'glass border-jarvis-border text-jarvis-text'
        )}>
          {msg.status === 'thinking' && <TypingIndicator />}
          {msg.status === 'error' && (
            <div className="flex items-center gap-2 text-jarvis-red text-xs">
              <AlertCircle size={14} /> {msg.content || 'An error occurred.'}
            </div>
          )}
          {(msg.status === 'done' || msg.status === 'streaming' || !msg.status) && msg.content && (
            msg.html
              ? <div className="prose prose-sm prose-jarvis max-w-none" dangerouslySetInnerHTML={{ __html: msg.html }} />
              : <ReactMarkdown remarkPlugins={[remarkGfm]} className="prose prose-sm prose-jarvis max-w-none">
                  {msg.content}
                </ReactMarkdown>
          )}
        </div>

        <span className="text-[10px] text-jarvis-muted/60 px-1">
          {msg.ts ? formatDistanceToNow(new Date(msg.ts), { addSuffix: true }) : ''}
        </span>
      </div>
    </motion.div>
  )
}

// ── ChatPage ──────────────────────────────────────────────────────────────

export default function ChatPage() {
  const mockMode    = useStore(s => s.mockMode)
  const chatMessages = useStore(s => s.chatMessages)
  const addMsg      = useStore(s => s.addChatMessage)
  const updateMsg   = useStore(s => s.updateChatMessage)
  const clearChat   = useStore(s => s.clearChat)
  const wsEvents    = useStore(s => s.wsEvents)
  const taskPatches = useStore(s => s.taskPatches)

  const [input, setInput]     = useState('')
  const [persona, setPersona] = useState('')
  const [sending, setSending] = useState(false)
  const [activeId, setActiveId] = useState(null)

  const bottomRef = useRef(null)
  const inputRef  = useRef(null)
  const msgIdRef  = useRef(0)
  const nextMsgId = () => `msg-${++msgIdRef.current}`

  // Scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chatMessages])

  // Listen for WS events for the active task
  useEffect(() => {
    if (!activeId) return
    const latest = wsEvents[0]
    if (!latest || latest.data?.task_id !== activeId) return

    const { event, data } = latest

    if (event === 'tool_call' || event === 'tool_result') {
      updateMsg(`pending-${activeId}`, {
        toolEvents: [
          ...(chatMessages.find(m => m.id === `pending-${activeId}`)?.toolEvents ?? []),
          { type: event, data }
        ]
      })
    }

    if (event === 'task_done') {
      // Fetch the completed feed item and display it
      API.getFeed({}, mockMode).then(items => {
        const item = items.find(i => i.task_id === activeId)
        if (item) {
          updateMsg(`pending-${activeId}`, {
            status: 'done',
            content: item.content_markdown,
            html: item.content_html,
            toolEvents: chatMessages.find(m => m.id === `pending-${activeId}`)?.toolEvents ?? [],
          })
        } else {
          updateMsg(`pending-${activeId}`, { status: 'done', content: 'Task complete.' })
        }
        setSending(false)
        setActiveId(null)
      })
    }

    if (event === 'task_failed') {
      updateMsg(`pending-${activeId}`, { status: 'error', content: data.error ?? 'Task failed.' })
      setSending(false)
      setActiveId(null)
    }
  }, [wsEvents])

  const send = async () => {
    const text = input.trim()
    if (!text || sending) return
    setInput('')
    setSending(true)

    // Add user message
    addMsg({ id: nextMsgId(), role: 'user', content: text, ts: new Date().toISOString() })

    try {
      const task = await API.submitTask({
        prompt: text,
        system_prompt_override: persona || undefined,
      }, mockMode)

      const pendingId = `pending-${task.id}`
      setActiveId(task.id)

      // Add JARVIS thinking placeholder
      addMsg({
        id: pendingId,
        role: 'assistant',
        status: 'thinking',
        content: '',
        toolEvents: [],
        ts: new Date().toISOString(),
      })

      if (!mockMode) {
        // In live mode, polling fallback if WS isn't delivering
        const poll = setInterval(async () => {
          const tasks = await API.getTasks({ status: 'done' }, false)
          const done = tasks.find(t => t.id === task.id)
          if (done) {
            clearInterval(poll)
            const items = await API.getFeed({}, false)
            const fi = items.find(i => i.task_id === task.id)
            updateMsg(pendingId, {
              status: 'done',
              content: fi?.content_markdown ?? 'Task complete.',
              html: fi?.content_html ?? '',
            })
            setSending(false)
            setActiveId(null)
          }
        }, 3000)
        setTimeout(() => clearInterval(poll), 120000) // 2min timeout
      }
    } catch (err) {
      addMsg({ id: nextMsgId(), role: 'assistant', status: 'error', content: err.message, ts: new Date().toISOString() })
      setSending(false)
    }
  }

  return (
    <div className="flex flex-col h-full max-h-[calc(100vh-8rem)] md:max-h-full">
      {/* Top bar */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-jarvis-border shrink-0">
        <div className="flex items-center gap-2 flex-1">
          <Cpu size={15} className="text-jarvis-cyan" />
          <span className="text-xs text-jarvis-muted">Persona:</span>
          <select
            value={persona}
            onChange={e => setPersona(e.target.value)}
            className="bg-transparent text-xs text-jarvis-text outline-none cursor-pointer"
          >
            {PERSONAS.map(p => <option key={p.value} value={p.value}>{p.label}</option>)}
          </select>
        </div>
        <Button variant="ghost" size="xs" onClick={clearChat}>
          <Trash2 size={12} /> Clear
        </Button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 flex flex-col gap-4">
        {chatMessages.length === 0 && (
          <EmptyState
            icon={Bot}
            title="JARVIS is ready"
            description="Delegate a task, ask a question, or start a conversation. I'll use tools as needed and report back."
          />
        )}
        <AnimatePresence>
          {chatMessages.map(msg => <Message key={msg.id} msg={msg} />)}
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
              onKeyDown={e => {
                if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() }
              }}
              placeholder="Delegate a task or ask a question… (Enter to send, Shift+Enter for new line)"
              rows={1}
              disabled={sending}
              className="w-full bg-transparent px-4 py-3 text-sm text-jarvis-text placeholder:text-jarvis-muted/50 outline-none resize-none max-h-32 overflow-y-auto"
              style={{ fieldSizing: 'content' }}
            />
          </div>
          <Button
            variant={sending ? 'ghost' : 'solid'}
            size="md"
            onClick={send}
            disabled={!input.trim() || sending}
            className="shrink-0 h-11"
          >
            {sending ? <Spinner size={16} /> : <Send size={16} />}
          </Button>
        </div>
        <p className="text-[10px] text-jarvis-muted/50 mt-1.5 px-1">
          Messages create background tasks — track progress in the Task Queue.
        </p>
      </div>
    </div>
  )
}
