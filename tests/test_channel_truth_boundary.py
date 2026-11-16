"""Architecture boundary tests for estimated receiver code."""

from pathlib import Path

from channel_truth_guard import audit_source, is_protected_module, protected_sources

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_current_estimator_and_decoder_boundary_is_explicit() -> None:
    protected = {path.relative_to(PROJECT_ROOT).as_posix() for path in protected_sources()}
    assert {
        "src/hf_tcm/coding/hypotheses.py",
        "src/hf_tcm/coding/posterior.py",
        "src/hf_tcm/coding/likelihood.py",
    } <= protected
    assert "src/hf_tcm/receiver/paper_recursion.py" in protected
    assert "src/hf_tcm/receiver/iq_prediction.py" in protected
    assert "src/hf_tcm/decoding/paper_metric.py" in protected
    assert "src/hf_tcm/decoding/viterbi.py" in protected

    violations = tuple(
        (path, violation)
        for path in protected_sources()
        for violation in audit_source(path, path.read_text(encoding="utf-8"))
    )
    assert not violations, "forbidden ChannelTruth access in estimated receiver boundary"


def test_estimated_receiver_and_future_decoder_modules_are_protected() -> None:
    assert is_protected_module(PROJECT_ROOT / "src/hf_tcm/receiver/adaptive.py")
    assert is_protected_module(PROJECT_ROOT / "src/hf_tcm/decoding/adaptive_decoder.py")
    assert is_protected_module(PROJECT_ROOT / "src/hf_tcm/coding/posterior.py")


def test_artificial_truth_and_generator_state_leaks_are_detected() -> None:
    source = """\
from hf_tcm.channels.multipath import ChannelTruth
import hf_tcm.channels.multipath as multipath
from hf_tcm.channels.multipath import apply_multipath

def leak(output, rng):
    truth = ChannelTruth
    alias_truth = multipath.ChannelTruth
    coefficients = output.truth.coefficients
    state = rng.bit_generator.state
    result = apply_multipath
    return alias_truth, coefficients, state, result
"""
    violations = audit_source(
        PROJECT_ROOT / "src/hf_tcm/receiver/_synthetic_violation.py",
        source,
    )

    assert {violation.rule for violation in violations} >= {
        "channel-truth-import",
        "channel-truth-name",
        "channel-generator-import",
        "truth-attribute",
        "generator-state-access",
    }


def test_channel_simulator_and_oracle_test_usage_is_allowed() -> None:
    channel_source = (PROJECT_ROOT / "src/hf_tcm/channels/multipath.py").read_text(encoding="utf-8")
    oracle_source = (PROJECT_ROOT / "tests/test_multipath.py").read_text(encoding="utf-8")

    assert audit_source(PROJECT_ROOT / "src/hf_tcm/channels/multipath.py", channel_source) == ()
    assert audit_source(PROJECT_ROOT / "tests/test_multipath.py", oracle_source) == ()


def test_unprotected_modules_are_not_scanned_for_synthetic_leaks() -> None:
    source = "from hf_tcm.channels.multipath import ChannelTruth\nvalue = result.truth\n"

    assert audit_source(PROJECT_ROOT / "src/hf_tcm/simulation/oracle.py", source) == ()
