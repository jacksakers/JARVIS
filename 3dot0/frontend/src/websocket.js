/**
 * WebSocket manager.
 * In live mode: connects to the backend WS endpoint.
 * In mock mode: uses the ambient event simulator from mock.js.
 */
import { WS_URL } from './config'
import useStore from './store'
import { startAmbientEvents } from './mock'

let _ws = null
let _ambientTimer = null

export function connectWS() {
  const store = useStore.getState()
  store.setWsStatus('connecting')

  try {
    _ws = new WebSocket(WS_URL)

    _ws.onopen = () => {
      useStore.getState().setWsStatus('connected')
      useStore.getState().addWsEvent({ event: 'ws_connected', data: { url: WS_URL }, ts: new Date().toISOString() })
    }

    _ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data)
        handleEvent(msg.event, msg.data)
      } catch { /* ignore malformed */ }
    }

    _ws.onerror = () => useStore.getState().setWsStatus('error')

    _ws.onclose = () => {
      useStore.getState().setWsStatus('disconnected')
      useStore.getState().addWsEvent({ event: 'ws_disconnected', data: {}, ts: new Date().toISOString() })
      _ws = null
      // Auto-reconnect after 5s
      setTimeout(() => {
        if (!useStore.getState().mockMode) connectWS()
      }, 5000)
    }
  } catch (err) {
    useStore.getState().setWsStatus('error')
  }
}

export function connectMockWS() {
  disconnectWS()
  useStore.getState().setWsStatus('mock')
  useStore.getState().addWsEvent({ event: 'ws_mock_connected', data: { mode: 'MOCK' }, ts: new Date().toISOString() })
  _ambientTimer = startAmbientEvents()
}

export function disconnectWS() {
  if (_ws) { _ws.close(); _ws = null }
  if (_ambientTimer) { clearInterval(_ambientTimer); _ambientTimer = null }
}

function handleEvent(event, data) {
  const store = useStore.getState()

  // Always log to debug console
  store.addWsEvent({ event, data, ts: new Date().toISOString() })

  // Update derived state
  if (event === 'task_started') {
    store.patchTask(data.task_id, { status: 'running', started_at: new Date().toISOString() })
  }
  if (event === 'task_done') {
    store.patchTask(data.task_id, { status: 'done', completed_at: new Date().toISOString() })
    if (data.feed_item_id) store.addLiveFeedId(data.feed_item_id)
  }
  if (event === 'task_failed') {
    store.patchTask(data.task_id, { status: 'failed', completed_at: new Date().toISOString() })
  }
  if (event === 'feed_new') {
    store.incrementUnread()
  }
  if (event === 'task_queued') {
    store.patchTask(data.task_id, { status: 'queued' })
  }
}
