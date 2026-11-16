"""Isolated, provenance-aware transmitter research package."""

from typing import Any

__all__ = [
    "ChannelConfig",
    "ChannelResult",
    "TransmitterConfig",
    "TransmitterResult",
    "run_channel",
    "run_transmitter",
    "ReceiverFrontEndConfig",
    "SeparateReceiverConfig",
    "SeparateReceiverResult",
    "run_separate_receiver",
    "ViterbiConfig",
    "FiniteDepthViterbiDecoder",
    "run_viterbi",
]


def __getattr__(name: str) -> Any:
    if name == "TransmitterConfig":
        from hf_tcm.repro.config import TransmitterConfig

        return TransmitterConfig
    if name == "ChannelConfig":
        from hf_tcm.repro.channel_config import ChannelConfig

        return ChannelConfig
    if name == "ChannelResult":
        from hf_tcm.repro.channel_result import ChannelResult

        return ChannelResult
    if name == "run_channel":
        from hf_tcm.repro.channel_runner import run_channel

        return run_channel
    if name in {"TransmitterResult", "run_transmitter"}:
        from hf_tcm.repro.transmitter import TransmitterResult, run_transmitter

        return {
            "TransmitterResult": TransmitterResult,
            "run_transmitter": run_transmitter,
        }[name]
    if name == "ReceiverFrontEndConfig":
        from hf_tcm.repro.receiver_config import ReceiverFrontEndConfig

        return ReceiverFrontEndConfig
    if name == "SeparateReceiverConfig":
        from hf_tcm.repro.receiver_config import SeparateReceiverConfig

        return SeparateReceiverConfig
    if name in {"SeparateReceiverResult", "run_separate_receiver"}:
        from hf_tcm.repro.separate_receiver import SeparateReceiverResult, run_separate_receiver

        return {
            "SeparateReceiverResult": SeparateReceiverResult,
            "run_separate_receiver": run_separate_receiver,
        }[name]
    if name in {"ViterbiConfig", "FiniteDepthViterbiDecoder", "run_viterbi"}:
        from hf_tcm.repro.finite_viterbi import (
            FiniteDepthViterbiDecoder,
            ViterbiConfig,
            run_viterbi,
        )

        return {
            "ViterbiConfig": ViterbiConfig,
            "FiniteDepthViterbiDecoder": FiniteDepthViterbiDecoder,
            "run_viterbi": run_viterbi,
        }[name]
    raise AttributeError(name)
