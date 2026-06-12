/**
 * Zustand global store.
 * Handles: mock mode toggle, WS event log, live task/feed patches,
 * connection status, unread count, and auth state.
 */
import { create } from 'zustand'
import { MOCK_DEFAULT } from './config'

// Load persisted auth from localStorage
const _storedToken = localStorage.getItem('jarvis_token') || null
const _storedUser  = (() => {
  try { return JSON.parse(localStorage.getItem('jarvis_user') || 'null') }
  catch { return null }
})()

const useStore = create((set, get) => ({
  // ── Mock mode ────────────────────────────────────────────────────────────
  mockMode: MOCK_DEFAULT,
  toggleMock: () => set(s => ({ mockMode: !s.mockMode })),

  // ── Auth ────────────────────────────────────────────────────────────────
  authToken: _storedToken,
  currentUser: _storedUser,
  setAuth: (user, token) => {
    localStorage.setItem('jarvis_token', token)
    localStorage.setItem('jarvis_user', JSON.stringify(user))
    set({ authToken: token, currentUser: user })
  },
  clearAuth: () => {
    localStorage.removeItem('jarvis_token')
    localStorage.removeItem('jarvis_user')
    set({ authToken: null, currentUser: null })
  },
  updateCurrentUser: (user) => {
    localStorage.setItem('jarvis_user', JSON.stringify(user))
    set({ currentUser: user })
  },

  // ── Connection status ─────────────────────────────────────────────────
  wsStatus: 'disconnected', // 'connected' | 'disconnected' | 'mock' | 'error'
  setWsStatus: (wsStatus) => set({ wsStatus }),

  // ── WS event log (debug console) ─────────────────────────────────────
  wsEvents: [],
  addWsEvent: (evt) => set(s => ({ wsEvents: [evt, ...s.wsEvents].slice(0, 200) })),
  clearWsEvents: () => set({ wsEvents: [] }),

  // ── Live feed patches (new items arrive via WS) ────────────────────
  liveNewFeedIds: [],   // IDs of newly arrived feed items not yet fetched
  addLiveFeedId: (id) => set(s => ({ liveNewFeedIds: [...s.liveNewFeedIds, id] })),
  clearLiveFeedIds: () => set({ liveNewFeedIds: [] }),
  newFeedItem: null,    // Full item object if pushed directly from mock
  setNewFeedItem: (item) => set({ newFeedItem: item }),

  // ── Live task state patches ────────────────────────────────────────
  taskPatches: {},      // { [taskId]: partial Task }
  patchTask: (id, patch) => set(s => ({ taskPatches: { ...s.taskPatches, [id]: { ...(s.taskPatches[id] ?? {}), ...patch } } })),

  // ── Unread count ─────────────────────────────────────────────────────
  unreadCount: 2,
  setUnreadCount: (n) => set({ unreadCount: n }),
  incrementUnread: () => set(s => ({ unreadCount: s.unreadCount + 1 })),
  decrementUnread: (n = 1) => set(s => ({ unreadCount: Math.max(0, s.unreadCount - n) })),

  // ── Chat (session-only — not persisted) ───────────────────────────
  chatMessages: [],
  addChatMessage: (msg) => set(s => ({ chatMessages: [...s.chatMessages, msg] })),
  updateChatMessage: (id, patch) => set(s => ({
    chatMessages: s.chatMessages.map(m => m.id === id ? { ...m, ...patch } : m)
  })),
  clearChat: () => set({ chatMessages: [] }),

  // ── Active running task ID (for progress tracking in chat) ────────
  activeTaskId: null,
  setActiveTaskId: (id) => set({ activeTaskId: id }),

  // ── Active conversation ───────────────────────────────────────────
  activeConversationId: null,
  setActiveConversationId: (id) => set({ activeConversationId: id }),
}))

export default useStore

// ── Convenience exports (called from mock.js without circular import issues)

export const addWsEvent  = (evt)  => useStore.getState().addWsEvent(evt)
export const addFeedItem = (item) => {
  useStore.getState().setNewFeedItem(item)
  useStore.getState().addLiveFeedId(item.id)
  useStore.getState().incrementUnread()
}
export const updateTask  = (id, patch) => useStore.getState().patchTask(id, patch)
