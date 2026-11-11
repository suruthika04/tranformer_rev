import React, { useState, useEffect } from 'react';
import { 
  Plus, 
  MessageSquare, 
  Trash2, 
  Search, 
  Bot, 
  LogOut, 
  Sparkles,
  ChevronRight
} from 'lucide-react';
import { useChat } from '../contexts/ChatContext';
import { useAuth } from '../contexts/AuthContext';

export default function Sidebar({ isOpen, onClose }) {
  const { 
    conversations, 
    activeConversation, 
    selectConversation, 
    newConversation, 
    deleteConversation,
    loadConversations
  } = useChat();
  const { user, logout } = useAuth();
  const [searchTerm, setSearchTerm] = useState('');

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  const filteredConversations = (conversations || []).filter((c) =>
    (c.title || 'New Conversation').toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <aside className={`sidebar ${isOpen ? 'open' : ''}`}>
      <div className="sidebar-header">
        <div className="brand-wrapper">
          <div className="brand-logo-icon">
            <Bot size={18} color="#ffffff" />
          </div>
          <div>
            <div className="brand-title">NEXA AI</div>
            <div style={{ fontSize: '10px', color: '#64748b' }}>Enterprise Token Evaluator</div>
          </div>
        </div>
      </div>

      <button className="new-chat-btn" onClick={() => newConversation()}>
        <Plus size={16} />
        <span>New Conversation</span>
      </button>

      <div className="sidebar-search">
        <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
          <Search size={14} style={{ position: 'absolute', left: '10px', color: '#64748b' }} />
          <input
            type="text"
            className="search-input-box"
            placeholder="Search conversations..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
      </div>

      <div className="sidebar-section-title">Recent Conversations</div>

      <div className="conversation-list">
        {filteredConversations.length === 0 ? (
          <div style={{ padding: '16px', fontSize: '12px', color: '#475569', textAlign: 'center' }}>
            No conversations found
          </div>
        ) : (
          filteredConversations.map((conv) => {
            const isActive = activeConversation?.id === conv.id;
            return (
              <div
                key={conv.id}
                className={`conversation-item ${isActive ? 'active' : ''}`}
                onClick={() => selectConversation(conv)}
              >
                <MessageSquare size={14} style={{ marginRight: '8px', flexShrink: 0 }} />
                <span className="conv-title-text">{conv.title || 'New Conversation'}</span>
                <div className="conv-actions">
                  <button
                    className="conv-action-btn"
                    onClick={(e) => {
                      e.stopPropagation();
                      deleteConversation(conv.id);
                    }}
                    title="Delete Conversation"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>

      {user && (
        <div className="sidebar-footer">
          <div className="user-badge">
            <div className="user-avatar">
              {user.name ? user.name[0].toUpperCase() : 'U'}
            </div>
            <div className="user-info">
              <span className="user-name">{user.name || 'User'}</span>
              <span className="user-email">{user.email}</span>
            </div>
          </div>
          <button className="logout-icon-btn" onClick={logout} title="Sign Out">
            <LogOut size={16} />
          </button>
        </div>
      )}
    </aside>
  );
}
