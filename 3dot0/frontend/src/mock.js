/**
 * Mock data and handlers for UI/UX testing without a live backend.
 * All functions return realistic data with artificial latency.
 * The mock WebSocket simulation is exported as `startMockWS`.
 */
import { addWsEvent, addFeedItem, updateTask } from './store'

// ── IDs ───────────────────────────────────────────────────────────────────

let _nextId = 100
export const nextId = () => ++_nextId

// ── Delay ─────────────────────────────────────────────────────────────────

const delay = (ms = 200) => new Promise(r => setTimeout(r, ms))

// ── Seed data ─────────────────────────────────────────────────────────────

const now = new Date()
const ago = m => new Date(now - m * 60 * 1000).toISOString()

export const MOCK_USER = { id: 1, name: 'Commander', is_primary: true, created_at: ago(10000) }

export const MOCK_SKILLS = [
  { id: 1, name: 'get_system_time', description: 'Returns the current local date and time.',         module_name: 'SystemTimeSkill',  updated_at: ago(5000) },
  { id: 2, name: 'calculate',       description: 'Safely evaluates a mathematical expression.',     module_name: 'CalculatorSkill',  updated_at: ago(5000) },
  { id: 3, name: 'save_memory',     description: 'Saves a fact to long-term memory.',               module_name: 'SaveMemorySkill',  updated_at: ago(5000) },
  { id: 4, name: 'search_memory',   description: 'Searches long-term memory for stored facts.',     module_name: 'SearchMemorySkill',updated_at: ago(5000) },
]

let _routines = [
  { id: 1, user_id: 1, name: 'Morning Briefing',    description: 'Daily 6 AM summary of time, priorities, and reminders.',  trigger_type: 'cron', trigger_value: '0 6 * * *',   system_prompt: 'You are JARVIS morning briefer. Provide a concise daily briefing. Start with the current time, then list top priorities for the day, and any reminders.', allowed_skill_names: '["get_system_time","search_memory"]', active: true,  created_at: ago(2880), updated_at: ago(100) },
  { id: 2, user_id: 1, name: 'Evening Reflection',  description: 'Daily 8 PM analysis of unprocessed journal entries.',     trigger_type: 'cron', trigger_value: '0 20 * * *',  system_prompt: 'You are a thoughtful philosophical analyst. Review the user\'s recent journal entries, connect themes, challenge assumptions gently, and offer fresh perspectives in a Reflection Report.', allowed_skill_names: '["search_memory"]', active: true,  created_at: ago(2000), updated_at: ago(80) },
  { id: 3, user_id: 1, name: 'Hourly News Digest',  description: 'Quick summary of new messages and events every hour.',    trigger_type: 'cron', trigger_value: '0 * * * *',   system_prompt: 'You are JARVIS news desk. Briefly summarize any important events or messages from the last hour. Be very concise — bullet points only.', allowed_skill_names: '["get_system_time"]', active: false, created_at: ago(1440), updated_at: ago(30) },
  { id: 4, user_id: 1, name: 'Weekly Review',       description: 'Monday 9 AM retrospective and week-ahead planning.',      trigger_type: 'cron', trigger_value: '0 9 * * 1',   system_prompt: 'You are JARVIS weekly strategist. Summarize last week\'s completed tasks and goals from memory, then help plan the upcoming week with priorities.', allowed_skill_names: '["get_system_time","search_memory","save_memory"]', active: true,  created_at: ago(1200), updated_at: ago(20) },
]

const MORNING_BRIEFING_HTML = `
<h1>Morning Briefing — Monday, June 9, 2026</h1>
<p><strong>Current time:</strong> 06:00 AM</p>
<h2>Today's Priorities</h2>
<ul>
  <li>Review the JARVIS v3.0 frontend build — confirm all features are in place</li>
  <li>Test the WebSocket event stream with the mock backend</li>
  <li>Schedule a 30-minute block for the weekly strategy session</li>
</ul>
<h2>Reminders</h2>
<ul>
  <li>Call the insurance company before 5 PM</li>
  <li>Fiancée's gym class at 7 PM — book a dinner reservation nearby</li>
</ul>
<blockquote><p>Systems nominal. All four routines active. Have a focused day, Commander.</p></blockquote>`

