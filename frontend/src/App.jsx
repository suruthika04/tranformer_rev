import React, { useState, useEffect, useRef } from "react";
import Sidebar from "./components/Sidebar";
import Header from "./components/Header";
import MessageBubble from "./components/MessageBubble";
import Composer from "./components/Composer";
import WelcomeScreen from "./components/WelcomeScreen";
import AuthModal from "./components/AuthModal";
import { AuthProvider } from "./contexts/AuthContext";
import { ChatProvider, useChat } from "./contexts/ChatContext";
import { fetchHealth } from "./api/client";

function ChatApp() {
  const { messages, messagesLoading, activeConvId } = useChat();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [modelStatus, setModelStatus] = useState({ online: false, name: "Connecting..." });
  const messagesEndRef = useRef(null);

  useEffect(() => {
    fetchHealth()
      .then((data) => {
        setModelStatus({
          online: data.model_loaded,
          name: data.model_name || "Active",
        });
      })
      .catch(() => {
        setModelStatus({ online: false, name: "Offline" });
      });
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="flex h-screen w-screen bg-[#0e0e0e] text-[#e0e0e0] font-sans overflow-hidden">
      {/* Sidebar */}
      <Sidebar
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
      />

      {/* Main View Area */}
      <div className="flex-1 flex flex-col h-full min-w-0 bg-[#0e0e0e]">
        <Header
          sidebarCollapsed={sidebarCollapsed}
          onToggleSidebar={() => setSidebarCollapsed(!sidebarCollapsed)}
          onOpenAuth={() => setAuthModalOpen(true)}
          modelStatus={modelStatus}
        />

        {/* Scrollable Conversation Stream */}
        <main className="flex-1 overflow-y-auto custom-scrollbar flex flex-col">
          {messagesLoading ? (
            <div className="flex-1 flex items-center justify-center text-xs text-[#666]">
              <div className="w-4 h-4 rounded-full border border-[#666] border-t-transparent animate-spin mr-2" />
              Loading messages...
            </div>
          ) : messages.length === 0 ? (
            <WelcomeScreen />
          ) : (
            <div className="max-w-3xl w-full mx-auto px-4 py-6 flex-1">
              {messages.map((msg, idx) => (
                <MessageBubble
                  key={msg.id || idx}
                  message={msg}
                  isLast={idx === messages.length - 1}
                />
              ))}
              <div ref={messagesEndRef} />
            </div>
          )}
        </main>

        {/* Bottom Message Composer */}
        <Composer />
      </div>

      {/* Auth Modal */}
      <AuthModal isOpen={authModalOpen} onClose={() => setAuthModalOpen(false)} />
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <ChatProvider>
        <ChatApp />
      </ChatProvider>
    </AuthProvider>
  );
}
