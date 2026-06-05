import { useEffect, useState } from 'react'
import { MessageSquare, Plus, StopCircle, Play, Trash2, RefreshCw } from 'lucide-react'
import { api } from '../../lib/api'
import { useStore } from '../../store'
import { formatDistanceToNow } from 'date-fns'
import clsx from 'clsx'

export default function ConversationSidebar() {
  const {
    conversations, setConversations,
    activeConversationId, setActiveConversation,
    setActiveMessages, clearActiveConversation,
    updateConversationStatus, loadingConversations,
  } = useStore()

  const [loading, setLoading] = useState(false)

  const fetchConversations = async () => {
    setLoading(true)
    try {
      const data = await api.get('/conversations/')
      setConversations(data.conversations)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchConversations()
    const interval = setInterval(fetchConversations, 15000)
    return () => clearInterval(interval)
  }, [])

  const openConversation = async (conv) => {
    try {
      const data = await api.get(`/conversations/${conv.id}`)
      setActiveConversation(conv.id)
      setActiveMessages(data.messages || [])
    } catch (e) {
      console.error(e)
    }
  }

  const cancelConv = async (e, conv) => {
    e.stopPropagation()
    try {
      await api.post(`/conversations/${conv.id}/cancel`, {})
      updateConversationStatus(conv.id, 'cancelled')
    } catch (e) { console.error(e) }
  }

  const resumeConv = async (e, conv) => {
    e.stopPropagation()
    try {
      await api.post(`/conversations/${conv.id}/resume`, {})
      updateConversationStatus(conv.id, 'active')
    } catch (e) { console.error(e) }
  }

  const deleteConv = async (e, conv) => {
    e.stopPropagation()
    try {
      await api.delete(`/conversations/${conv.id}`)
      setConversations(conversations.filter(c => c.id !== conv.id))
      if (activeConversationId === conv.id) clearActiveConversation()
    } catch (e) { console.error(e) }
  }

  return (
    <aside className="w-64 flex flex-col bg-ollive-surface border-r border-ollive-border h-screen">
      <div className="p-4 border-b border-ollive-border flex items-center justify-between">
        <span className="font-mono text-xs text-ollive-accent font-medium tracking-widest uppercase">Conversations</span>
        <div className="flex gap-1">
          <button onClick={fetchConversations} className="p-1.5 rounded hover:bg-ollive-border text-ollive-muted hover:text-ollive-text transition-colors">
            <RefreshCw size={13} />
          </button>
          <button onClick={clearActiveConversation} className="p-1.5 rounded hover:bg-ollive-accent/20 text-ollive-accent transition-colors">
            <Plus size={13} />
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {loading && conversations.length === 0 && (
          <div className="p-4 text-ollive-muted text-xs text-center">Loading...</div>
        )}
        {conversations.length === 0 && !loading && (
          <div className="p-6 text-center">
            <MessageSquare size={28} className="mx-auto mb-2 text-ollive-border" />
            <p className="text-xs text-ollive-muted">No conversations yet</p>
          </div>
        )}
        {conversations.map((conv) => (
          <div
            key={conv.id}
            onClick={() => openConversation(conv)}
            className={clsx(
              'group px-3 py-3 cursor-pointer border-b border-ollive-border/50 hover:bg-white/[0.02] transition-colors',
              activeConversationId === conv.id && 'bg-ollive-accent/10 border-l-2 border-l-ollive-accent'
            )}
          >
            <div className="flex items-start justify-between gap-1">
              <p className="text-xs text-ollive-text line-clamp-2 flex-1 leading-relaxed">
                {conv.title || 'Untitled'}
              </p>
              <div className="flex gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                {conv.status === 'active' ? (
                  <button onClick={(e) => cancelConv(e, conv)} title="Cancel" className="p-1 rounded hover:bg-red-500/20 text-ollive-muted hover:text-red-400 transition-colors">
                    <StopCircle size={11} />
                  </button>
                ) : conv.status === 'cancelled' ? (
                  <button onClick={(e) => resumeConv(e, conv)} title="Resume" className="p-1 rounded hover:bg-green-500/20 text-ollive-muted hover:text-green-400 transition-colors">
                    <Play size={11} />
                  </button>
                ) : null}
                <button onClick={(e) => deleteConv(e, conv)} title="Delete" className="p-1 rounded hover:bg-red-500/20 text-ollive-muted hover:text-red-400 transition-colors">
                  <Trash2 size={11} />
                </button>
              </div>
            </div>
            <div className="flex items-center gap-2 mt-1">
              <span className={clsx(
                'text-[10px] px-1.5 py-0.5 rounded-full font-mono',
                conv.status === 'active' ? 'bg-green-500/15 text-green-400' :
                conv.status === 'cancelled' ? 'bg-red-500/15 text-red-400' :
                'bg-ollive-border text-ollive-muted'
              )}>{conv.status}</span>
              <span className="text-[10px] text-ollive-muted">
                {formatDistanceToNow(new Date(conv.created_at), { addSuffix: true })}
              </span>
            </div>
          </div>
        ))}
      </div>
    </aside>
  )
}
