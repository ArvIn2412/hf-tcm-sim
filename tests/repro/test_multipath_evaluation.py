from __future__ import annotations

from hf_tcm.repro.channel_config import ChannelConfig, ChannelPathConfig
from hf_tcm.repro.channel_runner import run_channel
from hf_tcm.repro.config import TransmitterConfig
from hf_tcm.repro.multipath_evaluation import evaluate_multipath_receiver
from hf_tcm.repro.multipath_joint_receiver import run_multipath_joint_receiver
from hf_tcm.repro.multipath_receiver_config import (
    MultipathPathConfig,
    MultipathReceiverConfig,
)
from hf_tcm.repro.transmitter import run_transmitter


def test_evaluation_adapter_compares_only_after_decode_and_excludes_explicit_tail() -> None:
    transmitter = run_transmitter(
        TransmitterConfig(
            source_mode="manual",
            frame_symbols=5,
            manual_bits="0011011001",
            termination_policy="zero_tail_2",
        )
    )
    channel = run_channel(
        transmitter,
        ChannelConfig(
            profile_id="evaluation_test_static",
            paths=(
                ChannelPathConfig(0, 1, 0, constant_coefficient=1 + 0j),
                ChannelPathConfig(3, 0.09, 0, constant_coefficient=0.3 + 0j),
            ),
            fading_mode="constant",
            noise_model="none",
            noise_complex_variance=0,
            fading_seed=1,
            noise_seed=2,
        ),
    )
    result = run_multipath_joint_receiver(
        channel.receiver_observation,
        MultipathReceiverConfig(
            expected_symbol_count=7,
            paths=(MultipathPathConfig(0, 1 + 0j), MultipathPathConfig(3, 0.3 + 0j)),
            termination_policy="zero_tail_2",
            final_state_policy="known_terminated",
        ),
    )

    evaluation = evaluate_multipath_receiver(
        result, transmitter.information_bits, transmitter.phase_indices[:5]
    )

    assert evaluation.bit_errors == 0
    assert evaluation.symbol_errors == 0
    assert evaluation.compared_information_bit_count == 10
    assert evaluation.compared_symbol_count == 5


def test_evaluation_reports_real_error_positions_and_validates_payload_lengths() -> None:
    transmitter = run_transmitter(
        TransmitterConfig(source_mode="manual", frame_symbols=4, manual_bits="00110110")
    )
    channel = run_channel(
        transmitter,
        ChannelConfig(
            profile_id="evaluation_test_identity",
            paths=(ChannelPathConfig(0, 1, 0, constant_coefficient=1 + 0j),),
            fading_mode="constant",
            noise_model="none",
            noise_complex_variance=0,
            fading_seed=1,
            noise_seed=2,
        ),
    )
    result = run_multipath_joint_receiver(
        channel.receiver_observation,
        MultipathReceiverConfig(expected_symbol_count=4, paths=(MultipathPathConfig(0, 1 + 0j),)),
    )
    wrong = transmitter.information_bits.copy()
    wrong[1] ^= 1
    evaluation = evaluate_multipath_receiver(result, wrong, transmitter.phase_indices)

    assert evaluation.bit_errors == 1
    assert evaluation.bit_error_positions.tolist() == [1]
