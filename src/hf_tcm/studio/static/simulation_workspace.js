/* Minimal simulation workspace using the existing controls and submit handler. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const view = $('view-parameters'), form = $('metric-study-form');
  const primary = document.createElement('div');
  primary.className = 'simulation-primary';
  primary.append(document.querySelector('.simulation-channel-controls'));
  function moveLabel(id, title, target) {
    const label = $(id).closest('label');
    label.firstChild.textContent = title;
    label.querySelectorAll('small, .parameter-explanation').forEach(node => node.remove());
    target.append(label);
  }
  moveLabel('mx-tract', 'Тракт приймача', primary);
  moveLabel('mx-euclid', 'Евклідова метрика', primary);
  moveLabel('mx-noise', 'Дисперсія шуму σ²', primary);
  moveLabel('mx-frame', 'Довжина N', primary);
  moveLabel('mx-seed', 'Seed', primary);
  moveLabel('article-mode', 'Режим', primary);
  const mode = primary.querySelector('#article-mode');
  mode.options[0].textContent = 'Один запуск';
  mode.options[1].textContent = 'Статистична серія';
  $('article-sweep').checked = false;
  const advanced = document.createElement('details');
  advanced.className = 'simulation-advanced';
  advanced.innerHTML = '<summary>Додатково</summary>';
  const fields = document.createElement('div');
  fields.className = 'simulation-primary';
  for (const [id, title] of [
    ['model-delays', 'Затримки променів'], ['model-powers', 'Потужності променів'],
    ['model-k', 'K-фактори'], ['model-los', 'Фази променів'], ['mx-rho', 'Кореляція ρ'],
    ['mx-preamble', 'Довжина преамбули'], ['mx-period', 'Період пілотів'],
    ['mx-burst', 'Довжина пілотного блоку'], ['mx-trials', 'Кількість повторень'],
    ['mx-target', 'Цільовий BER'], ['mx-grid', 'Енергетична сітка'],
    ['mx-budget', 'Ліміт часу, с'], ['mx-sweep', 'Спосіб зміни енергії'],
    ['mx-amplitude', 'Амплітуда сигналу'], ['article-sweep', 'Виконати енергетичну серію']
  ]) moveLabel(id, title, fields);
  advanced.append(fields);
  const run = $('mx-run'), stop = $('mx-stop'), status = $('mx-status'), progress = $('mx-progress');
  run.textContent = 'Запустити моделювання';
  status.textContent = '';
  const updateStop = () => { stop.hidden = stop.disabled; };
  new MutationObserver(updateStop).observe(stop, {attributes: true, attributeFilter: ['disabled']});
  updateStop();
  const actions = document.createElement('div');
  actions.className = 'simulation-actions';
  actions.append(run, stop);
  const resultButton = document.createElement('button');
  resultButton.type = 'button'; resultButton.className = 'secondary-button';
  resultButton.textContent = 'Переглянути результати'; resultButton.hidden = true;
  resultButton.addEventListener('click', () => document.querySelector('.tab[data-view="metric"]').click());
  const backing = document.createElement('div');
  backing.hidden = true;
  for (const id of ['mx-id', 'mx-scenario', 'article-profile', 'restore-article', 'mx-overhead', 'model-rays']) backing.append($(id));
  const heading = document.createElement('h1'); heading.textContent = 'Моделювання сигналу';
  form.replaceChildren(primary, actions, status, progress, resultButton, advanced, backing);
  view.replaceChildren(heading, form);
  const noise = $('mx-noise');
  const toggleNoise = () => { noise.closest('label').hidden = $('channel-awgn').value === 'off'; };
  $('channel-awgn').addEventListener('change', toggleNoise); toggleNoise();
  window.addEventListener('metric-summary', () => { resultButton.hidden = false; });
})();
