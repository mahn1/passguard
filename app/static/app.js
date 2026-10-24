const $ = (id) => document.getElementById(id);
const COLORS = ["var(--s0)", "var(--s1)", "var(--s2)", "var(--s3)", "var(--s4)"];
const LABELS = ["очень слабый", "слабый", "средний", "надёжный", "очень надёжный"];

// ---------- API ----------
// Токен держим в sessionStorage: после закрытия вкладки нужно войти заново
let token = sessionStorage.getItem("token");

async function api(path, { method = "GET", body } = {}) {
  const res = await fetch(path, {
    method,
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (res.status === 401 && token) { logout(); throw new Error("Сессия истекла, войдите снова"); }
  if (res.status === 204) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = Array.isArray(data.detail) ? data.detail.map((d) => d.msg).join("; ") : data.detail;
    throw new Error(detail || `Ошибка ${res.status}`);
  }
  return data;
}

let toastTimer;
function toast(text) {
  const t = $("toast");
  t.textContent = text;
  t.classList.add("is-shown");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove("is-shown"), 2200);
}
async function copy(text) {
  try { await navigator.clipboard.writeText(text); toast("Скопировано в буфер обмена"); }
  catch { toast("Не удалось скопировать"); }
}
function paintMeter(el, score) {
  const bar = el.querySelector("i");
  bar.style.width = score === null ? "0" : `${(score + 1) * 20}%`;
  bar.style.background = score === null ? "transparent" : COLORS[score];
}
const debounce = (fn, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };

// ---------- Вкладки ----------
function show(view) {
  if ((view === "vault" || view === "audit") && !token) { openAuth(); return; }
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("is-active", t.dataset.view === view));
  document.querySelectorAll(".view").forEach((v) => v.classList.toggle("is-active", v.id === `view-${view}`));
  if (view === "vault") loadEntries();
  if (view === "audit") loadAudit();
}
$("tabs").addEventListener("click", (e) => { const b = e.target.closest("[data-view]"); if (b) show(b.dataset.view); });

// ---------- Генератор ----------
const genOpts = () => ({
  length: Number($("gen-length").value),
  lower: $("opt-lower").checked,
  upper: $("opt-upper").checked,
  digits: $("opt-digits").checked,
  symbols: $("opt-symbols").checked,
  exclude_ambiguous: $("opt-ambiguous").checked,
});

async function generate() {
  try {
    const data = await api("/api/tools/generate", { method: "POST", body: genOpts() });
    const { password, strength } = data.passwords[0];
    $("gen-output").value = password;
    paintMeter($("gen-meter"), strength.score);
    $("gen-meter-text").innerHTML = `<b>${strength.label}</b> · ${strength.entropy_bits} бит · подбор: ${strength.crack_time_offline}`;
  } catch (err) {
    $("gen-meter-text").textContent = err.message;
    paintMeter($("gen-meter"), null);
  }
}
$("gen-length").addEventListener("input", () => { $("len-out").textContent = $("gen-length").value; });
$("gen-length").addEventListener("change", generate);
document.querySelectorAll(".gen-opts input[type=checkbox]").forEach((c) => c.addEventListener("change", generate));
$("gen-refresh").addEventListener("click", generate);
$("gen-copy").addEventListener("click", () => copy($("gen-output").value));
$("gen-save").addEventListener("click", () => {
  if (!token) { openAuth(); return; }
  openEntry(null, $("gen-output").value);
});

// ---------- Проверка ----------
async function runCheck() {
  const pw = $("check-input").value;
  if (!pw) {
    paintMeter($("check-meter"), null);
    ["r-label", "r-entropy", "r-offline", "r-online"].forEach((id) => { $(id).textContent = "—"; });
    $("r-notes").innerHTML = "";
    return;
  }
  const r = await api("/api/tools/check", { method: "POST", body: { password: pw } });
  paintMeter($("check-meter"), r.score);
  $("r-label").textContent = r.label;
  $("r-label").style.color = COLORS[r.score];
  $("r-entropy").textContent = `${r.entropy_bits} бит`;
  $("r-offline").textContent = r.crack_time_offline;
  $("r-online").textContent = r.crack_time_online;
  $("r-notes").innerHTML = [
    ...r.warnings.map((w) => `<li class="warn">⚠ ${w}</li>`),
    ...r.suggestions.map((s) => `<li class="tip">→ ${s}</li>`),
  ].join("");
}
$("check-input").addEventListener("input", debounce(runCheck, 250));
const eye = (btn, input) => btn.addEventListener("click", () => { input.type = input.type === "password" ? "text" : "password"; });
eye($("check-eye"), $("check-input"));

