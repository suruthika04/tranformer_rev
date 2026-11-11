import React, { useState } from 'react';
import { ChevronDown, ChevronUp, Layers } from 'lucide-react';

export default function TokenConfidenceView({ tokenAnalysis = [] }) {
  const [showTable, setShowTable] = useState(false);

  if (!tokenAnalysis || tokenAnalysis.length === 0) {
    return null;
  }

  return (
    <div className="token-chips-section">
      <div className="section-label">
        <span>Token Confidence Breakdown</span>
        <span style={{ fontSize: '11px', color: '#64748b' }}>
          {tokenAnalysis.length} tokens
        </span>
      </div>

      {/* Visual Token Chips */}
      <div className="token-chips-container">
        {tokenAnalysis.map((item, idx) => {
          const conf = item.confidence ?? 0;
          const isRetained = item.retained ?? true;
          const isLow = conf < 0.5 && isRetained;

          let chipClass = 'selected';
          if (!isRetained) chipClass = 'filtered';
          else if (isLow) chipClass = 'low-confidence';

          return (
            <div
              key={idx}
              className={`token-chip ${chipClass}`}
              title={`Token: "${item.token}" | Score: ${(conf * 100).toFixed(0)}% | Status: ${isRetained ? 'Retained' : 'Filtered'}`}
            >
              <span>{item.token}</span>
              <span className="token-chip-score">{(conf * 100).toFixed(0)}%</span>
            </div>
          );
        })}
      </div>

      {/* Table Toggle Button */}
      <button
        onClick={() => setShowTable(!showTable)}
        style={{
          background: '#13131e',
          border: '1px solid #1f1f2e',
          borderRadius: '8px',
          padding: '8px 12px',
          color: '#cbd5e1',
          fontSize: '12px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          cursor: 'pointer',
          marginTop: '6px',
        }}
      >
        <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Layers size={13} color="#a855f7" />
          <span>Detailed Feature Table</span>
        </span>
        {showTable ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
      </button>

      {/* Detailed Table */}
      {showTable && (
        <div className="token-table-wrap">
          <table className="token-table">
            <thead>
              <tr>
                <th>Token</th>
                <th>Score</th>
                <th>Status</th>
                <th>Key Features</th>
              </tr>
            </thead>
            <tbody>
              {tokenAnalysis.map((item, idx) => {
                const conf = item.confidence ?? 0;
                const isRetained = item.retained ?? true;
                const features = item.features || {};
                const topFeatures = Object.entries(features)
                  .filter(([_, v]) => v > 0.5)
                  .map(([k]) => k.replace('_score', '').replace('_relevance', ''))
                  .slice(0, 2)
                  .join(', ') || 'base';

                return (
                  <tr key={idx}>
                    <td style={{ fontFamily: 'monospace', fontWeight: 600 }}>{item.token}</td>
                    <td>
                      <span
                        style={{
                          fontWeight: 700,
                          color: conf >= 0.7 ? '#4ade80' : conf >= 0.4 ? '#facc15' : '#f87171',
                        }}
                      >
                        {conf.toFixed(2)}
                      </span>
                    </td>
                    <td>
                      <span className={`status-badge ${isRetained ? 'selected' : 'filtered'}`}>
                        {isRetained ? 'Selected' : 'Filtered'}
                      </span>
                    </td>
                    <td style={{ color: '#94a3b8', fontSize: '10px' }}>
                      {topFeatures}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
