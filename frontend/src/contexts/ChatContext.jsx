import { createContext, useContext, useState, useCallback } from 'react';
import {
  getConversations,
  createConversation,
  getMessages,
  deleteConversation as apiDeleteConv,
  streamChat,
} from '../services/api';

const ChatContext = createContext(null);

export function ChatProvider({ children }) {
  const [conversations, setConversations] = useState([]);
  const [activeConversation, setActiveConversation] = useState(null);
  const [messages, setMessages] = useState([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [tokenMetrics, setTokenMetrics] = useState(null);
  const [threshold, setThreshold] = useState(0.5);

  const loadConversations = useCallback(async () => {
    try {
      const data = await getConversations();
      setConversations(data);
    } catch {}
  }, []);

  const selectConversation = useCallback(async (conv) => {
    setActiveConversation(conv);
    setTokenMetrics(null);
    try {
      const msgs = await getMessages(conv.id);
      setMessages(msgs);
    } catch {
      setMessages([]);
    }
  }, []);

  const newConversation = useCallback(async () => {
    try {
      const conv = await createConversation('New Conversation');
      setActiveConversation(conv);
      setMessages([]);
      setTokenMetrics(null);
      await loadConversations();
      return conv;
    } catch (err) {
      throw err;
    }
  }, [loadConversations]);

  const deleteConversation = useCallback(
    async (convId) => {
      try {
        await apiDeleteConv(convId);
        if (activeConversation?.id === convId) {
          setActiveConversation(null);
          setMessages([]);
          setTokenMetrics(null);
        }
        await loadConversations();
      } catch {}
    },
    [activeConversation, loadConversations]
  );

  const sendMessage = useCallback(
    async (text) => {
      if (!text.trim() || isStreaming) return;

      let convId = activeConversation?.id;

      // Auto-create conversation if none exists
      if (!convId) {
        try {
          const conv = await createConversation('New Conversation');
          convId = conv.id;
          setActiveConversation(conv);
        } catch (err) {
          throw err;
        }
      }

      // Add user message
      const userMsg = {
        id: `temp-${Date.now()}`,
        role: 'user',
        content: text,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, userMsg]);

      // Add placeholder for assistant
      const assistantMsgId = `assistant-${Date.now()}`;
      const assistantMsg = {
        id: assistantMsgId,
        role: 'assistant',
        content: '',
        created_at: new Date().toISOString(),
        isStreaming: true,
      };
      setMessages((prev) => [...prev, assistantMsg]);

      setIsStreaming(true);
      setTokenMetrics(null);

      try {
        await streamChat(text, convId, threshold, (event) => {
          if (event.type === 'eval') {
            setTokenMetrics(event);
          } else if (event.type === 'token') {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsgId
                  ? { ...m, content: m.content + event.text }
                  : m
              )
            );
          } else if (event.type === 'done') {
            setTokenMetrics((prev) => ({
              ...prev,
              ...event,
              _doneReceived: true,
            }));
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsgId ? { ...m, isStreaming: false, metrics: event } : m
              )
            );
          } else if (event.type === 'error') {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsgId
                  ? { ...m, content: `Error: ${event.message}`, isStreaming: false }
                  : m
              )
            );
          }
        });
      } catch (err) {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMsgId
              ? { ...m, content: `Error: ${err.message}`, isStreaming: false }
              : m
          )
        );
      } finally {
        setIsStreaming(false);
        loadConversations();
      }
    },
    [activeConversation, isStreaming, threshold, loadConversations]
  );

  return (
    <ChatContext.Provider
      value={{
        conversations,
        activeConversation,
        messages,
        isStreaming,
        tokenMetrics,
        threshold,
        setThreshold,
        setTokenMetrics,
        loadConversations,
        selectConversation,
        newConversation,
        deleteConversation,
        sendMessage,
        setMessages,
        setActiveConversation,
      }}
    >
      {children}
    </ChatContext.Provider>
  );
}

export const useChat = () => useContext(ChatContext);
