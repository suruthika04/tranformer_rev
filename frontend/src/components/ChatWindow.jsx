import React, { useRef, useEffect } from 'react';
import { Bot, Sparkles, Terminal, Code2, ArrowRight } from 'lucide-react';
import { useChat } from '../contexts/ChatContext';
import MessageBubble from './MessageBubble';
import ChatInput from './ChatInput';

export default function ChatWindow({ toggleTokenPanel }) {
  const { messages, sendMessage, isStreaming } = useChat();
  const scrollEndRef = useRef(null);

  const scrollToBottom = () => {
    scrollEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const presetPrompts = [
    {
      title: 'Token Filtering Demo',
      desc: 'Write a Python program to add two numbers.',
      prompt: 'Write a Python program to add two numbers.',
    },
    {
      title: 'Attention Mechanism',
      desc: 'Explain multi-head self-attention in Transformer architectures.',
      prompt: 'Explain multi-head self-attention in Transformer architectures with key formulas.',
    },
    {
      title: 'Algorithm Design',
      desc: 'Compare Breadth-First Search and Depth-First Search in Python.',
      prompt: 'Compare Breadth-First Search and Depth-First Search with clean Python examples.',
    },
  ];

  return (
    <div className="chat-window">
      <div className="messages-scroll-area">
        {messages.length === 0 ? (
          <div className="welcome-hero">
            <div className="hero-logo-box">
              <Bot size={36} color="#ffffff" />
            </div>
            <h1 className="hero-title">Welcome to Nexa AI</h1>
            <p className="hero-subtitle">
              Intelligent conversational assistant with real-time confidence-based token evaluation, 
              semantic safety verification, and Google Gemini integration.
            </p>

            <div className="hero-cards-grid">
              {presetPrompts.map((p, idx) => (
                <div
                  key={idx}
                  className="hero-prompt-card"
                  onClick={() => sendMessage(p.prompt)}
                >
                  <div className="hero-card-title">{p.title}</div>
                  <div className="hero-card-desc">{p.desc}</div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg, index) => (
            <MessageBubble
              key={msg.id || index}
              message={msg}
              onRetry={
                msg.role === 'assistant' && index === messages.length - 1
                  ? () => {
                      const lastUserMsg = [...messages].reverse().find((m) => m.role === 'user');
                      if (lastUserMsg) sendMessage(lastUserMsg.content);
                    }
                  : undefined
              }
            />
          ))
        )}
        <div ref={scrollEndRef} />
      </div>

      <ChatInput onSendMessage={sendMessage} toggleTokenPanel={toggleTokenPanel} />
    </div>
  );
}
