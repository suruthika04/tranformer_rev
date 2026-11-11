import React, { useState } from 'react';
import Sidebar from '../components/Sidebar';
import Header from '../components/Header';
import ChatWindow from '../components/ChatWindow';
import TokenFilteringPanel from '../components/TokenFilteringPanel';
import '../styles/chat.css';
import '../styles/token-filter.css';

export default function ChatPage() {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isTokenPanelOpen, setIsTokenPanelOpen] = useState(true);

  return (
    <div className="app-layout">
      <Sidebar isOpen={isSidebarOpen} onClose={() => setIsSidebarOpen(false)} />

      <div className="main-wrapper">
        <Header
          toggleSidebar={() => setIsSidebarOpen(!isSidebarOpen)}
          toggleTokenPanel={() => setIsTokenPanelOpen(!isTokenPanelOpen)}
          isTokenPanelOpen={isTokenPanelOpen}
        />

        <div className="content-row">
          <ChatWindow toggleTokenPanel={() => setIsTokenPanelOpen(!isTokenPanelOpen)} />
          <TokenFilteringPanel
            isOpen={isTokenPanelOpen}
            onClose={() => setIsTokenPanelOpen(false)}
          />
        </div>
      </div>
    </div>
  );
}
