'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const {tone, PAGES} = require('../src/hf_tcm/studio/static/design_shell.js');

test('status chip tone follows the job status text', () => {
  assert.equal(tone('Очікує параметрів'), 'idle');
  assert.equal(tone('Симуляцію завершено · результати збережено.'), 'ok');
  assert.equal(tone('Порівняння метрик завершено (1/1 кадрів).'), 'ok');
  assert.equal(tone('Виконується кадр 3/10…'), 'busy');
  assert.equal(tone('Не вдалося запустити: помилка сервера'), 'error');
  assert.equal(tone(''), 'idle');
});

test('workflow pages are numbered 1-5 and the archive has no step', () => {
  assert.deepEqual(['parameters', 'stages', 'transmitter', 'viterbi', 'metric'].map(k => PAGES[k].step), ['1', '2', '3', '4', '5']);
  assert.equal(PAGES.saved.step, undefined);
  for (const page of Object.values(PAGES)) assert.ok(page.tab && page.eyebrow && page.lead);
});