// ---------- Авторизация ----------
let authMode = "login";
function openAuth() {
  $("auth-error").hidden = true;
  $("auth-modal").showModal();
}
function setAuthMode(mode) {
  authMode = mode;
  $("auth-title").textContent = mode === "login" ? "Вход" : "Регистрация";
  $("auth-submit").textContent = mode === "login" ? "Войти" : "Создать аккаунт";
  $("auth-switch").textContent = mode === "login" ? "Нет аккаунта? Зарегистрироваться" : "Уже есть аккаунт? Войти";
  $("auth-form").password.autocomplete = mode === "login" ? "current-password" : "new-password";
}
$("auth-switch").addEventListener("click", () => setAuthMode(authMode === "login" ? "register" : "login"));
$("auth-modal").addEventListener("click", (e) => { if (e.target === $("auth-modal")) $("auth-modal").close(); });
async function signIn(data) {
  token = data.access_token;
  sessionStorage.setItem("token", token);
  $("auth-form").reset();
  if ($("auth-modal").open) $("auth-modal").close();
  await renderUser();
}
$("auth-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = e.target;
  try {
    await signIn(await api(`/api/auth/${authMode}`, { method: "POST", body: { username: f.username.value.trim(), password: f.password.value } }));
    toast(authMode === "login" ? "С возвращением!" : "Аккаунт создан");
  } catch (err) {
    $("auth-error").textContent = err.message;
    $("auth-error").hidden = false;
  }
});

// Демо-режим: вход одним кликом в аккаунт с примерами записей
async function startDemo() {
  try {
    await signIn(await api("/api/auth/demo", { method: "POST" }));
    toast("Демо-аккаунт готов: загляните в хранилище и аудит");
    show("vault");
  } catch (err) {
    toast(err.message);
  }
}
async function initDemo() {
  const { demo_mode } = await api("/api/config").catch(() => ({}));
  if (!demo_mode) return;
  $("demo-bar").hidden = false;
  $("auth-demo").hidden = false;
}
$("demo-start").addEventListener("click", startDemo);
$("auth-demo").addEventListener("click", startDemo);

async function renderUser() {
  $("demo-start").hidden = Boolean(token);
  if (!token) {
    $("user-box").innerHTML = '<button class="btn btn--ghost btn--sm" id="login-open">Войти</button>';
    $("login-open").addEventListener("click", openAuth);
    return;
  }
  try {
    const me = await api("/api/auth/me");
    $("user-box").innerHTML = `<span><b>${escapeHtml(me.username)}</b></span><button class="btn btn--ghost btn--sm" id="logout">Выйти</button>`;
    $("logout").addEventListener("click", logout);
  } catch { /* logout уже вызван в api() */ }
}
function logout() {
  token = null;
  sessionStorage.removeItem("token");
  renderUser();
  show("generator");
}

// ---------- Хранилище ----------
const escapeHtml = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmtDate = (iso) => new Date(iso.endsWith("Z") || iso.includes("+") ? iso : iso + "Z").toLocaleDateString("ru-RU");
const badge = (s) => `<span class="badge" style="background:${COLORS[s]}">${LABELS[s]}</span>`;

async function loadEntries() {
  const q = encodeURIComponent($("search").value.trim());
  const list = await api(`/api/entries?q=${q}&sort=${$("sort").value}`);
  $("entries-empty").hidden = list.length > 0;
  $("entries").innerHTML = list.map((e) => `
    <tr data-id="${e.id}">
      <td><b>${escapeHtml(e.title)}</b><small>${escapeHtml(e.url)}</small></td>
      <td>${escapeHtml(e.login)}</td>
      <td>${badge(e.strength_score)}</td>
      <td>${fmtDate(e.updated_at)}</td>
      <td><div class="row-actions">
        <button class="icon-btn" data-copy="${e.id}" title="Скопировать пароль">⧉</button>
      </div></td>
    </tr>`).join("");
}
$("search").addEventListener("input", debounce(loadEntries, 250));
$("sort").addEventListener("change", loadEntries);
$("entries").addEventListener("click", async (e) => {
  const copyBtn = e.target.closest("[data-copy]");
  if (copyBtn) {
    const entry = await api(`/api/entries/${copyBtn.dataset.copy}`);
    copy(entry.password);
    return;
  }
  const row = e.target.closest("tr[data-id]");
  if (row) openEntry(Number(row.dataset.id));
});
$("add-entry").addEventListener("click", () => openEntry(null));

