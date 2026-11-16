# REPRO-08 article crosswalk — source inventory refreshed for REPRO-09

## Verified source files

| Exact repository path | Edition / role | SHA-256 | Verification |
|---|---|---|---|
| `references/Яковів_Гриненко_2026_в7 27-10-26(4).docx` | Article v7, primary edition per `references/README.md` | `4e41d33a898d2bfec2118a0cd11d3879ac01d4095264b14f7123bc9840d5f1e3` | Hash matches `references/SHA256SUMS.txt`; DOCX package XML and text inspected. |
| `references/alternate_versions/Яковів_Гриненко_2026_в7 27-10-26(6).docx` | Alternate v7 revision; not silently substituted | `190163b9f123e99648ce9dc2d57cb4fdcc24a8a675001009da41cb0ecf6f9a87` | Hash matches manifest; package present. |
| `references/Раздел_4.doc` | Supporting chapter on statistical simulation of discrete-signal reception | `e877a9272da0e8baa0e4eb21256acf1e2112428d3dbf14472d9b12d3239cfd59` | Hash matches manifest; legacy binary DOC could not be rendered in this environment. |
| `references/supervisor/4.pdf` | Supervisor-provided scan/PDF, separately retained | `97b8868bbb3cd48a7113fa89615bac5286f185957f9441d7159b9f7d548a5904` | Hash verified; not treated as byte-equivalent to `Раздел_4.doc`. |
| `references/source_paper_2026.docx` | Earlier article copy | `a03ff0b41a79d1fe9b4051c2e94c4ea78f72ac5f7fc30269e590150b2ed653c8` | Historical cross-reference only, not the v7 replacement. |
| `references/supervisor/Яковів_Гриненко_2026_в3_24_10_2026.docx` | Earlier v3 edition | `2f070e438f1d8fa4a6cd84e3e6cab24c560ba55670c93ec759a6f4fe82e76b58` | Retained as an older related source; not substituted for v7. |

The alternate v7 and chapter source are separate materials. Chapter-4 coding, sampling, or experiment values are not transferred into the article model without an explicit, separate resolution.

## Article and implementation crosswalk

| Topic | Article v7 (4) | Chapter 4 | Implemented REPRO profile |
|---|---|---|---|
| Coding | Rate 2/3 convolutional TCM, four-state construction in article figures | Discusses additional receiver/code experiments, including other trellis sizes | GUI uses REPRO-02 Encoder A. The 16-state Encoder B preview is not substituted. |
| Modulation | 8PSK; printed phase increment `Δφ=π/4` | Related discrete-signal experiment context | REPRO-02 mapping ID is ADR-002 reconstructed; increment and absolute phase offset remain separate. |
| Joint receiver | Adaptive quadrature/channel estimates, candidate metrics, Viterbi, equations (1)–(10) | Supporting reception/statistical-simulation discussion | REPRO-06C survivor-specific adaptive multipath profile. This is project-defined and not claimed as a literal reproduction of every source operation. |
| Metric (2) | Printed expression does not resolve all norm/square and summation details unambiguously from available extraction | No automatic resolution of article notation | GUI records `squared_euclidean` as the selected project metric profile; source exactness stays open. |
| Channel | Multipath and Rician narrative/formulas; not every numerical/random-process convention is uniquely specified | May provide related channel/experiment details | REPRO-03 discrete complex-baseband paths, sample-domain noise and Rician AR(1), explicitly project-defined. Not a validated RF or complete physical HF model. |
| Sampling | Eight samples per signal element are stated | Separate chapter conventions remain separate | Article-oriented GUI uses 8 samples/symbol under REPRO-02/03. |
| Traceback | `η=20` is stated | Not interchangeable with a visual window length | REPRO-06 finite decoder uses 20 trellis transitions; the GUI reports its actual mode/depth. |
| Experiment length | `N*=20000` appears in the article | Chapter quantities may describe another experiment | GUI labels its configured F as TCM symbols/transitions. The source does not establish an equivalent payload-bit denominator. |
| `p*=5·10⁻²` | Source notation is not proven to mean decoded information-bit BER | Chapter terminology remains distinct | It is not silently used as GUI BER target. |
| Energy gain | Article reports 1.5 dB | No automatic transfer of chapter gain | GUI only displays completed computed experiment results; a single run cannot estimate gain. REPRO-08 remains `ENERGY_GAIN_NOT_ESTIMABLE`. |

