# -*- coding: utf-8 -*-
'''
Display compact output data structure
=====================================

Example output::
'saltdev': {'test_|-always-passes_|-foo_|-succeed_without_changes': {'comment': 'Success!', 'name': 'foo', 'start_time': '05:16:26.111814', 'result': True, 'duration': 1, '__run_num__': 0, 'changes': {}}, 'test_|-my-custom-combo_|-foo_|-configurable_test_state': {'comment': 'bar.baz', 'name': 'foo', 'start_time': '05:16:26.117177', 'result': False, 'duration': 1, '__run_num__': 4, 'changes': {'testing': {'new': 'Something pretended to change', 'old': 'Unchanged'}}}, 'test_|-always-fails_|-foo_|-fail_without_changes': {'comment': 'Failure!', 'name': 'foo', 'start_time': '05:16:26.113124', 'result': False, 'duration': 1, '__run_num__': 1, 'changes': {}}, 'test_|-always-changes-and-succeeds_|-foo_|-succeed_with_changes': {'comment': 'Success!', 'name': 'foo', 'start_time': '05:16:26.114570', 'result': True, 'duration': 0, '__run_num__': 2, 'changes': {'testing': {'new': 'Something pretended to change', 'old': 'Unchanged'}}}, 'test_|-always-changes-and-fails_|-foo_|-fail_with_changes': {'comment': 'Failure!', 'name': 'foo', 'start_time': '05:16:26.115561', 'result': False, 'duration': 1, '__run_num__': 3, 'changes': {'testing': {'new': 'Something pretended to change', 'old': 'Unchanged'}}}}}{'myminion': {'foo': {'list': ['Hello', 'World'], 'bar': 'baz', 'dictionary': {'abc': 123, 'def': 456}}}}
'''
from __future__ import absolute_import

# Import salt libs
import salt.output.highstate


def output(data):
    '''
    Rather basic....
    '''
    tmp = {}
    for min_ in data:
        for process in data[min_]:
            add = False
            if data[min_][process]['result'] is False:
                add = True
            elif data[min_][process]['changes']:
                add = True
            if add is True:
                if min_ not in tmp:
                    tmp[min_] = {process: data[min_][process]}
                else:
                    tmp[min_][process] = {process: data[min_][process]}

    return salt.output.highstate.output(tmp)
