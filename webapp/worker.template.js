// task-calendar: serves the webapp and proxies /api/tasks to the bot VPS.
/*ASSETS*/

const enc = (s) => new TextEncoder().encode(s);

function resp(body, type) {
  return new Response(body, {
    headers: { "Content-Type": type, "Cache-Control": "no-cache" },
  });
}

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

async function toHex(buf) {
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function sha256(data) {
  return crypto.subtle.digest("SHA-256", enc(data));
}

async function hmac(key, data) {
  const keyObj = await crypto.subtle.importKey(
    "raw",
    key,
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );
  return crypto.subtle.sign("HMAC", keyObj, enc(data));
}

async function verifyInitData(initData, botToken) {
  if (!initData) return null;
  const params = new URLSearchParams(initData);
  const hash = params.get("hash");
  if (!hash) return null;

  const authDate = Number(params.get("auth_date"));
  if (!Number.isFinite(authDate)) return null;
  const age = Math.floor(Date.now() / 1000) - authDate;
  if (age < 0 || age > 86400) return null;

  params.delete("hash");
  const pairs = [...params.entries()].sort(([a], [b]) => a.localeCompare(b));
  const dataCheck = pairs.map(([k, v]) => `${k}=${v}`).join("\n");

  const secretKey = await hmac(enc("WebAppData"), botToken);
  const check = await hmac(secretKey, dataCheck);
  const expect = await toHex(check);
  if (expect.toLowerCase() !== hash.toLowerCase()) return null;

  try {
    const user = JSON.parse(params.get("user"));
    const id = typeof user.id === "number" ? user.id : parseInt(user.id, 10);
    return Number.isInteger(id) ? id : null;
  } catch {
    return null;
  }
}

async function fetchTasks(userId, vpsOrigin, appSecret) {
  const res = await fetch(`${vpsOrigin}/api/tasks?user_id=${userId}`, {
    headers: { "X-App-Secret": appSecret },
  });
  const text = await res.text();
  try {
    return json(JSON.parse(text), res.status);
  } catch {
    return new Response(text, { status: res.status });
  }
}

async function handle(request, env) {
  const { BOT_TOKEN, VPS_ORIGIN, APP_SECRET } = env;
  const url = new URL(request.url);

  if (request.method === "GET") {
    if (url.pathname === "/") return resp(INDEX_HTML, "text/html; charset=utf-8");
    if (url.pathname === "/style.css") return resp(STYLE_CSS, "text/css; charset=utf-8");
    if (url.pathname === "/app.js") return resp(APP_JS, "application/javascript; charset=utf-8");
    return new Response("Not found", { status: 404 });
  }

  if (request.method === "POST" && url.pathname === "/api/tasks") {
    try {
      const body = await request.json();
      const userId = await verifyInitData(body.initData || "", BOT_TOKEN);
      if (userId === null) return json({ error: "bad initData" }, 401);
      return await fetchTasks(userId, VPS_ORIGIN, APP_SECRET);
    } catch (e) {
      return json({ error: "internal" }, 500);
    }
  }

  return new Response("Not found", { status: 404 });
}

export default {
  async fetch(request, env) {
    return handle(request, env);
  },
};
