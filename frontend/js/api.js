// api.js - small wrapper around fetch() that adds the JWT token to every request.

const API_BASE = "/api";

function getToken() {
  return localStorage.getItem("vn_token");
}

// Turn FastAPI error responses into one readable message
function errorMessage(data, fallback) {
  if (!data || !data.detail) return fallback;
  if (typeof data.detail === "string") return data.detail;
  if (Array.isArray(data.detail)) {
    // Pydantic validation errors: [{loc: [...], msg: "..."}]
    return data.detail
      .map((e) => {
        const field = Array.isArray(e.loc) ? e.loc[e.loc.length - 1] : "";
        return field ? `${field}: ${e.msg}` : e.msg;
      })
      .join("; ");
  }
  return fallback;
}

// Low-level call. Returns the raw Response after checking for errors.
async function apiRaw(path, options = {}) {
  const headers = options.headers || {};
  const token = getToken();
  if (token) headers["Authorization"] = "Bearer " + token;

  let body = options.body;
  // Plain objects are sent as JSON; FormData is sent as multipart automatically
  if (body && !(body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(body);
  }

  let response;
  try {
    response = await fetch(API_BASE + path, { method: options.method || "GET", headers, body });
  } catch (err) {
    throw new Error("Cannot reach the server. Is the backend running?");
  }

  if (!response.ok) {
    let data = null;
    try { data = await response.json(); } catch (e) { /* not JSON */ }
    // Token missing/expired on a protected page -> go to login
    if (response.status === 401 && token && !options.noRedirect) {
      localStorage.clear();
      window.location.href = "login.html";
    }
    const error = new Error(errorMessage(data, `Request failed (${response.status})`));
    error.status = response.status;
    throw error;
  }
  return response;
}

// JSON helper: await api("/requests") or api("/requests", {method: "POST", body: {...}})
async function api(path, options = {}) {
  const response = await apiRaw(path, options);
  return response.json();
}

// File helper (photos, PDF): returns a Blob
async function apiBlob(path) {
  const response = await apiRaw(path);
  return response.blob();
}