const RESEARCH_HTML = `
<h1>Research Report: Italian Restaurants — Weekend Itinerary</h1>
<p>I've completed my research. Here are the top three options, ranked by suitability:</p>
<h2>1. Osteria del Teatro ⭐⭐⭐⭐⭐</h2>
<p>5-star reviewed, ~20 min drive. Specialises in handmade pasta. Booking recommended — I've found a 7:30 PM slot available Saturday.</p>
<h2>2. La Piazza ⭐⭐⭐⭐</h2>
<p>Excellent wood-fired pizza. 15 min drive. Walk-in friendly, great for a casual evening.</p>
<h2>3. Ristorante Belvedere ⭐⭐⭐⭐</h2>
<p>Rooftop terrace with city views. More upscale. 25 min drive. Perfect for a special occasion.</p>
<h2>Recommendation</h2>
<p><strong>Osteria del Teatro</strong> best matches your request for a nice Italian dinner. Shall I draft a reservation request?</p>`

let _feedItems = [
  { id: 1, user_id: 1, task_id: 10, type: 'briefing',    title: 'Morning Briefing — June 9',       content_markdown: '# Morning Briefing\nGood morning. Systems nominal.', content_html: MORNING_BRIEFING_HTML, is_read: true,  created_at: ago(30) },
  { id: 2, user_id: 1, task_id: 11, type: 'report',      title: 'Italian Restaurant Research',     content_markdown: '# Research Report', content_html: RESEARCH_HTML, is_read: false, created_at: ago(120) },
  { id: 3, user_id: 1, task_id: 12, type: 'reflection',  title: 'Evening Reflection — June 8',    content_markdown: '# Evening Reflection\nYesterday you mentioned feeling...', content_html: '<h1>Evening Reflection</h1><p>You mentioned feeling drained after back-to-back meetings on June 8. This is the third Monday this month with the same note. It may be worth protecting your Monday mornings as focus blocks.</p><p>Your note about the "solar hydroponics" idea connects interestingly with last week\'s thought about sustainability. Worth exploring further?</p>', is_read: false, created_at: ago(750) },
  { id: 4, user_id: 1, task_id: null, type: 'action',    title: 'Evening Routine Complete',        content_markdown: '# Evening Routine\nSecurity cameras armed.', content_html: '<p>Security cameras armed. Living room lights off. Sleep mode activated at 22:00.</p>', is_read: true, created_at: ago(840) },
]

let _tasks = [
  { id: 10, user_id: 1, routine_id: 1,    prompt: '[Automated routine: Morning Briefing] Execute this routine now.', status: 'done',    error_message: null, created_at: ago(35),  started_at: ago(33), completed_at: ago(30) },
  { id: 11, user_id: 1, routine_id: null, prompt: 'Research Italian restaurants near the city centre for a romantic Saturday evening dinner.', status: 'done', error_message: null, created_at: ago(130), started_at: ago(128), completed_at: ago(120) },
  { id: 12, user_id: 1, routine_id: 2,    prompt: '[Automated routine: Evening Reflection] Execute this routine now.', status: 'done',  error_message: null, created_at: ago(760), started_at: ago(758), completed_at: ago(750) },
  { id: 13, user_id: 1, routine_id: null, prompt: 'Draft a polite but firm follow-up email to the contractor about the delayed quote.', status: 'failed', error_message: 'Ollama connection refused: model not loaded.', created_at: ago(5),   started_at: ago(4),  completed_at: ago(3) },
]

let _categories = [
  { id: 1, user_id: 1, name: 'Personal',  color: '#06b6d4', icon: '🧠', description: 'Thoughts, reflections, and personal notes.',   entry_count: 2, created_at: ago(5000) },
  { id: 2, user_id: 1, name: 'Fitness',   color: '#22c55e', icon: '🏋️', description: 'Workout logs, nutrition, and health tracking.',  entry_count: 2, created_at: ago(4000) },
  { id: 3, user_id: 1, name: 'Shopping',  color: '#f59e0b', icon: '🛒', description: 'Shopping lists and purchase tracking.',           entry_count: 1, created_at: ago(3000) },
  { id: 4, user_id: 1, name: 'Work',      color: '#a855f7', icon: '💼', description: 'Work tasks, meeting notes, and project ideas.',   entry_count: 1, created_at: ago(2000) },
]

