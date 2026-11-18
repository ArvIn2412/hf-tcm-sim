// Design shell for the scientific studio (light academic theme).
// Runs after system_workspace.js and exp04_results.js have built the active
// workspace: it restyles and regroups existing nodes, adds page headings and
// empty states, and never changes element ids, API calls or simulation logic.
(() => {
  'use strict';

  const PAGES = {
    parameters: {
      step: '1', tab: 'Експеримент', eyebrow: 'Крок 1 · Експеримент',
      lead: 'Задайте канал, тракт приймача й метрику. Обидва декодери — Хемінг із жорстким рішенням і Евклід із м’якою метрикою — обробляють одне й те саме спостереження.',
    },
    stages: {
      step: '2', tab: 'Етапи обробки', eyebrow: 'Крок 2 · Етапи обробки',
      lead: 'Один парний кадр з режиму «Метрики», символ за символом. Спільні етапи — угорі; далі ліва половина показує Хемінга (жорстке рішення), права — Евкліда (м’яке рішення) на тому самому z_k.',
    },
    transmitter: {
      step: '3', tab: 'Сигнал і канал', eyebrow: 'Крок 3 · Сигнал і канал',
      lead: 'Передані й прийняті відліки, сузір’я 8PSK, шум і внесок променів для останнього кадру. Позицію в кадрі задає панель угорі.',
    },
    viterbi: {
      step: '4', tab: 'Декодування', eyebrow: 'Крок 4 · Декодування',
      lead: 'Решітки Вітербі обох декодерів на тих самих спостереженнях. Оберіть перехід, щоб порівняти метрики Хемінга й Евкліда на одному такті.',
    },
    metric: {
      step: '5', tab: 'Результати', eyebrow: 'Крок 5 · Результати',
      lead: 'BER і час приймання для останнього запуску та енергетичний виграш за статистичною серією.',
    },
    saved: {
      tab: 'Дослідження', eyebrow: 'Архів',
      lead: 'Усі збережені кадри й серії. Відкрийте запис, щоб переглянути його, або використайте його конфігурацію для нового запуску.',
    },
  };

  const ICONS = {
    signal: '<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2 12h3l2-6 4 12 3-9 2 3h6"/></svg>',
    trellis: '<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><circle cx="5" cy="6" r="1.6"/><circle cx="5" cy="18" r="1.6"/><circle cx="12" cy="6" r="1.6"/><circle cx="12" cy="18" r="1.6"/><circle cx="19" cy="6" r="1.6"/><circle cx="19" cy="18" r="1.6"/><path d="M6.6 6h3.8M6.4 7l4.2 10M13.6 18h3.8M13.4 17l4.2-10"/></svg>',
    chart: '<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 4v16h16"/><path d="M7 7c3 0 4 3 6 6s4 4 7 4"/></svg>',
  };

  const $ = id => document.getElementById(id);
  const el = (tag, attrs = {}, html = '') => {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
    if (html) node.innerHTML = html;
    return node;
  };
  const go = view => document.querySelector(`.tabs .tab[data-view="${view}"]`)?.click();

  function tone(text) {
    const t = (text || '').toLowerCase();
    if (/помилк|не вдалося|відмов|error/.test(t)) return 'error';
    if (/заверш|збережено|готово/.test(t)) return 'ok';
    if (/викон|запуск|обчисл|кадр.*\/|%|…/.test(t) && !/очікує/.test(t)) return 'busy';
    return 'idle';
  }

  if (typeof module !== 'undefined') module.exports = {tone, PAGES};
  if (typeof document === 'undefined') return;

  function pageHead(view, key) {
    const page = PAGES[key];
    const h1 = view.querySelector(':scope > h1');
    if (!page || !h1) return;
    const head = el('div', {class: 'ds-page-head'});
    const text = el('div');
    text.append(el('p', {class: 'ds-eyebrow'}, page.eyebrow), h1, el('p', {class: 'ds-lead'}, page.lead));
    head.append(text);
    view.prepend(head);
  }

  function emptyState({icon, title, text, actions}) {
    const box = el('div', {class: 'ds-empty', role: 'status'});
    box.append(el('div', {class: 'ds-empty-icon'}, ICONS[icon]));
    box.append(el('div', {}, `<h2>${title}</h2><p>${text}</p>`));
    const row = el('div', {class: 'ds-actions'});
    for (const [label, handler, primary] of actions) {
      const button = el('button', {type: 'button', class: primary ? 'ds-primary' : ''});
      button.textContent = label;
      button.addEventListener('click', handler);
      row.append(button);
    }
    box.append(row);
    return box;
  }

  function setContrast(value) {
    const contrast = $('exp-contrast');
    if (contrast && contrast.value !== value) {
      contrast.value = value;
      contrast.dispatchEvent(new Event('change', {bubbles: true}));
    }
  }
  function frameLengthInput() {
    return [...document.querySelectorAll('#run-form label')].find(l => /^N\b/.test(l.textContent.trim()))?.querySelector('input');
  }
  function runDemoFrame() {
    setContrast('system');
    const n = frameLengthInput();
    if (n) { n.value = '256'; n.dispatchEvent(new Event('input', {bubbles: true})); n.dispatchEvent(new Event('change', {bubbles: true})); }
    $('run-button')?.click();
  }
  function configureSystemRun() { setContrast('system'); go('parameters'); }

  function experimentLayout(view) {
    const form = $('run-form');
    if (!form) return;
    const layout = el('div', {class: 'ds-exp-layout'});
    const left = el('div');
    const aside = el('aside', {class: 'ds-aside', 'aria-label': 'Пояснення до експерименту'});
    view.append(layout);
    layout.append(left, aside);
    left.append(form);

    const primary = form.querySelector(':scope > .simulation-primary');
    const card = el('div', {class: 'card ds-form-card'});
    card.append(el('h2', {}, 'Параметри моделювання'));
    form.prepend(card);
    if (primary) card.append(primary);
    form.querySelectorAll(':scope > .metric-mode-hint').forEach(p => card.append(p));
    const bar = el('div', {class: 'ds-run-bar'});
    const run = $('run-button'), progress = $('es-progress');
    if (run) bar.append(run);
    if (progress) bar.append(progress);
    card.append(bar);
    const details = form.querySelector(':scope > details');
    if (details) details.querySelector('summary').textContent = 'Додаткові параметри: кадр, пілоти, промені, seed';

    aside.innerHTML = `
      <div class="card"><h2>Що порівнюється</h2>
        <div class="ds-legend-row"><span class="ds-swatch" style="background:var(--ds-hamming)"></span><span><strong>Хемінг</strong> — жорстке рішення 8PSK → 3 біти → Вітербі з цілочисельною метрикою.</span></div>
        <div class="ds-legend-row"><span class="ds-swatch" style="background:var(--ds-euclid)"></span><span><strong>Евклід</strong> — спільні демодуляція й декодування: Вітербі з метрикою |z − s|², зваженою за станом тракту.</span></div>
        <p style="margin:10px 0 0">Код TCM R = 2/3, 4 стани, 8PSK, глибина відкладеного рішення η = 20.</p></div>
      <div class="card"><h2>Два режими запуску</h2><ul>
        <li><strong>Метрики</strong> — ізольоване порівняння метрик на одному виході тракту; дає BER і енергетичний виграш.</li>
        <li><strong>Повні приймачі Joint / B0</strong> — зберігає сигнал і решітки: їх показують вкладки «Сигнал і канал» та «Декодування».</li></ul></div>
      <div class="card"><h2>Після запуску</h2><p>Відкриється вкладка «Результати». Як саме відрізняються рішення Хемінга й Евкліда на кожному символі — у вкладці «Етапи обробки». Підтверджені висновки (серія EXP-04, 99 200 кадрів) — у вкладці «Головний результат».</p></div>`;
  }

  function signalLayout(view) {
    const tools = view.querySelector(':scope > .system-signal-tools');
    const canvas = $('system-signal-canvas');
    const inspector = $('system-symbol-inspector');
    if (!tools || !canvas) return;
    const panel = el('div', {class: 'card ds-panel'});
    tools.before(panel);
    panel.append(tools, canvas);
    if (inspector) panel.append(inspector);
    const nav = view.querySelector(':scope > .sequence-navigator');
    if (nav) panel.before(nav);
  }

  function watchEmpty(view, box, isEmpty, targets) {
    view.querySelector('.ds-page-head')?.after(box);
    const update = () => { box.hidden = !isEmpty(); };
    const observer = new MutationObserver(update);
    for (const node of targets) if (node) observer.observe(node, {childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ['hidden']});
    update();
  }

  function init() {
    document.body.classList.add('ds');
    const link = el('link', {rel: 'stylesheet', href: '/static/design.css'});
    document.head.append(link);

    // Header: tabs with step numbers, status chip at the right, contextual toolbar below.
    const header = document.querySelector('header.topbar');
    for (const [key, page] of Object.entries(PAGES)) {
      const tab = document.querySelector(`.tabs .tab[data-view="${key}"]`);
      if (!tab) continue;
      tab.textContent = page.tab;
      if (page.step) tab.dataset.step = page.step;
      const option = document.querySelector(`.mobile-view-menu option[value="${key}"]`);
      if (option) option.textContent = page.tab;
    }
    const resultTab = document.querySelector('.tabs .tab[data-view="result"]');
    if (resultTab) resultTab.textContent = 'Головний результат';
    const status = $('job-status');
    const toolbar = header?.querySelector('.sync-toolbar');
    if (header && status) {
      header.insertBefore(status, toolbar || null);
      status.setAttribute('role', 'status');
      const refresh = () => { status.dataset.tone = tone(status.textContent); status.title = status.textContent; };
      new MutationObserver(refresh).observe(status, {childList: true, characterData: true, subtree: true});
      refresh();
    }
    const zoom = $('zoom-20-samples');
    if (zoom) zoom.textContent = 'Наблизити 20 відліків';

    // Track the active view on <body> for contextual styling.
    const views = [...document.querySelectorAll('main > .view')];
    const syncView = () => {
      const active = document.querySelector('main > .view.active');
      document.body.dataset.view = active ? active.id.replace('view-', '') : '';
    };
    const viewObserver = new MutationObserver(syncView);
    for (const v of views) viewObserver.observe(v, {attributes: true, attributeFilter: ['class']});
    syncView();

    for (const key of Object.keys(PAGES)) {
      const view = $('view-' + key);
      if (view) pageHead(view, key);
    }
    const parameters = $('view-parameters');
    if (parameters) experimentLayout(parameters);
    const transmitter = $('view-transmitter');
    if (transmitter) signalLayout(transmitter);

    // Empty states: signal and trellises exist only after a full-receiver run.
    const trellis = $('system-trellis-joint');
    const noSystemRun = () => !trellis || trellis.childElementCount === 0;
    const markRun = () => { if (noSystemRun()) document.body.dataset.noRun = ''; else delete document.body.dataset.noRun; };
    if (trellis) new MutationObserver(markRun).observe(trellis, {childList: true});
    markRun();
    if (transmitter) watchEmpty(transmitter, emptyState({
      icon: 'signal', title: 'Сигнал ще не побудовано',
      text: 'Відліки, сузір’я та внесок каналу зберігає режим «Повні приймачі Joint / B0». Для порівняння метрик символ за символом відкрийте «Етапи обробки». Запустіть короткий кадр (256 елементів) або налаштуйте власний.',
      actions: [['Запустити кадр N = 256', runDemoFrame, true], ['Налаштувати', configureSystemRun]],
    }), noSystemRun, [trellis]);
    const viterbi = $('view-viterbi');
    if (viterbi) watchEmpty(viterbi, emptyState({
      icon: 'trellis', title: 'Решітки ще не побудовано',
      text: 'Решітки Вітербі обох декодерів зберігає режим «Повні приймачі Joint / B0». Після запуску тут можна вибрати перехід і порівняти метрики.',
      actions: [['Запустити кадр N = 256', runDemoFrame, true], ['Налаштувати', configureSystemRun]],
    }), noSystemRun, [trellis]);
    const metric = $('view-metric');
    const runResults = $('system-run-results'), metricResults = $('metric-mode-results');
    if (runResults) {
      const placeholder = () => runResults.classList.toggle('ds-placeholder', /^\s*Запуск ще не виконано/.test(runResults.textContent));
      new MutationObserver(placeholder).observe(runResults, {childList: true, characterData: true, subtree: true});
      placeholder();
    }
    if (metric) watchEmpty(metric, emptyState({
      icon: 'chart', title: 'Запуску ще не було',
      text: 'Виконайте експеримент, щоб побачити BER обох декодерів. Підтверджені результати серії EXP-04 вже доступні у вкладці «Головний результат».',
      actions: [['До експерименту', () => go('parameters'), true], ['Головний результат', () => go('result')]],
    }), () => (!runResults || /^\s*Запуск ще не виконано/.test(runResults.textContent)) && (!metricResults || metricResults.hidden), [runResults, metricResults]);
  }

  // Deferred scripts run while readyState is 'interactive'; earlier scripts register
  // their DOMContentLoaded handlers first, so this one runs after their rebuild.
  if (document.readyState === 'complete') init(); else document.addEventListener('DOMContentLoaded', init);
})();
