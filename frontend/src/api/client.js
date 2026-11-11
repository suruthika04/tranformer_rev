/**
 * Nexa AI — API client
 * All backend communication is centralized here.
 */
const rawUrl = (import.meta.env.VITE_BACKEND_URL || "https://nexa-ai-backend-chi.vercel.app").trim();
export const API_BASE = rawUrl.replace(/\/+$/, "").replace(/\/api$/, "");

// ─── helpers ────────────────────────────────────────────────────────────────

function authHeaders(token) {
  const h = { "Content-Type": "application/json" };
  if (token) h["Authorization"] = `Bearer ${token}`;
  return h;
}

async function handleResponse(res) {
  if (!res.ok) {
    let msg = `Request failed (${res.status})`;
    try {
      const data = await res.json();
      msg = data.detail || data.message || msg;
    } catch (_) {}
    throw new Error(msg);
  }
  return res.json();
}

// ─── health ─────────────────────────────────────────────────────────────────

export async function fetchHealth() {
  const res = await fetch(`${API_BASE}/api/health`);
  return handleResponse(res);
}

// ─── auth ───────────────────────────────────────────────────────────────────

export async function signup(name, email, password) {
  const res = await fetch(`${API_BASE}/api/auth/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, email, password }),
  });
  return handleResponse(res);
}

export async function login(email, password) {
  const res = await fetch(`${API_BASE}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  return handleResponse(res);
}

export async function fetchMe(token) {
  const res = await fetch(`${API_BASE}/api/auth/me`, {
    headers: authHeaders(token),
  });
  return handleResponse(res);
}

// ─── conversations ───────────────────────────────────────────────────────────

export async function listConversations(token) {
  const res = await fetch(`${API_BASE}/api/conversations`, {
    headers: authHeaders(token),
  });
  return handleResponse(res);
}

export async function createConversation(token, title = null) {
  const res = await fetch(`${API_BASE}/api/conversations`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ title }),
  });
  return handleResponse(res);
}

export async function getMessages(token, conversationId) {
  const res = await fetch(`${API_BASE}/api/conversations/${conversationId}/messages`, {
    headers: authHeaders(token),
  });
  return handleResponse(res);
}

export async function renameConversation(token, conversationId, title) {
  const res = await fetch(`${API_BASE}/api/conversations/${conversationId}`, {
    method: "PATCH",
    headers: authHeaders(token),
    body: JSON.stringify({ title }),
  });
  return handleResponse(res);
}

export async function deleteConversation(token, conversationId) {
  const res = await fetch(`${API_BASE}/api/conversations/${conversationId}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
  return handleResponse(res);
}

// ─── chat (SSE streaming) ────────────────────────────────────────────────────

/**
 * Stream a chat response from the backend via SSE.
 *
 * @param {string} message - User message
 * @param {object} opts - { token, conversationId, threshold, fileId, history, signal }
 * @param {function} onToken - Called with each streamed text fragment
 * @param {function} onEval - Called with evaluator metadata object
 * @param {function} onDone - Called with final metrics
 * @param {function} onError - Called with error string
 */
export async function streamChat(message, opts, onToken, onEval, onDone, onError) {
  const { token, conversationId, threshold = 0.5, fileId, signal } = opts;

  const headers = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  let response;
  try {
    response = await fetch(`${API_BASE}/api/chat/stream`, {
      method: "POST",
      headers,
      body: JSON.stringify({
        message,
        conversation_id: conversationId || null,
        threshold: parseFloat(threshold),
        file_id: fileId || null,
      }),
      signal,
    });
  } catch (err) {
    if (err.name === "AbortError") return;
    onError?.(err.message || "Connection failed");
    return;
  }

  if (!response.ok) {
    let msg = `Server error (${response.status})`;
    try { const d = await response.json(); msg = d.detail || msg; } catch (_) {}
    onError?.(msg);
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // Process complete SSE lines
      const lines = buffer.split("\n");
      buffer = lines.pop(); // keep incomplete line

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const raw = line.slice(6).trim();
        if (!raw || raw === "[DONE]") continue;
        try {
          const msg = JSON.parse(raw);
          if (msg.type === "token") onToken?.(msg.text || "");
          else if (msg.type === "eval") onEval?.(msg);
          else if (msg.type === "done") onDone?.(msg);
          else if (msg.type === "error") onError?.(msg.message || "Unknown error");
        } catch (_) {}
      }
    }
  } catch (err) {
    if (err.name === "AbortError") return;
    onError?.(err.message || "Stream interrupted");
  }
}

// ─── legacy evaluate (non-streaming) ────────────────────────────────────────

export async function evaluateText(text, threshold = 0.5, history = []) {
  const res = await fetch(`${API_BASE}/api/evaluate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, threshold, history }),
  });
  return handleResponse(res);
}

export async function recalculateTokens(tokenAnalysis, threshold) {
  const res = await fetch(`${API_BASE}/api/recalculate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token_analysis: tokenAnalysis, threshold }),
  });
  return handleResponse(res);
}

// ─── file upload ─────────────────────────────────────────────────────────────

export async function uploadFile(token, file, onProgress) {
  const formData = new FormData();
  formData.append("file", file);

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE}/api/upload`);
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try { resolve(JSON.parse(xhr.responseText)); }
        catch (_) { reject(new Error("Invalid response")); }
      } else {
        try {
          const err = JSON.parse(xhr.responseText);
          reject(new Error(err.detail || `Upload failed (${xhr.status})`));
        } catch (_) {
          reject(new Error(`Upload failed (${xhr.status})`));
        }
      }
    };

    xhr.onerror = () => reject(new Error("Network error during upload"));
    xhr.send(formData);
  });
}
