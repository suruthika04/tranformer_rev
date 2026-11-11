import React, { useState } from 'react';
import { Check, Copy } from 'lucide-react';

export default function CodeBlock({ language, value }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    if (!value) return;
    navigator.clipboard.writeText(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="code-block-container">
      <div className="code-block-header">
        <span className="code-language-tag">{language || 'code'}</span>
        <button className="copy-code-btn" onClick={handleCopy}>
          {copied ? (
            <>
              <Check size={13} color="#22c55e" />
              <span style={{ color: '#22c55e' }}>Copied!</span>
            </>
          ) : (
            <>
              <Copy size={13} />
              <span>Copy Code</span>
            </>
          )}
        </button>
      </div>
      <pre className="code-content">
        <code>{value}</code>
      </pre>
    </div>
  );
}
