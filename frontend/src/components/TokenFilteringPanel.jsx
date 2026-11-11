import React, { useState } from 'react';
import { 
  X, 
  Sparkles, 
  ShieldCheck, 
  ShieldAlert, 
  Clock, 
  Cpu, 
  Send, 
  Eye,
  CheckCircle2,
  AlertTriangle
} from 'lucide-react';
import { useChat } from '../contexts/ChatContext';
import { recalculateTokens } from '../services/api';
import ThresholdControl from './ThresholdControl';
import TokenConfidenceView from './TokenConfidenceView';

export default function TokenFilteringPanel({ isOpen, onClose }) {
  const { tokenMetrics, threshold, setThreshold, setTokenMetrics, isStreaming } = useChat();
  const [isRecalculating, setIsRecalculating] = useState(false);

  const handleThresholdChange = async (newVal) => {
    setThreshold(newVal);
    if (tokenMetrics?.token_analysis && tokenMetrics.token_analysis.length > 0) {
      setIsRecalculating(true);
      try {
        const updated = await recalculateTokens(tokenMetrics.token_analysis, newVal);
        setTokenMetrics((prev) => ({
          ...prev,
          ...updated,
          confidence_threshold: newVal,
        }));
      } catch (err) {
        console.error('Recalculation error:', err);
      } finally {
        setIsRecalculating(false);
      }
    }
  };

  if (!isOpen) return null;

  return (
    <aside className="token-panel">
      <div className="token-panel-header">
        <div className="token-panel-title-box">
          <Sparkles size={16} color="#a855f7" />
          <span className="token-panel-title">Token Filtering Engine</span>
        </div>
        <button className="panel-close-btn" onClick={onClose} title="Close Panel">
          <X size={16} />
        </button>
      </div>

      <div className="token-panel-body">
        {!tokenMetrics ? (
          <div className="token-empty-state">
            <div className="token-empty-icon">
              <Cpu size={24} />
            </div>
            <div style={{ fontWeight: 600, color: '#e2e8f0', fontSize: '13px' }}>
              No Evaluation Data
            </div>
            <div style={{ fontSize: '12px' }}>
              Send a prompt to trigger the confidence-based token evaluation engine.
            </div>
          </div>
        ) : (
          <>
            {/* 1. Overall Message Confidence Score */}
            <div className="confidence-card">
              <div className="confidence-info">
                <span className="confidence-label">Message Confidence</span>
                <span className="confidence-score-val">
                  {typeof tokenMetrics.message_confidence === 'number'
                    ? `${(tokenMetrics.message_confidence * 100).toFixed(0)}%`
                    : 'N/A'}
                </span>
              </div>
              <div className="confidence-gauge-badge">
                <CheckCircle2 size={14} />
                <span>Evaluated</span>
              </div>
            </div>

            {/* 2. Token Reduction Stats Grid */}
            <div className="token-stats-grid">
              <div className="token-stat-card">
                <span className="stat-label">Original Tokens</span>
                <span className="stat-value">{tokenMetrics.original_tokens ?? 0}</span>
              </div>
              <div className="token-stat-card">
                <span className="stat-label">Selected Tokens</span>
                <span className="stat-value green">{tokenMetrics.selected_tokens ?? 0}</span>
              </div>
              <div className="token-stat-card">
                <span className="stat-label">Filtered Tokens</span>
                <span className="stat-value red">
                  {tokenMetrics.filtered_tokens_count ??
                    (tokenMetrics.tokens_saved ?? 0)}
                </span>
              </div>
              <div className="token-stat-card">
                <span className="stat-label">Token Reduction</span>
                <span className="stat-value purple">
                  {parseFloat(tokenMetrics.token_saving_percentage || 0).toFixed(1)}%
                </span>
              </div>
            </div>

            {/* 3. Interactive Threshold Slider */}
            <ThresholdControl
              threshold={threshold}
              onChange={handleThresholdChange}
              disabled={isStreaming || isRecalculating}
            />

            {/* 4. Semantic Safety Status */}
            <div
              className={`semantic-safety-box ${
                tokenMetrics.semantic_fallback_activated ? 'fallback' : 'passed'
              }`}
            >
              {tokenMetrics.semantic_fallback_activated ? (
                <ShieldAlert size={16} style={{ flexShrink: 0, marginTop: '2px' }} />
              ) : (
                <ShieldCheck size={16} style={{ flexShrink: 0, marginTop: '2px' }} />
              )}
              <div>
                <div style={{ fontWeight: 600 }}>
                  {tokenMetrics.semantic_fallback_activated
                    ? 'Semantic Fallback Active'
                    : 'Semantic Safety Preserved'}
                </div>
                <div style={{ fontSize: '11px', opacity: 0.85, marginTop: '2px' }}>
                  {tokenMetrics.semantic_preservation_message ||
                    'Critical keywords, negations, and technical entities are protected.'}
                </div>
              </div>
            </div>

            {/* 5. Latency / Timing */}
            {(tokenMetrics.latency_seconds || tokenMetrics.evaluation_time_ms) && (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '8px 12px',
                  background: '#13131e',
                  border: '1px solid #1f1f2e',
                  borderRadius: '8px',
                  fontSize: '11px',
                  color: '#94a3b8',
                }}
              >
                <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Clock size={13} color="#a855f7" />
                  <span>Response Latency</span>
                </span>
                <span style={{ fontWeight: 600, color: '#e2e8f0' }}>
                  {tokenMetrics.latency_seconds ? `${tokenMetrics.latency_seconds}s` : 'N/A'}
                </span>
              </div>
            )}

            {/* 6. Token Confidence Chips & Feature Inspector */}
            <TokenConfidenceView tokenAnalysis={tokenMetrics.token_analysis} />

            {/* 7. Final Prompt Preview */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <div className="section-label">
                <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                  <Send size={12} color="#a855f7" />
                  <span>Prompt Sent to Gemini</span>
                </span>
              </div>
              <div className="prompt-preview-box">
                {tokenMetrics.selected_text || 'Original prompt sent'}
              </div>
            </div>
          </>
        )}
      </div>
    </aside>
  );
}
