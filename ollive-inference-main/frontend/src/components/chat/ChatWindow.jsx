import { useState, useRef, useEffect } from 'react'
import { Send, Bot, User, Zap, ChevronDown } from 'lucide-react'
import { useStore } from '../../store'
import { streamChat } from '../../lib/api'
import clsx from 'clsx'

const PROVIDERS = [
  { id: 'anthropic', label: 'Claude', models: ['claude-3-5-haiku-20241022', 'claude-3-5-sonnet-20241022', 'claude-opus-4-5'] },
  { id: 'openai', label: 'OpenAI', models: ['gpt-4o-mini', 'gpt-4o', 'gpt-4-turbo'] },
  { id: 'google', label: 'Gemini', models: ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-2.0-flash-exp'] },
]

function TypingIndicator() {
  return (
    <div className="flex items-center gap-1 px-1">
      {[0,1,2].map(i => (
        <span key={i} className="typing-dot w-1.5 h-1.5 rounded-full bg-ollive-accent inline-block" />
      ))}
    </div>
  )
}

function Message({ msg, isStreaming }) {
  const isUser = msg.role === 'user'
  return (
    <div className={clsx('flex gap-3 message-enter', isUser ? 'justify-end' : 'justify-start')}>
      {!isUser && (
        <div className="w-7 h-7 rounded-lg bg-ollive-accent/20 flex items-center justify-center shrink-0 mt-0.5">
          <Bot size={14} className="text-ollive-accent" />
        </div>
      )}
      <div className={clsx(
        'max-w-[75%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed',
        isUser
          ? 'bg-ollive-accent/20 text-ollive-text rounded-tr-sm'
          : 'bg-ollive-surface border border-ollive-border text-ollive-text rounded-tl-sm'
      )}>
        {msg.content || (isStreaming ? <TypingIndicator /> : '')}
        {isStreaming && msg.content && <span className="stream-cursor" />}
      </div>
      {isUser && (
        <div className="w-7 h-7 rounded-lg bg-white/10 flex items-center justify-center shrink-0 mt-0.5">
          <User size={14} className="text-ollive-text-dim" />
        </div>
      )}
    </div>
  )
}

export default function ChatWindow() {
  const {
    activeMessages, addMessage, appendToLastMessage, setActiveMessages,
    activeConversationId, setActiveConversation,
    streaming, setStreaming,
    provider, setProvider, model, setModel,
    conversations, setConversations,
  } = useStore()

  const [input, setInput] = useState('')
  const [error, setError] = useState(null)
  const [providerOpen, setProviderOpen] = useState(false)
  const bottomRef = useRef(null)
  const inputRef = useRef(null)

  const currentProvider = PROVIDERS.find(p => p.id === provider) || PROVIDERS[0]
  const currentModel = model || currentProvider.models[0]

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [activeMessages])

  const handleSend = async () => {
    if (!input.trim() || streaming) return
    const text = input.trim()
    setInput('')
    setError(null)

    // Add user message
    addMessage({ role: 'user', content: text, id: Date.now() })
    // Add empty assistant placeholder
    addMessage({ role: 'assistant', content: '', id: Date.now() + 1 })
    setStreaming(true)

    try {
      let convId = activeConversationId
      const gen = streamChat({
        message: text,
        conversation_id: convId,
        provider,
        model: currentModel,
      })

      for await (const event of gen) {
        if (event.type === 'token') {
          appendToLastMessage(event.token)
        } else if (event.type === 'meta') {
          if (!convId) {
            setActiveConversation(event.conversation_id)
            convId = event.conversation_id
          }
        } else if (event.type === 'error') {
          setError(event.message)
        }
      }
    } catch (e) {
      setError(e.message)
    } finally {
      setStreaming(false)
      inputRef.current?.focus()
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="flex-1 flex flex-col h-screen overflow-hidden">
      {/* Header */}
      <div className="px-6 py-3 border-b border-ollive-border flex items-center justify-between bg-ollive-surface/50">
        <div className="flex items-center gap-2">
          <Zap size={14} className="text-ollive-accent" />
          <span className="font-mono text-xs text-ollive-accent tracking-wider uppercase">
            {activeConversationId ? `Session ${activeConversationId.slice(0,8)}...` : 'New Chat'}
          </span>
        </div>

        {/* Provider selector */}
        <div className="relative">
          <button
            onClick={() => setProviderOpen(!providerOpen)}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-ollive-border/60 hover:bg-ollive-border text-xs text-ollive-text-dim hover:text-ollive-text transition-colors font-mono"
          >
            {currentProvider.label} / {currentModel}
            <ChevronDown size={11} />
          </button>
          {providerOpen && (
            <div className="absolute right-0 top-full mt-1 w-56 bg-ollive-surface border border-ollive-border rounded-xl shadow-2xl z-50 overflow-hidden">
              {PROVIDERS.map(p => (
                <div key={p.id}>
                  <div className="px-3 py-1.5 text-[10px] text-ollive-muted font-mono uppercase tracking-widest bg-black/30">{p.label}</div>
                  {p.models.map(m => (
                    <button
                      key={m}
                      onClick={() => { setProvider(p.id); setModel(m); setProviderOpen(false) }}
                      className={clsx(
                        'w-full text-left px-3 py-2 text-xs hover:bg-ollive-accent/10 hover:text-ollive-accent transition-colors font-mono',
                        provider === p.id && currentModel === m ? 'text-ollive-accent bg-ollive-accent/5' : 'text-ollive-text-dim'
                      )}
                    >
                      {m}
                    </button>
                  ))}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-4">
        {activeMessages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center gap-4">
            <div className="w-14 h-14 rounded-2xl bg-ollive-accent/10 flex items-center justify-center">
              <Bot size={28} className="text-ollive-accent" />
            </div>
            <div>
              <p className="text-ollive-text font-medium mb-1">Start a conversation</p>
              <p className="text-xs text-ollive-muted">All inference is logged with latency, tokens, and metadata.</p>
            </div>
          </div>
        )}
        {activeMessages.map((msg, i) => (
          <Message
            key={msg.id || i}
            msg={msg}
            isStreaming={streaming && i === activeMessages.length - 1 && msg.role === 'assistant'}
          />
        ))}
        {error && (
          <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-4 py-2.5">
            {error}
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="px-4 pb-4">
        <div className="flex items-end gap-2 bg-ollive-surface border border-ollive-border rounded-2xl px-4 py-3 focus-within:border-ollive-accent/50 transition-colors">
          <textarea
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Message..."
            rows={1}
            disabled={streaming}
            className="flex-1 bg-transparent text-sm text-ollive-text placeholder:text-ollive-muted resize-none outline-none max-h-32 leading-relaxed disabled:opacity-50"
            style={{ height: 'auto' }}
            onInput={e => {
              e.target.style.height = 'auto'
              e.target.style.height = e.target.scrollHeight + 'px'
            }}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || streaming}
            className="p-2 rounded-xl bg-ollive-accent hover:bg-ollive-accent-hover disabled:opacity-30 disabled:cursor-not-allowed transition-colors shrink-0"
          >
            <Send size={14} className="text-white" />
          </button>
        </div>
        <p className="text-[10px] text-ollive-muted text-center mt-2 font-mono">
          Enter to send · Shift+Enter for newline
        </p>
      </div>
    </div>
  )
}
