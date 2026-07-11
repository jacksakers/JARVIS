import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  GitBranch, GitMerge, GitPullRequest, Folder, Play, X, Check,
  ChevronRight, ChevronDown, Terminal, RefreshCw, AlertCircle, Code2, Trash2,
  MessageSquare, ArrowLeft, FileCode, Copy, Pause,
} from 'lucide-react'
import clsx from 'clsx'
import * as API from '../api'
import useStore from '../store'
import { Spinner, EmptyState } from '../components/ui'
import ModelPicker from '../components/ModelPicker'

// ── Diff viewer ───────────────────────────────────────────────────────────

function DiffViewer({ diff }) {
  if (!diff) return <p className="text-jarvis-muted text-sm">No diff available.</p>

  const lines = diff.split('\n')
  return (
    <div className="font-mono text-xs overflow-x-auto">
      {lines.map((line, i) => {
        let cls = 'text-jarvis-muted/70'
        if (line.startsWith('+++') || line.startsWith('---')) cls = 'text-jarvis-muted font-semibold'
        else if (line.startsWith('+')) cls = 'text-green-400 bg-green-400/5'
        else if (line.startsWith('-')) cls = 'text-red-400 bg-red-400/5'
        else if (line.startsWith('@@')) cls = 'text-jarvis-cyan/70'
        else if (line.startsWith('diff ') || line.startsWith('index ')) cls = 'text-jarvis-muted/50'
        return (
          <div key={i} className={clsx('px-2 py-px whitespace-pre', cls)}>
            {line || ' '}
          </div>
        )
      })}
    </div>
  )
}

// ── Project card ──────────────────────────────────────────────────────────

function ProjectCard({ project, onSelect }) {
  return (
    <motion.div
      whileHover={{ scale: 1.02 }}
      onClick={() => onSelect(project)}
      className="glass rounded-xl p-4 border border-jarvis-border hover:border-jarvis-cyan/40 cursor-pointer transition-colors"
    >
      <div className="flex items-start gap-3">
        <div className="p-2 rounded-lg bg-jarvis-cyan/10 border border-jarvis-cyan/20 shrink-0">
          <Folder size={18} className="text-jarvis-cyan" />
        </div>
        <div className="min-w-0">
          <div className="text-sm font-semibold text-white truncate">{project.name}</div>
          <div className="flex items-center gap-1 mt-1">
            <GitBranch size={11} className="text-jarvis-muted" />
            <span className="text-xs text-jarvis-muted font-mono">{project.branch}</span>
          </div>
          {project.last_commit && (
            <div className="text-[11px] text-jarvis-muted/60 mt-1 truncate font-mono">
              {project.last_commit}
            </div>
          )}
        </div>
      </div>
    </motion.div>
  )
}

// ── PR status badge ───────────────────────────────────────────────────────

function PRBadge({ status }) {
  const map = {
    pending:   { cls: 'bg-amber-500/15 text-amber-400 border-amber-500/30', label: 'Awaiting Review' },
    merged:    { cls: 'bg-green-500/15 text-green-400 border-green-500/30', label: 'Merged' },
    discarded: { cls: 'bg-red-500/15 text-red-400 border-red-500/30', label: 'Discarded' },
  }
  const { cls, label } = map[status] ?? map.pending
  return (
    <span className={clsx('text-[10px] px-2 py-0.5 rounded-full border font-medium', cls)}>
      {label}
    </span>
  )
}

// ── Directory tree viewer ────────────────────────────────────────────────

