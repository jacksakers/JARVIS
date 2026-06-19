/**
 * JARVIS API client.
 * All functions accept an optional `mock` flag (from the Zustand store).
 * When mock=true they delegate to the mock layer instead of fetching.
 */
import { API_BASE } from './config'
import * as Mock from './mock'

// ── Low-level fetch wrapper ────────────────────────────────────────────────

async function request(method, path, body, isMock, mockFn) {
  if (isMock) return mockFn()
  const url = `${API_BASE}${path}`
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
    ...(body != null ? { body: JSON.stringify(body) } : {}),
  }
  const res = await fetch(url, opts)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? `HTTP ${res.status}`)
  }
  if (res.status === 204) return null
  return res.json()
}

const get    = (path, mock, fn) => request('GET',    path, null, mock, fn)
const post   = (path, body, mock, fn) => request('POST',   path, body, mock, fn)
const patch  = (path, body, mock, fn) => request('PATCH',  path, body, mock, fn)
const del    = (path, mock, fn)       => request('DELETE', path, null, mock, fn)

// ── Feed ──────────────────────────────────────────────────────────────────

export const getFeed = (params = {}, mock) => {
  const qs = new URLSearchParams(params).toString()
  return get(`/api/v1/feed/?${qs}`, mock, Mock.getFeed)
}
export const markRead      = (id, mock) => post(`/api/v1/feed/${id}/read`,    null, mock, () => Mock.markRead(id))
export const markAllRead   = (mock)     => post('/api/v1/feed/read-all',       null, mock, Mock.markAllRead)
export const deleteFeedItem = (id, mock) => del(`/api/v1/feed/${id}`,          mock, () => null)
export const bulkDeleteFeed = (readOnly = true, mock) =>
  del(`/api/v1/feed/?read_only=${readOnly}`, mock, () => ({ deleted: 0 }))
export const replyToFeedItem = (id, replyText, mock) =>
  post(`/api/v1/feed/${id}/reply`, { reply_text: replyText }, mock, () => null)

// ── Tasks ─────────────────────────────────────────────────────────────────

export const getTasks    = (params = {}, mock) => {
  const qs = new URLSearchParams(params).toString()
  return get(`/api/v1/tasks/?${qs}`, mock, Mock.getTasks)
}
export const submitTask  = (payload, mock)     => post('/api/v1/tasks/',             payload, mock, () => Mock.submitTask(payload))
export const cancelTask  = (id, mock)          => del(`/api/v1/tasks/${id}`,         mock, () => Mock.cancelTask(id))
export const retryTask   = (id, mock)          => post(`/api/v1/tasks/${id}/retry`,  null, mock, () => Mock.retryTask(id))
export const bulkDeleteTasks = (statusFilter = 'done,failed', mock) =>
  del(`/api/v1/tasks/?status_filter=${statusFilter}`, mock, () => ({ deleted: 0 }))

// ── Routines ──────────────────────────────────────────────────────────────

export const getRoutines    = (mock)           => get('/api/v1/routines/',               mock, Mock.getRoutines)
export const getRoutine     = (id, mock)       => get(`/api/v1/routines/${id}`,          mock, () => Mock.getRoutine(id))
export const createRoutine  = (payload, mock)  => post('/api/v1/routines/',       payload, mock, () => Mock.createRoutine(payload))
export const updateRoutine  = (id, data, mock) => patch(`/api/v1/routines/${id}`, data,    mock, () => Mock.updateRoutine(id, data))
export const deleteRoutine  = (id, mock)       => del(`/api/v1/routines/${id}`,          mock, () => Mock.deleteRoutine(id))
export const runRoutine     = (id, mock)       => post(`/api/v1/routines/${id}/run`, null, mock, () => Mock.runRoutine(id))

// ── Journal ───────────────────────────────────────────────────────────────

export const getJournal     = (params = {}, mock) => {
  const qs = new URLSearchParams(params).toString()
  return get(`/api/v1/journal/?${qs}`, mock, Mock.getJournal)
}
export const createJournal  = (payload, mock) => post('/api/v1/journal/', payload, mock, () => Mock.createJournal(payload))
export const updateJournal  = (id, payload, mock) => patch(`/api/v1/journal/${id}`, payload, mock, () => Mock.updateJournal(id, payload))
export const deleteJournal  = (id, mock)      => del(`/api/v1/journal/${id}`, mock, () => Mock.deleteJournal(id))

