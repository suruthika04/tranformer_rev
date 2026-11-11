import React, { useState, useRef, useEffect } from 'react';
import { Send, Paperclip, Sliders, ArrowUp } from 'lucide-react';
import { useChat } from '../contexts/ChatContext';

export default function ChatInput({ onSendMessage, toggleTokenPanel }) {
  const [text, setText] = useState('');
  const { isStreaming, threshold } = useChat();
  const textareaRef = useRef(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 180)}px`;
    }
  }, [text]);

  const handleSubmit = (e) => {
    if (e) e.preventDefault();
    if (!text.trim() || isStreaming) return;
    onSendMessage(text);
    setText('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="bottom-input-container">
      <div className="input-box-wrapper">
        <textarea
          ref={textareaRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Message Nexa AI... (Shift + Enter for new line)"
          rows={1}
          className="chat-textarea"
          disabled={isStreaming}
        />

        <div className="input-toolbar">
          <div className="toolbar-left">
            <button
              type="button"
              className="toolbar-icon-btn"
              title="Attach File"
              onClick={() => alert('File upload: select text, code, or pdf files')}
            >
              <Paperclip size={16} />
            </button>

            <button
              type="button"
              className="toolbar-icon-btn"
              onClick={toggleTokenPanel}
              title="Token Filter Threshold"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                fontSize: '11px',
                color: '#a855f7',
                padding: '4px 8px',
                background: 'rgba(124, 58, 237, 0.1)',
                border: '1px solid rgba(124, 58, 237, 0.25)',
                borderRadius: '12px',
              }}
            >
              <Sliders size={13} />
              <span>Threshold: {parseFloat(threshold).toFixed(2)}</span>
            </button>
          </div>

          <button
            type="button"
            className="send-message-btn"
            onClick={handleSubmit}
            disabled={!text.trim() || isStreaming}
            title="Send Message"
          >
            <ArrowUp size={18} />
          </button>
        </div>
      </div>

      <div className="bottom-disclaimer">
        Nexa AI evaluates token confidence & semantic safety before Gemini API dispatch. Double-check responses.
      </div>
    </div>
  );
}
