"""Synthetic state-machine and payload checks. No phone or real transport exists."""
from copy import deepcopy
from dataclasses import replace
import plistlib

import pytest

from ipsm.draft_rules import plan_swap
from research.duo_simulator import (
    FakeTransport, InventoryQuery, InventoryReceipt, Observation, Scenario, Status,
    builtin_scenarios, scenario_suite, simulate, synthetic_scenario,
)


def cases():
    return {case.name: case for case in builtin_scenarios()}


@pytest.mark.parametrize("case", builtin_scenarios(), ids=lambda s: s.name)
def test_every_simulation_has_one_send_at_most_and_never_authorizes_a_phone(case, monkeypatch):
    import socket
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: pytest.fail("Simulator attempted a socket"))
    result = simulate(case)
    assert result.send_attempts <= 1
    assert result.rollback_attempts == 0
    assert result.read_attempts <= case.max_readback_attempts
    assert result.fresh_connection_ids == tuple(range(1, result.read_attempts + 1))
    assert result.can_write is False
    assert result.fully_verified is False
    assert set(result.unverified_factors) == {
        "hidden_page_visibility", "native_gaps", "widget_runtime_configuration", "duo_pose_behavior"}
    assert result.to_dict()["can_write"] is False
    if result.status is Status.BLOCKED:
        assert result.send_attempts == result.read_attempts == 0
        assert "SEND_STARTED" not in result.events


@pytest.mark.parametrize("name", [
    "missing_inventory", "failed_empty_inventory", "incomplete_inventory", "placeholders_unknown",
    "hidden_webclips_unknown", "visible_exclusion_conflict", "identity_mismatch", "stale_baseline",
    "backup_failure", "backup_corrupt",
])
def test_preflight_failures_never_reach_fake_send(name):
    result = simulate(cases()[name])
    assert result.status is Status.BLOCKED
    assert result.send_attempts == 0
    assert result.fake_effect_applied is False


def test_send_timeout_after_effect_remains_uncertain_without_reads():
    result = simulate(cases()["send_timeout_after_side_effect"])
    assert result.status is Status.UNCERTAIN
    assert result.fake_effect_applied
    assert result.send_uncertain
    assert result.events.count("SEND_STARTED") == 1
    assert result.read_attempts == 3
    assert result.rollback_attempts == 0


def test_no_reply_plus_exact_readback_is_exported_match_only():
    result = simulate(cases()["no_reply_with_match"])
    assert result.status is Status.EXPORTED_FIELDS_MATCH_ONLY
    assert result.send_uncertain
    assert result.events.index("SEND_UNCERTAIN") < result.events.index("EXPORTED_FIELDS_MATCH_ONLY")
    assert result.differences == ()
    assert not result.fully_verified


def test_successful_reply_does_not_override_a_failed_readback():
    result = simulate(cases()["read_failure"])
    assert "REPLY_RECEIVED" in result.events
    assert result.status is Status.UNCERTAIN
    assert result.send_attempts == 1


def test_delayed_read_only_verification_never_resends():
    result = simulate(cases()["delayed_read_match"])
    assert result.status is Status.EXPORTED_FIELDS_MATCH_ONLY
    assert result.read_attempts == 2
    assert result.fresh_connection_ids == (1, 2)
    assert result.send_attempts == 1


@pytest.mark.parametrize("name,diagnostic", [
    ("widget_selection_lost", "userSelectedElementIdentifier"),
    ("stack_order_changed", "elements"),
    ("bool_became_integer", "type_changed"),
    ("opaque_bytes_changed", "opaque.data"),
    ("date_precision_lost", "iconModDate"),
    ("library_app_added", "length_changed"),
])
def test_readback_has_no_silent_widget_metadata_or_type_normalization(name, diagnostic):
    result = simulate(cases()[name])
    assert result.status is Status.MISMATCH
    assert any(diagnostic in difference for difference in result.differences)
    assert result.send_attempts == 1 and result.rollback_attempts == 0


def test_old_mismatch_followed_by_no_read_is_not_claimed_as_current_known_state():
    result = simulate(cases()["mismatch_then_unavailable"])
    assert result.status is Status.UNCERTAIN
    assert result.differences  # Retain the earlier diagnostic, without calling it final truth.
    assert result.rollback_attempts == 0


def test_inventory_includes_synthetic_user_system_offloaded_and_hidden_clip_exclusions():
    result = simulate(synthetic_scenario())
    # example.library + example.offloaded + example.system.hidden + hidden webclip.
    assert result.ignored_count == 4
    assert result.status is Status.EXPORTED_FIELDS_MATCH_ONLY


def test_display_alias_and_bundle_id_both_count_as_visible():
    scenario = synthetic_scenario()
    origin = deepcopy(scenario.origin)
    origin[1][1]["displayIdentifier"] = "example.display.alias"
    receipt = scenario.inventory
    receipt = replace(receipt, user=replace(receipt.user, identifiers=receipt.user.identifiers + ("example.display.alias",)))
    result = simulate(replace(scenario, origin=origin, current=deepcopy(origin),
                              candidate=plan_swap(origin, 1, 1, 2), inventory=receipt))
    assert result.status is Status.EXPORTED_FIELDS_MATCH_ONLY
    assert result.ignored_count == 4  # Alias must not become an extra excluded app.