// Модальное окно записи: создание и редактирование
let editingId = null;
const entryForm = $("entry-form");

async function openEntry(id, presetPassword = "") {
  editingId = id;
  entryForm.reset();
  $("entry-error").hidden = true;
  $("entry-password").type = "password";
  $("entry-delete").hidden = id === null;
  $("entry-title").textContent = id === null ? "Новая запись" : "Редактирование";
  if (id !== null) {
    const e = await api(`/api/entries/${id}`);
    ["title", "login", "url", "notes", "password"].forEach((k) => { entryForm[k].value = e[k]; });
  } else {
    entryForm.password.value = presetPassword;
  }
  entryForm.password.required = id === null;
  updateEntryMeter();
  $("entry-modal").showModal();
}

const updateEntryMeter = debounce(async () => {
  const pw = entryForm.password.value;
  if (!pw) { paintMeter($("entry-meter"), null); return; }
  const r = await api("/api/tools/check", { method: "POST", body: { password: pw } });
  paintMeter($("entry-meter"), r.score);
}, 200);
entryForm.password.addEventListener("input", updateEntryMeter);
eye($("entry-eye"), $("entry-password"));
$("entry-gen").addEventListener("click", async () => {
  const data = await api("/api/tools/generate", { method: "POST", body: { length: 20 } });
  entryForm.password.value = data.passwords[0].password;
  entryForm.password.type = "text";
  updateEntryMeter();
});
$("entry-cancel").addEventListener("click", () => $("entry-modal").close());

entryForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const body = Object.fromEntries(["title", "login", "url", "notes", "password"].map((k) => [k, entryForm[k].value]));
  try {
    if (editingId === null) {
      await api("/api/entries", { method: "POST", body });
      toast("Запись сохранена");
    } else {
      if (!body.password) delete body.password;
      await api(`/api/entries/${editingId}`, { method: "PATCH", body });
      toast("Изменения сохранены");
    }
    $("entry-modal").close();
    if ($("view-vault").classList.contains("is-active")) loadEntries(); else show("vault");
    if ($("view-audit").classList.contains("is-active")) loadAudit();
  } catch (err) {
    $("entry-error").textContent = err.message;
    $("entry-error").hidden = false;
  }
});

$("entry-delete").addEventListener("click", async () => {
  if (!confirm("Удалить запись без возможности восстановления?")) return;
  await api(`/api/entries/${editingId}`, { method: "DELETE" });
  $("entry-modal").close();
  toast("Запись удалена");
  loadEntries();
});

// ---------- Аудит ----------
async function loadAudit() {
  const a = await api("/api/entries/audit");
  $("health").textContent = `${a.health}%`;
  $("ring").style.setProperty("--p", a.health);
  $("a-total").textContent = a.total;
  $("a-weak").textContent = a.weak.length;
  $("a-reused").textContent = a.reused.reduce((n, g) => n + g.length, 0);
  $("a-old").textContent = a.old.length;
  const item = (e) => `<li data-id="${e.id}"><span>${escapeHtml(e.title)}</span>${badge(e.strength_score)}</li>`;
  const groups = [];
  if (a.weak.length) groups.push(`<div class="audit-group"><h3>Слабые пароли — замените их</h3><ul>${a.weak.map(item).join("")}</ul></div>`);
  a.reused.forEach((g, i) => groups.push(`<div class="audit-group"><h3>Один пароль на ${g.length} записях${a.reused.length > 1 ? ` (группа ${i + 1})` : ""}</h3><ul>${g.map(item).join("")}</ul></div>`));
  if (a.old.length) groups.push(`<div class="audit-group"><h3>Не менялись больше полугода</h3><ul>${a.old.map(item).join("")}</ul></div>`);
  $("audit-lists").innerHTML = groups.join("") || (a.total ? '<p class="audit-ok">Проблем не найдено — все пароли надёжные и уникальные.</p>' : '<p class="audit-ok">Добавьте записи в хранилище, чтобы проверить их.</p>');
}
$("audit-lists").addEventListener("click", (e) => { const li = e.target.closest("li[data-id]"); if (li) openEntry(Number(li.dataset.id)); });

// ---------- Старт ----------
renderUser();
initDemo();
generate();
