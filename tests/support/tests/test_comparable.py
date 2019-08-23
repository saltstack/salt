# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, unicode_literals, print_function

# Import locke libs
from tests.support.comparables import (ComparableSubDict,
                                       ComparableStateEntry,
                                       StateReturn)


def test_comparable_sub_dict_against_empty_other():
    # This will always be True because ComparableSubDict does not define any __comparable_keys__
    assert (ComparableSubDict(a=1) == {}) is True
    assert (ComparableSubDict(a=1) == {'b': 1}) is True


def test_comparable_state_entry_against_empty_other():
    assert (ComparableStateEntry(a=1) == {}) is True
    assert (ComparableStateEntry(a=1) == {'b': 1}) is True
    # The remaining assertions will be false because we're passing valid __comparable_keys__
    for key in ComparableStateEntry.__comparable_keys__:
        assert (ComparableStateEntry({key: 'foo'}) == {}) is False


def test_comparable_state_entry_direct_matching():
    for key in ComparableStateEntry.__comparable_keys__:
        if key == 'changes':
            continue
        assert (ComparableStateEntry({key: 'foo'}) == {key: 'foo'}) is True


def test_comparable_state_entry_regex_matching():
    for key in ComparableStateEntry.__comparable_keys__:
        if key in ('changes', 'result', 'status'):
            # We only regex match on strings
            continue
        value = 'foo'
        match = ComparableStateEntry({key: value}) == {key: '.*'}
        assert match is True, "Failed to regex match {{'{0}': '.*'}} against {{'{0}': '{1}'}}".format(key, value)
        match = ComparableStateEntry({key: 'foo'}) == {key: 'b.*'}
        assert match is False


def test_state_return_matching():
    a = StateReturn({
        'user_|-create_user1_account_|-user1_|-present': {
            '__id__': 'create_user1_account',
            '__run_num__': 4,
            '__sls__': 'locke.system.software.docker_daemon_trusted_users_access_bad',
            'changes': {'groups': ['docker', 'user1']},
            'comment': 'Updated user user1',
            'duration': 28.058,
            'name': 'user1',
            'result': True,
            'start_time': '19:26:52.780178'},
        'user_|-create_user2_account_|-user2_|-present': {
            '__id__': 'create_user2_account',
            '__run_num__': 5,
            '__sls__': 'locke.system.software.docker_daemon_trusted_users_access_bad',
            'changes': {'groups': ['docker', 'user2']},
            'comment': 'Updated user user2',
            'duration': 23.088,
            'name': 'user2',
            'result': True,
            'start_time': '19:26:52.816815'
        },
        'user_|-create_user3_account_|-user3_|-present': {
            '__id__': 'create_user3_account',
            '__run_num__': 6,
            '__sls__': 'locke.system.software.docker_daemon_trusted_users_access_bad',
            'changes': {'groups': ['docker', 'user3']},
            'comment': 'Updated user user3',
            'duration': 22.614,
            'name': 'user3',
            'result': True,
            'start_time': '19:26:52.848631'
        }
    })
    b = {'state_entries': [{'result': True}, {'result': True}, {'result': True}]}
    assert a == b
    b = {'state_entries': [{'result': True}, {'result': True}, {'result': True, 'comment': '.* user3'}]}
    assert a == b
    b = {'state_entries': [{'result': True}, {'result': True}, {'changes': {'groups': ['docker', 'user3']}}]}
    assert a == b
    b = {'state_entries': [{'result': True}, {'result': True}]}
    assert a != b


def test_state_return_status_matching():
    a = StateReturn({
        'changes': {},
        'comment': 'Non Compliant status 1 set\nNon Compliant status 2 set\nNon Compliant status 3 set',
        'duration': 1.463,
        'locke_|-report-conflict-status-1_|-report-conflict-status-1_|-notify': {
            '__id__': 'report-conflict-status-1',
            '__run_num__': 0,
            '__sls__': 'locke.testing.conflicting_statuses',
            'changes': {},
            'comment': 'Non Compliant status 1 set',
            'duration': 0.591,
            'name': 'report-conflict-status-1',
            'result': None,
            'start_time': '18:03:20.045771',
            'status': 'compliant'
        },
        'locke_|-report-conflict-status-2_|-report-conflict-status-2_|-notify': {
            '__id__': 'report-conflict-status-2',
            '__run_num__': 1,
            '__sls__': 'locke.testing.conflicting_statuses',
            'changes': {},
            'comment': 'Non Compliant status 2 set',
            'duration': 0.443,
            'name': 'report-conflict-status-2',
            'result': None,
            'start_time': '18:03:20.054269',
            'status': 'noncompliant'
        },

        'locke_|-report-conflict-status-3_|-report-conflict-status-3_|-notify': {
            '__id__': 'report-conflict-status-3',
            '__run_num__': 2,
            '__sls__': 'locke.testing.conflicting_statuses',
            'changes': {},
            'comment': 'Non Compliant status 3 set',
            'duration': 0.429,
            'name': 'report-conflict-status-3',
            'result': None,
            'start_time': '18:03:20.062623',
            'status': 'compliant'
        },
        'result': None,
        'status': 'error'
    })
    b = {'state_entries': [{'status': 'compliant'}, {'status': 'noncompliant'}, {'status': 'compliant'}]}
    assert a == b
    b = {'state_entries': [{'status': 'compliant'}, {'status': 'compliant'}, {'status': 'compliant'}]}
    assert a != b
    b = {'state_entries': [{'status': 'compliant'}, {'status': 'noncompliant'}]}
    assert a != b
