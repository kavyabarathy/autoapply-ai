const API = "http://localhost:8000";
const KEY = "autoapply_token";

export const getToken = () => localStorage.getItem(KEY);
export const setToken = (token) => localStorage.setItem(KEY, token);
export const clearToken = () => localStorage.removeItem(KEY);

async function request(path, options = {}) {
  const token = getToken();
  const res = await fetch(`${API}${path}`, {
    ...options,
    headers: { ...(options.headers || {}), ...(token ? { Authorization: `Bearer ${token}` } : {}) },
  });
  if (res.status === 401 && token) {
    clearToken();
    window.location.reload();
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Request failed (${res.status})`);
  }
  return res;
}

export async function api(path, options) {
  return (await request(path, options)).json();
}

export async function fetchBlob(path, options) {
  return (await request(path, options)).blob();
}

export async function downloadBlob(path, filename, options) {
  const url = URL.createObjectURL(await fetchBlob(path, options));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export function json(method, body) {
  return { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
}