def test_observed_empty_user_inventory_is_distinct_from_failed_empty_inventory():
    origin = [[], [{"displayIdentifier": "example.system.a"}, {"displayIdentifier": "example.system.b"}]]
    receipt = InventoryReceipt(InventoryQuery("observed", (), True),
                               InventoryQuery("observed", ("example.system.a", "example.system.b"), True),
                               True, True)
    base = replace(synthetic_scenario(), origin=origin, candidate=plan_swap(origin, 1, 0, 1),
                   current=deepcopy(origin), intent=(1, 0, 1), inventory=receipt)
    observed = simulate(base)
    failed = simulate(replace(base, inventory=replace(receipt, user=InventoryQuery("failed"))))
    assert observed.status is Status.EXPORTED_FIELDS_MATCH_ONLY
    assert observed.ignored_count == 0
    assert failed.status is Status.BLOCKED and failed.send_attempts == 0


@pytest.mark.parametrize("change", [
    {"synthetic": False}, {"placeholders_requested": 1}, {"hidden_webclips_known": False},
    {"hidden_webclip_ids": ("x", "x")},
])
def test_coverage_flags_must_be_explicit_synthetic_boolean_receipts(change):
    scenario = synthetic_scenario()
    result = simulate(replace(scenario, inventory=replace(scenario.inventory, **change)))
    assert result.status is Status.BLOCKED and result.send_attempts == 0


@pytest.mark.parametrize("query", [
    InventoryQuery("missing"), InventoryQuery("failed", (), True),
    InventoryQuery("observed", ("x",), 1),
    InventoryQuery("observed", ("x", "x"), True),
    InventoryQuery("observed", ("x",), True, ("not-listed",)),
])
def test_invalid_or_incomplete_inventory_query_is_refused(query):
    scenario = synthetic_scenario()
    result = simulate(replace(scenario, inventory=replace(scenario.inventory, user=query)))
    assert result.status is Status.BLOCKED and result.send_attempts == 0


def test_visible_offloaded_item_cannot_be_missing_from_complete_fake_inventory():
    scenario = synthetic_scenario()
    origin = deepcopy(scenario.origin)
    origin[1].append({"displayIdentifier": "example.placeholder.visible"})
    candidate = plan_swap(origin, 1, 1, 2)
    result = simulate(replace(scenario, origin=origin, current=deepcopy(origin), candidate=candidate))
    assert result.reason == "visible_app_missing_from_inventory"
    assert result.send_attempts == 0


def test_user_and_system_type_conflict_is_not_silently_deduplicated():
    scenario = synthetic_scenario()
    receipt = scenario.inventory
    receipt = replace(receipt, system=replace(receipt.system, identifiers=receipt.system.identifiers + ("example.user.a",)))
    result = simulate(replace(scenario, inventory=receipt))
    assert result.reason == "inventory_type_conflict"


def test_input_snapshots_and_observation_payloads_are_never_mutated():
    scenario = cases()["widget_selection_lost"]
    before = [plistlib.dumps(value, fmt=plistlib.FMT_BINARY) for value in
              (scenario.origin, scenario.candidate, scenario.current, scenario.readbacks[0].state)]
    simulate(scenario)
    after = [plistlib.dumps(value, fmt=plistlib.FMT_BINARY) for value in
             (scenario.origin, scenario.candidate, scenario.current, scenario.readbacks[0].state)]
    assert after == before


def test_a_live_like_adapter_or_callback_cannot_be_injected():
    class NotADataScenario:
        def __getattribute__(self, name):
            raise AssertionError("Foreign adapter was inspected")
    with pytest.raises(TypeError):
        simulate(NotADataScenario())
    with pytest.raises(TypeError):
        simulate(synthetic_scenario(), transport=object())
    with pytest.raises(TypeError):
        FakeTransport(object())
    with pytest.raises(TypeError):
        class DerivedTransport(FakeTransport):
            pass


def test_custom_observation_hooks_are_never_executed():
    class Hook:
        def __deepcopy__(self, memo):
            raise AssertionError("Custom deepcopy hook executed")
    scenario = replace(synthetic_scenario(), readbacks=(Observation("snapshot", [Hook()]),))
    with pytest.raises(ValueError):
        simulate(scenario)
    with pytest.raises(ValueError):
        FakeTransport(replace(synthetic_scenario(), current=[Hook()]))
    transport = FakeTransport(synthetic_scenario())
    with pytest.raises(ValueError):
        transport.send({"buttonBar": [], "iconLists": [[Hook()]], "ignored": []})
    assert transport.send_attempts == 0


@pytest.mark.parametrize("attempts", [0, -1, True, 6, None])
def test_read_attempts_are_bounded(attempts):
    with pytest.raises(ValueError):
        simulate(replace(synthetic_scenario(), max_readback_attempts=attempts))


def test_fake_transport_itself_refuses_a_second_send():
    scenario = synthetic_scenario()
    transport = FakeTransport(scenario)
    payload = {"buttonBar": scenario.candidate[0], "iconLists": scenario.candidate[1:], "ignored": []}
    transport.send(payload)
    with pytest.raises(RuntimeError):
        transport.send(payload)
    assert transport.send_attempts == 1


def test_suite_report_does_not_dump_app_inventory_or_widget_values():
    for result in scenario_suite():
        text = repr(result.to_dict())
        assert "example.user.a" not in text
        assert "example.member.1" not in text
        assert "buttonBar" not in text
