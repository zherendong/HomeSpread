"""Independent adversarial checks for a pure offline Duo swap study.

All identifiers and payloads here are fabricated. No phone or SDK is used.
"""
from __future__ import annotations

import ast
import copy
from datetime import datetime
from pathlib import Path
import plistlib
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'src'))

from research.duo_planner import DraftError, analyze_layout, plan_swap, validate_swap
from ipsm.write_policy import write_block_reason


def app(number: int, **extra):
    return {'displayIdentifier': f'example.qa.app{number}',
            'bundleIdentifier': f'example.qa.app{number}',
            'displayName': f'Example {number}',
            'iconModDate': datetime(2026, 1, 2, 3, 4, 5, 678901),
            'opaqueFutureValue': {'bytes': b'\x00\xff\x01', 'flag': True}, **extra}


def widget(number: int):
    return {'displayIdentifier': f'example-qa-widget-{number}',
            'iconType': 'custom', 'elementType': 'widget',
            'widgetIdentifier': f'example.qa.widget{number}',
            'gridSize': 'small', 'iconLists': [],
            'opaqueFutureValue': {'bytes': b'\x00\x80', 'flag': True}}


STACK = {'displayIdentifier': 'example-qa-stack', 'iconType': 'custom',
         'gridSize': 'medium', 'iconLists': [],
         'elements': [{'elementType': 'widget',
                       'widgetIdentifier': f'example.qa.stack{i}',
                       'uniqueIdentifier': f'example-qa-member-{i}',
                       'futureDate': datetime(2026, 1, 2, 1, 2, 3, 456789)}
                      for i in range(7)],
         'userSelectedElementIdentifier': 'example-qa-member-4',
         'allowsSuggestions': True, 'allowsExternalSuggestions': False,
         'opaqueFutureValue': {'bytes': b'\x00\xff', 'flag': True}}
FOLDER = {'listType': 'folder', 'displayName': 'Example folder',
          'iconLists': [[app(80), app(81)], [app(82)]],
          'opaqueFolderField': {'flag': True, 'data': b'folder metadata'}}
STATE = [[app(99)], [copy.deepcopy(STACK), app(1), app(2), copy.deepcopy(FOLDER)],
         [widget(1), app(3), app(4), widget(2)]]


def binary(value):
    return plistlib.dumps(value, fmt=plistlib.FMT_BINARY, sort_keys=True)


def test_valid_offline_swap_does_not_authorize_production_write():
    original = copy.deepcopy(STATE)
    before = binary(original)
    candidate = plan_swap(original, 1, 1, 2)
    assert validate_swap(original, candidate, 1, 1, 2)['valid'] is True
    assert binary(original) == before
    assert write_block_reason(candidate, product_type='iPhone19,4')
    assert write_block_reason(candidate, product_type='iPhone14,7')
    assert binary(candidate[1][0]) == binary(original[1][0])
    assert binary(candidate[1][3]) == binary(original[1][3])
    assert binary(candidate[0]) == binary(original[0])


def test_plain_research_candidate_still_cannot_unlock_duo():
    plain = [[], [app(1), app(2)]]
    candidate = plan_swap(plain, 1, 0, 1)
    assert validate_swap(plain, candidate, 1, 0, 1)['valid']
    assert write_block_reason(candidate, product_type='iPhone19,4')


def test_analysis_counts_stacks_as_blocks_and_preserves_input():
    raw = copy.deepcopy(STATE)
    before = binary(raw)
    report = analyze_layout(raw)
    assert report['counts']['widget_blocks'] == 3
    assert report['counts']['widget_members'] == 9
    assert report['counts']['folders'] == 1
    assert binary(raw) == before


