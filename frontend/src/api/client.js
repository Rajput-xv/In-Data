// Tiny fetch wrapper.
//
// I deliberately did not pull in axios or react-query. The API surface
// is six endpoints and four call sites; a real client would benefit
// from caching, but for a prototype it'd be ceremony.
//
// `request` throws on non-2xx so call sites can `try/catch`. The error
// it throws carries the server's `detail` string when present, which
// is what the UI surfaces to the analyst.

import { getEmail } from "../auth.js";

const BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

// Read the analyst email at request time, not at module load time -
// the user signs in after the bundle is parsed, and we want every
// request to carry whichever email is currently in session.
function currentAnalyst() {
  return getEmail() || import.meta.env.VITE_ANALYST_EMAIL || "analyst@example.com";
}

async function request(path, { method = "GET", body, headers = {} } = {}) {
  const init = {
    method,
    headers: {
      "X-Analyst-Email": currentAnalyst(),
      ...headers,
    },
  };
  if (body && !(body instanceof FormData)) {
    init.headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  } else if (body instanceof FormData) {
    init.body = body;
  }

  const res = await fetch(`${BASE}${path}`, init);
  const text = await res.text();
  let data = null;
  if (text) {
    try { data = JSON.parse(text); } catch { data = { detail: text }; }
  }
  if (!res.ok) {
    const message = data?.detail || `HTTP ${res.status}`;
    const err = new Error(message);
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
}

export const api = {
  listBatches: () => request("/api/batches/"),
  getBatch: (id) => request(`/api/batches/${id}/`),
  listActivities: (params = {}) => {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== undefined && v !== "")
    ).toString();
    return request(`/api/activities/${qs ? `?${qs}` : ""}`);
  },
  getActivity: (id) => request(`/api/activities/${id}/`),
  approveActivity: (id, note) =>
    request(`/api/activities/${id}/approve/`, {
      method: "POST",
      body: { note },
    }),
  rejectActivity: (id, note) =>
    request(`/api/activities/${id}/reject/`, {
      method: "POST",
      body: { note },
    }),
  uploadFile: (source, file) => {
    const fd = new FormData();
    fd.append("file", file);
    return request(`/api/ingest/${source}/`, { method: "POST", body: fd });
  },
};

