# -*- coding: utf-8 -*-
'''
unittests for highstate outputter
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase

# Import Salt Libs
import salt.utils.stringutils
import salt.output.highstate as highstate

# Import 3rd-party libs
from salt.ext import six


class JsonTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.output.highstate
    '''
    def setup_loader_modules(self):
        return {
            highstate: {
                '__opts__': {
                    'extension_modules': '',
                    'color': False,
                }
            }
        }

    def setUp(self):
        self.data = {
            'data': {
                'master': {
                    'salt_|-call_sleep_state_|-call_sleep_state_|-state': {
                        '__id__': 'call_sleep_state',
                        '__jid__': '20170418153529810135',
                        '__run_num__': 0,
                        '__sls__': 'orch.simple',
                        'changes': {
                            'out': 'highstate',
                            'ret': {
                                'minion': {
                                    'module_|-simple-ping_|-test.ping_|-run': {
                                        '__id__': 'simple-ping',
                                        '__run_num__': 0,
                                        '__sls__': 'simple-ping',
                                        'changes': {'ret': True},
                                        'comment': 'Module function test.ping executed',
                                        'duration': 56.179,
                                        'name': 'test.ping',
                                        'result': True,
                                        'start_time': '15:35:31.282099'
                                    }
                                },
                                'sub_minion': {
                                    'module_|-simple-ping_|-test.ping_|-run': {
                                        '__id__': 'simple-ping',
                                        '__run_num__': 0,
                                        '__sls__': 'simple-ping',
                                        'changes': {'ret': True},
                                        'comment': 'Module function test.ping executed',
                                        'duration': 54.103,
                                        'name': 'test.ping',
                                        'result': True,
                                        'start_time': '15:35:31.005606'
                                    }
                                }
                            }
                        },
                        'comment': 'States ran successfully. Updating sub_minion, minion.',
                        'duration': 1638.047,
                        'name': 'call_sleep_state',
                        'result': True,
                        'start_time': '15:35:29.762657'
                    }
                }
            },
            'outputter': 'highstate',
            'retcode': 0
        }
        self.addCleanup(delattr, self, 'data')

    def test_default_output(self):
        ret = highstate.output(self.data)
        self.assertIn('Succeeded: 1 (changed=1)', ret)
        self.assertIn('Failed:    0', ret)
        self.assertIn('Total states run:     1', ret)

    def test_output_comment_is_not_unicode(self):
        entry = None
        for key in ('data', 'master', 'salt_|-call_sleep_state_|-call_sleep_state_|-state',
                    'changes', 'ret', 'minion', 'module_|-simple-ping_|-test.ping_|-run'):
            if entry is None:
                entry = self.data[key]
                continue
            entry = entry[key]
        if six.PY2:
            entry['comment'] = salt.utils.stringutils.to_unicode(entry['comment'])
        else:
            entry['comment'] = salt.utils.stringutils.to_bytes(entry['comment'])
        ret = highstate.output(self.data)
        self.assertIn('Succeeded: 1 (changed=1)', ret)
        self.assertIn('Failed:    0', ret)
        self.assertIn('Total states run:     1', ret)
