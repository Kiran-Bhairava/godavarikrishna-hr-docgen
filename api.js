// Use relative paths - works in both dev and production
const BASE = "";

function getToken() {
    return localStorage.getItem("token");
}

function getUser() {
    const u = localStorage.getItem("user");
    return u ? JSON.parse(u) : null;
}

function logout() {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    window.location.href = "/index.html";
}

function authHeaders() {
    return {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${getToken()}`
    };
}

async function api(method, path, body = null) {
    const opts = { method, headers: authHeaders() };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(BASE + path, opts);
    if (res.status === 401) { logout(); return; }
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || "Request failed");
    return data;
}

async function login(email, password) {
    const res = await fetch(BASE + "/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Login failed");
    return data;
}

// Guard — call at top of each protected page
function requireAuth(role = null) {
    const token = getToken();
    const user  = getUser();
    if (!token || !user) { window.location.href = "/index.html"; return null; }
    if (role && user.role !== role) {
        window.location.href = user.role === "admin"
            ? "/admin/dashboard.html"
            : "/recruiter/dashboard.html";
        return null;
    }
    return user;
}