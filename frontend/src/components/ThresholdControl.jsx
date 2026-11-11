import React from 'react';
import { Sliders } from 'lucide-react';

export default function ThresholdControl({ threshold, onChange, disabled }) {
  return (
    <div className="threshold-slider-box">
      <div className="threshold-slider-header">
        <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Sliders size={14} color="#a855f7" />
          <span>Confidence Threshold</span>
        </span>
        <span className="threshold-val-pill">
          {parseFloat(threshold).toFixed(2)}
        </span>
      </div>

      <input
        type="range"
        min="0.0"
        max="1.0"
        step="0.05"
        value={threshold}
        disabled={disabled}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="threshold-slider-input"
      />

      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', color: '#64748b' }}>
        <span>0.00 (Keep All)</span>
        <span>0.50 (Balanced)</span>
        <span>1.00 (Max Filter)</span>
      </div>
    </div>
  );
}
