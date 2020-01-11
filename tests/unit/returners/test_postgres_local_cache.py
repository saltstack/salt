# -*- coding: utf-8 -*-
'''
tests.unit.returners.postgres_local_cache_test
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for the postgres_local_cache.
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import shutil
import logging

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase
from tests.support.mock import (
    patch,
    call,
    MagicMock
)

# Import Salt libs
import salt.utils.stringutils
import salt.returners.postgres_local_cache as postgres_local_cache
from salt.ext import six

log = logging.getLogger(__name__)


class PostgresLocalCacheTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Tests for the postgre_local_cache returner.
    '''
    @classmethod
    def setUpClass(cls):
        cls.TMP_CACHE_DIR = os.path.join(RUNTIME_VARS.TMP, 'salt_test_job_cache')
        cls.TMP_JID_DIR = os.path.join(cls.TMP_CACHE_DIR, 'jobs')

    def setup_loader_modules(self):
        return {postgres_local_cache: {'__opts__': {'cachedir': self.TMP_CACHE_DIR, 'keep_jobs': 1}}}

    def tearDown(self):
        '''
        Clean up after tests.

        Note that a setUp function is not used in this TestCase because the
        _make_tmp_jid_dirs replaces it.
        '''
        if os.path.exists(self.TMP_CACHE_DIR):
            shutil.rmtree(self.TMP_CACHE_DIR)

    def test_returner(self):
        '''
        Tests that the returner function
        '''
        load = {'tgt_type': 'glob',
                'fun_args': [],
                'jid': '20200108221839189167',
                'return': True,
                'retcode': 0,
                'success': True,
                'tgt': 'minion',
                'cmd': '_return',
                '_stamp': '2020-01-08T22:18:39.197774',
                'arg': [],
                'fun': 'test.ping',
                'id': 'minion'}

        connect_mock = MagicMock()
        with patch.object(postgres_local_cache, '_get_conn', connect_mock):
            postgres_local_cache.returner(load)

            query_string = ('INSERT INTO salt_returns\n            '
                            '(fun, jid, return, id, success)\n            '
                            'VALUES (%s, %s, %s, %s, %s)')
            query_values = ('test.ping',
                            '20200108221839189167',
                            '{"return": "True", "retcode": 0, "success": true}',
                            'minion',
                            True)
            calls = (
                call().cursor().execute(query_string, query_values),
            )
            connect_mock.assert_has_calls(calls, any_order=True)

    def test_returner_unicode_exception(self):
        '''
        Tests that the returner function
        '''
        load = {'tgt_type': 'glob',
                'fun_args': [],
                'jid': '20200108221839189167',
                'return': 'glücklich',
                'retcode': 0,
                'success': True,
                'tgt': 'minion',
                'cmd': '_return',
                '_stamp': '2020-01-08T22:18:39.197774',
                'arg': [],
                'fun': 'test.ping',
                'id': 'minion'}

        if six.PY3:
            expected_return = '{"return": "glücklich", "retcode": 0, "success": true}'
        else:
            expected_return = salt.utils.stringutils.to_str('{"return": "glücklich", "retcode": 0, "success": true}')

        query_string = ('INSERT INTO salt_returns\n            '
                        '(fun, jid, return, id, success)\n            '
                        'VALUES (%s, %s, %s, %s, %s)')
        query_values = ('test.ping',
                        '20200108221839189167',
                        expected_return,
                        'minion',
                        True)

        connect_mock = MagicMock()
        with patch.object(postgres_local_cache, '_get_conn', connect_mock):
            postgres_local_cache.returner(load)

            calls = (
                call().cursor().execute(query_string, query_values),
            )
            connect_mock.assert_has_calls(calls, any_order=True)
