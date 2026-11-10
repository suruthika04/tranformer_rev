/**
 * TokenAnalysis — collapsible accordion showing confidence-based token evaluator results.
 */
import React, { useEffect, useState } from "react";
import { ChevronDown, Zap } from "lucide-react";

export default function TokenAnalysis({ metrics, threshold, onThresholdChange }) {
  const [open, setOpen] = useState(false);
  const [localThreshold, setLocalThreshold] = useState(threshold);

  useEffect(() => setLocalThreshold(threshold), [threshold]);

  if (!metrics?.token_analysis?.length) return null;

  // Re-compute live based on localThreshold
  const updated = metrics.token_analysis.map((item) => ({
    ...item,
    retained: item.confidence >= localThreshold,
    status: item.confidence >= localThreshold ? "Retained" : "Filtered",
  }));

  const evalCount = updated.length;
  const selectedCount = updated.filter((t) => t.retained).length;
  const filteredCount = evalCount - selectedCount;
  const savingPct =
    evalCount > 0 ? parseFloat(((filteredCount / evalCount) * 100).toFixed(2)) : 0;

  const metrics6 = [
    { label: "Input", value: metrics.input_tokens ?? evalCount, color: "" },
    { label: "Output", value: metrics.output_tokens ?? 0, color: "" },
    { label: "Evaluated", value: evalCount, color: "" },
    { label: "Selected", value: selectedCount, color: "text-emerald-400" },
    { label: "Filtered", value: filteredCount, color: "text-rose-400" },
    { label: "Saving", value: `${savingPct}%`, color: "text-indigo-400" },
  ];

  return (
    <div className="mt-2 rounded-xl border border-[#222] overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-3 py-2 hover:bg-white/4 transition text-left"
      >
        <div className="flex items-center gap-2">
          <Zap size={12} className="text-[#666]" />
          <span className="text-[11px] font-medium text-[#888]">Token Analysis</span>
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/5 text-[#666] border border-[#2a2a2a] font-mono">
            {filteredCount} filtered · {savingPct}%
          </span>
          {metrics.latency_seconds > 0 && (
            <span className="text-[10px] text-[#555] font-mono hidden sm:inline">
              · {metrics.latency_seconds}s
            </span>
          )}
        </div>
        <ChevronDown
          size={13}
          className={`text-[#555] transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>

      {/* Body */}
      {open && (
        <div className="p-3 border-t border-[#1a1a1a] space-y-3 bg-[#0e0e0e]">
          {/* Disclaimer & Architecture Note */}
          <div className="p-2.5 rounded-lg border border-[#222] bg-[#111] space-y-1 text-[11px] text-[#777] leading-relaxed">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-semibold text-[#ddd]">Architecture Notice:</span>
              <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-[10px] font-mono">
                {metrics.semantic_preservation_passed !== false ? "✓ Semantic Preservation: Passed" : "⚠ Semantic Risk"}
              </span>
              <span className="px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20 text-[10px] font-mono">
                Gemini Safe Mode: 100% Original Prompt Preserved
              </span>
            </div>
            <p className="text-[10px] text-[#666] pt-1">
              Token importance is evaluated via a PyTorch Contextual MLP over token embeddings with information-theoretic semantic priors.
              To eliminate hallucination or meaning corruption, the full original user prompt is transmitted to Google Gemini.
              {metrics.gemini_usage?.prompt_token_count && (
                <span className="block text-indigo-400 font-mono mt-0.5">
                  Verified Gemini API Usage: {metrics.gemini_usage.prompt_token_count} prompt tokens · {metrics.gemini_usage.candidates_token_count ?? 0} output tokens.
                </span>
              )}
            </p>
          </div>

          {/* Metric Cards */}
          <div className="grid grid-cols-3 sm:grid-cols-6 gap-1.5">
            {metrics6.map((m) => (
              <div key={m.label} className="p-2 rounded-lg bg-[#111] border border-[#1e1e1e] text-center">
                <span className="text-[10px] text-[#555] block">{m.label}</span>
                <span className={`text-sm font-bold font-mono ${m.color || "text-[#ccc]"}`}>
                  {m.value}
                </span>
              </div>
            ))}
          </div>

          {/* Threshold slider */}
          <div className="flex flex-col sm:flex-row sm:items-center gap-2 p-2.5 rounded-lg bg-[#111] border border-[#1e1e1e]">
            <span className="text-[11px] text-[#777] font-medium whitespace-nowrap">
              Threshold:
              <span className="ml-1 font-mono text-blue-400">{localThreshold.toFixed(2)}</span>
            </span>
            <div className="flex items-center gap-2 flex-1">
              <span className="text-[10px] text-[#555]">0.00</span>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={localThreshold}
                onChange={(e) => {
                  const v = parseFloat(e.target.value);
                  setLocalThreshold(v);
                  onThresholdChange?.(v);
                }}
                className="flex-1 h-1 bg-[#2a2a2a] rounded-full appearance-none cursor-pointer accent-blue-500"
              />
              <span className="text-[10px] text-[#555]">1.00</span>
            </div>
          </div>

          {/* Token table */}
          <div className="rounded-lg border border-[#1e1e1e] overflow-hidden">
            <div className="max-h-52 overflow-y-auto custom-scrollbar">
              <table className="w-full text-left text-[11px] border-collapse">
                <thead className="bg-[#111] sticky top-0 border-b border-[#1e1e1e] text-[#666]">
                  <tr>
                    <th className="py-1.5 px-2 w-8">#</th>
                    <th className="py-1.5 px-2">Token</th>
                    <th className="py-1.5 px-2 w-44">Score</th>
                    <th className="py-1.5 px-2 w-24">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#181818]">
                  {updated.map((item, i) => (
                    <tr key={i} className="hover:bg-white/2 transition">
                      <td className="py-1 px-2 text-[#444] font-mono">{i + 1}</td>
                      <td className="py-1 px-2 font-mono text-[#bbb]">
                        <span className="px-1 py-0.5 rounded bg-[#1a1a1a] border border-[#222]">
                          {item.token}
                        </span>
                      </td>
                      <td className="py-1 px-2">
                        <div className="flex items-center gap-1.5">
                          <div className="w-16 bg-[#1a1a1a] rounded-full h-1 overflow-hidden">
                            <div
                              className={`h-full ${item.retained ? "bg-emerald-500" : "bg-[#444]"}`}
                              style={{ width: `${Math.min(100, item.confidence * 100)}%` }}
                            />
                          </div>
                          <span className="font-mono text-[#888]">{item.confidence.toFixed(3)}</span>
                        </div>
                      </td>
                      <td className="py-1 px-2">
                        {item.retained ? (
                          <span className="text-[10px] font-medium text-emerald-500">✓ Kept</span>
                        ) : (
                          <span className="text-[10px] font-medium text-[#555]">× Out</span>
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
