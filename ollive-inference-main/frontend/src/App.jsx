import { useState } from 'react'
import { MessageSquare, BarChart2, Zap } from 'lucide-react'
import ConversationSidebar from './components/conversations/Sidebar'
import ChatWindow from './components/chat/ChatWindow'
import Dashboard from './components/dashboard/Dashboard'
import clsx from 'clsx'

export default function App() {
  const [view, setView] = useState('chat')

  return (
    <div className="flex h-screen bg-ollive-bg text-ollive-text overflow-hidden">
      {/* Left nav */}
      <nav className="w-12 flex flex-col items-center py-4 bg-black/40 border-r border-ollive-border gap-1 shrink-0">
        <div className="mb-4">
          <Zap size={18} className="text-ollive-accent" />
        </div>
        <button
          onClick={() => setView('chat')}
          className={clsx(
            'w-9 h-9 rounded-xl flex items-center justify-center transition-colors',
            view === 'chat' ? 'bg-ollive-accent/20 text-ollive-accent' : 'text-ollive-muted hover:text-ollive-text hover:bg-white/5'
          )}
          title="Chat"
        >
          <MessageSquare size={15} />
        </button>
        <button
          onClick={() => setView('dashboard')}
          className={clsx(
            'w-9 h-9 rounded-xl flex items-center justify-center transition-colors',
            view === 'dashboard' ? 'bg-ollive-accent/20 text-ollive-accent' : 'text-ollive-muted hover:text-ollive-text hover:bg-white/5'
          )}
          title="Dashboard"
        >
          <BarChart2 size={15} />
        </button>
      </nav>

      {/* Chat sidebar - only on chat view */}
      {view === 'chat' && <ConversationSidebar />}

      {/* Main content */}
      {view === 'chat' ? <ChatWindow /> : <Dashboard />}
    </div>
  )
}