export const getJournalCategories    = (mock)          => get('/api/v1/journal/categories/', mock, Mock.getJournalCategories)
export const createJournalCategory   = (payload, mock) => post('/api/v1/journal/categories/', payload, mock, () => Mock.createJournalCategory(payload))
export const updateJournalCategory   = (id, data, mock) => patch(`/api/v1/journal/categories/${id}`, data, mock, () => Mock.updateJournalCategory(id, data))
export const deleteJournalCategory   = (id, mock)      => del(`/api/v1/journal/categories/${id}`, mock, () => Mock.deleteJournalCategory(id))

// ── Skills ────────────────────────────────────────────────────────────────

export const getSkills = (mock) => get('/api/v1/skills/', mock, Mock.getSkills)

// ── Users ─────────────────────────────────────────────────────────────────

export const getMe    = (mock)            => get('/api/v1/users/me', mock, Mock.getMe)
export const updateMe = (payload, mock)   => patch('/api/v1/users/me', payload, mock, () => null)
export const getUsers = (mock)            => get('/api/v1/users/', mock, () => [])

// ── Auth ──────────────────────────────────────────────────────────────────

export const login          = (username, password) =>
  post('/api/v1/auth/login', { username, password }, false, () => null)
export const register       = (username, password) =>
  post('/api/v1/auth/register', { username, password }, false, () => null)
export const getAuthMe      = (token)              =>
  get(`/api/v1/auth/me?token=${encodeURIComponent(token)}`, false, () => null)
export const updateAuthMe   = (token, payload)     =>
  request('PATCH', `/api/v1/auth/me?token=${encodeURIComponent(token)}`, payload, false, () => null)
export const logoutAuth     = (token)              =>
  request('POST', `/api/v1/auth/logout?token=${encodeURIComponent(token)}`, null, false, () => null)

// ── Conversations ─────────────────────────────────────────────────────────

export const getConversations   = (mock)           => get('/api/v1/conversations/', mock, () => [])
export const createConversation = (payload, mock)  => post('/api/v1/conversations/', payload, mock, () => null)
export const updateConversation = (id, data, mock) => patch(`/api/v1/conversations/${id}`, data, mock, () => null)
export const deleteConversation = (id, mock)       => del(`/api/v1/conversations/${id}`, mock, () => null)
export const getConversationMessages = (id, mock)  => get(`/api/v1/conversations/${id}/messages`, mock, () => [])
export const sendConversationMessage = (id, content, allowedSkills, mock, modelId) =>
  post(`/api/v1/conversations/${id}/messages`, {
    content,
    ...(allowedSkills !== undefined ? { allowed_skill_names: allowedSkills } : {}),
    ...(modelId ? { model_id: modelId } : {}),
  }, mock, () => null)

// ── Models ────────────────────────────────────────────────────────────────

export const getModels = () => get('/api/v1/models/', false, () => [])

// ── Routines generate ─────────────────────────────────────────────────────

export const generateRoutine = (description, mock) =>
  post('/api/v1/routines/generate', { description }, mock, () => null)

// ── Health ────────────────────────────────────────────────────────────────

export const getHealth = () => get('/health', false, () => ({ status: 'ok' }))

// ── Development ───────────────────────────────────────────────────────────

export const getDevProjects     = (mock)           => get('/api/v1/dev/projects', mock, () => [])
export const getDevActiveTask   = (mock)           => get('/api/v1/dev/active-task', mock, () => ({ task: null, pr: null }))
export const getDevProjectTree  = (name, path, mock) => get(`/api/v1/dev/projects/${encodeURIComponent(name)}/tree?path=${encodeURIComponent(path || '.')}`, mock, () => ({ tree: '' }))
export const getDevPRs          = (mock)           => get('/api/v1/dev/prs', mock, () => [])
export const getDevPR           = (id, mock)       => get(`/api/v1/dev/prs/${id}`, mock, () => null)
export const mergeDevPR         = (id, mock)       => post(`/api/v1/dev/prs/${id}/merge`, null, mock, () => null)
export const discardDevPR       = (id, mock)       => post(`/api/v1/dev/prs/${id}/discard`, null, mock, () => null)
export const cancelDevPR        = (id, mock)       => post(`/api/v1/dev/prs/${id}/cancel`, null, mock, () => null)
export const requestDevChanges  = (id, feedback, mock) => post(`/api/v1/dev/prs/${id}/request-changes`, { feedback }, mock, () => null)
export const createDevTask      = (project_name, description, mock, modelId, maxToolIterations) => post('/api/v1/dev/task', { project_name, description, ...(modelId ? { model_id: modelId } : {}), ...(maxToolIterations ? { max_tool_iterations: maxToolIterations } : {}) }, mock, () => null)
