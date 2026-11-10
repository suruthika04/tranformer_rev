/**
 * Sidebar component — conversation list, new chat, search, rename/delete.
 */
import React, { useEffect, useRef, useState } from "react";
import {
  Check,
  ChevronLeft,
  ChevronRight,
  LogOut,
  MessageSquare,
  Pencil,
  Plus,
  Search,
  Trash2,
  User,
  X,
  Zap,
} from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import { useChat } from "../contexts/ChatContext";

export default function Sidebar({ collapsed, onToggle }) {
  const { user, logout } = useAuth();
  const {
    conversations,
    convsLoading,
    loadConversations,
    activeConvId,
    openConversation,
    startNewChat,
    renameConv,
    deleteConv,
  } = useChat();

  const [search, setSearch] = useState("");
  const [renamingId, setRenamingId] = useState(null);
  const [renameValue, setRenameValue] = useState("");
  const [deletingId, setDeletingId] = useState(null);
  const renameInputRef = useRef(null);

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  useEffect(() => {
    if (renamingId && renameInputRef.current) {
      renameInputRef.current.focus();
      renameInputRef.current.select();
    }
  }, [renamingId]);

  const filtered = conversations.filter((c) =>
    c.title?.toLowerCase().includes(search.toLowerCase())
  );

  const handleRenameSubmit = async (id) => {
    const v = renameValue.trim();
    if (v) {
      try { await renameConv(id, v); } catch (_) {}
    }
    setRenamingId(null);
  };

  const handleDelete = async (id) => {
    setDeletingId(id);
    try { await deleteConv(id); } catch (_) {}
    setDeletingId(null);
  };

  if (collapsed) {
    return (
      <div className="w-14 h-screen bg-[#111111] border-r border-[#2a2a2a] flex flex-col items-center py-3 gap-3 shrink-0">
        <div className="w-8 h-8 rounded-lg bg-white/10 flex items-center justify-center">
          <Zap size={15} className="text-white" />
        </div>
        <button
          onClick={startNewChat}
          className="w-9 h-9 rounded-lg hover:bg-white/10 flex items-center justify-center text-[#aaa] hover:text-white transition"
          title="New Chat"
        >
          <Plus size={17} />
        </button>
        <button
          onClick={onToggle}
          className="mt-auto w-9 h-9 rounded-lg hover:bg-white/10 flex items-center justify-center text-[#555] hover:text-white transition"
          title="Expand sidebar"
        >
          <ChevronRight size={16} />
        </button>
      </div>
    );
  }

  return (
    <div className="w-64 h-screen bg-[#111111] border-r border-[#2a2a2a] flex flex-col shrink-0">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[#222]">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-md bg-white/10 flex items-center justify-center">
            <Zap size={14} className="text-white" />
          </div>
          <span className="font-semibold text-white text-sm tracking-tight">Nexa AI</span>
        </div>
        <button
          onClick={onToggle}
          className="p-1 rounded hover:bg-white/10 text-[#555] hover:text-white transition"
          title="Collapse sidebar"
        >
          <ChevronLeft size={16} />
        </button>
      </div>

      {/* New Chat */}
      <div className="px-3 py-2">
        <button
          onClick={startNewChat}
          className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-[#ccc] hover:text-white hover:bg-white/8 transition group"
        >
          <Plus size={15} className="text-[#666] group-hover:text-white transition" />
          New chat
        </button>
      </div>

      {/* Search */}
      <div className="px-3 pb-2">
        <div className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-white/5 border border-[#2a2a2a]">
          <Search size={13} className="text-[#555] shrink-0" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search conversations"
            className="flex-1 bg-transparent text-xs text-[#ccc] placeholder-[#555] focus:outline-none"
          />
          {search && (
            <button onClick={() => setSearch("")} className="text-[#555] hover:text-white">
              <X size={12} />
            </button>
          )}
        </div>
      </div>

      {/* Conversation List */}
      <div className="flex-1 overflow-y-auto px-2 pb-2 space-y-0.5 custom-scrollbar">
        {!user && (
          <p className="text-[11px] text-[#555] px-3 py-2">Sign in to save chats</p>
        )}

        {convsLoading && (
          <div className="flex items-center gap-2 px-3 py-2 text-xs text-[#555]">
            <div className="w-3 h-3 rounded-full border border-[#555] border-t-transparent animate-spin" />
            Loading...
          </div>
        )}

        {!convsLoading && user && filtered.length === 0 && (
          <p className="text-[11px] text-[#555] px-3 py-2">
            {search ? "No results." : "No conversations yet."}
          </p>
        )}

        {filtered.map((conv) => {
          const isActive = conv.id === activeConvId;
          const isRenaming = renamingId === conv.id;
          const isDeleting = deletingId === conv.id;

          return (
            <div
              key={conv.id}
              className={`group flex items-center gap-1.5 rounded-lg px-2 py-1.5 cursor-pointer transition ${
                isActive ? "bg-white/10 text-white" : "text-[#aaa] hover:bg-white/6 hover:text-white"
              }`}
              onClick={() => !isRenaming && openConversation(conv.id)}
            >
              <MessageSquare size={13} className="shrink-0 opacity-60" />

              {isRenaming ? (
                <input
                  ref={renameInputRef}
                  value={renameValue}
                  onChange={(e) => setRenameValue(e.target.value)}
                  onBlur={() => handleRenameSubmit(conv.id)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") handleRenameSubmit(conv.id);
                    if (e.key === "Escape") setRenamingId(null);
                  }}
                  onClick={(e) => e.stopPropagation()}
                  className="flex-1 bg-transparent text-xs text-white focus:outline-none border-b border-white/40"
                />
              ) : (
                <span className="flex-1 text-xs truncate">{conv.title || "New Conversation"}</span>
              )}

              {/* Action buttons */}
              <div
                className={`flex items-center gap-0.5 ${isActive ? "opacity-100" : "opacity-0 group-hover:opacity-100"} transition`}
                onClick={(e) => e.stopPropagation()}
              >
                <button
                  onClick={() => {
                    setRenamingId(conv.id);
                    setRenameValue(conv.title || "");
                  }}
                  className="p-1 rounded hover:bg-white/15 text-[#777] hover:text-white transition"
                  title="Rename"
                >
                  <Pencil size={11} />
                </button>
                <button
                  onClick={() => handleDelete(conv.id)}
                  disabled={isDeleting}
                  className="p-1 rounded hover:bg-rose-500/20 text-[#777] hover:text-rose-400 transition"
                  title="Delete"
                >
                  {isDeleting ? (
                    <div className="w-2.5 h-2.5 rounded-full border border-current border-t-transparent animate-spin" />
                  ) : (
                    <Trash2 size={11} />
                  )}
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* User Profile */}
      <div className="border-t border-[#222] px-3 py-3">
        {user ? (
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-full bg-white/15 flex items-center justify-center text-xs font-semibold text-white shrink-0">
              {user.name?.[0]?.toUpperCase() || "U"}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-white truncate">{user.name}</p>
              <p className="text-[10px] text-[#666] truncate">{user.email}</p>
            </div>
            <button
              onClick={logout}
              className="p-1.5 rounded-lg hover:bg-white/10 text-[#555] hover:text-white transition"
              title="Sign out"
            >
              <LogOut size={13} />
            </button>
          </div>
        ) : (
          <p className="text-[11px] text-[#555] text-center">Not signed in</p>
        )}
      </div>
    </div>
  );
}
