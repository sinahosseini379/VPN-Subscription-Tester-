/* ============================================================
   VPN Subscription Tester — dashboard controller
   Vanilla JS, no build step. All third-party data (config URIs,
   subscription URLs, node names) is rendered via textContent /
   createElement, never innerHTML, so a crafted #fragment cannot
   inject markup into the dashboard.
   ============================================================ */
"use strict";

const $ = (id) => document.getElementById(id);
let logSeq = 0;

/* ── i18n ─────────────────────────────────────────────────── */
const I18N = {
  en: {
    run_now: "Run now", run_status: "Run status", logs: "Live log", clear: "Clear",
    subscription_link: "Subscription link",
    subscription_help: "Import this URL in your VPN app. It carries the profile title and auto-update interval that GitHub raw links cannot.",
    copy: "Copy", schedule: "Automatic run schedule", time: "Time", timezone: "Timezone",
    save: "Save", final_configs: "Final configs", th_name: "Name", th_proto: "Protocol",
    th_uri: "URI", th_latency: "Latency", th_errors: "Errors", no_configs: "No published configs yet.",
    sources: "Subscription sources", add: "Add", up_to: "Up to", urls: "URLs",
    footer: "VPN Subscription Tester · dark dashboard", remove: "Remove",
    kpi_configs: "Published configs", kpi_countries_empty: "no data yet",
    kpi_latency: "Avg latency", kpi_latency_foot: "across all configs",
    kpi_errors: "Avg error rate", kpi_errors_foot: "weighted per target",
    kpi_updated: "Last generated",
    st_idle: "idle", st_running: "running", st_done: "done", st_failed: "failed",
    copied: "Copied to clipboard", run_started: "Run started",
    run_busy: "A run is already in progress", saved_next: "Saved — next run at",
    countries_n: (n) => `${n} ${n === 1 ? "country" : "countries"}`,
    no_sources: "No sources configured.", err: "Error",
  },
  fa: {
    run_now: "اجرای فوری", run_status: "وضعیت اجرا", logs: "گزارش زنده", clear: "پاک‌کردن",
    subscription_link: "لینک اشتراک",
    subscription_help: "این آدرس را در اپ VPN خود وارد کنید. برخلاف لینک خام گیت‌هاب، نام پروفایل و بازهٔ بروزرسانی خودکار را همراه دارد.",
    copy: "کپی", schedule: "زمان‌بندی اجرای خودکار", time: "زمان", timezone: "منطقهٔ زمانی",
    save: "ذخیره", final_configs: "کانفیگ‌های نهایی", th_name: "نام", th_proto: "پروتکل",
    th_uri: "آدرس", th_latency: "تأخیر", th_errors: "خطا", no_configs: "هنوز کانفیگی منتشر نشده است.",
    sources: "منابع اشتراک", add: "افزودن", up_to: "حداکثر", urls: "آدرس",
    footer: "تستر اشتراک VPN · داشبورد تیره", remove: "حذف",
    kpi_configs: "کانفیگ‌های منتشرشده", kpi_countries_empty: "بدون داده",
    kpi_latency: "میانگین تأخیر", kpi_latency_foot: "روی همهٔ کانفیگ‌ها",
    kpi_errors: "میانگین نرخ خطا", kpi_errors_foot: "وزنی بر اساس هدف",
    kpi_updated: "آخرین تولید",
    st_idle: "بی‌کار", st_running: "در حال اجرا", st_done: "انجام شد", st_failed: "ناموفق",
    copied: "در کلیپ‌بورد کپی شد", run_started: "اجرا آغاز شد",
    run_busy: "یک اجرا هم‌اکنون در جریان است", saved_next: "ذخیره شد — اجرای بعدی در",
    countries_n: (n) => `${n} کشور`,
    no_sources: "هیچ منبعی تنظیم نشده است.", err: "خطا",
  },
};
let lang = localStorage.getItem("vpnt_lang") || "en";
const t = (key) => (I18N[lang] && I18N[lang][key] != null ? I18N[lang][key] : key);

function applyLang() {
  const root = document.documentElement;
  root.lang = lang;
  root.dir = lang === "fa" ? "rtl" : "ltr";
  $("langBtn").textContent = lang === "fa" ? "EN" : "فا";
  document.querySelectorAll("[data-i18n]").forEach((n) => {
    n.textContent = t(n.getAttribute("data-i18n"));
  });
  renderStatus(lastStatus);
  renderConfigs(lastConfigs);
  renderSources(lastSources);
}

/* ── tiny DOM helper (safe by construction) ───────────────── */
function el(tag, props = {}, children = []) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === "class") node.className = v;
    else if (k === "text") node.textContent = v;
    else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2), v);
    else if (v != null) node.setAttribute(k, v);
  }
  for (const c of [].concat(children)) if (c != null) node.append(c);
  return node;
}

