/**
 * Header — top bar with model indicator, connection status, auth trigger, new chat.
 */
import React from "react";
import { Plus, PanelLeft, LogIn, UserCircle, Cpu } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import { useChat } from "../contexts/ChatContext";

export default function Header({ sidebarCollapsed, onToggleSidebar, onOpenAuth, modelStatus }) {
  const { user } = useAuth();
  const { startNewChat, activeConvId, conversations } = useChat();

  const currentTitle = conversations.find((c) => c.id === activeConvId)?.title || "Nexa AI";

  return (
    <header className="h-13 border-b border-[#222] bg-[#111] px-4 flex items-center justify-between z-10 shrink-0">
      <div className="flex items-center gap-3">
        {sidebarCollapsed && (
          <button
            onClick={onToggleSidebar}
            className="p-1.5 rounded-lg text-[#777] hover:text-white hover:bg-white/5 transition"
            title="Expand sidebar"
          >
            <PanelLeft size={17} />
          </button>
        )}

        <button
          onClick={startNewChat}
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium text-[#ccc] hover:text-white hover:bg-white/5 transition"
          title="New conversation"
        >
          <Plus size={14} />
          <span className="hidden sm:inline">New Chat</span>
        </button>

        <div className="h-4 w-[1px] bg-[#222]" />

        <div className="flex items-center gap-2 text-xs">
          <span className="text-[#eee] font-medium max-w-[200px] sm:max-w-xs truncate">
            {currentTitle}
          </span>
        </div>
      </div>

      <div className="flex items-center gap-3">
        {/* Model status tag */}
        <div className="hidden sm:flex items-center gap-2 px-2.5 py-1 rounded-full bg-white/5 border border-[#262626] text-[11px] text-[#888]">
          <span className={`w-1.5 h-1.5 rounded-full ${modelStatus?.online ? "bg-emerald-400" : "bg-amber-400"}`} />
          <span className="font-mono truncate max-w-[150px]">
            {modelStatus?.name || "Initializing..."}
          </span>
        </div>

        {/* Auth profile / sign in */}
        {user ? (
          <div className="flex items-center gap-2 text-xs text-[#aaa]">
            <div className="w-6 h-6 rounded-full bg-white/10 flex items-center justify-center text-[10px] text-white font-medium">
              {user.name?.[0]?.toUpperCase() || "U"}
            </div>
            <span className="hidden md:inline font-medium text-white">{user.name}</span>
          </div>
        ) : (
          <button
            onClick={onOpenAuth}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white text-black text-xs font-semibold hover:bg-[#ddd] transition shadow-xs cursor-pointer"
          >
            <LogIn size={13} />
            <span>Sign In</span>
          </button>
        )}
      </div>
    </header>
  );
}