function TreeViewer({ tree }) {
  const [copiedPath, setCopiedPath] = useState(null)

  const items = useMemo(() => {
    if (!tree) return []
    const lines = tree.split('\n').slice(1) // skip header line
    const result = []
    const pathStack = []

    for (const line of lines) {
      if (!line.trim()) continue
      const depth = Math.floor((line.length - line.trimStart().length) / 2)
      const name = line.trim()
      const isDir = name.endsWith('/')
      const cleanName = isDir ? name.slice(0, -1) : name
      pathStack.length = depth
      pathStack[depth] = cleanName
      const fullPath = pathStack.filter(Boolean).join('/')
      result.push({ name, depth, fullPath, isDir })
    }
    return result
  }, [tree])

  const handleCopy = (path) => {
    const doSet = () => {
      setCopiedPath(path)
      setTimeout(() => setCopiedPath(null), 1500)
    }
    if (navigator.clipboard) {
      navigator.clipboard.writeText(path).then(doSet).catch(() => {
        fallbackCopy(path)
        doSet()
      })
    } else {
      fallbackCopy(path)
      doSet()
    }
  }

  const fallbackCopy = (text) => {
    const el = document.createElement('textarea')
    el.value = text
    el.style.cssText = 'position:fixed;opacity:0;pointer-events:none'
    document.body.appendChild(el)
    el.focus()
    el.select()
    try { document.execCommand('copy') } catch {}
    document.body.removeChild(el)
  }

  if (!items.length) return <p className="text-jarvis-muted text-xs">Tree unavailable.</p>

  return (
    <div className="font-mono text-xs max-h-64 overflow-y-auto">
      {items.map((item, i) => (
        <div
          key={i}
          style={{ paddingLeft: `${item.depth * 14 + 8}px` }}
          className={clsx(
            'flex items-center gap-1.5 py-0.5 rounded group',
            !item.isDir && 'cursor-pointer hover:bg-jarvis-surface/50',
          )}
          onClick={() => !item.isDir && handleCopy(item.fullPath)}
          title={item.isDir ? undefined : `Click to copy: ${item.fullPath}`}
        >
          {item.isDir ? (
            <Folder size={10} className="text-jarvis-cyan/60 shrink-0" />
          ) : (
            <FileCode size={10} className="text-jarvis-muted/60 shrink-0" />
          )}
          <span className={item.isDir ? 'text-jarvis-muted/80' : 'text-white/70 group-hover:text-white'}>
            {item.name}
          </span>
          {!item.isDir && (
            <span className={clsx(
              'ml-auto pr-2 transition-opacity text-[10px]',
              copiedPath === item.fullPath
                ? 'text-green-400 opacity-100'
                : 'text-jarvis-muted/40 opacity-100 sm:opacity-0 sm:group-hover:opacity-100',
            )}>
              {copiedPath === item.fullPath ? 'copied!' : 'copy'}
            </span>
          )}
        </div>
      ))}
    </div>
  )
}

// ── Task progress event ───────────────────────────────────────────────────

function EventLine({ ev }) {

  if (ev.type === 'tool_call') {

    return (

      <div className="flex items-center gap-2 text-xs font-mono py-0.5">

        <Terminal size={11} className="text-jarvis-cyan shrink-0" />

        <span className="text-jarvis-muted">Calling</span>

        <span className="text-jarvis-cyan">{ev.name}</span>

        {ev.args && (

          <span className="text-jarvis-muted/60 truncate max-w-xs">

            ({JSON.stringify(ev.args).slice(0, 80)})

          </span>

        )}

      </div>

    )

  }

  if (ev.type === 'tool_result') {

    return (

      <div className="flex items-center gap-2 text-xs font-mono py-0.5">

        <Check size={11} className="text-green-400 shrink-0" />

        <span className="text-green-400/80 truncate max-w-sm">{String(ev.result ?? '').slice(0, 120)}</span>

      </div>

    )

  }

  if (ev.type === 'thought') {

    return (

      <div className="flex flex-col gap-1 text-xs py-1.5 px-3 bg-amber-500/5 border-l-2 border-amber-500/40 rounded font-mono my-1">

        <span className="text-[10px] text-amber-500/70 uppercase tracking-wider font-semibold">Thinking Process</span>

        <span className="text-jarvis-muted whitespace-pre-wrap">{ev.message}</span>

      </div>

    )

  }

  if (ev.type === 'content_chunk') {

    return (

      <div className="flex items-center gap-2 text-xs py-0.5 font-mono">

        <span className="text-jarvis-muted">{ev.content}</span>

      </div>

    )

  }

  if (ev.type === 'status') {

    return (

      <div className="flex items-center gap-2 text-xs py-0.5">

        <span className="text-jarvis-muted/60">{ev.message}</span>

      </div>

    )

  }

  return null

}

// ── Main DevelopmentPage ──────────────────────────────────────────────────

