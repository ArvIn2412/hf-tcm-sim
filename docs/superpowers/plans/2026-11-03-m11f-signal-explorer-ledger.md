# M11f execution ledger

- Baseline: M11e remains the verified release; user-provided counts are 958
  pytest, 293/293 Edge QA, 694/694 historical fingerprints.
- Source inspection: M11f is absent. Chapter 4 PDF pp.126–129 visually and
  textually show Code 2's four-register layout, generator matrix, full 64-row
  transition/output/B table, and zero state. The existing v7 audit and code
  show a separate four-state/16-edge model and an incompatible conditional
  Viterbi contract.
- TDD RED: `node --test tests/test_m11f_signal_window.js` failed because
  `signal_window.js` did not exist.
- TDD GREEN: added the pure sample-window/index helper; the same test now
  passes 5/5, including first/middle/last F=32 windows and short-frame clamp.
- Ruling: render only existing M11a trace arrays and label posterior as
  candidate-edge weights — no new channel-state HMM is present, and this
  avoids implying unimplemented channel inference.
- Ruling: source Chapter 4 Code 2 is suitable for an encoder/trellis source
  audit, but M11f will not add its receiver; the current receiver's accepted
  trellis is explicitly the distinct four-state M1 model.
