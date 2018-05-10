# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

# Import Salt Libs
import salt.modules.sysbench as sysbench


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SysbenchTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases to salt.modules.sysbench
    '''
    def setup_loader_modules(self):
        return {sysbench: {}}

    def test_cpu(self):
        '''
        Test to tests to the CPU performance of minions.
        '''
        with patch.dict(sysbench.__salt__,
                        {'cmd.run': MagicMock(return_value={'A': 'a'})}):
            with patch.object(sysbench, '_parser', return_value={'A': 'a'}):
                self.assertEqual(sysbench.cpu(),
                                 {'Prime numbers limit: 500':
                                  {'A': 'a'}, 'Prime numbers limit: 5000':
                                  {'A': 'a'}, 'Prime numbers limit: 2500':
                                  {'A': 'a'}, 'Prime numbers limit: 1000':
                                  {'A': 'a'}})

    def test_threads(self):
        '''
        Test to this tests the performance of the processor's scheduler
        '''
        with patch.dict(sysbench.__salt__,
                        {'cmd.run': MagicMock(return_value={'A': 'a'})}):
            with patch.object(sysbench, '_parser', return_value={'A': 'a'}):
                self.assertEqual(sysbench.threads(),
                                 {'Yields: 500 Locks: 8': {'A': 'a'},
                                  'Yields: 200 Locks: 4': {'A': 'a'},
                                  'Yields: 1000 Locks: 16': {'A': 'a'},
                                  'Yields: 100 Locks: 2': {'A': 'a'}})

    def test_mutex(self):
        '''
        Test to tests the implementation of mutex
        '''
        with patch.dict(sysbench.__salt__,
                        {'cmd.run': MagicMock(return_value={'A': 'a'})}):
            with patch.object(sysbench, '_parser', return_value={'A': 'a'}):
                self.assertEqual(sysbench.mutex(),
                                 {'Mutex: 1000 Locks: 25000 Loops: 10000':
                                  {'A': 'a'},
                                  'Mutex: 50 Locks: 10000 Loops: 2500':
                                  {'A': 'a'},
                                  'Mutex: 1000 Locks: 10000 Loops: 5000':
                                  {'A': 'a'},
                                  'Mutex: 500 Locks: 50000 Loops: 5000':
                                  {'A': 'a'},
                                  'Mutex: 500 Locks: 25000 Loops: 2500':
                                  {'A': 'a'},
                                  'Mutex: 500 Locks: 10000 Loops: 10000':
                                  {'A': 'a'},
                                  'Mutex: 50 Locks: 50000 Loops: 10000':
                                  {'A': 'a'},
                                  'Mutex: 1000 Locks: 50000 Loops: 2500':
                                  {'A': 'a'},
                                  'Mutex: 50 Locks: 25000 Loops: 5000':
                                  {'A': 'a'}})

    def test_memory(self):
        '''
        Test to this tests the memory for read and write operations.
        '''
        with patch.dict(sysbench.__salt__,
                        {'cmd.run': MagicMock(return_value={'A': 'a'})}):
            with patch.object(sysbench, '_parser', return_value={'A': 'a'}):
                self.assertEqual(sysbench.memory(),
                                 {'Operation: read Scope: local':
                                  {'A': 'a'},
                                  'Operation: write Scope: local':
                                  {'A': 'a'},
                                  'Operation: read Scope: global':
                                  {'A': 'a'},
                                  'Operation: write Scope: global':
                                  {'A': 'a'}})

    def test_fileio(self):
        '''
        Test to this tests for the file read and write operations
        '''
        with patch.dict(sysbench.__salt__,
                        {'cmd.run': MagicMock(return_value={'A': 'a'})}):
            with patch.object(sysbench, '_parser', return_value={'A': 'a'}):
                self.assertEqual(sysbench.fileio(),
                                 {'Mode: seqrd': {'A': 'a'},
                                  'Mode: seqwr': {'A': 'a'},
                                  'Mode: rndrd': {'A': 'a'},
                                  'Mode: rndwr': {'A': 'a'},
                                  'Mode: seqrewr': {'A': 'a'},
                                  'Mode: rndrw': {'A': 'a'}})

    def test_ping(self):
        '''
        Test to ping
        '''
        self.assertTrue(sysbench.ping())
