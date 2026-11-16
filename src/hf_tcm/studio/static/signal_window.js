(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.HFTCMSignalWindow = api;
})(typeof globalThis === "undefined" ? this : globalThis, function () {
  "use strict";

  function positiveInteger(value, name) {
    if (!Number.isSafeInteger(value) || value < 1) {
      throw new RangeError(`${name} must be a positive integer`);
    }
    return value;
  }

  function nonNegativeInteger(value, name) {
    if (!Number.isSafeInteger(value) || value < 0) {
      throw new RangeError(`${name} must be a non-negative integer`);
    }
    return value;
  }

  function calculateSampleWindow(totalSamples, requestedStartSample, windowSamples) {
    const total = positiveInteger(totalSamples, "totalSamples");
    const requested = nonNegativeInteger(requestedStartSample, "requestedStartSample");
    const requestedWindow = positiveInteger(windowSamples, "windowSamples");
    const visibleLength = Math.min(total, requestedWindow);
    const maxStartSample = Math.max(0, total - visibleLength);
    const startSample = Math.min(requested, maxStartSample);
    const endSample = startSample + visibleLength;
    return {
      startSample,
      endSample,
      length: visibleLength,
      maxStartSample,
      sampleIndices: Array.from({ length: visibleLength }, (_, index) => startSample + index),
    };
  }

  function symbolIndexAtSample(sampleIndex, symbolCount, samplesPerSymbol) {
    const sample = nonNegativeInteger(sampleIndex, "sampleIndex");
    const symbols = positiveInteger(symbolCount, "symbolCount");
    const samples = positiveInteger(samplesPerSymbol, "samplesPerSymbol");
    return Math.min(symbols - 1, Math.floor(sample / samples));
  }

  function windowStartSampleForSymbol(
    symbolIndex,
    symbolCount,
    samplesPerSymbol,
    windowSamples,
  ) {
    const selected = nonNegativeInteger(symbolIndex, "symbolIndex");
    const symbols = positiveInteger(symbolCount, "symbolCount");
    const samples = positiveInteger(samplesPerSymbol, "samplesPerSymbol");
    const requestedWindow = positiveInteger(windowSamples, "windowSamples");
    if (selected >= symbols) throw new RangeError("symbolIndex must be inside the frame");
    const totalSamples = symbols * samples;
    const window = calculateSampleWindow(totalSamples, 0, requestedWindow);
    const visibleSymbols = Math.max(1, Math.ceil(window.length / samples));
    const maximumStartSymbol = Math.max(0, symbols - visibleSymbols);
    const desiredStartSymbol = selected - Math.floor(visibleSymbols / 2);
    const startSymbol = Math.max(0, Math.min(maximumStartSymbol, desiredStartSymbol));
    return Math.min(startSymbol * samples, window.maxStartSample);
  }

  function validateBits(bits, maxBits) {
    if (!Number.isSafeInteger(maxBits) || maxBits < 2 || maxBits % 2 !== 0) {
      throw new RangeError("maxBits must be a positive even integer");
    }
    if (bits.length < 2) return { bits: null, error: "Потрібно щонайменше 2 біти." };
    if (bits.length > maxBits) {
      return { bits: null, error: `Дозволено від 2 до ${maxBits} бітів для цього режиму.` };
    }
    if (bits.length % 2 !== 0) {
      return { bits: null, error: "Кількість інформаційних бітів має бути парною для групування по 2." };
    }
    return { bits, error: null };
  }

  function parseManualBits(value, { maxBits = 64 } = {}) {
    if (typeof value !== "string" || !/^[01\s]*$/.test(value)) {
      return { bits: null, error: "Введіть лише символи 0 або 1; пробіли й переноси рядка дозволені." };
    }
    return validateBits(value.replace(/\s/g, ""), maxBits);
  }

  function parseDelimitedBitFile(value, { maxBits = 64 } = {}) {
    if (typeof value !== "string") {
      return { bits: null, error: "Файл має містити лише 0 та 1, розділені комами, крапками з комою або пробілами." };
    }
    const text = value.trim();
    if (!text || !/^[01](?:[01]|[\s,;]+[01])*$/.test(text)) {
      return { bits: null, error: "Файл має містити лише 0 та 1 без заголовка чи зайвих роздільників." };
    }
    return validateBits(text.replace(/[\s,;]/g, ""), maxBits);
  }

  return Object.freeze({
    calculateSampleWindow,
    symbolIndexAtSample,
    windowStartSampleForSymbol,
    parseManualBits,
    parseDelimitedBitFile,
  });
});
