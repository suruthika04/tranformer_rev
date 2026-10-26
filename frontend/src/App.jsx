import React, { useState, useEffect, useRef } from 'react';

// Configurable API base URL with fallback to local development
const rawUrl = import.meta.env.VITE_BACKEND_URL || "http://127.0.0.1:8000";
const API_BASE = rawUrl.replace(/\/+$/, "") + (rawUrl.endsWith("/api") ? "" : "/api");

// 4 clean corporate suggestion prompts for the welcome screen
const SUGGESTION_CARDS = [
  {
    title: "Explain a technical concept",
    description: "Break down self-attention and transformer mechanics",
    prompt: "Explain self-attention in simple terms."
  },
  {
    title: "Help me write Python code",
    description: "Generate structured code with error handling",
    prompt: "Write a Python program to add two numbers."
  },
  {
    title: "Summarize a topic",
    description: "Overview of artificial intelligence and its principles",
    prompt: "What is artificial intelligence?"
  },
  {
    title: "Answer a general question",
    description: "Explore neural networks and learning algorithms",
    prompt: "How do neural networks learn from data?"
  }
];

/**
 * Rich Markdown and Code Renderer for Corporate Chatbot Responses
 */
function MarkdownRenderer({ content }) {
  if (!content) return null;

  // Split content by code blocks: ```lang ... ```
  const codeBlockRegex = /```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g;
  const parts = [];
  let lastIndex = 0;
  let match;

  while ((match = codeBlockRegex.exec(content)) !== null) {
    if (match.index > lastIndex) {
      parts.push({ type: 'text', value: content.substring(lastIndex, match.index) });
    }
    parts.push({
      type: 'code',
      language: match[1] || 'plaintext',
      code: match[2].trimEnd()
    });
    lastIndex = codeBlockRegex.lastIndex;
  }

  if (lastIndex < content.length) {
    parts.push({ type: 'text', value: content.substring(lastIndex) });
  }

  return (
    <div className="space-y-3 leading-relaxed text-slate-800 text-[14px]">
      {parts.map((part, idx) => {
        if (part.type === 'code') {
          return <CodeBlock key={idx} language={part.language} code={part.code} />;
        }
        return <FormattedTextBlock key={idx} text={part.value} />;
      })}
    </div>
  );
}

/**
 * Polished Code Block with Syntax Styling & Copy Action
 */
function CodeBlock({ language, code }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="my-3 rounded-lg overflow-hidden border border-slate-700 bg-slate-900 text-slate-100 shadow-md">
      <div className="flex items-center justify-between px-4 py-2 bg-slate-800/80 border-b border-slate-700 text-xs font-mono text-slate-400">
        <span className="font-semibold text-slate-300 uppercase tracking-wider">{language}</span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-slate-700/60 hover:bg-slate-700 text-slate-300 hover:text-white transition cursor-pointer text-xs"
        >
          {copied ? (
            <>
              <svg className="w-3.5 h-3.5 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
              </svg>
              <span className="text-emerald-400 font-medium">Copied!</span>
            </>
          ) : (
            <>
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
              <span>Copy code</span>
            </>
          )}
        </button>
      </div>
      <pre className="p-4 overflow-x-auto text-xs font-mono leading-relaxed text-slate-200 whitespace-pre">
        <code>{code}</code>
      </pre>
    </div>
  );
}

/**
 * Text formatter for headings, lists, bold, inline code, and paragraphs
 */
function FormattedTextBlock({ text }) {
  const paragraphs = text.split(/\n\n+/);

  return (
    <>
      {paragraphs.map((para, pIdx) => {
        const trimmed = para.trim();
        if (!trimmed) return null;

        // Headings
        if (trimmed.startsWith('### ')) {
          return <h3 key={pIdx} className="text-base font-bold text-slate-900 mt-3 mb-1.5">{parseInlineFormatting(trimmed.substring(4))}</h3>;
        }
        if (trimmed.startsWith('## ')) {
          return <h2 key={pIdx} className="text-lg font-bold text-slate-900 mt-4 mb-2">{parseInlineFormatting(trimmed.substring(3))}</h2>;
        }
        if (trimmed.startsWith('# ')) {
          return <h1 key={pIdx} className="text-xl font-bold text-slate-900 mt-4 mb-2">{parseInlineFormatting(trimmed.substring(2))}</h1>;
        }

        // Bullet lists
        const lines = trimmed.split('\n');
        if (lines.every(line => line.trim().startsWith('- ') || line.trim().startsWith('* '))) {
          return (
            <ul key={pIdx} className="list-disc pl-5 space-y-1.5 my-2">
              {lines.map((l, lIdx) => (
                <li key={lIdx} className="leading-relaxed">
                  {parseInlineFormatting(l.trim().replace(/^[-*]\s+/, ''))}
                </li>
              ))}
            </ul>
          );
        }

        // Numbered lists
        if (lines.every(line => /^\d+\.\s/.test(line.trim()))) {
          return (
            <ol key={pIdx} className="list-decimal pl-5 space-y-1.5 my-2">
              {lines.map((l, lIdx) => (
                <li key={lIdx} className="leading-relaxed">
                  {parseInlineFormatting(l.trim().replace(/^\d+\.\s+/, ''))}
                </li>
              ))}
            </ol>
          );
        }

        // Standard Paragraph with potential line breaks
        return (
          <p key={pIdx} className="leading-relaxed">
            {lines.map((line, lIdx) => (
              <React.Fragment key={lIdx}>
                {parseInlineFormatting(line)}
                {lIdx < lines.length - 1 && <br />}
              </React.Fragment>
            ))}
          </p>
        );
      })}
    </>
  );
}

/**
 * Parse inline bold (**bold**) and inline code (`code`)
 */
function parseInlineFormatting(text) {
  const parts = [];
  let remaining = text;
  let key = 0;

  while (remaining.length > 0) {
    // Check for inline code `...`
    const codeMatch = remaining.match(/^`([^`]+)`/);
    if (codeMatch) {
      parts.push(
        <code key={key++} className="px-1.5 py-0.5 rounded bg-slate-100 text-blue-700 font-mono text-[13px] border border-slate-200">
          {codeMatch[1]}
        </code>
      );
      remaining = remaining.substring(codeMatch[0].length);
      continue;
    }

    // Check for bold **...**
    const boldMatch = remaining.match(/^\*\*([^*]+)\*\*/);
    if (boldMatch) {
      parts.push(<strong key={key++} className="font-semibold text-slate-900">{boldMatch[1]}</strong>);
      remaining = remaining.substring(boldMatch[0].length);
      continue;
    }

    // Check for italic *...*
    const italicMatch = remaining.match(/^\*([^*]+)\*/);
    if (italicMatch) {
      parts.push(<em key={key++} className="italic text-slate-800">{italicMatch[1]}</em>);
      remaining = remaining.substring(italicMatch[0].length);
      continue;
    }

    // Match until next delimiter
    const nextSpecial = remaining.search(/[`*]/);
    if (nextSpecial === -1) {
      parts.push(remaining);
      break;
    } else if (nextSpecial === 0) {
      // Stray character
      parts.push(remaining[0]);
      remaining = remaining.substring(1);
    } else {
      parts.push(remaining.substring(0, nextSpecial));
      remaining = remaining.substring(nextSpecial);
    }
  }

  return parts;
}

/**
 * Collapsible Token Analysis Accordion below each relevant response
 */
function TokenAnalysisSection({ metrics, threshold, onThresholdChange }) {
  const [isOpen, setIsOpen] = useState(false);
  const [localThreshold, setLocalThreshold] = useState(threshold);

  useEffect(() => {
    setLocalThreshold(threshold);
  }, [threshold]);

  if (!metrics || !metrics.token_analysis) return null;

  // Compute live values based on localThreshold
  const updatedTokens = metrics.token_analysis.map(item => {
    const isRetained = item.confidence >= localThreshold;
    return {
      ...item,
      retained: isRetained,
      status: isRetained ? "Retained" : "Filtered"
    };
  });

  const evaluatedCount = updatedTokens.length;
  const selectedCount = updatedTokens.filter(t => t.retained).length;
  const filteredCount = evaluatedCount - selectedCount;
  const savingPercentage = evaluatedCount > 0 
    ? parseFloat(((filteredCount / evaluatedCount) * 100).toFixed(2)) 
    : 0.0;

  return (
    <div className="mt-3 border border-slate-200 rounded-xl overflow-hidden bg-slate-50/70 transition-all">
      {/* Accordion Header / Toggle */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-3.5 py-2.5 text-left hover:bg-slate-100/80 transition cursor-pointer"
      >
        <div className="flex items-center gap-2">
          <div className="w-5 h-5 rounded-md bg-blue-100 text-blue-700 flex items-center justify-center text-xs font-bold">
            ⚡
          </div>
          <span className="text-xs font-semibold text-slate-700">Token Analysis</span>
          <span className="text-[11px] px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200 font-medium">
            {filteredCount} filtered ({savingPercentage}%)
          </span>
          {metrics.latency_seconds > 0 && (
            <span className="text-[11px] text-slate-500 font-mono hidden sm:inline">
              • {metrics.latency_seconds}s
            </span>
          )}
        </div>

        <div className="flex items-center gap-2 text-slate-400">
          <span className="text-[11px] font-medium hidden sm:inline">{isOpen ? "Hide metrics" : "View metrics"}</span>
          <svg
            className={`w-4 h-4 transform transition-transform ${isOpen ? "rotate-180" : ""}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </button>

      {/* Expanded Analysis Drawer */}
      {isOpen && (
        <div className="p-4 border-t border-slate-200/80 bg-white space-y-4">
          
          {/* Scientific Disclaimer Note */}
          <div className="p-3 bg-blue-50/60 border border-blue-100 rounded-lg text-xs text-blue-900 leading-relaxed">
            <span className="font-semibold text-blue-800">Pre-Attention Confidence Evaluation: </span>
            This module evaluates prompt token informational density using a PyTorch MLP (Embedding → Linear → GELU → Linear → Sigmoid) before self-attention. Full contextual embeddings are passed to the causal model to maintain grammatical and semantic integrity.
          </div>

          {/* Metric Cards Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2.5">
            <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200 text-center">
              <span className="text-[11px] font-medium text-slate-500 block">Input Tokens</span>
              <span className="text-base font-bold text-slate-800 font-mono">{metrics.input_tokens || evaluatedCount}</span>
            </div>

            <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200 text-center">
              <span className="text-[11px] font-medium text-slate-500 block">Output Tokens</span>
              <span className="text-base font-bold text-slate-800 font-mono">{metrics.output_tokens || 0}</span>
            </div>

            <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200 text-center">
              <span className="text-[11px] font-medium text-slate-500 block">Evaluated</span>
              <span className="text-base font-bold text-slate-800 font-mono">{evaluatedCount}</span>
            </div>

            <div className="p-2.5 rounded-lg bg-emerald-50/80 border border-emerald-200 text-center">
              <span className="text-[11px] font-medium text-emerald-700 block">Selected</span>
              <span className="text-base font-bold text-emerald-800 font-mono">{selectedCount}</span>
            </div>

            <div className="p-2.5 rounded-lg bg-rose-50/80 border border-rose-200 text-center">
              <span className="text-[11px] font-medium text-rose-700 block">Filtered</span>
              <span className="text-base font-bold text-rose-800 font-mono">{filteredCount}</span>
            </div>

            <div className="p-2.5 rounded-lg bg-indigo-50/80 border border-indigo-200 text-center">
              <span className="text-[11px] font-medium text-indigo-700 block">Saving %</span>
              <span className="text-base font-bold text-indigo-800 font-mono">{savingPercentage}%</span>
            </div>
          </div>

          {/* Threshold Sensitivity Slider */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3 bg-slate-50 rounded-lg border border-slate-200 text-xs">
            <div className="flex items-center gap-2">
              <span className="font-semibold text-slate-700">Adaptive Selection Threshold:</span>
              <span className="font-mono font-bold text-blue-700 bg-blue-50 px-2 py-0.5 rounded border border-blue-200">
                {parseFloat(localThreshold).toFixed(2)}
              </span>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-[11px] text-slate-400">0.00</span>
              <input
                type="range"
                min="0.00"
                max="1.00"
                step="0.05"
                value={localThreshold}
                onChange={(e) => {
                  const val = parseFloat(e.target.value);
                  setLocalThreshold(val);
                  if (onThresholdChange) onThresholdChange(val);
                }}
                className="w-36 h-1.5 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
              />
              <span className="text-[11px] text-slate-400">1.00</span>
            </div>
          </div>

          {/* Token Visualization Table */}
          <div className="border border-slate-200 rounded-lg overflow-hidden">
            <div className="max-h-56 overflow-y-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead className="bg-slate-50 sticky top-0 border-b border-slate-200 text-slate-600 font-semibold">
                  <tr>
                    <th className="py-2 px-3 w-12">#</th>
                    <th className="py-2 px-3">Token</th>
                    <th className="py-2 px-3 w-48">Confidence Score</th>
                    <th className="py-2 px-3 w-28">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {updatedTokens.map((item, idx) => (
                    <tr key={idx} className="hover:bg-slate-50/70 transition">
                      <td className="py-1.5 px-3 text-slate-400 font-mono text-[11px]">{idx + 1}</td>
                      <td className="py-1.5 px-3 font-mono font-medium text-slate-800">
                        <span className="px-1.5 py-0.5 rounded bg-slate-100 border border-slate-200">
                          {item.token}
                        </span>
                      </td>
                      <td className="py-1.5 px-3 font-mono">
                        <div className="flex items-center gap-2">
                          <div className="w-20 bg-slate-100 rounded-full h-1.5 border border-slate-200 overflow-hidden">
                            <div
                              className={`h-full ${item.retained ? "bg-emerald-500" : "bg-slate-400"}`}
                              style={{ width: `${Math.min(100, item.confidence * 100)}%` }}
                            />
                          </div>
                          <span className="font-semibold text-slate-700">{item.confidence.toFixed(3)}</span>
                        </div>
                      </td>
                      <td className="py-1.5 px-3">
                        {item.retained ? (
                          <span className="inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200">
                            ✓ Retained
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded bg-rose-50 text-rose-700 border border-rose-200">
                            × Filtered
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

        </div>
      )}
    </div>
  );
}

/**
 * Main Application Component
 */
export default function App() {
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [threshold, setThreshold] = useState(0.50);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [modelStatus, setModelStatus] = useState({ online: false, name: 'Connecting...' });
  const [copiedId, setCopiedId] = useState(null);

  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);

  // Auto-scroll to bottom of conversation
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  // Check backend health on initial load
  useEffect(() => {
    const checkHealth = async () => {
      try {
        const res = await fetch(`${API_BASE}/health`);
        if (res.ok) {
          const data = await res.json();
          setModelStatus({
            online: data.model_loaded,
            name: data.model_name || 'Active'
          });
        } else {
          setModelStatus({ online: false, name: 'Offline' });
        }
      } catch (err) {
        setModelStatus({ online: false, name: 'Offline' });
      }
    };
    checkHealth();
  }, []);

  // Handle message submission
  const handleSendMessage = async (textToSend = inputValue) => {
    const text = textToSend.trim();
    if (!text || loading) return;

    setErrorMsg('');
    setLoading(true);

    const userMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    // Update conversation state with user message
    const updatedMessages = [...messages, userMessage];
    setMessages(updatedMessages);
    setInputValue('');

    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }

    // Build conversation history for context (exclude metadata)
    const historyPayload = messages.map(m => ({
      role: m.role,
      content: m.content
    }));

    try {
      const res = await fetch(`${API_BASE}/evaluate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: text,
          threshold: parseFloat(threshold),
          history: historyPayload
        })
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || `Server returned error status ${res.status}`);
      }

      const data = await res.json();

      const assistantMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: data.answer || data.chatbot_response || "No answer generated.",
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        metrics: data
      };

      setMessages(prev => [...prev, assistantMessage]);
      setModelStatus({ online: true, name: data.model_name || 'Active' });

    } catch (err) {
      console.error("Inference Error:", err);
      setErrorMsg(err.message || "Failed to communicate with the AI model. Ensure backend server is running.");
      
      // Also show a failure message in chat rather than blank
      const errorMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: `⚠️ **Inference Failure:** ${err.message || "Could not connect to backend server. Please verify that the FastAPI backend is running on http://127.0.0.1:8000."}`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        isError: true
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  // Keyboard Enter handler (Enter sends, Shift+Enter newlines)
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  // Auto-resize textarea
  const handleInputChange = (e) => {
    setInputValue(e.target.value);
    e.target.style.height = 'auto';
    e.target.style.height = `${Math.min(e.target.scrollHeight, 180)}px`;
  };

  // Copy full response text
  const handleCopyMessage = (id, text) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  // Retry action (re-generates the last message)
  const handleRetry = (lastUserPrompt) => {
    if (!lastUserPrompt) return;
    // Remove the last assistant message if exists
    if (messages.length > 0 && messages[messages.length - 1].role === 'assistant') {
      setMessages(prev => prev.slice(0, -1));
    }
    handleSendMessage(lastUserPrompt);
  };

  // New Chat action (starts fresh conversation)
  const handleNewChat = () => {
    setMessages([]);
    setInputValue('');
    setErrorMsg('');
  };

  return (
    <div className="flex flex-col h-screen w-screen bg-slate-50 text-slate-900 font-sans overflow-hidden">
      
      {/* 1. COMPACT TOP NAVIGATION BAR */}
      <header className="h-14 border-b border-slate-200 bg-white/95 backdrop-blur-sm px-4 sm:px-6 flex items-center justify-between z-10 shrink-0">
        <div className="flex items-center gap-3">
          {/* Brand Logo & Product Name */}
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-blue-700 to-indigo-600 flex items-center justify-center text-white shadow-xs">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <div>
              <div className="flex items-center gap-1.5">
                <span className="font-bold text-slate-900 tracking-tight text-base">Nexa AI</span>
                <span className="text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200">
                  Enterprise
                </span>
              </div>
            </div>
          </div>

          {/* Model Status Pill */}
          <div className="hidden md:flex items-center gap-2 pl-4 border-l border-slate-200 text-xs text-slate-500">
            <span className="relative flex h-2 w-2">
              <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${modelStatus.online ? 'bg-emerald-400' : 'bg-amber-400'}`}></span>
              <span className={`relative inline-flex rounded-full h-2 w-2 ${modelStatus.online ? 'bg-emerald-500' : 'bg-amber-500'}`}></span>
            </span>
            <span className="font-medium text-slate-600 truncate max-w-[200px]">
              {modelStatus.online ? modelStatus.name : "Offline"}
            </span>
          </div>
        </div>

        {/* Global Controls & Actions */}
        <div className="flex items-center gap-3">
          {/* Threshold Control */}
          <div className="flex items-center gap-2 bg-slate-50 px-2.5 py-1 rounded-lg border border-slate-200">
            <label className="text-xs font-medium text-slate-600 hidden sm:inline whitespace-nowrap">
              Threshold:
            </label>
            <input
              type="range"
              min="0.00"
              max="1.00"
              step="0.05"
              value={threshold}
              onChange={(e) => setThreshold(parseFloat(e.target.value))}
              className="w-16 sm:w-20 h-1.5 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
              title="Confidence Threshold for Adaptive Selection"
            />
            <span className="text-xs font-mono font-bold text-blue-700 bg-blue-50 px-1.5 py-0.5 rounded border border-blue-200">
              {threshold.toFixed(2)}
            </span>
          </div>

          {/* New Chat Button */}
          <button
            onClick={handleNewChat}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white border border-slate-300 text-slate-700 hover:bg-slate-50 hover:text-slate-900 transition text-xs font-semibold shadow-2xs cursor-pointer"
          >
            <svg className="w-3.5 h-3.5 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M12 4v16m8-8H4" />
            </svg>
            <span>New Chat</span>
          </button>
        </div>
      </header>

      {/* 2. CENTRAL CONVERSATION AREA */}
      <main className="flex-1 overflow-y-auto px-4 py-6 sm:px-6">
        <div className="max-w-3xl mx-auto flex flex-col gap-6">

          {/* WELCOME SCREEN (When no messages sent yet) */}
          {messages.length === 0 ? (
            <div className="my-auto pt-8 sm:pt-16 pb-8 flex flex-col items-center text-center animate-fade-in">
              <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-blue-600 to-indigo-600 text-white flex items-center justify-center shadow-md mb-5">
                <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>

              <h2 className="text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight">
                What can I help you with?
              </h2>
              <p className="text-sm text-slate-500 mt-2 max-w-md">
                Ask a question, explore an idea, or solve a problem.
              </p>

              {/* 4 Clean Corporate Suggestion Cards */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-8 w-full max-w-xl text-left">
                {SUGGESTION_CARDS.map((card, idx) => (
                  <button
                    key={idx}
                    onClick={() => handleSendMessage(card.prompt)}
                    className="p-4 rounded-xl bg-white border border-slate-200 hover:border-blue-300 hover:shadow-xs transition group cursor-pointer text-left"
                  >
                    <div className="text-xs font-bold text-slate-900 group-hover:text-blue-600 transition flex items-center justify-between">
                      <span>{card.title}</span>
                      <svg className="w-3.5 h-3.5 text-slate-400 group-hover:text-blue-600 transition" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7" />
                      </svg>
                    </div>
                    <p className="text-[12px] text-slate-500 mt-1 leading-snug">
                      "{card.prompt}"
                    </p>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            /* CONVERSATION MESSAGE THREAD */
            messages.map((msg, index) => {
              const isUser = msg.role === 'user';
              const lastUserPrompt = !isUser && index > 0 && messages[index - 1].role === 'user'
                ? messages[index - 1].content
                : null;

              return (
                <div
                  key={msg.id || index}
                  className={`flex flex-col ${isUser ? "items-end" : "items-start"} gap-1.5`}
                >
                  {/* Message Bubble */}
                  <div className={`flex gap-3 max-w-[92%] sm:max-w-[85%] ${isUser ? "flex-row-reverse" : "flex-row"}`}>
                    
                    {/* Avatar */}
                    {!isUser && (
                      <div className="w-8 h-8 rounded-lg bg-blue-600 text-white flex items-center justify-center text-xs font-bold shrink-0 mt-0.5 shadow-2xs">
                        AI
                      </div>
                    )}

                    {/* Content Box */}
                    <div className="flex-1 overflow-hidden">
                      <div
                        className={`p-4 rounded-2xl shadow-2xs leading-relaxed text-[14px] ${
                          isUser
                            ? "bg-slate-900 text-white rounded-tr-xs"
                            : msg.isError
                            ? "bg-rose-50 border border-rose-200 text-rose-800 rounded-tl-xs"
                            : "bg-white border border-slate-200 text-slate-800 rounded-tl-xs"
                        }`}
                      >
                        {isUser ? (
                          <div className="whitespace-pre-wrap">{msg.content}</div>
                        ) : (
                          <MarkdownRenderer content={msg.content} />
                        )}
                      </div>

                      {/* Assistant Actions Toolbar (Copy & Retry) */}
                      {!isUser && !msg.isError && (
                        <div className="flex items-center gap-3 mt-1.5 px-1 text-xs text-slate-500">
                          <button
                            onClick={() => handleCopyMessage(msg.id, msg.content)}
                            className="flex items-center gap-1 hover:text-slate-800 transition cursor-pointer"
                          >
                            {copiedId === msg.id ? (
                              <>
                                <svg className="w-3.5 h-3.5 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                                </svg>
                                <span className="text-emerald-600 font-medium">Copied</span>
                              </>
                            ) : (
                              <>
                                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                                </svg>
                                <span>Copy Response</span>
                              </>
                            )}
                          </button>

                          {lastUserPrompt && (
                            <button
                              onClick={() => handleRetry(lastUserPrompt)}
                              disabled={loading}
                              className="flex items-center gap-1 hover:text-slate-800 transition cursor-pointer disabled:opacity-50"
                            >
                              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                              </svg>
                              <span>Retry</span>
                            </button>
                          )}

                          <span className="text-slate-400">•</span>
                          <span className="text-slate-400 font-mono text-[11px]">{msg.timestamp}</span>
                        </div>
                      )}

                      {/* Professional Token Analysis Interface */}
                      {!isUser && msg.metrics && (
                        <TokenAnalysisSection
                          metrics={msg.metrics}
                          threshold={threshold}
                          onThresholdChange={(newThresh) => setThreshold(newThresh)}
                        />
                      )}
                    </div>
                  </div>

                </div>
              );
            })
          )}

          {/* Typing Indicator while Model Generates */}
          {loading && (
            <div className="flex items-center gap-3 text-xs text-slate-500 bg-white border border-slate-200 p-3.5 rounded-2xl max-w-sm shadow-2xs">
              <div className="w-7 h-7 rounded-lg bg-blue-600 text-white flex items-center justify-center text-xs font-bold shrink-0">
                AI
              </div>
              <div className="flex items-center gap-2">
                <div className="flex gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-blue-600 animate-bounce" style={{ animationDelay: '0ms' }}></span>
                  <span className="w-1.5 h-1.5 rounded-full bg-blue-600 animate-bounce" style={{ animationDelay: '150ms' }}></span>
                  <span className="w-1.5 h-1.5 rounded-full bg-blue-600 animate-bounce" style={{ animationDelay: '300ms' }}></span>
                </div>
                <span className="text-slate-600 font-medium">Nexa AI is generating response...</span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </main>

      {/* 3. CHAT COMPOSER & BOTTOM INPUT */}
      <footer className="border-t border-slate-200 bg-white px-4 py-3 shrink-0">
        <div className="max-w-3xl mx-auto flex flex-col gap-2">
          
          {errorMsg && (
            <div className="p-2.5 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-700 flex items-center justify-between">
              <span>⚠️ {errorMsg}</span>
              <button onClick={() => setErrorMsg('')} className="font-bold cursor-pointer text-rose-800 hover:text-rose-900">×</button>
            </div>
          )}

          {/* Polished, Rounded Message Input */}
          <div className="relative flex items-end gap-2 bg-slate-50 border border-slate-300 rounded-2xl p-2 focus-within:bg-white focus-within:border-blue-600 focus-within:ring-2 focus-within:ring-blue-100 transition shadow-2xs">
            <textarea
              ref={textareaRef}
              rows="1"
              value={inputValue}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              disabled={loading}
              placeholder="Ask a question or enter a sentence to evaluate tokens..."
              className="w-full resize-none bg-transparent px-3 py-1.5 text-sm text-slate-800 placeholder-slate-400 focus:outline-none max-h-44 leading-relaxed"
            />
            <button
              onClick={() => handleSendMessage()}
              disabled={loading || !inputValue.trim()}
              className="w-9 h-9 rounded-xl bg-blue-600 text-white flex items-center justify-center shrink-0 hover:bg-blue-700 disabled:opacity-40 disabled:hover:bg-blue-600 transition shadow-xs cursor-pointer"
              title="Send message (Enter)"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M14 5l7 7m0 0l-7 7m7-7H3" />
              </svg>
            </button>
          </div>

          {/* Disclaimer Note */}
          <p className="text-[11px] text-center text-slate-400">
            Nexa AI may make mistakes. Verify important information. Confidence-based token evaluation module active.
          </p>

        </div>
      </footer>

    </div>
  );
}
