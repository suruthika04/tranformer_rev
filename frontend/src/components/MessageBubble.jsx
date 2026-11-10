/**
 * MessageBubble — renders a single chat message with markdown, code blocks,
 * copy/retry actions, token analysis accordion, and image/file attachments.
 */
import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Check, Copy, FileText, Image, RefreshCw } from "lucide-react";
import TokenAnalysis from "./TokenAnalysis";
import { useChat } from "../contexts/ChatContext";

function CopyButton({ text, className = "" }) {
  const [copied, setCopied] = useState(false);
  const handle = () => {
    navigator.clipboard.writeText(text).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <button
      onClick={handle}
      className={`flex items-center gap-1 text-[#666] hover:text-[#ccc] transition ${className}`}
      title="Copy"
    >
      {copied ? <Check size={13} className="text-emerald-400" /> : <Copy size={13} />}
      <span className="text-[11px]">{copied ? "Copied" : "Copy"}</span>
    </button>
  );
}

function CodeBlock({ children, className }) {
  const [copied, setCopied] = useState(false);
  const lang = className?.replace("language-", "") || "code";
  const code = String(children).trimEnd();

  const handleCopy = () => {
    navigator.clipboard.writeText(code).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="my-3 rounded-lg overflow-hidden border border-[#2a2a2a] bg-[#0d0d0d]">
      <div className="flex items-center justify-between px-4 py-2 bg-[#181818] border-b border-[#2a2a2a]">
        <span className="text-[11px] font-mono text-[#666] uppercase tracking-wider">{lang}</span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1 text-[11px] text-[#666] hover:text-[#ccc] transition"
        >
          {copied ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
          {copied ? "Copied" : "Copy code"}
        </button>
      </div>
      <pre className="p-4 overflow-x-auto text-xs font-mono leading-relaxed text-[#d4d4d4] whitespace-pre">
        <code>{code}</code>
      </pre>
    </div>
  );
}

const markdownComponents = {
  code({ node, inline, className, children, ...props }) {
    if (inline) {
      return (
        <code className="px-1 py-0.5 rounded bg-[#2a2a2a] text-[#d4d4d4] font-mono text-[12px]">
          {children}
        </code>
      );
    }
    return <CodeBlock className={className}>{children}</CodeBlock>;
  },
  h1: ({ children }) => <h1 className="text-xl font-bold text-white mt-4 mb-2">{children}</h1>,
  h2: ({ children }) => <h2 className="text-lg font-semibold text-white mt-3 mb-1.5">{children}</h2>,
  h3: ({ children }) => <h3 className="text-base font-semibold text-[#ddd] mt-2 mb-1">{children}</h3>,
  p: ({ children }) => <p className="leading-relaxed mb-2 last:mb-0">{children}</p>,
  ul: ({ children }) => <ul className="list-disc pl-5 space-y-1 my-2">{children}</ul>,
  ol: ({ children }) => <ol className="list-decimal pl-5 space-y-1 my-2">{children}</ol>,
  li: ({ children }) => <li className="leading-relaxed">{children}</li>,
  blockquote: ({ children }) => (
    <blockquote className="border-l-2 border-[#444] pl-3 text-[#aaa] italic my-2">{children}</blockquote>
  ),
  table: ({ children }) => (
    <div className="overflow-x-auto my-3">
      <table className="w-full text-xs border-collapse border border-[#2a2a2a]">{children}</table>
    </div>
  ),
  th: ({ children }) => (
    <th className="px-3 py-2 text-left font-semibold text-[#ddd] bg-[#1a1a1a] border border-[#2a2a2a]">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="px-3 py-2 text-[#ccc] border border-[#2a2a2a]">{children}</td>
  ),
  a: ({ href, children }) => (
    <a href={href} target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:underline">
      {children}
    </a>
  ),
  strong: ({ children }) => <strong className="font-semibold text-white">{children}</strong>,
  em: ({ children }) => <em className="italic text-[#ccc]">{children}</em>,
  hr: () => <hr className="border-[#2a2a2a] my-4" />,
};

export default function MessageBubble({ message, isLast }) {
  const { retryLast, streaming, threshold, setThreshold } = useChat();
  const isUser = message.role === "user";
  const isStreaming = message.streaming;

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-6`}>
      <div className={`flex gap-3 max-w-[88%] ${isUser ? "flex-row-reverse" : "flex-row"}`}>
        {/* Avatar */}
        {!isUser && (
          <div className="w-7 h-7 rounded-lg bg-white/10 flex items-center justify-center text-[10px] font-bold text-white shrink-0 mt-0.5">
            N
          </div>
        )}

        <div className="flex-1 min-w-0">
          {/* Image attachment (user) */}
          {message.attachment?.isImage && message.attachment.preview && (
            <div className={`mb-2 ${isUser ? "flex justify-end" : ""}`}>
              <img
                src={message.attachment.preview}
                alt="Attached image"
                className="max-w-[280px] max-h-[200px] rounded-lg object-cover border border-[#2a2a2a]"
              />
            </div>
          )}

          {/* Document attachment (user) */}
          {message.attachment?.isDocument && (
            <div className={`mb-2 flex ${isUser ? "justify-end" : ""}`}>
              <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[#1a1a1a] border border-[#2a2a2a] text-xs text-[#aaa]">
                <FileText size={13} className="text-blue-400" />
                <span className="truncate max-w-[160px]">{message.attachment.filename}</span>
              </div>
            </div>
          )}

          {/* Message content */}
          <div
            className={`px-4 py-3 rounded-2xl text-sm leading-relaxed ${
              isUser
                ? "bg-[#1e1e1e] text-[#e5e5e5] rounded-tr-sm border border-[#2a2a2a]"
                : message.isError
                ? "bg-rose-950/40 border border-rose-800/40 text-rose-300 rounded-tl-sm"
                : "bg-[#161616] border border-[#222] text-[#e0e0e0] rounded-tl-sm"
            }`}
          >
            {isUser ? (
              <span className="whitespace-pre-wrap">{message.content}</span>
            ) : (
              <div className="prose prose-invert prose-sm max-w-none">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={markdownComponents}
                >
                  {message.content || ""}
                </ReactMarkdown>
                {isStreaming && (
                  <span className="inline-block w-0.5 h-4 bg-white/60 animate-pulse ml-0.5 align-middle" />
                )}
              </div>
            )}
          </div>

          {/* Toolbar */}
          {!isUser && !isStreaming && !message.isError && (
            <div className="flex items-center gap-3 mt-1.5 px-1">
              <CopyButton text={message.content} />
              {isLast && (
                <button
                  onClick={retryLast}
                  disabled={streaming}
                  className="flex items-center gap-1 text-[#666] hover:text-[#ccc] transition disabled:opacity-40 text-[11px]"
                >
                  <RefreshCw size={12} />
                  Retry
                </button>
              )}
              {message.metrics?.latency_seconds > 0 && (
                <span className="text-[10px] text-[#555] font-mono">
                  {message.metrics.latency_seconds}s
                </span>
              )}
            </div>
          )}

          {/* Token Analysis */}
          {!isUser && !isStreaming && message.metrics?.token_analysis?.length > 0 && (
            <TokenAnalysis
              metrics={message.metrics}
              threshold={threshold}
              onThresholdChange={setThreshold}
            />
          )}
        </div>
      </div>
    </div>
  );
}
