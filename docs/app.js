// Fiddel landing page — subscription links, copy, language toggle.
"use strict";

const RAW_BASE =
  "https://raw.githubusercontent.com/sinahosseini379/VPN-Subscription-Tester-/main/";
const MAIN_FILE = "felfelconfig.txt";

// Kept in sync with the tester's default allowed countries (config.py).
const COUNTRIES = [
  { cc: "DE", flag: "🇩🇪", fa: "آلمان", en: "Germany" },
  { cc: "FI", flag: "🇫🇮", fa: "فنلاند", en: "Finland" },
  { cc: "NL", flag: "🇳🇱", fa: "هلند", en: "Netherlands" },
  { cc: "GB", flag: "🇬🇧", fa: "انگلستان", en: "United Kingdom" },
  { cc: "US", flag: "🇺🇸", fa: "آمریکا", en: "United States" },
  { cc: "TR", flag: "🇹🇷", fa: "ترکیه", en: "Turkey" },
];

const $ = (id) => document.getElementById(id);
const countryUrl = (cc) => `${RAW_BASE}felfelconfig-${cc}.txt`;
const isFa = () => document.documentElement.lang === "fa";

let toastTimer;
function toast(msg) {
  const t = $("toast");
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove("show"), 1900);
}

async function copy(text, btn) {
  try {
    await navigator.clipboard.writeText(text);
  } catch (_) {
    const ta = document.createElement("textarea");
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    ta.remove();
  }
  toast(isFa() ? "کپی شد ✓" : "Copied ✓");
  if (btn) {
    const label = btn.querySelector(isFa() ? ".lang-fa" : ".lang-en") || btn;
    const prev = label.textContent;
    btn.classList.add("copied");
    label.textContent = isFa() ? "کپی شد ✓" : "Copied ✓";
    setTimeout(() => {
      btn.classList.remove("copied");
      label.textContent = prev;
    }, 1400);
  }
}

// --- build main link ---
$("mainUrl").textContent = RAW_BASE + MAIN_FILE;

// --- build country grid ---
const grid = $("countryGrid");
COUNTRIES.forEach((c) => {
  const url = countryUrl(c.cc);
  const card = document.createElement("div");
  card.className = "country";

  const top = document.createElement("div");
  top.className = "c-top";
  const flag = document.createElement("span");
  flag.className = "flag";
  flag.textContent = c.flag;
  const names = document.createElement("div");
  const name = document.createElement("div");
  name.className = "c-name";
  name.textContent = isFa() ? c.fa : c.en;
  name.dataset.fa = c.fa;
  name.dataset.en = c.en;
  const sub = document.createElement("div");
  sub.className = "c-sub";
  sub.textContent = `felfelconfig-${c.cc}.txt`;
  names.append(name, sub);
  top.append(flag, names);

  const urlBox = document.createElement("div");
  urlBox.className = "c-url";
  urlBox.textContent = url;

  const btn = document.createElement("button");
  btn.className = "copy-sm";
  btn.type = "button";
  btn.dataset.fa = "کپی لینک " + c.fa;
  btn.dataset.en = "Copy " + c.en;
  btn.textContent = btn.dataset.fa;
  btn.addEventListener("click", () => copy(url, null).then(() => flashBtn(btn)));

  card.append(top, urlBox, btn);
  grid.append(card);
});

function flashBtn(btn) {
  const prev = btn.textContent;
  btn.classList.add("copied");
  btn.textContent = isFa() ? "کپی شد ✓" : "Copied ✓";
  setTimeout(() => {
    btn.classList.remove("copied");
    btn.textContent = prev;
  }, 1400);
}

// --- copy buttons that target an element by id (main link) ---
document.querySelectorAll(".copy-btn[data-target]").forEach((btn) => {
  btn.addEventListener("click", () => copy($(btn.dataset.target).textContent, btn));
});

// --- language toggle ---
function applyLang(lang) {
  const html = document.documentElement;
  html.lang = lang;
  html.dir = lang === "fa" ? "rtl" : "ltr";
  document.body.dir = html.dir;
  localStorage.setItem("fiddel_lang", lang);
  // re-label the data-driven country cards
  document.querySelectorAll(".country .c-name").forEach((n) => {
    n.textContent = lang === "fa" ? n.dataset.fa : n.dataset.en;
  });
  document.querySelectorAll(".country .copy-sm").forEach((b) => {
    if (!b.classList.contains("copied")) b.textContent = lang === "fa" ? b.dataset.fa : b.dataset.en;
  });
}
$("langToggle").addEventListener("click", () => {
  applyLang(isFa() ? "en" : "fa");
});

// restore saved language
const saved = localStorage.getItem("fiddel_lang");
if (saved && saved !== "fa") applyLang(saved);
