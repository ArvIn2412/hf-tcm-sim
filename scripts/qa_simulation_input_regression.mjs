import assert from 'node:assert/strict';
import {js, until, pause, errors, close} from './stage4_cdp.mjs';

try {
  await until('document.querySelector("#metric-study-form") && document.querySelector("#article-profile")');
  errors.length = 0;
  await js(`(() => {
    const profile = document.getElementById('article-profile');
    profile.value = 'article';
    const input = document.getElementById('mx-frame');
    input.dispatchEvent(new Event('input', {bubbles: true}));
  })()`);
  await pause(100);
  assert.equal(await js('document.getElementById("article-profile").value'), 'custom');
  assert.deepEqual(errors, []);
  console.log('PASS: input works after profile-origin is removed');
} finally {
  close();
}
