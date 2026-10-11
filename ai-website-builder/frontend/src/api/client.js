const BASE = "/api";

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let message = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      message = body.detail || message;
    } catch {
      /* ignore parse failure, use default message */
    }
    throw new Error(message);
  }
  return res.json();
}

export const api = {
  health: () => request("/health"),
  listProviders: () => request("/providers"),

  createProject: () => request("/projects", { method: "POST" }),

  generate: (projectId, body) =>
    request(`/projects/${projectId}/generate`, { method: "POST", body: JSON.stringify(body) }),

  modify: (projectId, body) =>
    request(`/projects/${projectId}/modify`, { method: "POST", body: JSON.stringify(body) }),

  cancel: (projectId) => request(`/projects/${projectId}/cancel`, { method: "POST" }),

  reset: (projectId) => request(`/projects/${projectId}/reset`, { method: "POST" }),

  status: (projectId) => request(`/projects/${projectId}/status`),

  files: (projectId) => request(`/projects/${projectId}/files`),

  fileContent: (projectId, path) => request(`/projects/${projectId}/files/${path}`),

  preview: (projectId) => request(`/projects/${projectId}/preview`),

  exportUrl: (projectId) => `${BASE}/projects/${projectId}/export`,

  /**
   * Subscribe to live progress via Server-Sent Events. Returns an
   * unsubscribe function. Falls back is handled by the caller (poll
   * `status` on error) rather than here, keeping this module simple.
   */
  subscribeEvents: (projectId, { onEvent, onError }) => {
    const source = new EventSource(`${BASE}/projects/${projectId}/events`);
    source.onmessage = (msg) => {
      try {
        onEvent(JSON.parse(msg.data));
      } catch (e) {
        console.error("Malformed SSE payload", e);
      }
    };
    source.onerror = (err) => {
      onError?.(err);
    };
    return () => source.close();
  },
};
