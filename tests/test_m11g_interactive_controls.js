const test = require("node:test");
const assert = require("node:assert/strict");

const studio = require("../src/hf_tcm/studio/static/signal_window.js");

test("manual bits accept only binary digits and whitespace", () => {
  assert.deepEqual(studio.parseManualBits("01 10\n0011", { maxBits: 64 }), {
    bits: "01100011",
    error: null,
  });
  assert.match(studio.parseManualBits("01x0", { maxBits: 64 }).error, /0 або 1/);
});

test("local TXT/CSV parser accepts explicit delimiters but rejects headers and dangling separators", () => {
  assert.deepEqual(studio.parseDelimitedBitFile("0,1,0\r\n1;0;1", { maxBits: 64 }), {
    bits: "010101",
    error: null,
  });
  assert.match(studio.parseDelimitedBitFile("bits\n0,1", { maxBits: 64 }).error, /лише 0 та 1/);
  assert.match(studio.parseDelimitedBitFile("0,1,", { maxBits: 64 }).error, /лише 0 та 1/);
});

test("input validation requires even groups and enforces encoder-specific safe maximum", () => {
  assert.match(studio.parseManualBits("010", { maxBits: 64 }).error, /має бути парною/);
  assert.match(studio.parseManualBits("0".repeat(66), { maxBits: 64 }).error, /2 до 64/);
  assert.deepEqual(studio.parseManualBits("01".repeat(128), { maxBits: 256 }), {
    bits: "01".repeat(128),
    error: null,
  });
});

