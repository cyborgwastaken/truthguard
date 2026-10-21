import { useState, useRef, useEffect, useId } from 'react'
import type { FinalAnswer, AnswerStatus } from '../../types'
import { askQuestion, ApiError } from '../../api/client'

// ---- Status badge ----

const STATUS_LABELS: Record<AnswerStatus, string> = {
  resolved: 'Resolved',
  conflict_unresolved: 'Conflict – unresolved',
  insufficient_evidence: 'Insufficient evidence',
  verification_failed: 'Verification failed',
}

function StatusBadge({ status }: { status: AnswerStatus }) {
  return (
    <span className={`answer-badge answer-badge-${status}`} aria-label={`Status: ${STATUS_LABELS[status]}`}>
      {STATUS_LABELS[status]}
    </span>
  )
}

// ---- Message types ----

type UserMessage = { kind: 'user'; text: string; id: string }
type AnswerMessage = { kind: 'answer'; answer: FinalAnswer; id: string }
type ErrorMessage = { kind: 'error'; text: string; id: string }
type LoadingMessage = { kind: 'loading'; id: string }
type Message = UserMessage | AnswerMessage | ErrorMessage | LoadingMessage

// ---- Answer bubble ----

function AnswerBubble({ answer }: { answer: FinalAnswer }) {
  const isInsufficient = answer.status === 'insufficient_evidence'
  return (
    <div className="msg-bubble msg-answer">
      <StatusBadge status={answer.status} />
      <p className="answer-text">
        {isInsufficient
          ? 'The documents don\'t contain enough information to answer this question.'
          : answer.answer}
      </p>
      {answer.resolution_reason && (
        <p className="answer-reason muted">
          <strong>Reason:</strong> {answer.resolution_reason}
        </p>
      )}
      {answer.conflicts_detected > 0 && (
        <p className="answer-conflicts muted">
          {answer.conflicts_detected} conflict{answer.conflicts_detected > 1 ? 's' : ''} detected.
        </p>
      )}
    </div>
  )
}

// ---- Message list ----

function MessageList({ messages }: { messages: Message[] }) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  if (messages.length === 0) {
    return (
      <div className="chat-empty muted" role="status">
        Ask a question about the uploaded documents.
      </div>
    )
  }

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
              <div className="msg-bubble msg-loading" role="status" aria-label="Thinking">
                <span className="typing-dot" />
                <span className="typing-dot" />
                <span className="typing-dot" />
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
        // kind === 'answer'
        return (
          <div key={m.id} className="msg-row msg-row-answer">
            <AnswerBubble answer={m.answer} />
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
      const answer = await askQuestion(question)
      setMessages((prev) =>
        prev.map((m) =>
          m.id === loadingId ? { kind: 'answer', answer, id: nextId() } : m,
        ),
      )
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Request failed. Please try again.'
      setMessages((prev) =>
        prev.map((m) =>
          m.id === loadingId ? { kind: 'error', text: msg, id: nextId() } : m,
        ),
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="chat-page">
      <h1>Chat</h1>
      <p className="muted page-subtitle">
        Ask questions about uploaded documents. Answers include their verification status.
      </p>
      <div className="chat-container">
        <MessageList messages={messages} />
        <InputArea onSend={handleSend} disabled={loading} />
      </div>
      <p className="chat-note muted">
        <strong>Note:</strong> Answers are mocked until the <code>POST /questions</code> endpoint
        lands in T14. The status badges, loading states and error handling are all wired.
      </p>
    </section>
  )
}
