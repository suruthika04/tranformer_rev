import React, { useState, useEffect } from 'react';

const API_BASE = "http://127.0.0.1:8000/api";

const PRESET_SENTENCE = "The cat is sleeping on the mat because it is tired.";

export default function App() {
  const [textInput, setTextInput] = useState('');
  const [threshold, setThreshold] = useState(0.50);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  // Current analysis data
  const [currentAnalysis, setCurrentAnalysis] = useState(null);

  // Chat message history
  const [chatHistory, setChatHistory] = useState([
    {
      role: 'assistant',
      text: 'Hello! Enter a sentence to observe how confidence-based token evaluation filters tokens before self-attention.',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }
  ]);

  // Handle message submission
  const handleSubmit = async (textToSubmit = textInput) => {
    const text = textToSubmit.trim();
    if (!text) return;

    setLoading(true);
    setErrorMsg('');

    const userMessage = {
      role: 'user',
      text: text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    setChatHistory(prev => [...prev, userMessage]);

    try {
      const res = await fetch(`${API_BASE}/evaluate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, threshold: parseFloat(threshold) })
      });

      if (!res.ok) {
        throw new Error(`Server returned ${res.status}`);
      }

      const data = await res.json();
      setCurrentAnalysis(data);

      const assistantMessage = {
        role: 'assistant',
        text: data.chatbot_response,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        metrics: {
          original: data.original_tokens,
          selected: data.selected_tokens,
          saved: data.tokens_saved,
          percentage: data.saving_percentage
        }
      };

      setChatHistory(prev => [...prev, assistantMessage]);
      setTextInput('');
    } catch (err) {
      console.error("Evaluation error:", err);
      setErrorMsg("Failed to connect to backend server. Ensure FastAPI backend is running.");
    } finally {
      setLoading(false);
    }
  };

  // Recalculate metrics locally & sync when threshold changes
  useEffect(() => {
    if (!currentAnalysis || !currentAnalysis.token_analysis) return;

    const newThreshold = parseFloat(threshold);
    const updatedAnalysis = currentAnalysis.token_analysis.map(item => {
      const isRetained = item.confidence >= newThreshold;
      return {
        ...item,
        retained: isRetained,
        status: isRetained ? "Retained" : "Filtered"
      };
    });

    const retainedTokens = updatedAnalysis.filter(i => i.retained).map(i => i.token);
    const filteredTokens = updatedAnalysis.filter(i => !i.retained).map(i => i.token);

    const originalTokens = updatedAnalysis.length;
    const selectedTokens = retainedTokens.length;
    const tokensSaved = originalTokens - selectedTokens;
    const savingPercentage = originalTokens > 0 
      ? parseFloat(((tokensSaved / originalTokens) * 100).toFixed(2)) 
      : 0.0;

    setCurrentAnalysis(prev => ({
      ...prev,
      confidence_threshold: newThreshold,
      token_analysis: updatedAnalysis,
      retained_tokens: retainedTokens,
      filtered_tokens: filteredTokens,
      original_tokens: originalTokens,
      selected_tokens: selectedTokens,
      tokens_saved: tokensSaved,
      saving_percentage: savingPercentage
    }));
  }, [threshold]);

  // Reset analysis & chat
  const handleReset = () => {
    setCurrentAnalysis(null);
    setTextInput('');
    setThreshold(0.50);
    setErrorMsg('');
    setChatHistory([
      {
        role: 'assistant',
        text: 'Session reset. Enter a sentence to observe token evaluation.',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      }
    ]);
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-sans flex flex-col">
      {/* Header Bar */}
      <header className="bg-white border-b border-slate-200 px-6 py-4 shadow-xs">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold px-2 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-200">
                Academic Project
              </span>
              <h1 className="text-xl font-bold text-slate-900 tracking-tight">
                Confidence-Based Token Evaluator
              </h1>
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              Efficient Token Selection for Transformer Models
            </p>
          </div>

          <div className="flex items-center gap-4">
            {/* Threshold Control */}
            <div className="flex items-center gap-3 bg-slate-50 px-3 py-1.5 rounded-md border border-slate-200">
              <label className="text-xs font-medium text-slate-700 whitespace-nowrap">
                Confidence Threshold:
              </label>
              <input
                type="range"
                min="0.00"
                max="1.00"
                step="0.05"
                value={threshold}
                onChange={(e) => setThreshold(parseFloat(e.target.value))}
                className="w-24 h-1.5 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
              />
              <span className="text-xs font-bold text-blue-700 bg-blue-50 border border-blue-200 px-2 py-0.5 rounded min-w-[50px] text-center">
                {parseFloat(threshold).toFixed(2)}
              </span>
            </div>

            {/* Reset Button */}
            <button
              onClick={handleReset}
              className="text-xs font-medium px-3 py-1.5 rounded bg-white border border-slate-300 text-slate-700 hover:bg-slate-50 transition cursor-pointer"
            >
              Reset Analysis
            </button>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="max-w-7xl w-full mx-auto p-4 sm:p-6 flex-1 flex flex-col gap-6">
        
        {/* Preset Quick Demo Action Bar */}
        <div className="bg-white p-3 rounded-lg border border-slate-200 flex flex-wrap items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-slate-700">Quick Test Sentence:</span>
            <span className="text-slate-600 italic font-mono bg-slate-50 px-2 py-1 rounded border border-slate-200">
              "{PRESET_SENTENCE}"
            </span>
          </div>
          <button
            onClick={() => {
              setTextInput(PRESET_SENTENCE);
              handleSubmit(PRESET_SENTENCE);
            }}
            disabled={loading}
            className="px-3 py-1.5 rounded bg-blue-600 hover:bg-blue-700 text-white font-medium transition cursor-pointer disabled:opacity-50"
          >
            Run Demo Analysis
          </button>
        </div>

        {errorMsg && (
          <div className="bg-rose-50 border border-rose-200 text-rose-700 p-3 rounded-md text-xs font-medium">
            ⚠️ {errorMsg}
          </div>
        )}

        {/* Main 2-Column Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          
          {/* LEFT: Chatbot Interface (5 cols) */}
          <div className="lg:col-span-5 bg-white border border-slate-200 rounded-lg flex flex-col h-[560px] shadow-xs">
            <div className="border-b border-slate-100 p-3.5 bg-slate-50 rounded-t-lg flex justify-between items-center">
              <h2 className="text-sm font-semibold text-slate-800">1. Chatbot Interface</h2>
              <span className="text-[11px] text-slate-500">Transformer Inference</span>
            </div>

            {/* Chat History Messages */}
            <div className="flex-1 p-4 overflow-y-auto flex flex-col gap-3">
              {chatHistory.map((msg, idx) => (
                <div
                  key={idx}
                  className={`flex flex-col max-w-[88%] ${
                    msg.role === 'user' ? 'self-end items-end' : 'self-start items-start'
                  }`}
                >
                  <div
                    className={`p-3 rounded-lg text-xs leading-relaxed ${
                      msg.role === 'user'
                        ? 'bg-blue-600 text-white rounded-br-none'
                        : 'bg-slate-100 text-slate-800 border border-slate-200 rounded-bl-none'
                    }`}
                  >
                    {msg.text}
                  </div>
                  
                  {msg.metrics && (
                    <div className="mt-1 text-[10px] text-slate-500 bg-slate-50 border border-slate-200 rounded px-2 py-0.5">
                      Tokens Saved: <span className="font-bold text-blue-700">{msg.metrics.saved}</span> ({msg.metrics.percentage}%)
                    </div>
                  )}

                  <span className="text-[10px] text-slate-400 mt-0.5">
                    {msg.role === 'user' ? 'You' : 'Assistant'} • {msg.timestamp}
                  </span>
                </div>
              ))}

              {loading && (
                <div className="self-start flex items-center gap-2 text-xs text-slate-500 bg-slate-50 p-2.5 rounded-lg border border-slate-200">
                  <div className="w-2 h-2 rounded-full bg-blue-600 animate-ping"></div>
                  Tokenizing & evaluating embeddings...
                </div>
              )}
            </div>

            {/* Input Form */}
            <form
              onSubmit={(e) => { e.preventDefault(); handleSubmit(); }}
              className="p-3 border-t border-slate-100 bg-white rounded-b-lg flex gap-2"
            >
              <input
                type="text"
                placeholder="Type a sentence (e.g. The cat is sleeping...)"
                value={textInput}
                onChange={(e) => setTextInput(e.target.value)}
                disabled={loading}
                className="flex-1 text-xs px-3 py-2 border border-slate-300 rounded focus:border-blue-500 focus:outline-none"
              />
              <button
                type="submit"
                disabled={loading || !textInput.trim()}
                className="px-4 py-2 text-xs font-semibold bg-blue-600 text-white rounded hover:bg-blue-700 transition disabled:opacity-50 cursor-pointer"
              >
                Send
              </button>
            </form>
          </div>

          {/* RIGHT: Token Analysis Panel (7 cols) */}
          <div className="lg:col-span-7 flex flex-col gap-4">
            
            {/* Main Result Panel */}
            <div className="bg-white border border-slate-200 rounded-lg p-4 shadow-xs">
              <div className="flex justify-between items-center border-b border-slate-100 pb-3 mb-4">
                <div>
                  <h2 className="text-sm font-bold text-slate-900">2. Token Analysis</h2>
                  <p className="text-[11px] text-slate-500">
                    Confidence Evaluation & Saving Metrics (Threshold: {parseFloat(threshold).toFixed(2)})
                  </p>
                </div>
              </div>

              {/* 4 Metric Cards */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
                <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 text-center">
                  <div className="text-[11px] font-medium text-slate-500">Original Tokens</div>
                  <div className="text-xl font-bold text-slate-900 mt-1">
                    {currentAnalysis ? currentAnalysis.original_tokens : 0}
                  </div>
                </div>

                <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-center">
                  <div className="text-[11px] font-medium text-emerald-800">Selected Tokens</div>
                  <div className="text-xl font-bold text-emerald-700 mt-1">
                    {currentAnalysis ? currentAnalysis.selected_tokens : 0}
                  </div>
                </div>

                <div className="p-3 rounded-lg bg-blue-50 border border-blue-200 text-center">
                  <div className="text-[11px] font-medium text-blue-800">Tokens Saved</div>
                  <div className="text-xl font-bold text-blue-700 mt-1">
                    {currentAnalysis ? currentAnalysis.tokens_saved : 0}
                  </div>
                </div>

                <div className="p-3 rounded-lg bg-indigo-50 border border-indigo-200 text-center">
                  <div className="text-[11px] font-medium text-indigo-800">Saving %</div>
                  <div className="text-xl font-bold text-indigo-700 mt-1">
                    {currentAnalysis ? `${currentAnalysis.saving_percentage}%` : '0.00%'}
                  </div>
                </div>
              </div>

              {/* Token Visualization Table */}
              <div className="border border-slate-200 rounded-md overflow-hidden">
                <div className="bg-slate-50 px-3 py-2 border-b border-slate-200 flex justify-between items-center text-xs font-semibold text-slate-700">
                  <span>Token Visualization</span>
                  <span>Evaluator Architecture: Embedding → MLP → Sigmoid</span>
                </div>
                
                <div className="max-h-[280px] overflow-y-auto">
                  {currentAnalysis && currentAnalysis.token_analysis ? (
                    <table className="w-full text-left text-xs border-collapse">
                      <thead className="bg-slate-50 sticky top-0 border-b border-slate-200 text-slate-600 font-semibold">
                        <tr>
                          <th className="py-2 px-3">#</th>
                          <th className="py-2 px-3">Token</th>
                          <th className="py-2 px-3">Confidence Score</th>
                          <th className="py-2 px-3">Status</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {currentAnalysis.token_analysis.map((item, idx) => (
                          <tr key={idx} className="hover:bg-slate-50 transition">
                            <td className="py-2 px-3 text-slate-400 font-mono text-[11px]">{idx + 1}</td>
                            <td className="py-2 px-3 font-medium text-slate-800 font-mono">
                              [{item.token}]
                            </td>
                            <td className="py-2 px-3 font-mono">
                              <div className="flex items-center gap-2">
                                <div className="w-16 bg-slate-100 rounded-full h-2 border border-slate-200 overflow-hidden">
                                  <div
                                    className={`h-full ${item.retained ? 'bg-emerald-500' : 'bg-slate-400'}`}
                                    style={{ width: `${Math.min(100, item.confidence * 100)}%` }}
                                  ></div>
                                </div>
                                <span className="font-bold text-slate-700">{item.confidence.toFixed(2)}</span>
                              </div>
                            </td>
                            <td className="py-2 px-3">
                              {item.retained ? (
                                <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200">
                                  ✓ Retained
                                </span>
                              ) : (
                                <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded bg-rose-50 text-rose-700 border border-rose-200">
                                  × Filtered
                                </span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : (
                    <div className="p-8 text-center text-xs text-slate-400">
                      Submit a text message or click "Run Demo Analysis" to inspect token confidence scores.
                    </div>
                  )}
                </div>
              </div>

            </div>

          </div>
        </div>

        {/* BOTTOM SECTION 1: Visual Process Flow */}
        <div className="bg-white border border-slate-200 rounded-lg p-5 shadow-xs">
          <h2 className="text-sm font-bold text-slate-900 mb-1">3. Visual Process Flow</h2>
          <p className="text-xs text-slate-500 mb-4">
            Pipeline layout showing how tokens pass through confidence evaluation before self-attention.
          </p>

          <div className="grid grid-cols-2 md:grid-cols-7 gap-2 text-center text-xs">
            <div className="p-3 bg-slate-50 border border-slate-200 rounded-md font-medium text-slate-800">
              <div className="text-[10px] text-slate-400 font-bold mb-1">STEP 1</div>
              Input Text
            </div>
            
            <div className="hidden md:flex items-center justify-center text-slate-400 font-bold">→</div>

            <div className="p-3 bg-slate-50 border border-slate-200 rounded-md font-medium text-slate-800">
              <div className="text-[10px] text-slate-400 font-bold mb-1">STEP 2</div>
              Tokenization
            </div>

            <div className="hidden md:flex items-center justify-center text-slate-400 font-bold">→</div>

            <div className="p-3 bg-slate-50 border border-slate-200 rounded-md font-medium text-slate-800">
              <div className="text-[10px] text-slate-400 font-bold mb-1">STEP 3</div>
              Token Embedding
            </div>

            <div className="hidden md:flex items-center justify-center text-slate-400 font-bold">→</div>

            <div className="p-3 bg-blue-50 border border-blue-200 rounded-md font-semibold text-blue-900">
              <div className="text-[10px] text-blue-600 font-bold mb-1">STEP 4 (MLP)</div>
              Confidence Evaluation
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-5 gap-2 text-center text-xs mt-3">
            <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-md font-semibold text-emerald-900">
              <div className="text-[10px] text-emerald-600 font-bold mb-1">STEP 5</div>
              Token Selection
            </div>

            <div className="hidden md:flex items-center justify-center text-slate-400 font-bold">→</div>

            <div className="p-3 bg-slate-50 border border-slate-200 rounded-md font-medium text-slate-800">
              <div className="text-[10px] text-slate-400 font-bold mb-1">STEP 6</div>
              Self-Attention
            </div>

            <div className="hidden md:flex items-center justify-center text-slate-400 font-bold">→</div>

            <div className="p-3 bg-slate-50 border border-slate-200 rounded-md font-medium text-slate-800">
              <div className="text-[10px] text-slate-400 font-bold mb-1">STEP 7</div>
              Chatbot Output
            </div>
          </div>
        </div>

        {/* BOTTOM SECTION 2: Demonstration Mode Breakdown */}
        {currentAnalysis && (
          <div className="bg-white border border-slate-200 rounded-lg p-5 shadow-xs flex flex-col gap-4">
            <div className="border-b border-slate-100 pb-2">
              <h2 className="text-sm font-bold text-slate-900">4. Demonstration Mode Breakdown</h2>
              <p className="text-xs text-slate-500">
                Step-by-step visual audit of current evaluation sentence.
              </p>
            </div>

            {/* Token Badges Comparison */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Retained Tokens */}
              <div className="p-3.5 bg-emerald-50/60 border border-emerald-200 rounded-md">
                <div className="text-xs font-bold text-emerald-900 mb-2 flex justify-between">
                  <span>Retained Tokens (Score ≥ {parseFloat(threshold).toFixed(2)})</span>
                  <span>Count: {currentAnalysis.selected_tokens}</span>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {currentAnalysis.retained_tokens.map((t, i) => (
                    <span key={i} className="text-xs font-mono font-medium px-2 py-1 rounded bg-white text-emerald-800 border border-emerald-300 shadow-2xs">
                      [{t} ✓]
                    </span>
                  ))}
                  {currentAnalysis.retained_tokens.length === 0 && (
                    <span className="text-xs text-slate-400 italic">No tokens retained</span>
                  )}
                </div>
              </div>

              {/* Filtered Tokens */}
              <div className="p-3.5 bg-rose-50/60 border border-rose-200 rounded-md">
                <div className="text-xs font-bold text-rose-900 mb-2 flex justify-between">
                  <span>Filtered Tokens (Score &lt; {parseFloat(threshold).toFixed(2)})</span>
                  <span>Count: {currentAnalysis.filtered_tokens.length}</span>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {currentAnalysis.filtered_tokens.map((t, i) => (
                    <span key={i} className="text-xs font-mono font-medium px-2 py-1 rounded bg-white text-rose-800 border border-rose-300 shadow-2xs">
                      [{t} ×]
                    </span>
                  ))}
                  {currentAnalysis.filtered_tokens.length === 0 && (
                    <span className="text-xs text-slate-400 italic">No tokens filtered</span>
                  )}
                </div>
              </div>
            </div>

            {/* Exact Calculation Math Box */}
            <div className="p-3 bg-slate-50 border border-slate-200 rounded-md text-xs font-mono text-slate-700 flex flex-col gap-1.5">
              <div className="font-bold text-slate-900 font-sans text-xs">Dynamic Calculation Formula:</div>
              <div>• Tokens Saved = Original Tokens ({currentAnalysis.original_tokens}) - Selected Tokens ({currentAnalysis.selected_tokens}) = <span className="font-bold text-blue-700">{currentAnalysis.tokens_saved}</span></div>
              <div>• Token Saving % = (Tokens Saved ({currentAnalysis.tokens_saved}) / Original Tokens ({currentAnalysis.original_tokens})) × 100 = <span className="font-bold text-indigo-700">{currentAnalysis.saving_percentage}%</span></div>
            </div>
          </div>
        )}

      </main>

      {/* Corporate Footer */}
      <footer className="bg-white border-t border-slate-200 py-3 text-center text-xs text-slate-500 mt-auto">
        Confidence-Based Token Evaluator in Transformer Models — Academic Project Demonstration
      </footer>
    </div>
  );
}
