import axios from "axios";

const TOKEN_KEY = "alm_token";

export const tokenStore = {
  get: () => localStorage.getItem(TOKEN_KEY),
  set: (t) => localStorage.setItem(TOKEN_KEY, t),
  clear: () => localStorage.removeItem(TOKEN_KEY),
};

// Single Axios instance: every request in the app goes through this.
export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1",
  timeout: 30000,
});

api.interceptors.request.use((config) => {
  const token = tokenStore.get();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

let onUnauthorized = null;
export const setUnauthorizedHandler = (fn) => {
  onUnauthorized = fn;
};

/**
 * Turn any failure into { status, message, code } so UI code never parses Axios errors.
 * FastAPI validation errors (422) return `detail` as a list; app errors return a string.
 */
export function normalizeError(error) {
  if (!error.response) {
    return {
      status: 0,
      code: "network",
      message: "Cannot reach the server. Check that the API is running and VITE_API_BASE_URL is correct.",
    };
  }
  const { status, data } = error.response;
  let message = "Something went wrong.";
  if (typeof data?.detail === "string") message = data.detail;
  else if (Array.isArray(data?.detail)) {
    message = data.detail.map((d) => `${(d.loc || []).slice(1).join(".")}: ${d.msg}`).join("; ");
  } else if (status >= 500) message = "The server hit an unexpected error.";
  return { status, code: data?.code || "error", message };
}

api.interceptors.response.use(
  (res) => res,
  (error) => {
    const normalized = normalizeError(error);
    // Expired/invalid token (but not a failed login attempt): force re-authentication.
    if (normalized.status === 401 && !error.config?.url?.includes("/auth/login")) {
      tokenStore.clear();
      if (onUnauthorized) onUnauthorized();
    }
    return Promise.reject(normalized);
  }
);

export const get = (url, params) => api.get(url, { params }).then((r) => r.data);
export const post = (url, body) => api.post(url, body).then((r) => r.data);
export const patch = (url, body) => api.patch(url, body).then((r) => r.data);

/** Authenticated file download (the Bearer header cannot be sent by a plain <a href>). */
export async function download(url, filename) {
  const res = await api.get(url, { responseType: "blob" });
  const href = URL.createObjectURL(res.data);
  const a = document.createElement("a");
  a.href = href;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(href);
}