export default function DevelopmentPage() {
  const mockMode       = useStore(s => s.mockMode)
  const wsEvents       = useStore(s => s.wsEvents)
  const devTaskState   = useStore(s => s.devTaskState)
  const setDevTaskState = useStore(s => s.setDevTaskState)

  const [view, setView] = useState('projects') // 'projects' | 'workspace' | 'pr_review'
  const [projects, setProjects] = useState([])
  const [prs, setPRs] = useState([])
  const [loadingProjects, setLoadingProjects] = useState(true)
  const [selectedProject, setSelectedProject] = useState(null)
  const [description, setDescription] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [activeTaskId, setActiveTaskId] = useState(null)
  const [taskEvents, setTaskEvents] = useState([])
  const [taskStatus, setTaskStatus] = useState(null) // null|'queued'|'running'|'done'|'failed'
  const [activePR, setActivePR] = useState(null)
  const [loadingPR, setLoadingPR] = useState(false)
  const [feedback, setFeedback] = useState('')
  const [actionLoading, setActionLoading] = useState(false)
  const [projectTree, setProjectTree] = useState(null)
  const [treeLoading, setTreeLoading] = useState(false)
  const [treeOpen, setTreeOpen] = useState(false)
  const [selectedModelId, setSelectedModelId] = useState(null)
  const [maxIterations, setMaxIterations] = useState(20)

  const eventsEndRef  = useRef(null)
  const activeTaskRef = useRef(null)
  useEffect(() => { activeTaskRef.current = activeTaskId }, [activeTaskId])

  // ── On mount: load projects/PRs and restore any active task ──────────────
  useEffect(() => {
    setLoadingProjects(true)
    Promise.all([
      API.getDevProjects(mockMode).catch(() => []),
      API.getDevPRs(mockMode).catch(() => []),
      API.getDevActiveTask(mockMode).catch(() => ({ task: null, pr: null })),
    ]).then(([projs, prList, active]) => {
      setProjects(projs)
      setPRs(prList)

      if (active.pr) {
        // A pending PR exists — go straight to review
        const proj = projs.find(p => p.name === active.pr.project_name)
        if (proj) setSelectedProject(proj)
        loadAndShowPR(active.pr.id)
        return
      }
      if (active.task) {
        const { id: taskId, status: taskSt, project_name: projectName, task_events: savedEvents } = active.task
        const proj = projs.find(p => p.name === projectName)
        if (proj) {
          setSelectedProject(proj)
          setActiveTaskId(taskId)
          setTaskStatus(taskSt)
          if (savedEvents && savedEvents.length > 0) {
            setTaskEvents(savedEvents)
          } else {
            setTaskEvents([{ type: 'status', message: `Task #${taskId} is ${taskSt} — waiting for updates…` }])
          }
          setView('workspace')
          // Persist so WS events reconnect correctly
          setDevTaskState({ taskId, projectName, taskStatus: taskSt, prId: null })
          return
        }
      }

      // No active task — check persisted state as fallback
      if (devTaskState?.prId) {
        const pr = prList.find(p => p.id === devTaskState.prId && p.status === 'pending')
        if (pr) {
          const proj = projs.find(p => p.name === devTaskState.projectName)
          if (proj) setSelectedProject(proj)
          loadAndShowPR(pr.id)
        }
      }
    }).finally(() => setLoadingProjects(false))
  }, [mockMode])

  // Auto-scroll events
  useEffect(() => {
    eventsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [taskEvents])

  // WebSocket events
  useEffect(() => {
    if (!wsEvents?.length) return
    const ev = wsEvents[wsEvents.length - 1]
    if (!ev) return
    const { event, data } = ev
    const tid = activeTaskRef.current

    if (event === 'task_started' && data.task_id === tid) {
      setTaskStatus('running')
      const cur = useStore.getState().devTaskState
      if (cur) setDevTaskState({ ...cur, taskStatus: 'running' })
    }
    if (event === 'tool_call' && data.task_id === tid) {
      setTaskEvents(prev => [...prev, { type: 'tool_call', name: data.name, args: data.arguments }])
    }
    if (event === 'tool_result' && data.task_id === tid) {
      setTaskEvents(prev => [...prev, { type: 'tool_result', result: data.result }])
    }
    if (event === 'thought' && data.task_id === tid) {
      setTaskEvents(prev => [...prev, { type: 'thought', message: data.message }])
    }
    if (event === 'content_chunk' && data.task_id === tid) {
      setTaskEvents(prev => [...prev, { type: 'content_chunk', content: data.content }])
    }
    if (event === 'status' && data.task_id === tid) {
      setTaskEvents(prev => [...prev, { type: 'status', message: data.message }])
    }
    if (event === 'task_done' && data.task_id === tid) {
      setTaskStatus('done')
      const cur = useStore.getState().devTaskState
      if (cur) setDevTaskState({ ...cur, taskStatus: 'done' })
      setTaskEvents(prev => [...prev, { type: 'status', message: '✓ Task complete — checking for PR…' }])
      setTimeout(() => refreshPRs(), 1500)
    }
    if (event === 'task_failed' && data.task_id === tid) {
      setTaskStatus('failed')
      const cur = useStore.getState().devTaskState
      if (cur) setDevTaskState({ ...cur, taskStatus: 'failed' })
      setTaskEvents(prev => [
        ...prev,
        { type: 'status', message: `✗ Task failed: ${data.error ?? 'Unknown error'}` },
      ])
    }
    if (event === 'dev_pr_created') {
      refreshPRs()
      const cur = useStore.getState().devTaskState
      if (cur) setDevTaskState({ ...cur, prId: data.pr_id })
      if (data.task_id === tid || view === 'workspace') {
        loadAndShowPR(data.pr_id)
      }
    }
  }, [wsEvents])

  const refreshPRs = useCallback(async () => {
    const list = await API.getDevPRs(mockMode).catch(() => [])
    setPRs(list)
    // If we were in workspace and a new pending PR came in for our project, switch to review
    const pending = list.find(
      p => p.status === 'pending' && p.project_name === selectedProject?.name
    )
    if (pending && view === 'workspace' && taskStatus === 'done') {
      loadAndShowPR(pending.id)
    }
  }, [mockMode, selectedProject, view, taskStatus])

  const loadAndShowPR = async (prId) => {
    setLoadingPR(true)
    try {
      const pr = await API.getDevPR(prId, mockMode)
      setActivePR(pr)
      setView('pr_review')
    } catch {
      // ignore
    } finally {
      setLoadingPR(false)
    }
  }

  const selectProject = (project) => {
    setSelectedProject(project)
    setDescription('')
    setTaskEvents([])
    setTaskStatus(null)
    setActiveTaskId(null)
    setActivePR(null)
    setProjectTree(null)
    setTreeOpen(true)
    // Fetch directory tree
    setTreeLoading(true)
    API.getDevProjectTree(project.name, '.', mockMode)
      .then(res => setProjectTree(res?.tree ?? null))
      .catch(() => setProjectTree(null))
      .finally(() => setTreeLoading(false))
    // Check for an existing pending PR for this project
    const pending = prs.find(p => p.status === 'pending' && p.project_name === project.name)
    if (pending) {
      loadAndShowPR(pending.id)
    } else {
      setView('workspace')
    }
  }
  const submitTask = async () => {
    if (!description.trim() || !selectedProject || submitting) return
    setSubmitting(true)
    setTaskEvents([])
    setTaskStatus('queued')
    try {
      const res = await API.createDevTask(selectedProject.name, description.trim(), mockMode, selectedModelId, maxIterations)
      setActiveTaskId(res.task_id)
      setDevTaskState({ taskId: res.task_id, projectName: selectedProject.name, taskStatus: 'queued', prId: null })
      setTaskEvents([{ type: 'status', message: `Task #${res.task_id} queued…` }])
    } catch (err) {
      setTaskStatus('failed')
      setTaskEvents([{ type: 'status', message: `Failed to queue: ${err.message}` }])
    } finally {
      setSubmitting(false)
    }
  }

  const [pausingTask, setPausingTask] = useState(false)

  const handlePauseTask = async () => {
    if (!activeTaskId || pausingTask) return
    setPausingTask(true)
    try {
      await API.pauseDevTask(activeTaskId, mockMode)
      setTaskEvents(prev => [...prev, { type: 'status', message: 'Pause requested. JARVIS will pause before the next step.' }])
    } catch (err) {
      setTaskEvents(prev => [...prev, { type: 'status', message: `Failed to pause: ${err.message}` }])
    } finally {
      setPausingTask(false)
    }
  }

  const handleMerge = async () => {
    if (!activePR) return
    setActionLoading(true)
    try {
      await API.mergeDevPR(activePR.id, mockMode)
      setDevTaskState(null)
      setView('projects')
      setSelectedProject(null)
      setActivePR(null)
      const list = await API.getDevProjects(mockMode).catch(() => [])
      setProjects(list)
      await refreshPRs()
    } catch (err) {
      alert(`Merge failed: ${err.message}`)
    } finally {
      setActionLoading(false)
    }
  }

  const handleDiscard = async () => {
    if (!activePR || !window.confirm('Discard all changes and delete the branch?')) return
    setActionLoading(true)
    try {
      await API.discardDevPR(activePR.id, mockMode)
      setDevTaskState(null)
      setView('projects')
      setSelectedProject(null)
      setActivePR(null)
      await refreshPRs()
    } catch (err) {
      alert(`Discard failed: ${err.message}`)
    } finally {
      setActionLoading(false)
    }
  }

  const handleCancel = async () => {
    if (!activePR || !window.confirm('Cancel this PR? The branch will not be deleted.')) return
    setActionLoading(true)
    try {
      await API.cancelDevPR(activePR.id, mockMode)
      setDevTaskState(null)
      setActivePR(null)
      await refreshPRs()
      setView('projects')
      setSelectedProject(null)
    } catch (err) {
      alert(`Cancel failed: ${err.message}`)
    } finally {
      setActionLoading(false)
    }
  }
  
  const handleRequestChanges = async () => {
    if (!activePR || !feedback.trim()) return
    setActionLoading(true)
    try {
      const res = await API.requestDevChanges(activePR.id, feedback.trim(), mockMode, selectedModelId)
      setActiveTaskId(res.task_id)
      setDevTaskState({ taskId: res.task_id, projectName: activePR.project_name, taskStatus: 'queued', prId: null })
      setTaskEvents([{ type: 'status', message: 'Change request sent — JARVIS is revising…' }])
      setTaskStatus('queued')
      setFeedback('')
      setView('workspace')
    } catch (err) {
      alert(`Request failed: ${err.message}`)
    } finally {
      setActionLoading(false)
    }
  }

  // ── Render ─────────────────────────────────────────────────────────────

  // PR list sidebar
  const pendingPRs = prs.filter(p => p.status === 'pending')

  return (
    <div className="flex h-full overflow-hidden">
      {/* Left sidebar: PR list */}
      {prs.length > 0 && (
        <div className="hidden lg:flex flex-col w-56 border-r border-jarvis-border bg-jarvis-bg shrink-0">
          <div className="px-3 py-3 border-b border-jarvis-border">
            <span className="text-xs font-semibold text-jarvis-muted uppercase tracking-wider">
              Pull Requests
            </span>
          </div>
          <div className="flex-1 overflow-y-auto p-2 space-y-1">
            {prs.map(pr => (
              <button
                key={pr.id}
                onClick={() => loadAndShowPR(pr.id)}
                className={clsx(
                  'w-full text-left px-3 py-2 rounded-lg text-xs transition-colors',
                  activePR?.id === pr.id
                    ? 'bg-jarvis-cyan/10 border border-jarvis-cyan/20 text-white'
                    : 'text-jarvis-muted hover:text-white hover:bg-jarvis-surface border border-transparent'
                )}
              >
                <div className="font-mono truncate">#{pr.id} {pr.project_name}</div>
                <div className="flex items-center gap-1 mt-0.5">
                  <PRBadge status={pr.status} />
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center gap-3 px-5 py-3 border-b border-jarvis-border shrink-0">
          {view !== 'projects' && (
            <button
              onClick={() => { setView('projects'); setActivePR(null) }}
              className="p-1.5 rounded-lg text-jarvis-muted hover:text-white hover:bg-jarvis-surface transition-colors"
            >
              <ArrowLeft size={14} />
            </button>
          )}
          <Code2 size={15} className="text-jarvis-cyan shrink-0" />
          <span className="text-sm font-medium text-white">
            {view === 'projects' && 'Development'}
            {view === 'workspace' && `${selectedProject?.name} — Workspace`}
            {view === 'pr_review' && `PR #${activePR?.id} — Review`}
          </span>
          {view === 'workspace' && selectedProject && (
            <div className="flex items-center gap-1 ml-auto">
              <GitBranch size={11} className="text-jarvis-muted" />
              <span className="text-xs text-jarvis-muted font-mono">{selectedProject.branch}</span>
            </div>
          )}
          <button
            onClick={() => {
              API.getDevProjects(mockMode).then(setProjects)
              API.getDevPRs(mockMode).then(setPRs)
            }}
            className="ml-auto p-1.5 rounded-lg text-jarvis-muted hover:text-jarvis-cyan transition-colors"
            title="Refresh"
          >
            <RefreshCw size={13} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5">
          {/* ── PROJECTS VIEW ── */}
          {view === 'projects' && (
            <div>
              {loadingProjects ? (
                <div className="flex justify-center py-16"><Spinner /></div>
              ) : projects.length === 0 ? (
                <EmptyState
                  icon={Folder}
                  title="No repositories found"
                  description="Set 'development.root_dir' in config.yaml to point to your projects folder."
                />
              ) : (
                <div>
                  <p className="text-jarvis-muted text-sm mb-4">
                    Select a project to start a development task or review a pending PR.
                  </p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                    {projects.map(p => (
                      <ProjectCard key={p.name} project={p} onSelect={selectProject} />
                    ))}
                  </div>

                  {pendingPRs.length > 0 && (
                    <div className="mt-8">
                      <h3 className="text-xs font-semibold text-jarvis-muted uppercase tracking-wider mb-3">
                        Pending Reviews
                      </h3>
                      <div className="space-y-2">
                        {pendingPRs.map(pr => (
                          <button
                            key={pr.id}
                            onClick={() => loadAndShowPR(pr.id)}
                            className="w-full flex items-center gap-3 px-4 py-3 glass rounded-xl border border-amber-500/25 hover:border-amber-500/50 transition-colors text-left"
                          >
                            <GitPullRequest size={16} className="text-amber-400 shrink-0" />
                            <div className="flex-1 min-w-0">
                              <div className="text-sm text-white truncate">
                                PR #{pr.id} — {pr.project_name}
                              </div>
                              <div className="text-xs text-jarvis-muted truncate">{pr.commit_message}</div>
                            </div>
                            <ChevronRight size={14} className="text-jarvis-muted shrink-0" />
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* ── WORKSPACE VIEW ── */}
          {view === 'workspace' && selectedProject && (
            <div className="max-w-2xl space-y-5">
              {/* Project tree panel */}
              <div className="glass rounded-xl border border-jarvis-border overflow-hidden">
                <button
                  onClick={() => setTreeOpen(o => !o)}
                  className="w-full flex items-center gap-2 px-4 py-2.5 hover:bg-jarvis-surface/30 transition-colors"
                >
                  {treeOpen ? <ChevronDown size={13} className="text-jarvis-muted" /> : <ChevronRight size={13} className="text-jarvis-muted" />}
                  <Folder size={12} className="text-jarvis-cyan" />
                  <span className="text-xs font-semibold text-jarvis-muted uppercase tracking-wider">Project Structure</span>
                  <span className="ml-auto text-[10px] text-jarvis-muted/50">click a file to copy its path</span>
                </button>
                {treeOpen && (
                  <div className="border-t border-jarvis-border px-2 py-2">
                    {treeLoading ? (
                      <p className="text-jarvis-muted text-xs px-2 py-1">Loading…</p>
                    ) : (
                      <TreeViewer tree={projectTree} />
                    )}
                  </div>
                )}
              </div>

              {/* Task input */}
              {!activeTaskId && (
                <div className="glass rounded-xl p-4 border border-jarvis-border">
                  <h3 className="text-sm font-semibold text-white mb-3">Describe the feature</h3>
                  <textarea
                    value={description}
                    onChange={e => setDescription(e.target.value)}
                    onKeyDown={e => { if (e.key === 'Enter' && e.ctrlKey) submitTask() }}
                    placeholder={`e.g. "Add a dark mode toggle to the settings page"`}
                    rows={4}
                    className="w-full bg-jarvis-bg border border-jarvis-border rounded-lg px-3 py-2 text-sm text-white placeholder:text-jarvis-muted/50 outline-none focus:border-jarvis-cyan/50 resize-y"
                  />
                  <div className="flex items-center justify-between mt-3 gap-2 flex-wrap">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-xs text-jarvis-muted">Ctrl+Enter to submit</span>
                      <ModelPicker
                        value={selectedModelId}
                        onChange={setSelectedModelId}
                        placeholder="Default model"
                      />
                      <div className="flex items-center gap-1.5">
                        <span className="text-xs text-jarvis-muted">Max iterations</span>
                        <input
                          type="number"
                          min={1}
                          max={200}
                          value={maxIterations}
                          onChange={e => setMaxIterations(Math.max(1, Math.min(200, parseInt(e.target.value) || 1)))}
                          className="w-16 bg-jarvis-bg border border-jarvis-border rounded px-2 py-1 text-xs text-white text-center outline-none focus:border-jarvis-cyan/50"
                        />
                      </div>
                    </div>
                    <button
                      onClick={submitTask}
                      disabled={!description.trim() || submitting}
                      className="flex items-center gap-2 px-4 py-2 rounded-lg bg-jarvis-cyan text-black text-sm font-semibold hover:bg-opacity-80 disabled:opacity-40 transition-all"
                    >
                      <Play size={13} />
                      {submitting ? 'Queuing…' : 'Start Task'}
                    </button>
                  </div>
                </div>
              )}

              {/* Progress events */}
              {taskEvents.length > 0 && (
                <div className="glass rounded-xl border border-jarvis-border overflow-hidden">
                  <div className="flex items-center gap-2 px-4 py-2 border-b border-jarvis-border">
                    <Terminal size={12} className="text-jarvis-cyan" />
                    <span className="text-xs font-semibold text-jarvis-muted uppercase tracking-wider">
                      Progress
                    </span>
                    {taskStatus === 'running' && (
                      <div className="ml-auto flex items-center gap-3">
                        <span className="flex items-center gap-1.5 text-xs text-jarvis-cyan">
                          <span className="w-1.5 h-1.5 rounded-full bg-jarvis-cyan animate-pulse" />
                          Working…
                        </span>
                        <button
                          onClick={handlePauseTask}
                          disabled={pausingTask}
                          className="flex items-center gap-1 px-2 py-0.5 rounded border border-amber-500/50 text-[10px] text-amber-500 font-semibold uppercase hover:bg-amber-500/10 disabled:opacity-40 transition-all cursor-pointer"
                        >
                          <Pause size={10} />
                          {pausingTask ? 'Pausing…' : 'Pause & Feedback'}
                        </button>
                      </div>
                    )}
                    {taskStatus === 'done' && (
                      <span className="ml-auto text-xs text-green-400">Complete</span>
                    )}
                    {taskStatus === 'failed' && (
                      <span className="ml-auto text-xs text-red-400">Failed</span>
                    )}
                  </div>
                  <div className="p-3 max-h-64 overflow-y-auto space-y-0.5">
                    <AnimatePresence initial={false}>
                      {taskEvents.map((ev, i) => (
                        <motion.div
                          key={i}
                          initial={{ opacity: 0, y: 4 }}
                          animate={{ opacity: 1, y: 0 }}
                        >
                          <EventLine ev={ev} />
                        </motion.div>
                      ))}
                    </AnimatePresence>
                    <div ref={eventsEndRef} />
                  </div>
                </div>
              )}

              {/* New task button after completion */}
              {taskStatus === 'done' && (
                <button
                  onClick={() => {
                    setActiveTaskId(null)
                    setTaskEvents([])
                    setTaskStatus(null)
                    setDescription('')
                  }}
                  className="text-sm text-jarvis-muted hover:text-jarvis-cyan transition-colors"
                >
                  + Start another task
                </button>
              )}
            </div>
          )}

          {/* ── PR REVIEW VIEW ── */}
          {view === 'pr_review' && (
            loadingPR ? (
              <div className="flex justify-center py-16"><Spinner /></div>
            ) : activePR ? (
              <div className="max-w-4xl space-y-5">
                {/* PR header */}
                <div className="glass rounded-xl p-4 border border-jarvis-border">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <GitPullRequest size={16} className="text-jarvis-cyan" />
                        <span className="text-sm font-semibold text-white">
                          PR #{activePR.id} — {activePR.project_name}
                        </span>
                        <PRBadge status={activePR.status} />
                      </div>
                      <div className="flex items-center gap-2 text-xs text-jarvis-muted">
                        <GitBranch size={11} />
                        <span className="font-mono">{activePR.branch_name}</span>
                      </div>
                      <p className="text-sm text-jarvis-text/80 mt-2">{activePR.commit_message}</p>
                    </div>
                  </div>
                </div>

                {/* Diff viewer */}
                <div className="glass rounded-xl border border-jarvis-border overflow-hidden">
                  <div className="flex items-center gap-2 px-4 py-2 border-b border-jarvis-border bg-jarvis-surface/30">
                    <Code2 size={12} className="text-jarvis-cyan" />
                    <span className="text-xs font-semibold text-jarvis-muted uppercase tracking-wider">
                      Files Changed
                    </span>
                  </div>
                  <div className="overflow-x-auto max-h-[55vh] overflow-y-auto p-3">
                    <DiffViewer diff={activePR.diff} />
                  </div>
                </div>

                {/* Actions (only for pending PRs) */}
                {activePR.status === 'pending' && (
                  <div className="space-y-4">
                    <div className="flex flex-wrap gap-3">
                      <button
                        onClick={handleMerge}
                        disabled={actionLoading}
                        className="flex items-center gap-2 px-4 py-2 rounded-lg bg-green-500/15 border border-green-500/30 text-green-400 text-sm font-semibold hover:bg-green-500/25 disabled:opacity-50 transition-all"
                      >
                        <GitMerge size={14} />
                        Merge & Delete Branch
                      </button>
                      <button
                        onClick={handleDiscard}
                        disabled={actionLoading}
                        className="flex items-center gap-2 px-4 py-2 rounded-lg bg-red-500/15 border border-red-500/30 text-red-400 text-sm font-semibold hover:bg-red-500/25 disabled:opacity-50 transition-all"
                      >
                        <Trash2 size={14} />
                        Discard
                      </button>
                      <button
                        onClick={handleCancel}
                        disabled={actionLoading}
                        className="flex items-center gap-2 px-4 py-2 rounded-lg bg-jarvis-surface border border-jarvis-border text-jarvis-muted text-sm font-semibold hover:text-white hover:border-jarvis-muted disabled:opacity-50 transition-all"
                        title="Dismiss this PR record without touching Git — use when the branch no longer exists"
                      >
                        <X size={14} />
                        Cancel PR
                      </button>
                    </div>
                    {/* Request Changes */}
                    <div className="glass rounded-xl p-4 border border-jarvis-border">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <MessageSquare size={13} className="text-jarvis-muted" />
                          <span className="text-sm font-semibold text-white">Request Changes</span>
                        </div>
                        <ModelPicker
                          value={selectedModelId}
                          onChange={setSelectedModelId}
                          placeholder="Model for revisions"
                          compact
                        />
                      </div>
                      <textarea
                        value={feedback}
                        onChange={e => setFeedback(e.target.value)}
                        placeholder="Describe what needs to be changed…"
                        rows={3}
                        className="w-full bg-jarvis-bg border border-jarvis-border rounded-lg px-3 py-2 text-sm text-white placeholder:text-jarvis-muted/50 outline-none focus:border-jarvis-cyan/50 resize-y"
                      />
                      <div className="flex justify-end mt-2">
                        <button
                          onClick={handleRequestChanges}
                          disabled={!feedback.trim() || actionLoading}
                          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-amber-500/15 border border-amber-500/30 text-amber-400 text-sm font-semibold hover:bg-amber-500/25 disabled:opacity-40 transition-all"
                        >
                          <Play size={13} />
                          Send Back to JARVIS
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <EmptyState icon={GitPullRequest} title="PR not found" description="It may have been merged or discarded." />
            )
          )}
        </div>
      </div>
    </div>
  )
}
