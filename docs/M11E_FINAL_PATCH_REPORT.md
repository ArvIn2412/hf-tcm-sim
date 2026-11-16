# M11e final GUI patch and scientific baseline freeze

**Status: M11E_RELEASE_READY**  
**Source fidelity: PAPER_PARTIAL; `paper_exact:false`; `receiver_enabled:false`.**

M11e applies a presentation-layer correction to Demo Studio and records the
verified baseline. No encoder, TCM mapping, 8PSK, channel, receiver, estimator,
candidate metric, posterior, conditional Viterbi, or M5–M10 artifact was
changed. No Monte Carlo or new scientific study was run. The independent audit
file `HF_TCM_INDEPENDENT_INITIAL_AUDIT_UK.md` was not present in the project;
the supplied findings were used.

## GUI correction

The summary read `trace.transmitter.channel_gain`, but the actual deterministic
trace schema provides the gain at `trace.input.channel_gain`. This made the
live channel gain render as `undefined`. The view now reads the schema field
and displays `Недоступно` when a value is missing, null, or non-finite; it does
not supply a hardcoded gain. A browser regression checks the rendered value
after a real deterministic F=32 POST and checks the unavailable-value cases.

Integer counts (symbols, bits, samples, and errors) are formatted as integers.
Rates, coefficients, metrics, posterior values, and plotted numbers use
round-trip-safe numeric strings; no stored values were changed. Confusing
Simple-mode labels were localized in Ukrainian, while Scientific mode keeps
technical names and full numeric precision.

## Scientific source note

- The article's convolutional generator matrix is algebraically consistent
  with the implementation under the corresponding bit ordering.
- Formula [A](5) is partially consistent with the project's IQ prediction.
- Formula [A](2) does not explicitly define whether the residual is squared,
  normed, or absolute-valued. The production metric uses a squared residual;
  this ambiguity was documented, not resolved by changing the mathematical
  core.
- Δφ = π/4 is a phase increment and is not necessarily the absolute φ₀.
- The author's complete phase labeling of all 16 transitions is not
  established.

The source status remains `SOURCE_AUDIT_COMPLETE` / `PAPER_PARTIAL`. ADR-002's
transition mapping remains a project assumption. SCI-02, SCI-03, and
SCI-METRIC-02 remain OPEN. No algorithm is described as paper-exact.

## Test portability

`tests/test_m11e_portability.py` separates immutable historical environment
metadata (Python 3.13.13 and NumPy 2.3.3 in the frozen release manifest) from
configuration equivalence checks for the deterministic demonstration. It does
not compare the running environment against the frozen versions, rewrite
historical manifests, weaken integrity assertions, or recompute mathematical
results. The current environment reported Python 3.13.13 and NumPy 2.3.3;
this does not constitute a cross-environment reproduction claim.

## Verification

- Full suite: `python -m pytest -q --tb=short --maxfail=1 --basetemp tmp/pytest-m11e-final-rerun -p no:cacheprovider` — **958 passed**.
- Ruff: `ruff check src tests scripts` — PASS; `ruff format --check src tests scripts` — PASS, 166 files formatted.
- Repository Ruff scan excluding generated review bundle and temporary artifacts: `ruff check . --exclude 'chatgpt_review_bundle/**,tmp/**,.pytest*'` and matching `ruff format --check` — PASS, 264 files formatted. Bare `ruff check .` encountered access-denied warnings while traversing old pytest basetemp directories and an unrelated F401 in the pre-existing generated `chatgpt_review_bundle/build_bundle.py`; bare root format traversal also errored on that generated bundle. The source/test/script scope and remaining repository source passed the stated checks.
- Node syntax: `node --check src/hf_tcm/studio/static/studio.js`, `node --check src/hf_tcm/studio/static/studio_ux.js`, and `node --check scripts/qa_m11e_browser.js` — PASS.
- Real Microsoft Edge QA: **293/293 checks**, 36 screenshots, at 1366×768 and 1920×1080; Edge 156.0.4314.58. Includes actual deterministic F=32 POST at both viewports, gain binding, whole-number counts, missing/non-finite fallback, no `undefined`/`NaN` in primary summaries, Ukrainian Simple mode, all four states and 16 transitions, Inspector/help, 18-step protection flow, and downloads. Zero console, network, and external-request errors. Machine-readable details: `tmp/m11e-browser-qa.json`.
- Historical M5–M10 read-only fingerprint comparison: **694/694 matched**, no missing files or mismatches. The M11c frozen release manifest and M11d source audit were unchanged.

The F=32 browser request is deterministic demonstration QA only, not an
experiment or performance evidence. No receiver, decoder, estimator, or Monte
Carlo job was separately launched for this patch.

## Baseline and unresolved questions

`paper_exact:false`; `receiver_enabled:false`; SCI-02, SCI-03, and
SCI-METRIC-02 remain OPEN. Historical M5–M10 artifacts and manifests remain
unchanged. Results remain limited to their documented reconstructed profiles;
this closeout makes no wider HF, paper-fidelity, superiority, or reproduction
claim. M12 was not started.