let _journal = [
  { id: 1, user_id: 1, category_id: 1, category_name: 'Personal', category_color: '#06b6d4', category_icon: '🧠', title: '', content: 'Thinking about quitting the side project — it\'s taking too much time away from things that actually matter.', pinned: false, processed: true,  llm_readable: true,  llm_editable: false, created_at: ago(1440), updated_at: ago(1440) },
  { id: 2, user_id: 1, category_id: 1, category_name: 'Personal', category_color: '#06b6d4', category_icon: '🧠', title: '', content: 'Had a great lunch with Alex. She suggested trying a completely different framework for the UI — might be worth it.', pinned: false, processed: true,  llm_readable: true,  llm_editable: false, created_at: ago(720), updated_at: ago(720) },
  { id: 3, user_id: 1, category_id: 4, category_name: 'Work',     category_color: '#a855f7', category_icon: '💼', title: '', content: 'Feel like I\'m finally making real progress on JARVIS. The async architecture is clicking.', pinned: true,  processed: false, llm_readable: true,  llm_editable: false, created_at: ago(60),  updated_at: ago(60) },
  { id: 4, user_id: 1, category_id: 3, category_name: 'Shopping', category_color: '#f59e0b', category_icon: '🛒', title: 'Weekly Groceries', content: '- Milk\n- Eggs\n- Coffee (dark roast)\n- Sourdough bread\n- Cherry tomatoes\n- Greek yoghurt', pinned: false, processed: false, llm_readable: true,  llm_editable: true,  created_at: ago(10),  updated_at: ago(10) },
  { id: 5, user_id: 1, category_id: 2, category_name: 'Fitness',  category_color: '#22c55e', category_icon: '🏋️', title: 'Monday Session', content: 'Bench: 5×5 @ 85kg\nOHP: 4×8 @ 55kg\nPull-ups: 4×10\nFelt strong. Sleep was good last night.', pinned: false, processed: true,  llm_readable: true,  llm_editable: false, created_at: ago(480), updated_at: ago(480) },
  { id: 6, user_id: 1, category_id: 2, category_name: 'Fitness',  category_color: '#22c55e', category_icon: '🏋️', title: 'Nutrition Log', content: 'Calories: ~2800\nProtein: 185g\nCarbs: 320g\nFat: 80g\nHydration: 3L', pinned: false, processed: false, llm_readable: true,  llm_editable: true,  created_at: ago(200), updated_at: ago(200) },
]

// ── API mock handlers ─────────────────────────────────────────────────────

export const getMe       = async () => { await delay(); return MOCK_USER }
export const getSkills   = async () => { await delay(); return [...MOCK_SKILLS] }
export const getFeed     = async () => { await delay(); return [..._feedItems].sort((a,b) => b.created_at.localeCompare(a.created_at)) }
export const getTasks    = async () => { await delay(); return [..._tasks].sort((a,b) => b.created_at.localeCompare(a.created_at)) }
export const getRoutines = async () => { await delay(); return [..._routines] }
export const getRoutine  = async (id) => { await delay(); return _routines.find(r => r.id === id) }
export const getJournal  = async (params = {}) => {
  await delay()
  let results = [..._journal]
  if (params.category_id != null) results = results.filter(e => e.category_id === Number(params.category_id))
  if (params.pinned_only === 'true' || params.pinned_only === true) results = results.filter(e => e.pinned)
  if (params.search) {
    const q = params.search.toLowerCase()
    results = results.filter(e => e.content.toLowerCase().includes(q) || (e.title || '').toLowerCase().includes(q))
  }
  const sort = params.sort || 'newest'
  results = results.sort((a, b) => {
    if (a.pinned !== b.pinned) return a.pinned ? -1 : 1
    if (sort === 'oldest') return a.created_at.localeCompare(b.created_at)
    if (sort === 'title')  return (a.title || '').localeCompare(b.title || '')
    if (sort === 'updated') return b.updated_at.localeCompare(a.updated_at)
    return b.created_at.localeCompare(a.created_at)
  })
  return results
}

