/**
 * WelcomeScreen — clean, minimal ChatGPT-style welcome layout.
 */
import React from "react";
import { Sparkles, Code2, BookOpen, Cpu } from "lucide-react";
import { useChat } from "../contexts/ChatContext";

const SUGGESTIONS = [
  {
    icon: Cpu,
    title: "Explain Transformers",
    subtitle: "Self-attention and confidence evaluation mechanics",
    prompt: "Explain how self-attention works in simple terms.",
  },
  {
    icon: Code2,
    title: "Python Implementation",
    subtitle: "Write an efficient data processing script",
    prompt: "Write a clean Python function to parse and summarize CSV data.",
  },
  {
    icon: Sparkles,
    title: "Explore Concept",
    subtitle: "Understand token evaluation & pruning trade-offs",
    prompt: "What are the benefits and risks of token pruning in transformers?",
  },
  {
    icon: BookOpen,
    title: "Document Analysis",
    subtitle: "Upload a file or ask questions directly",
    prompt: "How can I evaluate token importance before attention layers?",
  },
];

export default function WelcomeScreen() {
  const { sendMessage } = useChat();

  return (
    <div className="flex-1 flex flex-col items-center justify-center p-6 text-center max-w-2xl mx-auto my-auto animate-fade-in">
      <div className="w-12 h-12 rounded-2xl bg-[#1f1f1f] border border-[#2d2d2d] flex items-center justify-center mb-6 shadow-md">
        <Sparkles size={22} className="text-white" />
      </div>

      <h1 className="text-2xl sm:text-3xl font-semibold text-white tracking-tight">
        How can I help you today?
      </h1>
      <p className="text-xs sm:text-sm text-[#777] mt-2 max-w-md">
        Ask a question, upload a document or image, or analyze token confidence distributions in real time.
      </p>

      {/* Suggestion Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-8 w-full text-left">
        {SUGGESTIONS.map((item, idx) => {
          const Icon = item.icon;
          return (
            <button
              key={idx}
              onClick={() => sendMessage(item.prompt)}
              className="p-3.5 rounded-xl bg-[#141414] border border-[#242424] hover:border-[#383838] hover:bg-[#1a1a1a] transition group text-left cursor-pointer"
            >
              <div className="flex items-center gap-2 mb-1">
                <Icon size={14} className="text-[#888] group-hover:text-white transition" />
                <span className="text-xs font-medium text-[#eee] group-hover:text-white transition">
                  {item.title}
                </span>
              </div>
              <p className="text-[11px] text-[#666] leading-relaxed line-clamp-2">
                {item.subtitle}
              </p>
            </button>
          );
        })}
      </div>
    </div>
  );
}
