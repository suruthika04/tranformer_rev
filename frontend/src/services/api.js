const API_BASE = 'http://localhost:8000/api';

function getHeaders() {
  const headers = { 'Content-Type': 'application/json' };
  const token = localStorage.getItem('nexa_token');
  if (token) headers['Authorization'] = `Bearer ${token}`;
  return headers;
}

export async function apiRequest(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  const config = {
    headers: getHeaders(),
    ...options,
  };
  const res = await fetch(url, config);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || err.message || 'Request failed');
  }
  return res.json();
}

// Auth
export const signup = (data) =>
  apiRequest('/auth/signup', { method: 'POST', body: JSON.stringify(data) });

export const login = (data) =>
  apiRequest('/auth/login', { method: 'POST', body: JSON.stringify(data) });

export const getMe = () => apiRequest('/auth/me');

// Conversations
export const getConversations = () => apiRequest('/conversations');

export const createConversation = (title) =>
  apiRequest('/conversations', {
    method: 'POST',
    body: JSON.stringify({ title }),
  });

export const getMessages = (convId) =>
  apiRequest(`/conversations/${convId}/messages`);

export const deleteConversation = (convId) =>
  apiRequest(`/conversations/${convId}`, { method: 'DELETE' });

export const renameConversation = (convId, title) =>
  apiRequest(`/conversations/${convId}`, {
    method: 'PATCH',
    body: JSON.stringify({ title }),
  });

// Chat streaming
export function streamChat(message, conversationId, threshold, onEvent) {
  const token = localStorage.getItem('nexa_token');
  const body = JSON.stringify({
    message,
    conversation_id: conversationId,
    threshold,
  });

  return fetch(`${API_BASE}/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body,
  }).then(async (res) => {
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Stream failed');
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop();
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6));
            onEvent(data);
          } catch {}
        }
      }
    }
    // Process remaining buffer
    if (buffer.startsWith('data: ')) {
      try {
        const data = JSON.parse(buffer.slice(6));
        onEvent(data);
      } catch {}
    }
  });
}

// Token evaluation
export const evaluateTokens = (text, threshold) =>
  apiRequest('/evaluate', {
    method: 'POST',
    body: JSON.stringify({ text, threshold }),
  });

export const recalculateTokens = (tokenAnalysis, threshold) =>
  apiRequest('/recalculate', {
    method: 'POST',
    body: JSON.stringify({ token_analysis: tokenAnalysis, threshold }),
  });

// Health
export const getHealth = () =>
  fetch(`${API_BASE}/health`).then((r) => r.json());

// File upload
export function uploadFile(file) {
  const token = localStorage.getItem('nexa_token');
  const formData = new FormData();
  formData.append('file', file);
  return fetch(`${API_BASE}/upload`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: formData,
  }).then((r) => {
    if (!r.ok) throw new Error('Upload failed');
    return r.json();
  });
}
