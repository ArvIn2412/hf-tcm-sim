# HF-TCM-SIM Demo Release Manifest

**Release label:** `M11c-demo-freeze-1`  
**Freeze date:** 2026-11-02  
**Scope:** Offline defense demonstration package only. This manifest is a content fingerprint, not a signed release or a Git revision.

## Runtime and environment

| Item | Frozen value |
|---|---|
| Entrypoint | `python -m hf_tcm.demo_studio` |
| Windows helper | `start_demo.cmd` → `start_demo.ps1` → existing module; default port 8765; loopback only |
| Python | 3.13.13 (`C:\Users\grine\AppData\Local\Programs\Python\Python313\python.exe`) |
| Project distribution | `hf-tcm-sim` 0.1.0 |
| Runtime dependency | NumPy 2.3.3; HTTP server and GUI use Python standard library and static HTML/CSS/JS |
| QA tools | pytest 9.0.2; Ruff 0.17.2; Node v22.20.0 |
| Browser used for M11b/M11c automation | Microsoft Edge 156.0.4314.58, Chromium DevTools Protocol |
| OS | Windows 11, build 10.0.26300 |
| Git revision | Not available: this workspace has no `.git` metadata; no commit ID is asserted. |

The launcher checks for `python` and NumPy, never invokes pip, prints the local URL, reports a busy port, and leaves the existing Python process output visible. The `.cmd` wrapper uses `-ExecutionPolicy Bypass` only for its child PowerShell process; it does not change the machine policy.

## Scientific status and demo configuration

| Field | Frozen value |
|---|---|
| `paper_exact` | `false` |
| `receiver_enabled` | `false` |
| Model status | Reconstructed offline model; no SDR/radio or physical HF claim |
| Demo length | F=32 symbols; 64 information bits |
| Samples | 8 samples/symbol; 256 received complex samples |
| Input bits | `0001101100011011000110110001101100011011000110110001101100011011` |
| Noise | `low_amplitude_a`, explicit deterministic formula; no RNG |
| Channel gain | 0.75, fixed demo configuration |
| Receiver A | `historical_frozen_B`: alpha′=1.0; K̃=[0,0]; mu0=[0,0]; initial fluctuating/full state=[0.42,0.91]; beta=0.7 |
| Receiver B | `anch_a085_k025`: alpha′=0.85; K̃=[0.0875,-0.05]; mu0=[0.42,0.91]; initial fluctuating state=[0,0], full state=[0.42,0.91]; beta=0.7 |
| Received buffer | Shared by both receivers; explicit F=32 POST required to calculate receiver traces and conditional Viterbi |
| Parameter inventory | Frozen M11b inventory has 459 entries. The pre-run metadata exposes its 201 configuration entries; after explicit demo POST the runtime registry contains 459 entries, including actual trace fields. Selected-symbol Inspector values are read from that POST trace. |
| ADR boundary | ADR-002 reconstructed; ADR-005 pseudo-likelihood assumption; ADR-016 evaluation-only |
| Open science questions | SCI-02, SCI-03, SCI-METRIC-02 |

## Deterministic fixture fingerprints

Hash algorithms are SHA-256. Bit hash uses the 64 ASCII characters without separators. Noise hash uses UTF-8 JSON of the actual F=32 `transmitter.noise_samples`, with sorted keys and compact separators. The received hash is the trace's canonical complex-buffer SHA-256. Fixture-definition hash is UTF-8 JSON with sorted keys and compact separators over bits, noise fixture/formula, channel gain, sample count, receiver mode, alpha, K, beta, and both actual policy parameter objects.

| Fixture field | SHA-256 / value |
|---|---|
| Information bits | `d9be684a46e3c8c31f4a92873a9bab930efd4c9b4551eb133ac0081691b3a68f` |
| Actual deterministic noise samples | `f403cd4b8db2a1ef3edd9676034498a8ab6cdec0fbc43dd8b6719f413206db97` |
| Canonical fixture definition | `5731328eda46cb9005e8f447feb1ec1e50adf74fd67016e4008f9cd60a51ed91` |
| Shared received buffer | `40f60fbb4214ec05156930695164f74d7db73b04a554d182b120906eac648a4d` |
| Post-demo runtime parameter registry, 459 entries | `9f9ab7ad43d37c56f79eba3cd503186be498470613ccaf448b540243e648cb34` |

## Application and GUI source hashes

The following SHA-256 values are over exact file bytes at freeze time.