@pytest.mark.parametrize('field,value', [
    ('userSelectedElementIdentifier', 'example-qa-member-0'),
    ('allowsSuggestions', False),
    ('allowsExternalSuggestions', True),
    ('gridSize', 'small'),
    ('displayIdentifier', 'example-qa-replaced-stack'),
    ('iconLists', [[]]),
])
def test_validator_rejects_every_widget_metadata_change(field, value):
    candidate = plan_swap(STATE, 1, 1, 2)
    candidate[1][0][field] = value
    with pytest.raises(DraftError):
        validate_swap(STATE, candidate, 1, 1, 2)


def test_validator_does_not_ignore_selected_stack_member_or_member_order():
    for kind in ('order', 'content', 'date'):
        candidate = plan_swap(STATE, 1, 1, 2)
        members = candidate[1][0]['elements']
        if kind == 'order':
            members.reverse()
        elif kind == 'content':
            members[0]['widgetIdentifier'] = 'example.qa.other'
        else:
            members[0]['futureDate'] = members[0]['futureDate'].replace(microsecond=0)
        with pytest.raises(DraftError):
            validate_swap(STATE, candidate, 1, 1, 2)


@pytest.mark.parametrize('site', ['widget', 'folder', 'app'])
def test_python_bool_int_equality_cannot_hide_metadata_corruption(site):
    candidate = plan_swap(STATE, 1, 1, 2)
    target = {'widget': candidate[1][0]['opaqueFutureValue'],
              'folder': candidate[1][3]['opaqueFolderField'],
              'app': candidate[1][1]['opaqueFutureValue']}[site]
    target['flag'] = 1  # True == 1 in Python, but they are different plist values.
    with pytest.raises(DraftError):
        validate_swap(STATE, candidate, 1, 1, 2)


@pytest.mark.parametrize('change', ['folder_name', 'folder_order', 'dock', 'other_page',
                                  'page_removed', 'page_added', 'endpoint_omitted', 'extra_swap'])
def test_validator_rejects_changes_outside_declared_two_slots(change):
    candidate = plan_swap(STATE, 1, 1, 2)
    if change == 'folder_name': candidate[1][3]['displayName'] = 'Changed'
    elif change == 'folder_order': candidate[1][3]['iconLists'][0].reverse()
    elif change == 'dock': candidate[0].append(app(98))
    elif change == 'other_page': candidate[2][1]['displayName'] = 'Changed'
    elif change == 'page_removed': candidate.pop()
    elif change == 'page_added': candidate.append([])
    elif change == 'endpoint_omitted': candidate[1].pop(1)
    elif change == 'extra_swap': candidate[2][1], candidate[2][2] = candidate[2][2], candidate[2][1]
    with pytest.raises(DraftError):
        validate_swap(STATE, candidate, 1, 1, 2)


@pytest.mark.parametrize('intent', [(0,0,1),(1,1,1),(1,0,1),(1,1,3),
                                  (True,1,2),(1,True,2),(1,-1,2),(-1,1,2),
                                  (1,1,999),(999,1,2)])
def test_invalid_or_unsupported_intent_is_rejected_without_mutation(intent):
    raw = copy.deepcopy(STATE)
    before = binary(raw)
    with pytest.raises(DraftError):
        plan_swap(raw, *intent)
    assert binary(raw) == before


def test_duplicate_display_identifiers_use_occurrences_and_full_payloads():
    raw = [[], [app(1, occurrence=b'first'), app(1, occurrence=b'second'), app(2)]]
    candidate = plan_swap(raw, 1, 0, 1)
    assert validate_swap(raw, candidate, 1, 0, 1)['valid']
    assert candidate[1][0]['occurrence'] == b'second'
    assert candidate[1][1]['occurrence'] == b'first'
    candidate[1][1] = copy.deepcopy(candidate[1][0])
    with pytest.raises(DraftError):
        validate_swap(raw, candidate, 1, 0, 1)


def test_indistinguishable_duplicate_swap_is_not_a_change():
    raw = [[], [app(1), app(1)]]
    with pytest.raises(DraftError):
        plan_swap(raw, 1, 0, 1)


