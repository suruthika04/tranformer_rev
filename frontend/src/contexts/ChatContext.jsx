/**
 * ChatContext — manages conversations, messages, active conversation state,
 * and the streaming inference pipeline.
 */
import React, {
  createContext,
  useCallback,
  useContext,
  useRef,
  useState,
} from "react";
import {
  createConversation,
  deleteConversation,
  getMessages,
  listConversations,
  renameConversation,
  streamChat,
  uploadFile,
} from "../api/client";
import { useAuth } from "./AuthContext";

const ChatContext = createContext(null);

export function ChatProvider({ children }) {
  const { token } = useAuth();

  // Sidebar conversation list
  const [conversations, setConversations] = useState([]);
  const [convsLoading, setConvsLoading] = useState(false);

  // Active conversation
  const [activeConvId, setActiveConvId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [messagesLoading, setMessagesLoading] = useState(false);

  // Streaming state
  const [streaming, setStreaming] = useState(false);
  const [streamingText, setStreamingText] = useState("");
  const abortRef = useRef(null);

  // Global threshold for token evaluator
  const [threshold, setThreshold] = useState(0.5);

  // Pending attachment
  const [attachment, setAttachment] = useState(null); // { file, fileId, preview, type }
  const [uploadProgress, setUploadProgress] = useState(null);

  // ─── Load conversation list ─────────────────────────────────────────────
  const loadConversations = useCallback(async () => {
    if (!token) return;
    setConvsLoading(true);
    try {
      const data = await listConversations(token);
      setConversations(data);
    } catch (err) {
      console.error("loadConversations:", err);
    } finally {
      setConvsLoading(false);
    }
  }, [token]);

  // ─── Open conversation ──────────────────────────────────────────────────
  const openConversation = useCallback(
    async (convId) => {
      if (streaming) stopGeneration();
      setActiveConvId(convId);
      setMessages([]);
      setStreamingText("");

      if (!token) return;
      setMessagesLoading(true);
      try {
        const msgs = await getMessages(token, convId);
        setMessages(
          msgs.map((m) => ({
            id: m.id,
            role: m.role,
            content: m.content,
            timestamp: m.created_at,
            metrics: m.metrics,
            status: m.status,
          }))
        );
      } catch (err) {
        console.error("openConversation:", err);
      } finally {
        setMessagesLoading(false);
      }
    },
    [token, streaming]
  );

  // ─── New chat ────────────────────────────────────────────────────────────
  const startNewChat = useCallback(() => {
    if (streaming) stopGeneration();
    setActiveConvId(null);
    setMessages([]);
    setStreamingText("");
    setAttachment(null);
    setUploadProgress(null);
  }, [streaming]);

  // ─── Rename ──────────────────────────────────────────────────────────────
  const renameConv = useCallback(
    async (convId, title) => {
      await renameConversation(token, convId, title);
      setConversations((prev) =>
        prev.map((c) => (c.id === convId ? { ...c, title } : c))
      );
    },
    [token]
  );

  // ─── Delete ──────────────────────────────────────────────────────────────
  const deleteConv = useCallback(
    async (convId) => {
      await deleteConversation(token, convId);
      setConversations((prev) => prev.filter((c) => c.id !== convId));
      if (activeConvId === convId) startNewChat();
    },
    [token, activeConvId, startNewChat]
  );

  // ─── Upload attachment ────────────────────────────────────────────────────
  const attachFile = useCallback(
    async (file) => {
      if (!token) {
        // Without auth, create a local preview only (no server upload)
        const isImage = file.type.startsWith("image/");
        const preview = isImage ? URL.createObjectURL(file) : null;
        setAttachment({ file, fileId: null, preview, isImage, filename: file.name });
        return;
      }

      setUploadProgress(0);
      try {
        const result = await uploadFile(token, file, setUploadProgress);
        const isImage = result.is_image;
        const preview = isImage ? URL.createObjectURL(file) : null;
        setAttachment({
          file,
          fileId: result.file_id,
          preview,
          isImage,
          filename: result.filename,
          contentType: result.content_type,
          previewText: result.preview_text,
          isDocument: result.is_document,
        });
      } catch (err) {
        throw err;
      } finally {
        setUploadProgress(null);
      }
    },
    [token]
  );

  const clearAttachment = useCallback(() => {
    if (attachment?.preview) URL.revokeObjectURL(attachment.preview);
    setAttachment(null);
    setUploadProgress(null);
  }, [attachment]);

  // ─── Stop generation ──────────────────────────────────────────────────────
  const stopGeneration = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    setStreaming(false);
  }, []);

  // ─── Send message ──────────────────────────────────────────────────────────
  const sendMessage = useCallback(
    async (text) => {
      if (!text.trim() || streaming) return;

      const controller = new AbortController();
      abortRef.current = controller;
      setStreaming(true);
      setStreamingText("");

      // Optimistically add user message to UI
      const userMsg = {
        id: `u_${Date.now()}`,
        role: "user",
        content: text.trim(),
        timestamp: new Date().toISOString(),
        attachment: attachment ? { ...attachment } : null,
      };
      setMessages((prev) => [...prev, userMsg]);

      // Ensure conversation exists in DB (if authed)
      let convId = activeConvId;
      if (token && !convId) {
        try {
          const conv = await createConversation(token, null);
          convId = conv.id;
          setActiveConvId(convId);
          setConversations((prev) => [
            { id: convId, title: text.trim().slice(0, 60), updated_at: new Date().toISOString() },
            ...prev,
          ]);
        } catch (err) {
          console.error("createConversation:", err);
        }
      }

      const fileId = attachment?.fileId || null;
      const currentAttachment = attachment;
      clearAttachment();

      // Placeholder for assistant message
      const asstId = `a_${Date.now()}`;
      let evalData = null;
      let accText = "";

      setMessages((prev) => [
        ...prev,
        { id: asstId, role: "assistant", content: "", timestamp: new Date().toISOString(), streaming: true },
      ]);

      await streamChat(
        text.trim(),
        { token, conversationId: convId, threshold, fileId, signal: controller.signal },
        // onToken
        (chunk) => {
          accText += chunk;
          setStreamingText(accText);
          setMessages((prev) =>
            prev.map((m) => (m.id === asstId ? { ...m, content: accText } : m))
          );
        },
        // onEval
        (data) => { evalData = data; },
        // onDone
        (done) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === asstId
                ? {
                    ...m,
                    content: accText || "I've processed your message.",
                    streaming: false,
                    metrics: {
                      input_tokens: done.input_tokens,
                      output_tokens: done.output_tokens,
                      latency_seconds: done.latency_seconds,
                      model_name: done.model_name,
                      ...(evalData || {}),
                    },
                  }
                : m
            )
          );
          setStreamingText("");
          setStreaming(false);
          abortRef.current = null;

          // Refresh conversation list to update title/timestamp
          if (token) loadConversations();
        },
        // onError
        (err) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === asstId
                ? { ...m, content: `⚠️ ${err}`, streaming: false, isError: true }
                : m
            )
          );
          setStreamingText("");
          setStreaming(false);
          abortRef.current = null;
        }
      );
    },
    [streaming, activeConvId, token, threshold, attachment, clearAttachment, loadConversations]
  );

  // ─── Retry last message ───────────────────────────────────────────────────
  const retryLast = useCallback(() => {
    if (streaming) return;
    // Find last user message
    const lastUser = [...messages].reverse().find((m) => m.role === "user");
    if (!lastUser) return;
    // Remove last assistant message
    setMessages((prev) => {
      const idx = prev.findLastIndex((m) => m.role === "assistant");
      return idx >= 0 ? [...prev.slice(0, idx)] : prev;
    });
    sendMessage(lastUser.content);
  }, [messages, streaming, sendMessage]);

  return (
    <ChatContext.Provider
      value={{
        conversations,
        convsLoading,
        loadConversations,
        activeConvId,
        messages,
        messagesLoading,
        streaming,
        streamingText,
        threshold,
        setThreshold,
        attachment,
        uploadProgress,
        attachFile,
        clearAttachment,
        openConversation,
        startNewChat,
        sendMessage,
        stopGeneration,
        renameConv,
        deleteConv,
        retryLast,
      }}
    >
      {children}
    </ChatContext.Provider>
  );
}

export function useChat() {
  const ctx = useContext(ChatContext);
  if (!ctx) throw new Error("useChat must be used inside ChatProvider");
  return ctx;
}
