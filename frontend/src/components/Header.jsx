import React from 'react';
import { Sparkles, SlidersHorizontal, LogOut, User, Menu } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

export default function Header({ toggleSidebar, toggleTokenPanel, isTokenPanelOpen }) {
  const { user, logout } = useAuth();

  return (
    <header className="chat-header">
      <div className="header-left">
        <button className="mobile-menu-btn" onClick={toggleSidebar} title="Toggle Sidebar">
          <Menu size={20} />
        </button>
        <div className="model-status-pill">
          <div className="status-dot-active" />
          <span>Gemini 2.0 Flash</span>
          <span style={{ color: '#64748b', fontSize: '11px' }}>•</span>
          <span style={{ color: '#a855f7', fontWeight: 600 }}>Active</span>
        </div>
      </div>

      <div className="header-right">
        <button
          className={`header-action-btn ${isTokenPanelOpen ? 'active' : ''}`}
          onClick={toggleTokenPanel}
          title="Toggle Token Evaluator Panel"
        >
          <SlidersHorizontal size={15} color="#c084fc" />
          <span>Token Evaluator</span>
        </button>

        {user ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '50%',
                background: 'linear-gradient(135deg, #7c3aed, #4c1d95)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '12px',
                fontWeight: 700,
                color: '#fff',
              }}
              title={user.email}
            >
              {user.name ? user.name[0].toUpperCase() : 'U'}
            </div>
            <button
              onClick={logout}
              className="logout-icon-btn"
              title="Logout"
            >
              <LogOut size={16} />
            </button>
          </div>
        ) : null}
      </div>
    </header>
  );
}