/* ── networking ───────────────────────────────────────────── */
async function api(path, opts) {
  const r = await fetch(path, opts);
  if (!r.ok) {
    let msg = r.statusText;
    try { msg = (await r.text()) || msg; } catch (_) {}
    throw new Error(msg);
  }
  return r.json();
}

let toastTimer;
function toast(msg, kind) {
  const el = $("toast");
  el.textContent = msg;
  el.dataset.kind = kind || "info";
  el.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("show"), 2200);
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
  } catch (_) {
    const ta = el("textarea", { text });
    document.body.append(ta); ta.select();
    document.execCommand("copy"); ta.remove();
  }
  toast(t("copied"));
}

/* ── formatting ───────────────────────────────────────────── */
function fmtMs(v) { return v == null ? "—" : Math.round(v) + " ms"; }
function fmtPct(v) { return v == null ? "—" : Math.round(v * 100) + "%"; }
function latClass(v) { return v == null ? "" : v < 500 ? "metric-good" : v < 1200 ? "metric-warn" : "metric-bad"; }
function errClass(v) { return v == null ? "" : v <= 0.02 ? "metric-good" : v <= 0.15 ? "metric-warn" : "metric-bad"; }

/* Flag emoji from a 2-letter country code, so the table always shows a flag
   even when older metadata files predate the server-side "flag" field. */
function flagFromCC(cc) {
  if (!cc || cc.length !== 2 || !/^[a-z]{2}$/i.test(cc)) return "";
  const base = 0x1f1e6;
  return String.fromCodePoint(
    base + cc.toUpperCase().charCodeAt(0) - 65,
    base + cc.toUpperCase().charCodeAt(1) - 65,
  );
}

