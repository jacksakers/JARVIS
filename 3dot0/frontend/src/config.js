// Central config — reads from environment or falls back to proxy defaults
export const API_BASE = import.meta.env.VITE_API_URL ?? ''
export const WS_URL   = import.meta.env.VITE_WS_URL  ?? `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`

// Set VITE_MOCK_DEFAULT=true in .env.local to boot in mock mode
export const MOCK_DEFAULT = import.meta.env.VITE_MOCK_DEFAULT === 'true'
