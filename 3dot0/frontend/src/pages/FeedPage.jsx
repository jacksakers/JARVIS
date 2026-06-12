import { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Inbox, RefreshCw, CheckCheck, ChevronDown, ChevronUp, MessageSquare, Trash2 } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { formatDistanceToNow } from 'date-fns'
import { GlassPanel, Badge, Button, EmptyState, Spinner, SectionHeader, IconButton } from '../components/ui'
import useStore from '../store'
import * as API from '../api'
import clsx from 'clsx'

const FILTERS = ['all', 'briefing', 'report', 'reflection', 'question', 'action', 'error']

// ── FeedItem ──────────────────────────────────────────────────────────────

function FeedItem({ item, onMarkRead, onReply, onDelete }) {
  const [expanded, setExpanded] = useState(item.type === 'question' || !item.is_read)

  return (
    <motion.div
      layout
      initial={{ opacity: 0, x: -12 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 12 }}
      transition={{ duration: 0.2 }}
    >
      <GlassPanel
        className={clsx(
          'overflow-hidden transition-all group',
          !item.is_read && 'border-jarvis-cyan/30',
          item.type === 'question' && 'border-jarvis-amber/30'
        )}
      >
        {/* Header */}
        <div
          className="flex items-start gap-3 p-4 cursor-pointer hover:bg-white/[0.02]"
          onClick={() => { setExpanded(e => !e); if (!item.is_read) onMarkRead(item.id) }}
        >
          {/* Unread dot */}
          <div className="mt-1.5 shrink-0">
            {!item.is_read
              ? <span className="block w-2 h-2 rounded-full bg-jarvis-cyan animate-pulse" />
              : <span className="block w-2 h-2 rounded-full bg-transparent" />
            }
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap mb-1">
              <Badge type={item.type}>{item.type.replace('_', ' ')}</Badge>
              <span className="text-[11px] text-jarvis-muted font-mono">
                {formatDistanceToNow(new Date(item.created_at), { addSuffix: true })}
              </span>
            </div>
            <p className={clsx('text-sm font-medium leading-snug', item.is_read ? 'text-jarvis-muted' : 'text-jarvis-text')}>
              {item.title}
            </p>
          </div>

          <div className="flex items-center gap-1 shrink-0" onClick={e => e.stopPropagation()}>
            <button
              onClick={() => onDelete(item.id)}
              className="opacity-0 group-hover:opacity-100 transition-opacity p-1 text-jarvis-muted hover:text-jarvis-red"
              title="Delete"
            >
              <Trash2 size={13} />
            </button>
            <button className="p-1 text-jarvis-muted hover:text-jarvis-text">
              {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            </button>
          </div>
        </div>

        {/* Expanded content */}
        <AnimatePresence>
          {expanded && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="overflow-hidden"
            >
              <div className="px-5 pb-4 border-t border-jarvis-border pt-4">
                {/* Render pre-built HTML from backend, or fall back to react-markdown */}
                {item.content_html
                  ? <div
                      className="prose prose-sm prose-jarvis max-w-none text-jarvis-text"
                      dangerouslySetInnerHTML={{ __html: item.content_html }}
                    />
                  : <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      className="prose prose-sm prose-jarvis max-w-none"
                    >
                      {item.content_markdown}
                    </ReactMarkdown>
                }

                {/* Reply box for unanswered questions */}
                {item.type === 'question' && !item.reply_text && (
                  <ReplyBox item={item} onReply={onReply} />
                )}
                {/* Show existing reply */}
                {item.type === 'question' && item.reply_text && (
                  <div className="mt-3 text-sm text-jarvis-muted border-t border-jarvis-border pt-3">
                    <span className="text-jarvis-cyan/60 text-xs font-mono">Your reply: </span>
                    {item.reply_text}
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

function ReplyBox({ item, onReply }) {
  const [text, setText] = useState('')
  const [sending, setSending] = useState(false)

  const send = async () => {
    if (!text.trim()) return
    setSending(true)
    await onReply?.(item, text)
    setText('')
    setSending(false)
  }

  return (
    <div className="mt-4 flex gap-2">
      <input
        value={text}
        onChange={e => setText(e.target.value)}
        onKeyDown={e => e.key === 'Enter' && !e.shiftKey && send()}
        placeholder="Type your reply…"
        className="flex-1 glass rounded-lg px-3 py-2 text-sm text-jarvis-text placeholder:text-jarvis-muted/60 outline-none focus:border-jarvis-cyan/50"
      />
      <Button variant="primary" size="sm" onClick={send} disabled={sending || !text.trim()}>
        {sending ? <Spinner size={14} /> : <MessageSquare size={14} />}
        Reply
      </Button>
    </div>
  )
}

// ── FeedPage ──────────────────────────────────────────────────────────────

export default function FeedPage() {
  const mockMode    = useStore(s => s.mockMode)
  const newFeedItem = useStore(s => s.newFeedItem)
  const setUnread   = useStore(s => s.setUnreadCount)
  const decUnread   = useStore(s => s.decrementUnread)
  const setNewFeed  = useStore(s => s.setNewFeedItem)

  const [items, setItems]     = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter]   = useState('all')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await API.getFeed({}, mockMode)
      setItems(data)
      setUnread(data.filter(i => !i.is_read).length)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }, [mockMode])

  useEffect(() => { load() }, [load])

  // Inject live items pushed from mock WS
  useEffect(() => {
    if (newFeedItem) {
      setItems(prev => [newFeedItem, ...prev.filter(i => i.id !== newFeedItem.id)])
      setNewFeed(null)
    }
  }, [newFeedItem])

  const markRead = async (id) => {
    await API.markRead(id, mockMode)
    setItems(prev => prev.map(i => i.id === id ? { ...i, is_read: true } : i))
    decUnread()
  }

  const markAll = async () => {
    await API.markAllRead(mockMode)
    setItems(prev => prev.map(i => ({ ...i, is_read: true })))
    setUnread(0)
  }

  const deleteItem = async (id) => {
    await API.deleteFeedItem(id, mockMode)
    setItems(prev => prev.filter(i => i.id !== id))
    setUnread(prev => Math.max(0, prev))
  }

  const bulkClean = async () => {
    await API.bulkDeleteFeed(true, mockMode)
    await load()
  }

  const handleReply = async (item, text) => {
    await API.replyToQuestion(item.id, text, mockMode)
    setItems(prev => prev.map(i => i.id === item.id ? { ...i, reply_text: text, is_read: true } : i))
  }

  const filtered = filter === 'all' ? items : items.filter(i => i.type === filter)
  const unreadCount = items.filter(i => !i.is_read).length

  return (
    <div className="max-w-3xl mx-auto px-4 py-6">
      <SectionHeader
        title="Activity Feed"
        subtitle={unreadCount > 0 ? `${unreadCount} unread item${unreadCount > 1 ? 's' : ''}` : 'All caught up'}
        actions={
          <div className="flex items-center gap-2">
            {unreadCount > 0 && (
              <Button variant="ghost" size="sm" onClick={markAll}>
                <CheckCheck size={14} /> Mark all read
              </Button>
            )}
            <Button variant="ghost" size="sm" onClick={bulkClean} title="Delete all read items">
              <Trash2 size={14} /> Clean up
            </Button>
            <IconButton icon={RefreshCw} label="Refresh" onClick={load} className={loading ? 'animate-spin-slow' : ''} />
          </div>
        }
      />

      {/* Filter tabs */}
      <div className="flex gap-1 overflow-x-auto pb-1 mb-4 scrollbar-none">
        {FILTERS.map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={clsx(
              'px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-colors shrink-0',
              filter === f
                ? 'bg-jarvis-cyan/15 text-jarvis-cyan border border-jarvis-cyan/30'
                : 'text-jarvis-muted hover:text-jarvis-text hover:bg-white/5 border border-transparent'
            )}
          >
            {f === 'all' ? 'All' : f.replace('_', ' ')}
            {f === 'all' && items.length > 0 && (
              <span className="ml-1.5 text-jarvis-muted">{items.length}</span>
            )}
          </button>
        ))}
      </div>

      {/* List */}
      {loading ? (
        <div className="flex justify-center py-20"><Spinner size={24} /></div>
      ) : filtered.length === 0 ? (
        <EmptyState icon={Inbox} title="Nothing here yet" description="Reports and briefings from your automations will appear here." />
      ) : (
        <div className="flex flex-col gap-3">
          <AnimatePresence mode="popLayout">
            {filtered.map(item => (
              <FeedItem key={item.id} item={item} onMarkRead={markRead} onReply={handleReply} onDelete={deleteItem} />
            ))}
          </AnimatePresence>
        </div>
      )}
    </div>
  )
}
