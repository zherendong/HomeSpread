"""Closed, in-memory experiments for a future layout-write state machine.

No phone, socket, SDK, file, arbitrary adapter, or callback is accepted. Sending
means replacing a Python value inside FakeTransport. A matching fake readback
still proves only exported fields, never full device compatibility or permission.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum
import json
import plistlib
from typing import Any

from ipsm.draft_rules import DraftError, analyze_layout, plan_swap, validate_swap
from research.duo_envelope import simulate_dictionary_payload


class Status(str, Enum):
    BLOCKED = "BLOCKED"
    UNCERTAIN = "UNCERTAIN"
    MISMATCH = "MISMATCH"
    EXPORTED_FIELDS_MATCH_ONLY = "EXPORTED_FIELDS_MATCH_ONLY"


@dataclass(frozen=True)
class InventoryQuery:
    status: str
    identifiers: tuple[str, ...] = ()
    complete: bool = False
    placeholder_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class InventoryReceipt:
    user: InventoryQuery
    system: InventoryQuery
    placeholders_requested: bool = False
    hidden_webclips_known: bool = False
    hidden_webclip_ids: tuple[str, ...] = ()
    synthetic: bool = True


@dataclass(frozen=True)
class Observation:
    kind: str = "current"
    state: Any = None


@dataclass(frozen=True)
class Scenario:
    name: str
    origin: Any
    candidate: Any
    current: Any
    intent: tuple[int, int, int]
    expected_identity: str
    current_identity: str
    inventory: InventoryReceipt | None
    backup_result: str = "verified"
    send_behavior: str = "ack"
    readbacks: tuple[Observation, ...] = ()
    max_readback_attempts: int = 3


_UNVERIFIED = ("hidden_page_visibility", "native_gaps", "widget_runtime_configuration", "duo_pose_behavior")
_SEND_BEHAVIORS = frozenset({"ack", "no_reply", "timeout_before_effect", "timeout_after_effect",
                            "disconnect_before_effect", "disconnect_after_effect"})


@dataclass(frozen=True)
class SimulationResult:
    scenario: str
    status: Status
    reason: str
    events: tuple[str, ...]
    send_attempts: int = 0
    read_attempts: int = 0
    rollback_attempts: int = 0
    fresh_connection_ids: tuple[int, ...] = ()
    send_uncertain: bool = False
    differences: tuple[str, ...] = ()
    ignored_count: int = 0
    fake_effect_applied: bool = False

    @property
    def can_write(self) -> bool:
        return False

    @property
    def fully_verified(self) -> bool:
        return False

    @property
    def unverified_factors(self) -> tuple[str, ...]:
        return _UNVERIFIED

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario": self.scenario, "status": self.status.value, "reason": self.reason,
            "events": list(self.events), "send_attempts": self.send_attempts,
            "read_attempts": self.read_attempts, "rollback_attempts": self.rollback_attempts,
            "fresh_connection_ids": list(self.fresh_connection_ids),
            "send_uncertain": self.send_uncertain, "differences": list(self.differences),
            "ignored_count": self.ignored_count, "fake_effect_applied": self.fake_effect_applied,
            "synthetic_only": True, "can_write": False, "fully_verified": False,
            "unverified_factors": list(_UNVERIFIED),
        }


def _binary(value: Any) -> bytes:
    return plistlib.dumps(value, fmt=plistlib.FMT_BINARY, sort_keys=True)


def _identifiers(values: Any) -> bool:
    return (type(values) is tuple and all(type(v) is str and bool(v) for v in values)
            and len(set(values)) == len(values))


def _data_only(value: Any, active: set[int] | None = None, depth: int = 0) -> None:
    """Refuse custom Python objects before deepcopy can invoke their hooks."""
    if depth > 40:
        raise ValueError("Synthetic observation is nested too deeply")
    active = set() if active is None else active
    if type(value) in (dict, list):
        if id(value) in active:
            raise ValueError("Synthetic observation contains a cycle")
        active.add(id(value))
        if type(value) is dict and not all(type(k) is str for k in value):
            raise ValueError("Synthetic dictionary keys must be strings")
        for child in value.values() if type(value) is dict else value:
            _data_only(child, active, depth + 1)
        active.remove(id(value))
    elif value is not None and type(value) not in (str, bool, int, float, bytes, datetime, plistlib.UID):
        raise ValueError("Only raw plist data is accepted in observations")


def _visible(raw: list) -> tuple[set[str], set[str]]:
    aliases, primary = set(), set()
    for page in raw:
        for item in page:
            if item.get("listType") == "folder":
                nested_aliases, nested_primary = _visible(item["iconLists"])
                aliases.update(nested_aliases)
                primary.update(nested_primary)
            elif item.get("iconType") != "custom":
                primary.add(item.get("bundleIdentifier") or item["displayIdentifier"])
                for key in ("bundleIdentifier", "displayIdentifier"):
                    if item.get(key):
                        aliases.add(item[key])
    return aliases, primary


def _exclusions(raw: list, receipt: InventoryReceipt | None) -> tuple[str | None, list[str]]:
    if receipt is None:
        return "inventory_missing", []
    if type(receipt) is not InventoryReceipt or receipt.synthetic is not True:
        return "inventory_not_synthetic", []
    for scope, query in (("user", receipt.user), ("system", receipt.system)):
        if type(query) is not InventoryQuery or type(query.status) is not str or query.status != "observed":
            return "inventory_" + scope + "_not_observed", []
        if query.complete is not True:
            return "inventory_" + scope + "_incomplete", []
        if (not _identifiers(query.identifiers) or not _identifiers(query.placeholder_ids)
                or not set(query.placeholder_ids) <= set(query.identifiers)):
            return "inventory_" + scope + "_invalid", []
    if receipt.placeholders_requested is not True:
        return "placeholder_coverage_unknown", []
    if receipt.hidden_webclips_known is not True:
        return "hidden_webclip_coverage_unknown", []
    if not _identifiers(receipt.hidden_webclip_ids):
        return "hidden_webclip_inventory_invalid", []
    if set(receipt.user.identifiers) & set(receipt.system.identifiers):
        return "inventory_type_conflict", []
    installed = set(receipt.user.identifiers) | set(receipt.system.identifiers)
    aliases, primary = _visible(raw)
    if not primary <= installed:
        return "visible_app_missing_from_inventory", []
    # Hidden web-clips are modeled separately. This synthetic rule is not a
    # claim that USB can supply a complete real-world list.
    if set(receipt.hidden_webclip_ids) & (aliases | installed):
        return "hidden_webclip_identity_conflict", []
    return None, sorted((installed - aliases) | set(receipt.hidden_webclip_ids))


def _differences(expected: Any, observed: Any, path: str = "$", limit: int = 40) -> tuple[str, ...]:
    found: list[str] = []

    def visit(left: Any, right: Any, where: str) -> None:
        if len(found) >= limit:
            return
        if type(left) is not type(right):
            found.append(where + ":type_changed")
        elif type(left) is dict:
            for key in sorted(set(left) | set(right)):
                next_path = where + "." + key
                if key not in left or key not in right:
                    found.append(next_path + ":field_missing_or_added")
                else:
                    visit(left[key], right[key], next_path)
                if len(found) >= limit:
                    break
        elif type(left) is list:
            if len(left) != len(right):
                found.append(where + ":length_changed")
            for index, (a, b) in enumerate(zip(left, right)):
                visit(a, b, where + "[" + str(index) + "]")
        elif _binary(left) != _binary(right):
            found.append(where + ":value_changed")

    try:
        visit(expected, observed, path)
    except (TypeError, ValueError, OverflowError, RecursionError):
        return ("$:invalid_readback",)
    return tuple(found)


class FakeTransport:
    """Final, in-memory value holder. It cannot wrap a real device adapter."""

    def __init_subclass__(cls, **kwargs):
        raise TypeError("FakeTransport cannot be subclassed")

    def __init__(self, scenario: Scenario):
        if type(scenario) is not Scenario:
            raise TypeError("Only a Scenario value is accepted")
        if (type(scenario.send_behavior) is not str or scenario.send_behavior not in _SEND_BEHAVIORS
                or type(scenario.readbacks) is not tuple or len(scenario.readbacks) > 5):
            raise ValueError("Only a bounded memory-only script is accepted")
        _data_only(scenario.current)
        for observation in scenario.readbacks:
            if type(observation) is not Observation:
                raise ValueError("Only Observation values are accepted")
            _data_only(observation.state)
        self._state = deepcopy(scenario.current)
        self._behavior = scenario.send_behavior
        self._observations = deepcopy(scenario.readbacks)
        self.send_attempts = 0
        self.read_attempts = 0
        self.connection_ids: list[int] = []
        self.effect_applied = False

    def send(self, payload: dict) -> str:
        if self.send_attempts:
            raise RuntimeError("A simulated write cannot be retried")
        if type(payload) is not dict or set(payload) != {"buttonBar", "iconLists", "ignored"}:
            raise ValueError("Only a candidate dictionary value is accepted")
        _data_only(payload)
        self.send_attempts += 1
        if self._behavior not in ("timeout_before_effect", "disconnect_before_effect"):
            self._state = deepcopy([payload["buttonBar"], *payload["iconLists"]])
            self.effect_applied = True
        return "ack" if self._behavior == "ack" else "uncertain"

    def read_fresh(self) -> tuple[str, Any]:
        self.read_attempts += 1
        self.connection_ids.append(self.read_attempts)
        observation = (self._observations[min(self.read_attempts - 1, len(self._observations) - 1)]
                       if self._observations else Observation())
        if observation.kind in ("failure", "timeout"):
            return observation.kind, None
        return "observed", deepcopy(self._state if observation.kind == "current" else observation.state)


def simulate(scenario: Scenario) -> SimulationResult:
    """Evaluate data-only gates, attempt at most one fake send, and inspect reads."""
    if type(scenario) is not Scenario:
        raise TypeError("simulate accepts a Scenario, not a device or transport")
    if (type(scenario.name) is not str or not scenario.name
            or type(scenario.max_readback_attempts) is not int
            or not 1 <= scenario.max_readback_attempts <= 5
            or type(scenario.send_behavior) is not str or scenario.send_behavior not in _SEND_BEHAVIORS
            or type(scenario.backup_result) is not str or scenario.backup_result not in {"verified", "failed", "corrupt"}
            or type(scenario.readbacks) is not tuple or len(scenario.readbacks) > 5):
        raise ValueError("Invalid or unbounded synthetic scenario")
    for observation in scenario.readbacks:
        if (type(observation) is not Observation or type(observation.kind) is not str
                or observation.kind not in {"current", "snapshot", "failure", "timeout"}):
            raise ValueError("Invalid synthetic observation")
        if observation.kind != "snapshot" and observation.state is not None:
            raise ValueError("Only snapshot observations carry state")
        if observation.kind == "snapshot":
            # Validate raw types before any deepcopy or arbitrary value comparison.
            _data_only(observation.state)
            if len(_binary(observation.state)) > 16 * 1024 * 1024:
                raise ValueError("Synthetic observation exceeds its size limit")
    events = ["SYNTHETIC_ONLY"]

    def blocked(reason: str) -> SimulationResult:
        return SimulationResult(scenario.name, Status.BLOCKED, reason, tuple(events + ["BLOCKED"]))

    if (type(scenario.expected_identity) is not str or not scenario.expected_identity
            or type(scenario.current_identity) is not str
            or scenario.current_identity != scenario.expected_identity):
        return blocked("device_identity_mismatch")
    events.append("IDENTITY_MATCH")
    try:
        if type(scenario.intent) is not tuple or len(scenario.intent) != 3:
            return blocked("invalid_intent")
        validate_swap(scenario.origin, scenario.candidate, *scenario.intent)
        analyze_layout(scenario.current)
        if _binary(scenario.current) != _binary(scenario.origin):
            return blocked("stale_baseline")
    except (DraftError, TypeError, ValueError, OverflowError, RecursionError):
        return blocked("invalid_draft_or_current_layout")
    events.extend(("DRAFT_VALID", "BASELINE_MATCH"))
    reason, excluded = _exclusions(scenario.candidate, scenario.inventory)
    if reason:
        return blocked(reason)
    events.append("SYNTHETIC_INVENTORY_COMPLETE")
    try:
        study = simulate_dictionary_payload(scenario.candidate, excluded_app_ids=excluded)
    except (TypeError, ValueError, OverflowError, RecursionError):
        return blocked("candidate_envelope_invalid")
    if scenario.backup_result != "verified":
        return blocked("backup_" + scenario.backup_result)
    # A fake backup is checked as typed serialized data; no filesystem is used.
    backup = _binary(scenario.current)
    if _binary(plistlib.loads(backup)) != backup:
        return blocked("backup_roundtrip_failed")
    events.append("FAKE_BACKUP_VERIFIED")
    transport = FakeTransport(scenario)
    events.append("SEND_STARTED")
    uncertain = transport.send(study.payload) != "ack"
    events.append("SEND_UNCERTAIN" if uncertain else "REPLY_RECEIVED")
    latest_status = "not_read"
    differences: tuple[str, ...] = ()
    outcome, reason = Status.UNCERTAIN, "no_reliable_readback"
    for _ in range(scenario.max_readback_attempts):
        latest_status, observed = transport.read_fresh()
        events.append("FRESH_READ_" + str(transport.read_attempts) + "_" + latest_status.upper())
        if latest_status != "observed":
            continue
        differences = _differences(scenario.candidate, observed)
        if not differences:
            outcome, reason = Status.EXPORTED_FIELDS_MATCH_ONLY, "exported_fields_match_unobservable_state_remains"
            events.append("EXPORTED_FIELDS_MATCH_ONLY")
            break
    else:
        if latest_status == "observed":
            outcome, reason = Status.MISMATCH, "strict_readback_mismatch"
            events.append("MISMATCH_NO_ROLLBACK")
        else:
            events.append("UNCERTAIN_NO_RETRY")
    return SimulationResult(
        scenario.name, outcome, reason, tuple(events), transport.send_attempts,
        transport.read_attempts, 0, tuple(transport.connection_ids), uncertain,
        differences, len(excluded), transport.effect_applied,
    )


def synthetic_scenario(name: str = "ack_with_match") -> Scenario:
    """Fabricated apps/widgets/inventory; no personal snapshot is read."""
    def app(ident: str) -> dict:
        return {"displayIdentifier": ident, "bundleIdentifier": ident,
                "iconModDate": datetime(2026, 1, 2, 3, 4, 5, 123456),
                "opaque": {"flag": True, "data": b"\x00\xff"}}

    stack = {"iconType": "custom", "displayIdentifier": "example.stack", "gridSize": "medium", "iconLists": [],
             "elements": [{"elementType": "widget", "widgetIdentifier": "example.widget." + str(i),
                           "uniqueIdentifier": "example.member." + str(i)} for i in range(2)],
             "userSelectedElementIdentifier": "example.member.1", "allowsSuggestions": True}
    origin = [[app("example.system.dock")], [stack, app("example.user.a"), app("example.user.b")]]
    candidate = plan_swap(origin, 1, 1, 2)
    inventory = InventoryReceipt(
        InventoryQuery("observed", ("example.user.a", "example.user.b", "example.library", "example.offloaded"), True,
                       ("example.offloaded",)),
        InventoryQuery("observed", ("example.system.dock", "example.system.hidden"), True),
        True, True, ("example.hidden.webclip",),
    )
    return Scenario(name, origin, candidate, deepcopy(origin), (1, 1, 2),
                    "synthetic-phone-a", "synthetic-phone-a", inventory)


def builtin_scenarios() -> tuple[Scenario, ...]:
    base = synthetic_scenario()
    receipt = base.inventory
    failures = (Observation("timeout"),)
    missing_selection = deepcopy(base.candidate)
    missing_selection[1][0].pop("userSelectedElementIdentifier")
    reordered_stack = deepcopy(base.candidate)
    reordered_stack[1][0]["elements"].reverse()
    changed_type = deepcopy(base.candidate)
    changed_type[1][1]["opaque"]["flag"] = 1
    changed_bytes = deepcopy(base.candidate)
    changed_bytes[1][1]["opaque"]["data"] = b"changed"
    changed_date = deepcopy(base.candidate)
    changed_date[1][1]["iconModDate"] = changed_date[1][1]["iconModDate"].replace(microsecond=0)
    added = deepcopy(base.candidate)
    added.append([{"displayIdentifier": "example.library"}])
    return (
        base,
        replace(base, name="missing_inventory", inventory=None),
        replace(base, name="failed_empty_inventory", inventory=replace(receipt, user=InventoryQuery("failed"))),
        replace(base, name="incomplete_inventory", inventory=replace(receipt, user=replace(receipt.user, complete=False))),
        replace(base, name="placeholders_unknown", inventory=replace(receipt, placeholders_requested=False)),
        replace(base, name="hidden_webclips_unknown", inventory=replace(receipt, hidden_webclips_known=False)),
        replace(base, name="visible_exclusion_conflict", inventory=replace(receipt, hidden_webclip_ids=("example.user.a",))),
        replace(base, name="identity_mismatch", current_identity="synthetic-phone-b"),
        replace(base, name="stale_baseline", current=deepcopy(base.candidate)),
        replace(base, name="backup_failure", backup_result="failed"),
        replace(base, name="backup_corrupt", backup_result="corrupt"),
        replace(base, name="send_timeout_after_side_effect", send_behavior="timeout_after_effect", readbacks=failures),
        replace(base, name="send_timeout_before_effect", send_behavior="timeout_before_effect"),
        replace(base, name="disconnect_after_side_effect", send_behavior="disconnect_after_effect", readbacks=failures),
        replace(base, name="no_reply_with_match", send_behavior="no_reply"),
        replace(base, name="read_failure", readbacks=(Observation("failure"),)),
        replace(base, name="delayed_read_match", readbacks=(Observation("snapshot", base.origin), Observation("snapshot", base.candidate))),
        replace(base, name="widget_selection_lost", readbacks=(Observation("snapshot", missing_selection),)),
        replace(base, name="stack_order_changed", readbacks=(Observation("snapshot", reordered_stack),)),
        replace(base, name="bool_became_integer", readbacks=(Observation("snapshot", changed_type),)),
        replace(base, name="opaque_bytes_changed", readbacks=(Observation("snapshot", changed_bytes),)),
        replace(base, name="date_precision_lost", readbacks=(Observation("snapshot", changed_date),)),
        replace(base, name="library_app_added", readbacks=(Observation("snapshot", added),)),
        replace(base, name="mismatch_then_unavailable", readbacks=(Observation("snapshot", missing_selection), Observation("failure"))),
    )


def scenario_suite() -> tuple[SimulationResult, ...]:
    return tuple(simulate(scenario) for scenario in builtin_scenarios())


def main() -> int:
    parser = argparse.ArgumentParser(description="仅内存中的虚构设备模拟，不连接手机")
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--all", action="store_true", help="运行所有虚构情景")
    selection.add_argument("--scenario", choices=[s.name for s in builtin_scenarios()])
    args = parser.parse_args()
    scenarios = builtin_scenarios()
    if args.scenario:
        scenarios = tuple(s for s in scenarios if s.name == args.scenario)
    print(json.dumps([simulate(s).to_dict() for s in scenarios], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