function relTime(iso) {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const mins = Math.round((Date.now() - then) / 60000);
  if (mins < 1) return lang === "fa" ? "لحظاتی پیش" : "just now";
  if (mins < 60) return lang === "fa" ? `${mins} دقیقه پیش` : `${mins} min ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return lang === "fa" ? `${hrs} ساعت پیش` : `${hrs} h ago`;
  const days = Math.round(hrs / 24);
  return lang === "fa" ? `${days} روز پیش` : `${days} d ago`;
}

/* ── renderers ────────────────────────────────────────────── */
let lastStatus = null, lastConfigs = null, lastSources = null;

function renderStatus(s) {
  if (!s) return;
  const status = s.status || "idle";
  const pill = $("statusPill");
  pill.dataset.status = status;
  $("statusLabel").textContent = t("st_" + status) || status;
  $("stageChip").textContent = s.stage || "";
  $("runMsg").textContent = s.message || "";
  $("progressFill").style.width = Math.round((s.progress || 0) * 100) + "%";
  $("runBtn").disabled = status === "running";
}

function renderConfigs(d) {
  const body = $("configBody");
  const empty = $("configEmpty");
  body.replaceChildren();
  const configs = (d && d.configs) || [];
  $("configCount").textContent = configs.length;

  if (!configs.length) {
    empty.style.display = "block";
    updateKpis(d, configs);
    return;
  }
  empty.style.display = "none";

  configs.forEach((c, i) => {
    const flag = c.flag || flagFromCC(c.country);
    const label = c.country_name || c.name || "config";
    const name = el("td", { class: "cfg-name" }, [
      flag ? el("span", { class: "cfg-flag", text: flag }) : null,
      document.createTextNode(`${label} · ${String(i + 1).padStart(2, "0")}`),
    ]);
    const proto = el("td", {}, el("span", { class: "tag", text: c.protocol || "—" }));
    const uri = el("td", { class: "cfg-uri", title: c.uri, text: c.uri || "" });
    const lat = c.avg_latency_ms;
    const err = c.weighted_error_rate;
    const latency = el("td", {}, el("span", { class: "metric " + latClass(lat), text: fmtMs(lat) }));
    const errors = el("td", {}, el("span", { class: "metric " + errClass(err), text: fmtPct(err) }));
    const action = el("td", {}, el("button", {
      class: "btn btn-soft btn-xs", text: t("copy"),
      onclick: () => copyText(c.uri || ""),
    }));
    body.append(el("tr", {}, [name, proto, uri, latency, errors, action]));
  });
  updateKpis(d, configs);
}

function updateKpis(d, configs) {
  $("kpiCount").textContent = configs.length || "—";

  const countries = new Set(configs.map((c) => c.country).filter(Boolean));
  $("kpiCountries").textContent = countries.size
    ? t("countries_n")(countries.size) : t("kpi_countries_empty");

  const lats = configs.map((c) => c.avg_latency_ms).filter((v) => v != null);
  $("kpiLatency").textContent = lats.length ? fmtMs(lats.reduce((a, b) => a + b, 0) / lats.length) : "—";

  const errs = configs.map((c) => c.weighted_error_rate).filter((v) => v != null);
  $("kpiErrors").textContent = errs.length ? fmtPct(errs.reduce((a, b) => a + b, 0) / errs.length) : "—";

  const gen = d && d.generated_at;
  $("kpiUpdated").textContent = gen ? new Date(gen).toLocaleString() : "—";
  $("kpiUpdatedRel").textContent = relTime(gen);
}

function renderSources(d) {
  const list = $("sourceList");
  list.replaceChildren();
  const urls = (d && d.urls) || [];
  $("subCount").textContent = urls.length;
  $("subMax").textContent = (d && d.max) != null ? d.max : "—";

  if (!urls.length) {
    list.append(el("li", {}, el("span", { class: "src-url", text: t("no_sources") })));
    return;
  }
  urls.forEach((u) => {
    const btn = el("button", { class: "btn btn-danger btn-xs", text: t("remove"), onclick: () => removeSource(u) });
    list.append(el("li", {}, [el("span", { class: "src-url", text: u }), btn]));
  });
}

/* ── actions ──────────────────────────────────────────────── */
async function runNow() {
  $("runBtn").disabled = true;
  try {
    const d = await api("/api/run", { method: "POST" });
    toast(d.started ? t("run_started") : t("run_busy"));
    await refreshStatus();
  } catch (e) { toast(t("err") + ": " + e.message, "error"); }
}

async function addSource() {
  const url = $("newSub").value.trim();
  if (!url) return;
  try {
    await api("/api/subscriptions/add", jsonBody({ url }));
    $("newSub").value = "";
    await refreshSources();
  } catch (e) { toast(t("err") + ": " + e.message, "error"); }
}

async function removeSource(url) {
  try {
    await api("/api/subscriptions/remove", jsonBody({ url }));
    await refreshSources();
  } catch (e) { toast(t("err") + ": " + e.message, "error"); }
}

async function saveSchedule() {
  try {
    const d = await api("/api/schedule", jsonBody({
      schedule_time: $("schedTime").value,
      timezone: $("schedTz").value.trim(),
    }));
    $("schedMsg").textContent = `${t("saved_next")} ${d.schedule_time} ${d.timezone}`;
  } catch (e) { $("schedMsg").textContent = t("err") + ": " + e.message; }
}

const jsonBody = (obj) => ({
  method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(obj),
});

/* ── pollers ──────────────────────────────────────────────── */
async function refreshStatus() {
  try { lastStatus = await api("/api/status"); renderStatus(lastStatus); return lastStatus; }
  catch (_) { return null; }
}
async function refreshLogs() {
  try {
    const d = await api("/api/logs?after=" + logSeq);
    if (d.lines && d.lines.length) {
      logSeq = d.seq;
      const box = $("logs");
      box.textContent += d.lines.join("\n") + "\n";
      box.scrollTop = box.scrollHeight;
    }
  } catch (_) {}
}
async function refreshConfigs() {
  try { lastConfigs = await api("/api/configs"); renderConfigs(lastConfigs); } catch (_) {}
}
async function refreshSources() {
  try { lastSources = await api("/api/subscriptions"); renderSources(lastSources); } catch (_) {}
}
async function refreshSchedule() {
  try {
    const d = await api("/api/schedule");
    $("schedTime").value = d.schedule_time || "";
    $("schedTz").value = d.timezone || "";
  } catch (_) {}
}

/* ── boot ─────────────────────────────────────────────────── */
function initTheme() {
  const saved = localStorage.getItem("vpnt_theme");
  if (saved) document.documentElement.dataset.theme = saved;
}
$("themeBtn").addEventListener("click", () => {
  const root = document.documentElement;
  root.dataset.theme = root.dataset.theme === "light" ? "dark" : "light";
  localStorage.setItem("vpnt_theme", root.dataset.theme);
});
$("langBtn").addEventListener("click", () => {
  lang = lang === "fa" ? "en" : "fa";
  localStorage.setItem("vpnt_lang", lang);
  applyLang();
});
$("runBtn").addEventListener("click", runNow);
$("addSubBtn").addEventListener("click", addSource);
$("saveSchedBtn").addEventListener("click", saveSchedule);
$("copyLinkBtn").addEventListener("click", () => copyText($("subLink").value));
$("clearLogsBtn").addEventListener("click", () => { $("logs").textContent = ""; });
$("newSub").addEventListener("keydown", (e) => { if (e.key === "Enter") addSource(); });

initTheme();
$("subLink").value = window.location.origin + "/subscription";
applyLang();
refreshStatus(); refreshLogs(); refreshConfigs(); refreshSources(); refreshSchedule();

setInterval(async () => {
  const s = await refreshStatus();
  await refreshLogs();
  if (s && s.status === "done") refreshConfigs();
}, 1500);
setInterval(refreshSources, 10000);