def test_wrong_intent_cannot_validate_an_otherwise_valid_swap():
    raw = [[], [app(1), app(2), app(3)]]
    candidate = plan_swap(raw, 1, 0, 1)
    with pytest.raises(DraftError):
        validate_swap(raw, candidate, 1, 1, 2)


def test_returned_candidate_is_detached_from_original_and_other_drafts():
    raw = copy.deepcopy(STATE)
    before = binary(raw)
    first = plan_swap(raw, 1, 1, 2)
    second = plan_swap(raw, 1, 1, 2)
    first[1][0]['elements'][0]['uniqueIdentifier'] = 'mutated-after-return'
    assert binary(raw) == before
    assert binary(second[1][0]) == binary(raw[1][0])


def test_research_modules_have_no_device_or_transport_imports():
    allowed = {'__future__','argparse','collections','copy','dataclasses','datetime',
               'hashlib','itertools','json','math','pathlib','plistlib','sys','typing'}
    modules = sorted((ROOT / 'research').glob('*.py'))
    assert modules
    for path in modules:
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(alias.name.split('.')[0] in allowed for alias in node.names), path
            elif isinstance(node, ast.ImportFrom):
                assert node.level > 0 or (node.module or '').split('.')[0] in allowed, path
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in {'eval','exec','__import__','compile'}, path


def test_swap_keeps_all_modeled_widget_anchors_and_page_capacities():
    candidate = plan_swap(STATE, 1, 1, 2)
    before = analyze_layout(STATE)
    after = analyze_layout(candidate)
    assert len(before['pages']) == len(after['pages'])
    for left, right in zip(before['pages'], after['pages']):
        assert left['page'] == right['page']
        assert left['item_count'] == right['item_count']
        assert left['occupied_cells'] == right['occupied_cells']
        assert left['placements'] == right['placements']


def test_transport_envelope_is_not_silently_treated_as_raw_snapshot():
    envelope = {'buttonBar': copy.deepcopy(STATE[0]), 'iconLists': copy.deepcopy(STATE[1:]),
                'ignored': ['example.qa.not-on-homescreen']}
    before = binary(envelope)
    with pytest.raises(DraftError):
        analyze_layout(envelope)
    assert binary(envelope) == before


def test_analysis_report_does_not_expose_fixture_identifiers_or_payloads():
    import json
    report_text = json.dumps(analyze_layout(STATE), ensure_ascii=False)
    for private_value in ('example.qa.', 'example-qa-member-', 'Example folder', 'folder metadata'):
        assert private_value not in report_text
    assert 'device_write_supported' in report_text
    assert analyze_layout(STATE)['device_write_supported'] is False


def test_envelope_rejects_excluded_bundle_when_display_identifier_differs():
    from research.duo_envelope import simulate_dictionary_payload
    raw = [[], [{'displayIdentifier': 'example.qa.display-id',
                 'bundleIdentifier': 'example.qa.bundle-id', 'displayName': 'Example'}]]
    with pytest.raises(ValueError):
        simulate_dictionary_payload(raw, excluded_app_ids=['example.qa.bundle-id'])


def test_envelope_is_detached_and_never_becomes_a_write_capability():
    from research.duo_envelope import simulate_dictionary_payload
    before = binary(STATE)
    study = simulate_dictionary_payload(STATE, excluded_app_ids=['example.qa.library-only'])
    assert study.can_send is False
    assert binary([study.payload['buttonBar'], *study.payload['iconLists']]) == before
    assert write_block_reason(study.payload, product_type='iPhone19,4')
    study.payload['iconLists'][0][0]['elements'][0]['futureDate'] = datetime(2000, 1, 1)
    assert binary(STATE) == before
    assert study.can_send is False


def test_envelope_requires_explicit_inventory_without_querying_any_device():
    from research.duo_envelope import EvidenceMissing, simulate_dictionary_payload
    with pytest.raises(EvidenceMissing):
        simulate_dictionary_payload(STATE, excluded_app_ids=None)