| File | SHA-256 |
|---|---|
| `pyproject.toml` | `f5c1f67ce51c19896cc95d9511bb76b608cb9af51547ca5ea6818d94bfc533d5` |
| `start_demo.ps1` | `ed8e9f69dfaed5a75f9aeb639834edbecea89dbc85166ad1314906f987567039` |
| `start_demo.cmd` | `84e7c4933e39e917680432c5316ee1a9039bb877406be2150036bf54516eb6c5` |
| `src/hf_tcm/demo_studio.py` | `2f652479da237220358a1e0343cc4cbe591d0d88ea4ededfb4bb47b30acff815` |
| `src/hf_tcm/studio/server.py` | `d4c5def390981c89a63d99989c247ca4c5235a47fc77221a436b483f5656b8dc` |
| `src/hf_tcm/evaluation/m11a_demo_studio.py` | `188fa81fe1519e712f3a3158d41a10bb807963f2fec7f6e00aa361ad84e37161` |
| `src/hf_tcm/studio/static/index.html` | `6667d1e3fbcde1ae17be54ac52d39502bbfb30452b20fd028e52559426296b0a` |
| `src/hf_tcm/studio/static/studio.css` | `155324d5a30f58deff099c9e177a062968ae20d28f3f04890d758286b694b0fe` |
| `src/hf_tcm/studio/static/studio.js` | `a9163f637eb301828ae61df22b5769412f0d9ee865b636b184d66bdf271fa9c8` |
| `src/hf_tcm/coding/encoder.py` | `6883e760a43903c1cbad6615cb7a70cb1193696d8243450da335111cd7c08405` |
| `src/hf_tcm/coding/hypotheses.py` | `268219516615659479ef013a00177e82ecbc4f88ef24990f2391d6a3833ca2f2` |
| `src/hf_tcm/coding/trellis.py` | `c858b98dfa22a0a1b10246a472b389e1ab69b7395c64dd5731c669770e9f304f` |
| `src/hf_tcm/modulation/psk8.py` | `7d2c83892ddb10a955e21c39cf0085e120f107dd0879407aea18c8b4ff52739a` |
| `src/hf_tcm/receiver/reconstruction_posterior_estimator_sequence.py` | `ff0c1dbfffccdd2957af5a25ccd903c0df378defd638a2bfd7f7fd1923bd566e` |
| `src/hf_tcm/receiver/reconstruction_candidate_metrics.py` | `22573b4a90ab8e6873b60b58965529665dedf911dfd0f6d520b3ca6bcb8fff5d` |
| `src/hf_tcm/receiver/reconstruction_posterior.py` | `e9aac0eb6d77aa71c4cd3961afcf6bc476466d26c3c18bdecc85e6e8aa236337` |
| `src/hf_tcm/receiver/reconstruction_conditional_decode.py` | `b3af5a48f0759740b816326d36eb0c0d03b4a2d90f6a5dd3f08862512961f9eb` |

## Read-only historical dataset fingerprints

These hashes identify source summaries surfaced in the existing dashboard; they were read and verified against their current file bytes. Historical artifacts and integrity manifests were not modified.

| Dataset | Source summary | SHA-256 |
|---|---|---|
| M5j | `outputs/m5j_confirmatory/20261029T-run/summary.json` | `a2fc4e86d1c5dbddbc7254fba16a4a20a32bbd87db3576eaecc83cc8ca0cc2c6` |
| M7b | `outputs/m7b_train/m7_reconstructed_estimator_policy_study_v1/summary.json` | `b10875af7be6d69135d0fef436d3e6e7a92b7c06846fb98ed4f74cf2bead6045` |
| M8b recovery | `outputs/m8b_train_recovery/m8_anchored_reconstructed_adaptation_v1_attempt2/summary.json` | `29b6f70cf4da718de46c5d53f4954264460200abdfe93625f0275c892a5c8582` |
| M9b | `outputs/m9b_fixed_policy_evaluation/m9_fixed_anchored_vs_frozen_v1/summary.json` | `028b93ff494ac71d6fc121c427892a250c2dd97070aa030c7cf96cb7fb733b63` |
| M10b | `outputs/m10b_variable_gain/m10_controlled_piecewise_gain_v1/summary.json` | `ad341e08af257b7d30d3414147d9d44d8326ddc1955556889d46e831141a68aa` |

M7b is TRAIN-only and is not independent validation. M5j per-symbol estimator history is unavailable. M9/M10 values and intervals are archived evidence; both specified DeltaBER confidence intervals include zero.

## Frozen M11b QA baseline

| Baseline item | Evidence |
|---|---|
| M11b QA report SHA-256 | `8198b5a48351f6825d89a6baa29a69a20be6d63ef3033e5efea3d6b1e9c316ab` |
| Parameter coverage report SHA-256 | `4bd521b9828a00cdf96434b7b2b93d80ee905821f11169bc650e91ff23ee82de` |
| M11b verification | 942 pytest passed; Ruff and Node syntax checks passed |
| Browser viewports | Real Edge automation, 1366×768 and 1920×1080 |
| M11b screenshot hashes | 1366: `182f9d55bc9bfac1dcba97f95b1c1f01da9826431da1012fc55c99914e042108`; 1920: `9be7527c88d94f4c478dcda1b70d844dda512462aedabfdf5814adb248fb981a` |
| M11c UI-only additions | Searchable selected-symbol trace overlay in Inspector and defense-step wording/order; no receiver or historical code changes |
| M11c live browser screenshot SHA-256 | `1905c0b15332adc161aa8cb222d87143486a0074be885bd884576fb30ad2f6ff` (`docs/screenshots/m11c-rehearsal-m9m10-1366x768.png`) |

M11c verification and rehearsal details are recorded in `M11C_DEFENSE_READINESS_REPORT.md`. A live browser automation pass is not a human rehearsal.
