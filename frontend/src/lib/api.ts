const BASE_URL = "http://localhost:8000";

function getToken(): string | null {
  return localStorage.getItem("rs_token");
}

async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> || {}),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${BASE_URL}${path}`, { ...options, headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

function setToken(token: string) {
  localStorage.setItem("rs_token", token);
}

function clearToken() {
  localStorage.removeItem("rs_token");
  localStorage.removeItem("rs_company");
}

function isAuthenticated(): boolean {
  return !!localStorage.getItem("rs_token");
}

export { BASE_URL, apiFetch, setToken, clearToken, isAuthenticated, getToken };
