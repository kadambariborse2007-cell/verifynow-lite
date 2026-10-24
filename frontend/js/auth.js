// auth.js - login state, role checks, navbar and small shared UI helpers.

const APP_NAME = "PAMAC VerifyNow";

// Inline SVG logo: a tick inside a shield (no image files used)
const LOGO_SVG = `
<svg class="brand-logo" viewBox="0 0 24 24" aria-hidden="true">
  <path d="M12 2 4 5v6c0 5.2 3.4 9.9 8 11 4.6-1.1 8-5.8 8-11V5l-8-3z" fill="#ffffff"/>
  <path d="m8.2 12.2 2.7 2.7 5-5.6" fill="none" stroke="#0d6efd" stroke-width="2.3"
        stroke-linecap="round" stroke-linejoin="round"/>
</svg>`;

function saveLogin(data) {
  localStorage.setItem("vn_token", data.access_token);
  localStorage.setItem("vn_role", data.role);
  localStorage.setItem("vn_name", data.name);
}

function getRole() {
  return localStorage.getItem("vn_role");
}

function isLoggedIn() {
  return !!localStorage.getItem("vn_token");
}

function homePageFor(role) {
  return role === "staff" ? "staff-dashboard.html" : "my-requests.html";
}

function logout() {
  localStorage.clear();
  window.location.href = "login.html";
}

// Call at the top of every protected page.
// Confirms the token with the server (/api/me) and checks the role.
async function requireLogin(role) {
  if (!isLoggedIn()) {
    window.location.href = "login.html";
    return null;
  }
  try {
    const user = await api("/me");
    if (role && user.role !== role) {
      window.location.href = "login.html";
      return null;
    }
    localStorage.setItem("vn_role", user.role);
    localStorage.setItem("vn_name", user.name);
    return user;
  } catch (err) {
    localStorage.clear();
    window.location.href = "login.html";
    return null;
  }
}

// Builds the navbar inside <nav id="navbar"></nav>
function renderNavbar() {
  const nav = document.getElementById("navbar");
  if (!nav) return;
  const role = getRole();
  let links = "";
  if (isLoggedIn() && role === "customer") {
    links = `
      <li class="nav-item"><a class="nav-link" href="my-requests.html">My Requests</a></li>
      <li class="nav-item"><a class="nav-link" href="new-request.html">New Request</a></li>`;
  } else if (isLoggedIn() && role === "staff") {
    links = `<li class="nav-item"><a class="nav-link" href="staff-dashboard.html">Dashboard</a></li>`;
  }
  links += `<li class="nav-item"><a class="nav-link" href="verify.html">Verify Report</a></li>`;

  const right = isLoggedIn()
    ? `<span class="navbar-text text-white me-3">Hi, ${escapeHtml(localStorage.getItem("vn_name") || "")}
         <span class="badge bg-light text-primary ms-1">${escapeHtml(role || "")}</span></span>
       <button class="btn btn-outline-light btn-sm" onclick="logout()">Logout</button>`
    : `<a class="btn btn-outline-light btn-sm me-2" href="login.html">Login</a>
       <a class="btn btn-light btn-sm" href="register.html">Register</a>`;

  nav.className = "navbar navbar-expand-lg navbar-dark bg-primary";
  nav.innerHTML = `
    <div class="container">
      <a class="navbar-brand d-flex align-items-center gap-2 fw-semibold" href="index.html">
        ${LOGO_SVG}<span>${APP_NAME}</span>
      </a>
      <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navMenu"
              aria-controls="navMenu" aria-expanded="false" aria-label="Toggle navigation">
        <span class="navbar-toggler-icon"></span>
      </button>
      <div class="collapse navbar-collapse" id="navMenu">
        <ul class="navbar-nav me-auto">${links}</ul>
        <div class="d-flex align-items-center flex-wrap gap-1 py-2 py-lg-0">${right}</div>
      </div>
    </div>`;
}

// ---------- Shared UI helpers ----------

// Always escape user-entered text before putting it into innerHTML (prevents XSS)
function escapeHtml(text) {
  return String(text ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function statusBadge(status) {
  const css = {
    "Received": "status-received",
    "In Progress": "status-inprogress",
    "Completed": "status-completed",
  }[status] || "bg-secondary";
  return `<span class="badge badge-status ${css}">${escapeHtml(status)}</span>`;
}

function formatDateTime(value) {
  return new Date(value).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

function formatDate(value) {
  // "2026-10-24" -> local date text without timezone shifting
  const [y, m, d] = value.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(undefined, { dateStyle: "medium" });
}

function showAlert(elementId, message, type = "danger") {
  const el = document.getElementById(elementId);
  el.innerHTML = `<div class="alert alert-${type} mb-3" role="alert">${escapeHtml(message)}</div>`;
}

function clearAlert(elementId) {
  document.getElementById(elementId).innerHTML = "";
}

function renderTimeline(elementId, items) {
  const el = document.getElementById(elementId);
  if (!items.length) {
    el.innerHTML = `<p class="text-muted mb-0">No activity yet.</p>`;
    return;
  }
  el.innerHTML = `<ul class="timeline">${items
    .map((a) => `<li><div>${escapeHtml(a.action)}</div>
                 <small>${escapeHtml(a.user_name)} &middot; ${formatDateTime(a.created_at)}</small></li>`)
    .join("")}</ul>`;
}

// Download the PDF through the authenticated API and save it in the browser
async function downloadReportPdf(requestId, caseCode) {
  const blob = await apiBlob(`/requests/${requestId}/report-pdf`);
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${caseCode}-report.pdf`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function getQueryParam(name) {
  return new URLSearchParams(window.location.search).get(name);
}

document.addEventListener("DOMContentLoaded", renderNavbar);
