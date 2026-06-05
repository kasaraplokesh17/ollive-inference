import { create } from 'zustand'

export const useStore = create((set, get) => ({
  // Conversations list
  conversations: [],
  activeConversationId: null,
  activeMessages: [],
  loadingConversations: false,
  streaming: false,

  // Settings
  provider: 'anthropic',
  model: null,

  setProvider: (provider) => set({ provider, model: null }),
  setModel: (model) => set({ model }),

  setActiveConversation: (id) => set({ activeConversationId: id }),

  setConversations: (conversations) => set({ conversations }),

  addMessage: (msg) => set((s) => ({ activeMessages: [...s.activeMessages, msg] })),

  setActiveMessages: (msgs) => set({ activeMessages: msgs }),

  appendToLastMessage: (token) => set((s) => {
    const msgs = [...s.activeMessages]
    if (msgs.length === 0) return {}
    const last = { ...msgs[msgs.length - 1] }
    last.content = (last.content || '') + token
    msgs[msgs.length - 1] = last
    return { activeMessages: msgs }
  }),

  setStreaming: (v) => set({ streaming: v }),

  updateConversationStatus: (id, status) => set((s) => ({
    conversations: s.conversations.map((c) =>
      c.id === id ? { ...c, status } : c
    )
  })),

  clearActiveConversation: () => set({
    activeConversationId: null,
    activeMessages: [],
  }),
}))
