import { Routes, Route, Navigate } from 'react-router-dom'
import AppShell from './components/AppShell'
import FeedPage     from './pages/FeedPage'
import ChatPage     from './pages/ChatPage'
import RoutinesPage from './pages/RoutinesPage'
import TasksPage    from './pages/TasksPage'
import JournalPage  from './pages/JournalPage'
import DebugPage    from './pages/DebugPage'
import SettingsPage from './pages/SettingsPage'
import LoginPage    from './pages/LoginPage'
import useStore     from './store'

function RequireAuth({ children }) {
  const authToken = useStore(s => s.authToken)
  if (!authToken) return <Navigate to="/login" replace />
  return children
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={
        <RequireAuth>
          <AppShell />
        </RequireAuth>
      }>
        <Route index         element={<FeedPage />} />
        <Route path="chat"     element={<ChatPage />} />
        <Route path="routines" element={<RoutinesPage />} />
        <Route path="tasks"    element={<TasksPage />} />
        <Route path="journal"  element={<JournalPage />} />
        <Route path="debug"    element={<DebugPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="*"        element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}

