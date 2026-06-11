import { Routes, Route, Navigate } from 'react-router-dom'
import AppShell from './components/AppShell'
import FeedPage     from './pages/FeedPage'
import ChatPage     from './pages/ChatPage'
import RoutinesPage from './pages/RoutinesPage'
import TasksPage    from './pages/TasksPage'
import JournalPage  from './pages/JournalPage'
import DebugPage    from './pages/DebugPage'
import SettingsPage from './pages/SettingsPage'

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
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
