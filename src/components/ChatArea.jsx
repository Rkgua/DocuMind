import { useState, useRef, useEffect, useCallback } from 'react'
import { Send, Square, Trash2, Sparkles } from 'lucide-react'
import MarkdownRenderer from './MarkdownRenderer'
import ReferencePanel from './ReferencePanel'

function ChatArea({ messages, onSend, onStop, isStreaming, references = {}, onNewChat }) {
  const [input, setInput] = useState('')
  const messagesEndRef = useRef(null)
  const textareaRef = useRef(null)

  // Auto scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Auto resize textarea
  useEffect(() => {
    const ta = textareaRef.current
    if (ta) {
      ta.style.height = 'auto'
      ta.style.height = Math.min(ta.scrollHeight, 200) + 'px'
    }
  }, [input])

  const handleSend = useCallback(() => {
    const text = input.trim()
    if (!text || isStreaming) return
    onSend(text)
    setInput('')
    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }, [input, isStreaming, onSend])

  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }, [handleSend])

  const handleClearContext = useCallback(() => {
    if (onNewChat) onNewChat()
  }, [onNewChat])

  const hasMessages = messages.length > 0

  return (
    <main className="chat-area">
      {/* Header */}
      <div className="chat-header">
        <span className="chat-title">
          {hasMessages ? '当前对话' : '智能文档助手'}
        </span>
        <span className="chat-model-badge">
          <Sparkles size={12} style={{ marginRight: 4, verticalAlign: 'middle' }} />
          RAG 增强
        </span>
      </div>

      {/* Messages */}
      <div className="chat-messages">
        {!hasMessages ? (
          <div className="empty-state">
            <Sparkles size={56} className="empty-icon" />
            <div className="empty-title">DocuMind 智能文档助手</div>
            <div className="empty-subtitle">
              支持对 PDF、DOCX、MD、TXT 等多种格式文档进行智能问答与分析。
              上传文档或输入网页 URL，即可开始提问。
            </div>
          </div>
        ) : (
          <div className="message-container">
            {messages.map((msg, idx) => (
              <div
                key={msg.id || idx}
                className={`message-wrapper ${msg.role}`}
              >
                <div className={`message-bubble ${msg.role}`}>
                  {msg.role === 'ai' || msg.role === 'assistant' ? (
                    <div className="message-content">
                      {msg.content ? (
                        <MarkdownRenderer content={msg.content} />
                      ) : (
                        <span className="typing-cursor" />
                      )}
                      {(msg.role === 'ai' || msg.role === 'assistant') && msg.content && idx === messages.length - 1 && (
                        <ReferencePanel sources={references[msg.id]} />
                      )}
                    </div>
                  ) : (
                    <div style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</div>
                  )}
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input Area */}
      <div className="chat-input-area">
        <div className="chat-input-wrapper">
          <textarea
            ref={textareaRef}
            placeholder="输入您的问题... (Shift+Enter 换行)"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
            disabled={isStreaming}
          />
          <div className="chat-input-actions">
            <button
              className="chat-action-btn"
              onClick={handleClearContext}
              title="清空上下文"
            >
              <Trash2 size={18} />
            </button>
            {isStreaming ? (
              <button
                className="chat-action-btn stop-btn"
                onClick={onStop}
                title="停止生成"
              >
                <Square size={16} />
              </button>
            ) : (
              <button
                className="chat-action-btn send-btn"
                onClick={handleSend}
                disabled={!input.trim()}
                title="发送"
              >
                <Send size={16} />
              </button>
            )}
          </div>
        </div>
        <div className="chat-input-hint">
          Enter 发送 · Shift+Enter 换行
        </div>
      </div>
    </main>
  )
}

export default ChatArea
