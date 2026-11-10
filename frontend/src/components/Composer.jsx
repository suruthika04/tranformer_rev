/**
 * Composer — message input, file/image upload attachments,
 * stop generation, threshold indicator, keyboard controls (Enter to send, Shift+Enter newline).
 */
import React, { useRef, useState, useEffect } from "react";
import { ArrowUp, Paperclip, Square, X, Image as ImageIcon, FileText, Sliders } from "lucide-react";
import { useChat } from "../contexts/ChatContext";

export default function Composer() {
  const {
    sendMessage,
    streaming,
    stopGeneration,
    attachment,
    uploadProgress,
    attachFile,
    clearAttachment,
    threshold,
    setThreshold,
  } = useChat();

  const [input, setInput] = useState("");
  const [showThresholdSlider, setShowThresholdSlider] = useState(false);
  const textareaRef = useRef(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 180)}px`;
    }
  }, [input]);

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleSend = () => {
    if ((!input.trim() && !attachment) || streaming) return;
    sendMessage(input);
    setInput("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleFileChange = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      await attachFile(file);
    } catch (err) {
      alert(err.message || "File upload failed");
    } finally {
      e.target.value = "";
    }
  };

  return (
    <div className="w-full max-w-3xl mx-auto px-4 pb-4">
      {/* Attachment Preview Box */}
      {attachment && (
        <div className="mb-2 p-2 rounded-xl bg-[#1c1c1c] border border-[#2e2e2e] flex items-center justify-between">
          <div className="flex items-center gap-2 overflow-hidden">
            {attachment.isImage && attachment.preview ? (
              <img
                src={attachment.preview}
                alt="preview"
                className="w-10 h-10 object-cover rounded-lg border border-[#333]"
              />
            ) : (
              <div className="w-10 h-10 rounded-lg bg-[#252525] flex items-center justify-center text-blue-400">
                <FileText size={18} />
              </div>
            )}
            <div className="text-xs truncate">
              <p className="text-white font-medium truncate max-w-[200px] sm:max-w-xs">
                {attachment.filename}
              </p>
              <p className="text-[#777] text-[10px]">
                {uploadProgress !== null ? `Uploading (${uploadProgress}%)` : "Attached"}
              </p>
            </div>
          </div>
          <button
            onClick={clearAttachment}
            className="p-1 rounded-full hover:bg-white/10 text-[#777] hover:text-white transition"
          >
            <X size={14} />
          </button>
        </div>
      )}

      {/* Threshold Slider Quick Popover / Bar */}
      {showThresholdSlider && (
        <div className="mb-2 p-3 bg-[#181818] border border-[#2a2a2a] rounded-xl flex items-center gap-3 text-xs text-[#aaa]">
          <span className="font-medium whitespace-nowrap">Evaluator Threshold:</span>
          <input
            type="range"
            min="0.0"
            max="1.0"
            step="0.05"
            value={threshold}
            onChange={(e) => setThreshold(parseFloat(e.target.value))}
            className="w-full h-1 bg-[#333] rounded-lg appearance-none cursor-pointer accent-blue-500"
          />
          <span className="font-mono text-white text-xs px-2 py-0.5 bg-[#252525] rounded border border-[#333]">
            {threshold.toFixed(2)}
          </span>
        </div>
      )}

      {/* Main Composer Frame */}
      <div className="relative flex flex-col bg-[#161616] border border-[#2c2c2c] rounded-2xl p-2.5 focus-within:border-[#444] transition-colors shadow-lg">
        <textarea
          ref={textareaRef}
          rows={1}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask Nexa AI anything..."
          disabled={streaming}
          className="w-full bg-transparent px-3 py-1.5 text-sm text-[#eee] placeholder-[#555] focus:outline-none resize-none max-h-48 leading-relaxed"
        />

        {/* Action Row */}
        <div className="flex items-center justify-between pt-1 px-1">
          <div className="flex items-center gap-1.5">
            <input
              ref={fileInputRef}
              type="file"
              onChange={handleFileChange}
              accept="image/*,.pdf,.docx,.txt,.md,.csv,.json"
              className="hidden"
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="p-2 rounded-xl text-[#777] hover:text-[#ccc] hover:bg-white/5 transition"
              title="Attach an image or document (PDF, TXT, DOCX, CSV)"
            >
              <Paperclip size={16} />
            </button>

            <button
              type="button"
              onClick={() => setShowThresholdSlider(!showThresholdSlider)}
              className={`p-2 rounded-xl transition ${
                showThresholdSlider ? "text-blue-400 bg-blue-500/10" : "text-[#777] hover:text-[#ccc] hover:bg-white/5"
              }`}
              title="Adjust token evaluator threshold"
            >
              <Sliders size={16} />
            </button>
          </div>

          <div>
            {streaming ? (
              <button
                type="button"
                onClick={stopGeneration}
                className="w-8 h-8 rounded-xl bg-white text-black flex items-center justify-center hover:bg-[#ddd] transition shadow"
                title="Stop generation"
              >
                <Square size={13} fill="currentColor" />
              </button>
            ) : (
              <button
                type="button"
                onClick={handleSend}
                disabled={!input.trim() && !attachment}
                className="w-8 h-8 rounded-xl bg-white text-black flex items-center justify-center hover:bg-[#ddd] disabled:opacity-30 disabled:hover:bg-white transition shadow"
                title="Send message"
              >
                <ArrowUp size={16} strokeWidth={2.5} />
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="flex items-center justify-between text-[11px] text-[#555] px-2 pt-2">
        <span>Nexa AI may produce inaccurate information. Verify details.</span>
        <span className="font-mono text-[10px]">Threshold: {threshold.toFixed(2)}</span>
      </div>
    </div>
  );
}
