/* HF-TCM-SIM · Terra Focus adapter.
   Keeps the original tabs and their click handlers as the single source of truth.
   No simulation, receiver, statistical, or API logic is changed. */
(() => {
  "use strict";
  const MAIN = [
    { id: "parameters", label: "Моделювання" },
    { id: "transmitter", label: "Сигнал" },
    { id: "viterbi", label: "Декодування" },
    { id: "metric", label: "Результати" },
    { id: "saved", label: "Історія" },
  ];
  const SIGNAL = [
    { id: "transmitter", label: "Передавач і канал" },
    { id: "constellation", label: "Сузір’я 8PSK" },
  ];
  const SIGNAL_IDS = new Set(SIGNAL.map(x => x.id));
  let lastSignal = "transmitter";

  function setup() {
    if (document.body.classList.contains("terra-focus")) return;
    const originalNav = document.querySelector(".topbar .tabs");
    if (!originalNav) return;
    const original = new Map(
      [...originalNav.querySelectorAll("button[data-view]")].map(x => [x.dataset.view, x])
    );
    if (MAIN.some(x => !original.has(x.id)) || !original.has("constellation")) {
      return; // incompatible build: fail open and keep existing navigation
    }
    const main = document.querySelector("main");
    const nav = document.createElement("nav");
    nav.className = "terra-primary-nav";
    nav.setAttribute("aria-label", "Робочі простори");
    const subnav = document.createElement("nav");
    subnav.className = "terra-secondary-nav";
    subnav.setAttribute("aria-label", "Розділи сигналу");
    const primaryButtons = new Map();
    const secondaryButtons = new Map();

    function activate(target) {
      const button = original.get(target);
      if (!button) return;
      if (SIGNAL_IDS.has(target)) lastSignal = target;
      button.click();
      // Original UI scripts are authoritative; state refresh follows their handlers.
      queueMicrotask(refresh);
    }
    function makeButton(item, destination) {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = item.label;
      button.dataset.terraView = item.id;
      button.addEventListener("click", () => activate(destination(item.id)));
      return button;
    }
    for (const item of MAIN) {
      const button = makeButton(item, id => id === "transmitter" ? lastSignal : id);
      nav.append(button);
      primaryButtons.set(item.id, button);
    }
    for (const item of SIGNAL) {
      const button = makeButton(item, id => id);
      subnav.append(button);
      secondaryButtons.set(item.id, button);
    }

    function activeView() {
      return [...original.values()].find(x => x.classList.contains("active"))?.dataset.view
        || [...document.querySelectorAll("main > .view.active")][0]?.id?.replace(/^view-/, "")
        || "parameters";
    }
    function refresh() {
      const active = activeView();
      const group = SIGNAL_IDS.has(active) ? "transmitter" : active;
      for (const [id, button] of primaryButtons) {
        const current = group === id;
        if (current) button.setAttribute("aria-current", "page");
        else button.removeAttribute("aria-current");
      }
      for (const [id, button] of secondaryButtons) {
        const current = active === id;
        if (current) button.setAttribute("aria-current", "page");
        else button.removeAttribute("aria-current");
      }
      subnav.hidden = !SIGNAL_IDS.has(active);
      if (SIGNAL_IDS.has(active)) lastSignal = active;
    }

    originalNav.after(nav);
    main?.prepend(subnav);
    const observer = new MutationObserver(refresh);
    for (const button of original.values()) {
      observer.observe(button, { attributes: true, attributeFilter: ["class"] });
    }

    function installNavigator() {
      const element = document.querySelector(".sequence-navigator");
      if (!element || element.querySelector(".terra-navigator-head")) return Boolean(element);
      const title = element.querySelector("h2");
      if (!title) return false;
      const head = document.createElement("div");
      head.className = "terra-navigator-head";
      title.before(head);
      head.append(title);
      const more = element.querySelector(".navigator-more");
      if (!more) return true;
      element.classList.add("terra-compact");
      const button = document.createElement("button");
      button.type = "button";
      button.className = "terra-toggle";
      button.textContent = "Інструменти";
      button.setAttribute("aria-expanded", "false");
      if (!more.id) more.id = "terra-more-tools";
      button.setAttribute("aria-controls", more.id);
      button.addEventListener("click", () => {
        const opened = element.classList.toggle("terra-compact") === false;
        button.setAttribute("aria-expanded", String(opened));
        button.textContent = opened ? "Сховати інструменти" : "Інструменти";
      });
      head.append(button);
      return true;
    }

    function installSourceDetails() {
      const source = document.querySelector("#metric-active-source")
        || document.querySelector(".source-summary");
      if (!source || source.dataset.terraPrepared) return Boolean(source);
      source.dataset.terraPrepared = "true";
      source.classList.add("terra-collapsed-source");
      if (!source.id) source.id = "terra-source-details";
      const button = document.createElement("button");
      button.type = "button";
      button.className = "terra-toggle terra-source-button";
      button.textContent = "Джерело даних · Деталі";
      button.setAttribute("aria-expanded", "false");
      button.setAttribute("aria-controls", source.id);
      button.addEventListener("click", () => {
        const opened = source.classList.toggle("terra-collapsed-source") === false;
        button.setAttribute("aria-expanded", String(opened));
        button.textContent = opened ? "Сховати джерело даних" : "Джерело даних · Деталі";
      });
      source.before(button);
      return true;
    }

    document.body.classList.add("terra-focus");
    refresh();
    // Some legacy components are initialized asynchronously: retry briefly, no permanent polling.
    let attempts = 0;
    const timer = window.setInterval(() => {
      const okA = installNavigator();
      const okB = installSourceDetails();
      if ((okA && okB) || ++attempts >= 30) window.clearInterval(timer);
    }, 250);
    installNavigator();
    installSourceDetails();
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", setup, { once: true });
  } else {
    setup();
  }
})();
