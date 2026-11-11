import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Bot, User, Copy, Check, RotateCcw } from 'lucide-react';
import CodeBlock from './CodeBlock';

export default function MessageBubble({ message, onRetry }) {
  const isAssistant = message.role === 'assistant';
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    if (!message.content) return;
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className={`message-row ${message.role}`}>
      <div className={`message-avatar ${message.role}`}>
        {isAssistant ? <Bot size={18} /> : <User size={18} />}
      </div>

      <div className="message-content-box">
        <div className="message-sender-name">
          {isAssistant ? 'Nexa AI' : 'You'}
        </div>

        <div className="message-body">
          {message.content ? (
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                code({ node, inline, className, children, ...props }) {
                  const match = /language-(\w+)/.exec(className || '');
                  const codeValue = String(children).replace(/\n$/, '');
                  return !inline && (match || codeValue.includes('\n')) ? (
                    <CodeBlock
                      language={match ? match[1] : 'text'}
                      value={codeValue}
                    />
                  ) : (
                    <code
                      style={{
                        background: 'rgba(124, 58, 237, 0.15)',
                        color: '#c084fc',
                        padding: '2px 5px',
                        borderRadius: '4px',
                        fontFamily: 'monospace',
                        fontSize: '0.9em',
                      }}
                      {...props}
                    >
                      {children}
                    </code>
                  );
                },
              }}
            >
              {message.content}
            </ReactMarkdown>
          ) : message.isStreaming ? (
            <span style={{ color: '#94a3b8', fontStyle: 'italic' }}>
              Nexa AI is thinking...
            </span>
          ) : null}

          {message.isStreaming && <span className="streaming-cursor" />}
        </div>

        {/* Message Actions */}
        {isAssistant && !message.isStreaming && message.content && (
          <div className="message-actions-bar">
            <button className="msg-action-btn" onClick={handleCopy}>
              {copied ? (
                <>
                  <Check size={12} color="#22c55e" />
                  <span style={{ color: '#22c55e' }}>Copied</span>
                </>
              ) : (
                <>
                  <Copy size={12} />
                  <span>Copy</span>
                </>
              )}
            </button>
            {onRetry && (
              <button className="msg-action-btn" onClick={onRetry}>
                <RotateCcw size={12} />
                <span>Retry</span>
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