## Source-supported, project-defined, unresolved

**Source-supported:** article v7 (4) is the primary edition according to the reference inventory; it describes rate-2/3 TCM, 8PSK, the article's four-state code construction, eight samples per signal element, η=20 and reports a 1.5 dB result.

**Project-defined:** ADR-002 edge-to-phase table; REPRO-03 sample-domain complex-baseband Rician AR(1) channel and noise; the finite-depth indexing convention; deterministic seed plumbing; GUI defaults; and the selected squared-Euclidean profile.

**Still unresolved:** literal interpretation of metric (2); author-exact phase assignment; complete initial/termination rules; physical sample period, pulse/matched filter, noise spectral density and Eb/N0 normalization; the exact relation of N* and p* to the decoded payload denominator; and whether chapter numerical channel parameters belong to the article's four-state experiment. The chapter DOC hash is recorded, but this environment did not render the binary DOC for visual equation comparison.

The GUI preflight is an inventory and crosswalk update, not a claim that these ambiguities were scientifically closed. `paper_exact:false` remains.

## GUI_UX_01: direct v7 equation/figure visual verification (2026-11-10)

The exact primary v7 (4), alternate v7 (6), and binary chapter DOC are present
at the actual paths in the inventory above; their SHA-256 values were recomputed
and match the recorded values. The path strings inside `references/SHA256SUMS.txt`
still describe the earlier unpacking layout. Hash agreement applies to the bytes,
not to those obsolete path strings. Earlier reports saying v7 is absent are
historical statements, not the current source inventory.

The primary DOCX's original embedded WMF/EMF equations and figures were rendered
with Windows System.Drawing and visually inspected. Specifically:

- Equation (1), `word/media/image23.wmf` plus `image24.wmf`, has a posterior-weighted
  quadrature innovation and anchored offset. The active multipath PSP receiver's
  sample-causal complex Kalman/RLS is a project algorithm, not a literal realization
  of this source recursion.
- Equation (2), `image38.wmf`, visibly contains a signed sum of quadrature residuals;
  no square, absolute-value sign or norm is visible. The discrepancy with the
  nonnegative `squared_euclidean` default is now directly confirmed against v7,
  not merely an extraction limitation. Whether the source omitted a mathematical
  operation typographically still requires author clarification.
- Figure 2, `image66.emf`, confirms c2=x0, c1=x1 XOR D^2 x1, c0=D x1.
  Two binary memory cells imply four states; four information pairs per state
  imply sixteen edges. Phase labeling/serialization must still be treated separately.
- Figure 3, `image67.emf`, displays the four-state source trellis. It is not the
  project ISI-expanded 17-state trellis.
- Equations (3)–(6), (9), and (10) were visually inspected. Source `n` in (10)
  is samples per signal element, while the GUI's absolute sample index is a
  project coordinate. A tooltip must distinguish them.

The selected equation (1)/(2) images and figures 2/3 are byte-identical in both
v7 DOCX versions. This does not assert that the entire documents are identical.
The chapter's binary DOC remains unrendered; the already available rendering of
companion `supervisor/4.pdf` page 19 (printed page 127) was inspected. Its Figure
4.6 uses another encoder and is not substituted for article Figure 2.

Evidence, status-by-element table, notation table, and the 130 passing targeted
independent-reference tests are documented in
`GUI_UX_01_ARTICLE_COMPLIANCE_AUDIT.md`. Compact source renders and test logs are
in `outputs/gui_ux_01/source_audit/`. Mathematical algorithms were not changed.
Overall source compliance is PARTIAL; `ENERGY_GAIN_NOT_ESTIMABLE` remains.
