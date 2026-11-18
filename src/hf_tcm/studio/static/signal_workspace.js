/* One active signal canvas; the existing renderers and window API remain authoritative. */
(() => {
  'use strict';
  const byId = id => document.getElementById(id) || window.signalArchive.querySelector('#' + id);
  const view = document.getElementById('view-transmitter');
  const archive = document.createDocumentFragment();
  window.signalArchive = archive;
  const nav = document.querySelector('.sequence-navigator');
  const wave = document.getElementById('live-wave');
  const cloud = document.getElementById('received-cloud');
  const oldCloud = document.getElementById('view-constellation');
  archive.append(...view.childNodes, oldCloud);
  const oldControls = document.createElement('div');
  oldControls.append(...nav.childNodes);
  archive.append(oldControls);
  const title = document.createElement('h1'); title.textContent = 'Сигнал';
  const bar = document.createElement('div'); bar.className = 'signal-bar';
  const label = document.createElement('label'); label.textContent = 'Графік';
  const mode = document.createElement('select'); mode.id = 'signal-mode';
  mode.innerHTML = '<option value="overlay">TX/RX</option><option value="lanes">I/Q</option><option value="cloud">Сузір’я 8PSK</option>';
  label.append(mode); bar.append(label);
  const indexLabel = document.createElement('label'); indexLabel.textContent = 'Символ';
  indexLabel.append(byId('seq-index'));
  for (const id of ['seq-prev', 'seq-next']) bar.append(byId(id));
  bar.append(indexLabel, byId('seq-go'));
  const zoomIn = document.createElement('button'), zoomOut = document.createElement('button'), reset = document.createElement('button');
  for (const [button, text] of [[zoomIn, 'Zoom +'], [zoomOut, 'Zoom −'], [reset, 'Fit']]) {button.type='button';button.textContent=text;bar.append(button);}
  const domain = byId('seq-domain'); domain.hidden = true;
  nav.replaceChildren(bar, byId('seq-status'), domain); nav.classList.remove('card');
  const plot = document.createElement('div'); plot.className = 'signal-plot';
  const hover = byId('wave-hover');
  const inspector = document.createElement('section'); inspector.className = 'signal-inspector';
  inspector.innerHTML = '<h2>Вибраний символ</h2><p>Запустіть моделювання, щоб дослідити сигнал.</p>';
  view.append(title, nav, plot, hover, inspector);
  const tab = document.querySelector('.tab[data-view="constellation"]'); if (tab) tab.remove();
  document.querySelector('.tab[data-view="transmitter"]').textContent = 'Сигнал';
  const option = document.querySelector('.mobile-view-menu option[value="constellation"]'); if (option) option.remove();
  const signalOption = document.querySelector('.mobile-view-menu option[value="transmitter"]'); if (signalOption) signalOption.textContent = 'Сигнал';
  function activate() {
    if (mode.value === 'cloud') { archive.append(wave); plot.replaceChildren(cloud); byId('xy-fit').click(); }
    else { archive.append(cloud); plot.replaceChildren(wave); const select = byId('wave-mode'); select.value=mode.value; select.dispatchEvent(new Event('change')); }
    window.dispatchEvent(new Event('resize'));
  }
  mode.addEventListener('change', activate);
  zoomIn.onclick=()=>byId(mode.value==='cloud'?'xy-in':'seq-in').click();
  zoomOut.onclick=()=>byId(mode.value==='cloud'?'xy-out':'seq-out').click();
  reset.onclick=()=>byId(mode.value==='cloud'?'xy-fit':'wave-fit').click();
  window.addEventListener('lab-window', event => {
    const i=event.detail.inspector, bits=v=>Array.isArray(v)?v.join(' '):'—';
    const number=v=>Number.isFinite(v)?Number(v).toPrecision(6):'—';
    inspector.querySelector('p').textContent=`Символ ${i.symbol} · Вхідні біти: ${bits(i.input)} · Кодовані: ${bits(i.coded)} · TX I/Q: ${number(i.tx_i)} / ${number(i.tx_q)} · RX I/Q: ${number(i.rx_i)} / ${number(i.rx_q)} · Хемінг: ${bits(i.hamming)} · Евклід: ${bits(i.euclidean)}`;
  });
  window.addEventListener('metric-context-cleared',()=>{inspector.querySelector('p').textContent='Для вибраного дослідження сигнал недоступний.';});
  activate();
})();
