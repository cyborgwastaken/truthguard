import { useState, useRef, useEffect, useId } from 'react'
import type { AnswerResponse } from '../../types'
import { askQuestion, ApiError } from '../../api/client'
import { AnswerView, PassageDialog } from './AnswerView'

// ---- Message types ----

type UserMessage = { kind: 'user'; text: string; id: string }
type AnswerMessage = { kind: 'answer'; response: AnswerResponse; id: string }
type ErrorMessage = { kind: 'error'; text: string; id: string }
type LoadingMessage = { kind: 'loading'; id: string }
type Message = UserMessage | AnswerMessage | ErrorMessage | LoadingMessage

// Questions that show each situation the system is built for (they match the fictional sample documents).
const EXAMPLES = [
  { label: 'Superseded policy', question: 'How many days per week can employees work remotely?' },
  { label: 'Equally official sources disagree', question: 'How long do employees have to submit expense receipts?' },
  { label: 'Not in the documents', question: "What is Acme Corp's policy on employee stock options?" },
  { label: 'Different groups, no conflict', question: 'How many remote days per week can managers take versus interns?' },
]

// ---- Message list ----

interface ListProps {
  messages: Message[]
  onOpenPassage: (response: AnswerResponse, chunkId: string) => void
}

function MessageList({ messages, onOpenPassage }: ListProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView?.({ behavior: 'smooth' })
  }, [messages])

  return (
    <div className="chat-messages" role="log" aria-live="polite" aria-label="Conversation">
      {messages.map((m) => {
        if (m.kind === 'user') {
          return (
            <div key={m.id} className="msg-row msg-row-user">
              <div className="msg-bubble msg-user">{m.text}</div>
            </div>
          )
        }
        if (m.kind === 'loading') {
          return (
            <div key={m.id} className="msg-row msg-row-answer">
              <div className="msg-bubble msg-loading" role="status" aria-label="Checking the documents">
                <span className="typing-dot" />
                <span className="typing-dot" />
                <span className="typing-dot" />
                <span className="loading-text">Retrieving sources, drafting an answer and checking it…</span>
              </div>
            </div>
          )
        }
        if (m.kind === 'error') {
          return (
            <div key={m.id} className="msg-row msg-row-answer">
              <div className="msg-bubble msg-error" role="alert">
                <strong>Error:</strong> {m.text}
              </div>
            </div>
          )
        }
        return (
          <div key={m.id} className="msg-row msg-row-answer msg-row-wide">
            <AnswerView response={m.response} onOpenPassage={(chunkId) => onOpenPassage(m.response, chunkId)} />
          </div>
        )
      })}
      <div ref={bottomRef} />
    </div>
  )
}

// ---- Input form ----

interface InputAreaProps {
  onSend: (text: string) => void
  disabled: boolean
}

function InputArea({ onSend, disabled }: InputAreaProps) {
  const inputId = useId()
  const [text, setText] = useState('')

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const trimmed = text.trim()
    if (!trimmed) return
    onSend(trimmed)
    setText('')
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e as unknown as React.FormEvent)
    }
  }

  return (
    <form className="chat-input-form" onSubmit={handleSubmit} aria-label="Send a question">
      <label htmlFor={inputId} className="sr-only">
        Your question
      </label>
      <textarea
        id={inputId}
        className="chat-textarea"
        rows={3}
        placeholder="Ask a question about the documents… (Enter to send, Shift+Enter for new line)"
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        aria-disabled={disabled}
      />
      <button type="submit" className="btn-primary chat-send-btn" disabled={disabled || !text.trim()}>
        Send
      </button>
    </form>
  )
}

// ---- Page ----

let _msgSeq = 0
function nextId() { return String(++_msgSeq) }

export function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([])
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState<{ response: AnswerResponse; chunkId: string } | null>(null)

  async function handleSend(question: string) {
    const userMsgId = nextId()
    const loadingId = nextId()

    setMessages((prev) => [
      ...prev,
      { kind: 'user', text: question, id: userMsgId },
      { kind: 'loading', id: loadingId },
    ])
    setLoading(true)

    try {
      const response = await askQuestion(question)
      setMessages((prev) =>
        prev.map((m) => (m.id === loadingId ? { kind: 'answer', response, id: nextId() } : m)),
      )
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Request failed. Is the backend running?'
      setMessages((prev) =>
        prev.map((m) => (m.id === loadingId ? { kind: 'error', text: msg, id: nextId() } : m)),
      )
    } finally {
      setLoading(false)
    }
  }

  const passage = open ? open.response.verification.passages.find((p) => p.chunk_id === open.chunkId) ?? null : null

  return (
    <section className="chat-page">
      <h1>Chat</h1>
      <p className="muted page-subtitle">
        Ask questions about the uploaded documents. Every answer shows its sources, any conflict between them,
        and why it was decided that way.
      </p>
      <div className="chat-container">
        {messages.length === 0 ? (
          <div className="chat-empty" role="status">
            <div>
              <p className="muted">Ask a question, or try one of these:</p>
              <ul className="examples">
                {EXAMPLES.map((e) => (
                  <li key={e.label}>
                    <button type="button" className="example" disabled={loading} onClick={() => handleSend(e.question)}>
                      <span className="example-label">{e.label}</span>
                      <span className="example-question">{e.question}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        ) : (
          <MessageList messages={messages} onOpenPassage={(response, chunkId) => setOpen({ response, chunkId })} />
        )}
        <InputArea onSend={handleSend} disabled={loading} />
      </div>
      {open && passage && (
        <PassageDialog passage={passage} verification={open.response.verification} onClose={() => setOpen(null)} />
      )}
    </section>
  )
}
