# -*- coding: utf-8 -*-
'''
unit tests for the cache runner
'''

# Import Python Libs
from __future__ import absolute_import
import os

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.paths import TMP
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch
)

# Import Salt Libs
import salt.runners.queue as queue_mod


@skipIf(NO_MOCK, NO_MOCK_REASON)
class QueueTest(TestCase, LoaderModuleMockMixin):
    '''
    Validate the queue runner
    '''
    def setup_loader_modules(self):
        return {
            queue_mod: {
                '__opts__': {
                    'sock_dir': os.path.join(TMP, 'queue-runner-sock-dir'),
                    'transport': 'zeromq'
                }
            }
        }

    def test_insert_runner(self):
        queue_insert = MagicMock(return_value=True)
        with patch.object(queue_mod, 'insert', queue_insert):
            queue_mod.insert_runner('test.stdout_print', queue='salt')
        expected_call = {
            'queue': 'salt',
            'items': {
                'fun': 'test.stdout_print',
                'args': [],
                'kwargs': {},
            },
            'backend': 'pgjsonb',
        }
        queue_insert.assert_called_once_with(**expected_call)

    def test_process_runner(self):
        ret = [{
            'fun': 'test.stdout_print',
            'args': [],
            'kwargs': {},
        }]

        queue_pop = MagicMock(return_value=ret)
        test_stdout_print = MagicMock(return_value=True)
        queue_mod.__salt__['test.stdout_print'] = test_stdout_print
        with patch.object(queue_mod, 'pop', queue_pop):
            queue_mod.process_runner(queue='salt')
        queue_pop.assert_called_once_with(queue='salt', quantity=1, backend='pgjsonb')
        test_stdout_print.assert_called_once_with()
        queue_pop.assert_called_once_with(queue='salt', quantity=1, backend='pgjsonb')
