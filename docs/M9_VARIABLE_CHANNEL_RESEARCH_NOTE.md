# Future variable-channel research note

This is a scientific design note only. M9a is a constant-gain comparison and
does not simulate or imply a variable channel. No ADR is accepted and no
implementation, data generation, or receiver mode is authorized here.

Future questions must distinguish at least four different profiles:

1. **Fixed gain per frame:** the current M9a reference profile, with one real
   gain held constant during a sequence. It is not time variation.
2. **Controlled gain mismatch:** a constant simulation gain paired with an
   intentionally different receiver-side nominal gain/estimate. This tests a
   specified mismatch and requires a separate parameter/estimand decision.
3. **Time-varying real gain:** a real-valued gain changes across symbols or
   intervals under a separately specified deterministic/stochastic law. A
   piecewise switch and gradual drift are distinct models and must not be
   conflated.
4. **Future physical channel models:** multipath, correlated fading, complex
   fading, and other HF propagation models require separate physical
   assumptions and evidence. They are not equivalent to the first three
   cases or to each other.

Each branch needs a new profile, explicit scientific decision/ADR gates, an
independent dataset and seed namespaces, and its own evaluation protocol.
Nothing here authorizes piecewise switching, gradual variation, AR(1),
multipath, complex fading, or claims about physical HF behavior. The fixed
gain M9 design must not be silently replaced by a nonstationary model.

## M10a controlled piecewise real-gain proposal (2026-10-30)

M10a defines one proposed evaluation-side profile,
`controlled_piecewise_real_gain_v1`, with a constant control and two opposite
128-symbol real-gain schedules. It is a new experimental model, separate
from M9's constant-gain contract. The design holds AWGN variance fixed,
pairs the same waveform and noise across profiles, and does not provide the
gain schedule or channel truth to the receiver. P1/P2 share a gain histogram
in a different order; comparison with P0 also changes the gain distribution.

ADR-016 now accepts this exact model for evaluation-side generation and
analysis only. The separate approved M10b run completed and is reported in
`M10_VARIABLE_GAIN_EVALUATION_REPORT.md`. That study does not change M9's
constant-gain contract, integrate a production channel, or establish physical
HF performance. See `M10_VARIABLE_GAIN_MODEL_DESIGN.md` and
`M10_VARIABLE_GAIN_STATISTICAL_PROTOCOL.md`.
