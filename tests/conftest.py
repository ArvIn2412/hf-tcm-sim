"""Separate artifact-backed historical assertions from portable tests."""

import pytest

# These exact tests failed in GitHub Actions run 43856845811 because their
# immutable source data is not part of the Git checkout. Keep them executable
# in the historical job; never skip or xfail them.
_HISTORICAL_TEST_NAMES = {
    "test_saved_repro02_reference_frame_loads_with_verified_arrays",
    "test_channel_serialization_separates_receiver_and_truth",
    "test_reference_frame_channel_output_length_and_identity",
    "test_channel_plot_adapter_writes_sixteen_actual_svg_files",
    "test_channel_cli_executes_channel_only_and_writes_complete_manifest",
    "test_historical_energy_study_revalidates_provenance_and_recomputes_gain",
    "test_historical_energy_study_is_available_through_read_only_gui_route",
    "test_frozen_independent_protocol_builds_supported_receiver_specs_and_fresh_seeds",
    "test_exact_prior_redecode_reuses_identical_public_observation",
    "test_exp01b_static_series_opens_through_saved_study_route",
    "test_verified_long_frame_archives_keep_observation_sources_separate",
    "test_parameter_registry_and_coverage_are_explicit",
    "test_runtime_parameter_inspector_indexes_actual_symbol_and_study_values",
    "test_historical_dashboard_values_are_read_from_archived_summaries",
    "test_archived_m5j_and_train_rankings_preserve_evidence_categories",
    "test_m9_archived_ber_and_paired_ci_are_exact_without_rounding",
    "test_m10_archived_profile_results_and_primary_ci_are_exact",
    "test_archive_views_are_serializable_and_provenance_matches_source_bytes",
    "test_archive_view_does_not_import_receiver_or_rng_or_write_sources",
    "test_saved_planned_manifest_passes_exact_design_and_code_validation",
    "test_pilot_source_artifact_hashes_match_without_modifying_pilot_outputs",
    "test_pilot_recorded_variability_exactly_matches_saved_summary",
    "test_approved_run_snapshot_pins_design_manifest_code_and_scope",
    "test_approval_path_is_immutable_and_refuses_overwrite",
    "test_authorization_guard_must_block_before_any_execution_callback",
    "test_pilot_scope_cannot_authorize_confirmatory_execution",
    "test_approved_config_rejects_modified_code_or_manifest_snapshot",
    "test_saved_checkpoint_counts_replay_without_receiver_or_new_observations",
    "test_saved_count_bootstrap_reproduces_all_six_intervals",
    "test_saved_run_ids_seed_provenance_and_receiver_input_boundary",
    "test_m5f_m5h_and_m5j_historical_outputs_keep_baseline_bytes",
    "test_m5j_stored_summary_matches_checkpoint_inventory_and_counts",
    "test_historical_configs_and_m6b_trace_hashes_remain_unchanged",
    "test_validation_does_not_mutate_config_or_trace_files",
    "test_m6g_and_m6h_historical_traces_keep_recorded_hashes",
    "test_approved_config_freezes_exact_draft_and_train_only_seed_manifest",
    "test_m7b_closeout_replays_saved_integer_counts_without_receiver_calls",
    "test_recovery_snapshot_reuses_exact_original_design_seeds_and_hashes",
    "test_real_m8b_conditional_decode_smoke_for_all_eight_policies",
    "test_approved_config_inherits_exact_m8a_design_and_train_seeds",
    "test_saved_m8b_attempt_stays_incomplete_without_error_imputation",
    "test_m9a_draft_is_frozen_and_seed_manifest_matches_exact_design",
    "test_approved_snapshot_has_m9b_only_scope_and_no_circular_hash",
    "test_approved_guard_rejects_fingerprint_and_policy_drift_before_executor",
    "test_fixture_and_immutable_m6g_source_are_verified",
    "test_same_state_weight_swap_identities_and_first_symbol_agreement",
    "test_b_and_a_are_invariant_across_closed_clamp_and_common_regimes",
    "test_multistep_clamp_uses_b_weights_but_retains_own_posterior_history",
    "test_clamp_posteriors_match_independent_first_edge_and_continuation_oracle",
    "test_trace_schema_shapes_clocks_and_no_reference_or_truth_leakage",
    "test_nonfinite_or_wrong_fixture_and_mutated_m6g_artifact_are_rejected",
    "test_k_c_trajectory_differences_start_after_first_shared_update",
    "test_m6h_trace_serialization_round_trip_and_m6g_hash_preservation",
}


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    marker = pytest.mark.historical
    for item in items:
        if item.name in _HISTORICAL_TEST_NAMES:
            item.add_marker(marker)
