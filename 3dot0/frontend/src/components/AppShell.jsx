import { useState, useEffect } from 'react'
import { Outlet } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { Sidebar, MobileNav, TopBar, DesktopTopBar } from './Navigation'
import useStore from '../store'
import { connectWS, connectMockWS, disconnectWS } from '../websocket'

export default function AppShell() {
  const [drawerOpen, setDrawerOpen] = useState(false)
  const mockMode = useStore(s => s.mockMode)

  // Connect / disconnect WS when mode changes
  useEffect(() => {
    if (mockMode) {
      connectMockWS()
    } else {
      connectWS()
    }
    return () => disconnectWS()
  }, [mockMode])

  return (
    <div className="flex h-full bg-jarvis-bg bg-grid scanline">
      {/* Ambient hex glow */}
      <div className="fixed inset-0 bg-hex-glow pointer-events-none" />

      {/* ── Desktop sidebar ─────────────────────────────────────────── */}
      <aside className="hidden md:flex flex-col w-56 shrink-0 glass border-r border-jarvis-border relative z-10">
        <Sidebar />
      </aside>

      {/* ── Mobile sidebar drawer ────────────────────────────────────── */}
      <AnimatePresence>
        {drawerOpen && (
          <>
            <motion.div
              key="backdrop"
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              className="fixed inset-0 bg-black/60 z-40 md:hidden"
              onClick={() => setDrawerOpen(false)}
            />
            <motion.aside
              key="drawer"
              initial={{ x: -240 }} animate={{ x: 0 }} exit={{ x: -240 }}
              transition={{ type: 'spring', damping: 24, stiffness: 220 }}
              className="fixed left-0 top-0 bottom-0 w-60 glass border-r border-jarvis-border z-50 md:hidden"
            >
              <Sidebar onClose={() => setDrawerOpen(false)} />
            </motion.aside>
          </>
        )}
      </AnimatePresence>

      {/* ── Main content area ─────────────────────────────────────────── */}
      <div className="flex flex-col flex-1 min-w-0 relative z-10">
        {/* Mobile top bar */}
        <TopBar onMenuOpen={() => setDrawerOpen(true)} />
        {/* Desktop top bar */}
        <DesktopTopBar />

        {/* Page content */}
        <main className="flex-1 overflow-y-auto">
          <Outlet />
        </main>

        {/* Mobile bottom nav */}
        <MobileNav />
      </div>
    </div>
  )
}
