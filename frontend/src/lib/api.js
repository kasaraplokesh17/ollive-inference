const BASE = import.meta.env.VITE_API_URL || ''

export const api = {
  async get(path) {
    const r = await fetch(`${BASE}/api/v1${path}`)
    if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
    return r.json()
  },
  async post(path, body) {
    const r = await fetch(`${BASE}/api/v1${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
    return r.json()
  },
  async delete(path) {
    const r = await fetch(`${BASE}/api/v1${path}`, { method: 'DELETE' })
    if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
    return r.json()
  },
}

export async function* streamChat({ message, conversation_id, provider, model }) {
  const r = await fetch(`${BASE}/api/v1/chat/send`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, conversation_id, provider, model, stream: true }),
  })

  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)

  const conversationId = r.headers.get('X-Conversation-ID')
  const reader = r.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop()
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = line.slice(6)
        if (data === '[DONE]') return
        if (data.startsWith('{')) {
          try {
            const json = JSON.parse(data)
            if (json.conversation_id) yield { type: 'meta', conversation_id: json.conversation_id }
          } catch {}
        } else if (!data.startsWith('[ERROR]')) {
          yield { type: 'token', token: data }
        } else {
          yield { type: 'error', message: data }
        }
      }
    }
  }
}