export const markRead = async (id) => {
  await delay(100)
  const item = _feedItems.find(i => i.id === id)
  if (item) item.is_read = true
  return item
}
export const markAllRead = async () => {
  await delay(100)
  let count = 0
  _feedItems.forEach(i => { if (!i.is_read) { i.is_read = true; count++ } })
  return { marked_read: count }
}

export const submitTask = async (payload) => {
  await delay(150)
  const task = { id: nextId(), user_id: 1, routine_id: payload.routine_id ?? null, prompt: payload.prompt, status: 'queued', error_message: null, created_at: new Date().toISOString(), started_at: null, completed_at: null }
  _tasks.unshift(task)
  simulateTaskRun(task)
  return task
}
export const cancelTask = async (id) => { await delay(100); _tasks = _tasks.filter(t => t.id !== id) }
export const retryTask  = async (id) => {
  await delay(150)
  const orig = _tasks.find(t => t.id === id)
  return submitTask({ prompt: orig?.prompt ?? 'Retry task' })
}

export const createRoutine = async (payload) => {
  await delay(200)
  const r = { id: nextId(), user_id: 1, created_at: new Date().toISOString(), updated_at: new Date().toISOString(), ...payload }
  _routines.push(r)
  return r
}
export const updateRoutine = async (id, data) => {
  await delay(150)
  const idx = _routines.findIndex(r => r.id === id)
  if (idx >= 0) { _routines[idx] = { ..._routines[idx], ...data, updated_at: new Date().toISOString() } }
  return _routines[idx]
}
export const deleteRoutine = async (id) => { await delay(150); _routines = _routines.filter(r => r.id !== id) }
export const runRoutine    = async (id) => {
  await delay(150)
  const r = _routines.find(r => r.id === id)
  return submitTask({ prompt: `[Manual run: ${r?.name ?? 'Routine'}] Execute this routine now and produce a complete report.`, routine_id: id })
}

export const generateRoutine = async (description) => {
  await delay(100)
  // Create a task that will simulate routine generation
  const task = { 
    id: nextId(), 
    user_id: 1, 
    routine_id: null, 
    prompt: `Generate a routine: ${description}`,
    status: 'queued', 
    error_message: null, 
    created_at: new Date().toISOString(), 
    started_at: null, 
    completed_at: null 
  }
  _tasks.unshift(task)
  
  // Simulate routine generation (completes after a delay)
  setTimeout(() => {
    task.status = 'running'
    task.started_at = new Date().toISOString()
  }, 500)
  
  setTimeout(() => {
    // Create a mock generated routine
    const generated = {
      id: nextId(),
      user_id: 1,
      name: 'Generated: ' + description.substring(0, 30),
      description: description,
      trigger_type: 'manual',
      trigger_value: '',
      system_prompt: 'You are a helpful assistant.',
      allowed_skill_names: '[]',
      active: true,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    }
    _routines.push(generated)
    task.status = 'done'
    task.completed_at = new Date().toISOString()
  }, 2000)
  
  return { task_id: task.id, status: 'queued' }
}

export const createJournal = async (payload) => {
  await delay(150)
  const catId = payload.category_id ?? null
  const cat = catId ? _categories.find(c => c.id === catId) : null
  const entry = {
    id: nextId(), user_id: 1, processed: false,
    pinned: payload.pinned ?? false,
    llm_readable: payload.llm_readable ?? true,
    llm_editable: payload.llm_editable ?? false,
    category_name: cat?.name ?? null,
    category_color: cat?.color ?? null,
    category_icon: cat?.icon ?? null,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    ...payload,
  }
  _journal.unshift(entry)
  if (cat) cat.entry_count = (_journal.filter(e => e.category_id === catId)).length
  return entry
}
export const updateJournal = async (id, data) => {
  await delay(100)
  const idx = _journal.findIndex(e => e.id === id)
  if (idx >= 0) {
    const catId = data.category_id !== undefined ? data.category_id : _journal[idx].category_id
    const cat = catId ? _categories.find(c => c.id === catId) : null
    _journal[idx] = {
      ..._journal[idx], ...data,
      category_name: cat?.name ?? null,
      category_color: cat?.color ?? null,
      category_icon: cat?.icon ?? null,
      updated_at: new Date().toISOString(),
    }
    return _journal[idx]
  }
  return null
}
export const deleteJournal = async (id) => { await delay(100); _journal = _journal.filter(e => e.id !== id) }

export const getJournalCategories = async () => { await delay(); return [..._categories] }
export const createJournalCategory = async (payload) => {
  await delay(150)
  const cat = { id: nextId(), user_id: 1, entry_count: 0, created_at: new Date().toISOString(), ...payload }
  _categories.push(cat)
  return cat
}
export const updateJournalCategory = async (id, data) => {
  await delay(100)
  const idx = _categories.findIndex(c => c.id === id)
  if (idx >= 0) _categories[idx] = { ..._categories[idx], ...data }
  return _categories[idx]
}
export const deleteJournalCategory = async (id) => {
  await delay(100)
  _categories = _categories.filter(c => c.id !== id)
  _journal = _journal.map(e => e.category_id === id ? { ...e, category_id: null, category_name: null, category_color: null, category_icon: null } : e)
}

// ── Mock WebSocket simulation ─────────────────────────────────────────────

const MOCK_RESPONSES = [
  `# Task Complete\n\nI've analyzed your request and here is what I found.\n\n## Summary\n\n- Retrieved current system time: **Monday, June 9, 2026 at ${new Date().toLocaleTimeString()}**\n- Searched memory for relevant context\n- Generated a comprehensive response\n\n## Details\n\nAll systems are operating nominally. The task has been completed successfully with no errors detected.\n\n> Ready for your next instruction, Commander.`,
]

export function simulateTaskRun(task) {
  const id = task.id
  const emit = (event, data) => {
    // Push to global store WS event log
    addWsEvent({ event, data: { task_id: id, ...data }, ts: new Date().toISOString() })
    // Also update task state in store
    if (event === 'task_started')  updateTask(id, { status: 'running', started_at: new Date().toISOString() })
    if (event === 'task_done')     updateTask(id, { status: 'done', completed_at: new Date().toISOString() })
    if (event === 'task_failed')   updateTask(id, { status: 'failed', completed_at: new Date().toISOString() })
  }

  setTimeout(() => emit('task_started', {}), 600)
  setTimeout(() => emit('tool_call',    { name: 'get_system_time', arguments: {} }), 1300)
  setTimeout(() => emit('tool_result',  { name: 'get_system_time', result: `Current date and time: ${new Date().toLocaleString()}` }), 1800)
  setTimeout(() => emit('tool_call',    { name: 'search_memory',   arguments: { query: task.prompt.slice(0, 30) } }), 2200)
  setTimeout(() => emit('tool_result',  { name: 'search_memory',   result: 'Found 2 relevant memories.' }), 2700)
  setTimeout(() => {
    const md = MOCK_RESPONSES[0]
    const html = `<h1>Task Complete</h1><p>I've analyzed your request. All systems nominal.</p><ul><li>System time retrieved</li><li>Memory searched</li><li>Response generated</li></ul><blockquote><p>Ready for your next instruction, Commander.</p></blockquote>`
    const feedItem = { id: nextId(), user_id: 1, task_id: id, type: 'report', title: `Report: ${task.prompt.slice(0, 40)}…`, content_markdown: md, content_html: html, is_read: false, created_at: new Date().toISOString() }
    _feedItems.unshift(feedItem)
    addFeedItem(feedItem)
    emit('task_done', { feed_item_id: feedItem.id, title: feedItem.title })
    emit('feed_new',  { id: feedItem.id, title: feedItem.title, type: 'report' })
  }, 4000)
}

// Periodic ambient events (make the debug console feel alive)
export function startAmbientEvents() {
  const ambientMessages = [
    ['system_heartbeat',   { status: 'ok', uptime_s: 3600 }],
    ['scheduler_tick',     { next_job: 'Morning Briefing', in_seconds: 1800 }],
    ['memory_gc',          { freed_entries: 0, total_entries: 47 }],
    ['skill_registry_ok',  { skills_loaded: 4 }],
  ]
  let i = 0
  return setInterval(() => {
    const [event, data] = ambientMessages[i % ambientMessages.length]
    addWsEvent({ event, data, ts: new Date().toISOString() })
    i++
  }, 8000)
}
