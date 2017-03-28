# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import
import os

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

# Import Salt Libs
import salt.modules.solr as solr


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SolrTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.solr
    '''
    def setup_loader_modules(self):
        return {solr: {}}

    def test_lucene_version(self):
        '''
        Test to get the lucene version that solr is using.
        '''
        with patch.object(solr, '_get_return_dict', return_value={'A': 'a'}):
            with patch.object(solr, '_get_none_or_value',
                              side_effect=[None, True, True]):
                with patch.object(solr, '_check_for_cores',
                                  side_effect=[True, False, False]):
                    tempdict = {'success': 'success', 'errors': 'errors',
                                'data': {'lucene': {'lucene-spec-version': 1}}}
                    with patch.object(solr, '_get_admin_info',
                                      side_effect=[tempdict, tempdict,
                                                   {'success': None}]):
                        with patch.dict(solr.__salt__,
                                        {'config.option':
                                         MagicMock(return_value=['A'])}):

                            with patch.object(solr, '_update_return_dict',
                                              return_value={'A': 'a'}):
                                self.assertDictEqual(solr.lucene_version('c'),
                                                     {'A': 'a'})

                            self.assertDictEqual(solr.lucene_version('c'),
                                                 {'A': 'a'})

                            self.assertDictEqual(solr.lucene_version('c'),
                                                 {'success': None})

    def test_version(self):
        '''
        Test to get the solr version for the core specified
        '''
        with patch.object(solr, '_get_return_dict', return_value={'A': 'a'}):
            with patch.object(solr, '_get_none_or_value',
                              side_effect=[None, True, True]):
                with patch.object(solr, '_check_for_cores',
                                  side_effect=[True, False, False]):

                    tempdict = {'success': 'success', 'errors': 'errors',
                                'warnings': 'warnings',
                                'data': {'lucene': {'solr-spec-version': 1}}}
                    with patch.object(solr, '_get_admin_info',
                                      side_effect=[tempdict, tempdict]):
                        with patch.dict(solr.__opts__,
                                        {'solr.cores':
                                         MagicMock(return_value=['A'])}):
                            with patch.object(solr, '_update_return_dict',
                                              return_value={'A': 'a'}):
                                self.assertDictEqual(solr.version(),
                                                     {'A': 'a'})

                            self.assertDictEqual(solr.version(),
                                                 {'A': 'a'})

                    with patch.object(solr, '_get_admin_info',
                                      return_value={'success': None}):
                        self.assertDictEqual(solr.version(), {'success': None})

    def test_optimize(self):
        '''
        Test to search queries fast, but it is a very expensive operation.
        '''
        with patch.object(solr, '_get_return_dict', return_value={'A': 'a'}):
            with patch.object(solr, '_get_none_or_value',
                              side_effect=[None, True]):
                with patch.object(solr, '_check_for_cores',
                                  side_effect=[True, False]):

                    tempdict = {'success': 'success', 'errors': 'errors',
                                'warnings': 'warnings',
                                'data': {'lucene': {'solr-spec-version': 1}}}
                    with patch.object(solr, '_format_url',
                                      return_value='A'):
                        with patch.dict(solr.__salt__,
                                        {'config.option':
                                         MagicMock(return_value=['A'])}):
                            with patch.object(solr, '_http_request',
                                              return_value=tempdict):
                                with patch.object(solr, '_update_return_dict',
                                                  return_value={'A': 'a'}):
                                    self.assertDictEqual(solr.optimize(),
                                                         {'A': 'a'})

                        with patch.object(solr, '_http_request',
                                                return_value='A'):
                            self.assertEqual(solr.optimize(), 'A')

    def test_ping(self):
        '''
        Test to check on solr, makes sure solr can talk to the
        indexes.
        '''
        with patch.object(solr, '_get_return_dict', return_value={'A': 'a'}):
            with patch.object(solr, '_get_none_or_value',
                              side_effect=[None, True]):
                with patch.object(solr, '_check_for_cores',
                                  side_effect=[True, False]):

                    tempdict = {'success': 'success', 'errors': 'errors',
                                'warnings': 'warnings',
                                'data': {'lucene': {'solr-spec-version': 1}}}

                    with patch.dict(solr.__opts__,
                                    {'solr.cores':
                                     MagicMock(return_value=['A'])}):
                        with patch.object(solr, '_get_admin_info',
                                          return_value=tempdict):
                            with patch.object(solr, '_update_return_dict',
                                              return_value={'A': 'a'}):
                                self.assertDictEqual(solr.ping(), {'A': 'a'})

                    with patch.object(solr, '_get_admin_info',
                                            return_value='A'):
                        self.assertEqual(solr.ping(), 'A')

    def test_is_replication_enabled(self):
        '''
        Test to check for errors, and determine if a slave
        is replicating or not.
        '''
        error = 'Only "slave" minions can run "is_replication_enabled"'
        with patch.object(solr, '_get_return_dict', return_value={'A': 'a'}):
            with patch.object(solr, '_is_master', side_effect=[True, False]):

                self.assertIsNone(solr.is_replication_enabled())

                with patch.object(solr, '_get_none_or_value',
                                  return_value=None):
                    with patch.object(solr, '_check_for_cores',
                                      return_value=True):
                        with patch.dict(solr.__opts__,
                                        {'solr.cores':
                                         MagicMock(return_value='A')}):
                            with patch.object(solr, '_replication_request',
                                              return_value='A'):
                                self.assertDictEqual(solr.is_replication_enabled
                                                     (), {'A': 'a',
                                                          'errors': [error],
                                                          'success': False})

    def test_match_index_versions(self):
        '''
        Test to verifies that the master and the slave versions are in sync by
        comparing the index version.
        '''
        err = 'solr.match_index_versions can only be called by "slave" minions'
        with patch.object(solr, '_get_return_dict', return_value={'A': 'a'}):
            with patch.object(solr, '_is_master', side_effect=[True, False]):

                self.assertIsNone(solr.match_index_versions())

                with patch.object(solr, '_get_none_or_value',
                                  return_value=None):
                    with patch.object(solr, '_check_for_cores',
                                      return_value=True):
                        with patch.dict(solr.__opts__,
                                        {'solr.cores':
                                         MagicMock(return_value='A')}):
                            with patch.object(solr, '_replication_request',
                                              return_value='A'):
                                self.assertDictEqual(solr.match_index_versions
                                                     (), {'A': 'a',
                                                          'errors': [err],
                                                          'success': False})

    def test_replication_details(self):
        '''
        Test to get the full replication details.
        '''
        tempdict1 = {'success': 'success', 'errors': 'errors',
                     'warnings': 'warnings', 'data': 'data'}

        tempdict2 = {'success': None, 'errors': 'errors',
                     'warnings': 'warnings', 'data': 'data'}

        with patch.object(solr, '_get_return_dict', return_value={'A': 'a'}):
            with patch.object(solr, '_get_none_or_value', return_value=True):
                with patch.object(solr, '_replication_request',
                                  side_effect=[tempdict2,
                                               tempdict1]):

                    self.assertDictEqual(solr.replication_details(), tempdict2)

                    with patch.object(solr, '_update_return_dict',
                                      return_value=tempdict1):
                        self.assertDictEqual(solr.replication_details(),
                                             tempdict1)

    def test_backup(self):
        '''
        Test to tell solr make a backup.
        '''
        tempdict = {'success': 'success', 'errors': 'errors',
                    'warnings': 'warnings', 'data': 'data'}

        with patch.object(solr, '_get_return_dict', return_value={'A': 'a'}):
            with patch.dict(solr.__opts__, {'solr.backup_path':
                                            MagicMock(return_value='A'),
                                            'solr.num_backups':
                                            MagicMock(return_value='B'),
                                            'solr.cores':
                                            MagicMock(return_value=['A'])}):
                with patch.object(os.path, 'sep', return_value='B'):
                    with patch.object(solr, '_get_none_or_value',
                                      side_effect=[None, True]):
                        with patch.object(solr, '_check_for_cores',
                                          side_effect=[True, False]):
                            with patch.object(solr, '_replication_request',
                                              return_value=tempdict):

                                with patch.dict(solr.__opts__,
                                                {'solr.cores':
                                                 MagicMock
                                                 (return_value=['A'])}):
                                    with patch.object(solr,
                                                      '_update_return_dict',
                                                      return_value='A'):
                                        self.assertDictEqual(solr.backup(),
                                                             {'A': 'a'})

                                self.assertDictEqual(solr.backup(), tempdict)

    def test_set_is_polling(self):
        '''
        Test to prevent the slaves from polling the master for updates.
        '''
        tempdict = {'success': 'success', 'errors': 'errors',
                    'warnings': 'warnings', 'data': 'data'}

        err = 'solr.set_is_polling can only be called by "slave" minions'

        with patch.object(solr, '_get_return_dict', return_value={'A': 'a'}):
            with patch.object(solr, '_is_master', side_effect=[True, False,
                                                               False]):
                with patch.object(solr, '_get_none_or_value',
                                  side_effect=[None, None, True]):
                    with patch.object(solr, '_check_for_cores',
                                      side_effect=[True, False]):

                        self.assertIsNone(solr.set_is_polling('p'))

                        with patch.dict(solr.__opts__,
                                        {'solr.cores':
                                         MagicMock(return_value='A')}):
                            with patch.object(solr, '_update_return_dict',
                                              return_value=tempdict):
                                self.assertDictEqual(solr.set_is_polling('p'),
                                                     {'A': 'a', 'errors': [err],
                                                      'success': False})

                        with patch.object(solr, '_replication_request',
                                          return_value='A'):
                            self.assertEqual(solr.set_is_polling('p'), 'A')

    def test_set_replication_enabled(self):
        '''
        Test to sets the master to ignore poll requests from the slaves.
        '''
        with patch.object(solr, '_is_master', side_effect=[False, True, True,
                                                           True]):
            with patch.object(solr, '_get_none_or_value',
                              side_effect=[None, None, True, True, True]):
                with patch.object(solr,
                                  '_get_return_dict',
                                  side_effect=[{'A': 'a'}, {}]):
                    with patch.object(solr, '_replication_request',
                                      return_value='A'):

                        self.assertDictEqual(solr.set_replication_enabled('s'),
                                             {'A': 'a'})

                        with patch.object(solr, '_check_for_cores',
                                          return_value=True):
                            with patch.dict(solr.__opts__,
                                            {'solr.cores':
                                             MagicMock(return_value='n')}):
                                self.assertEqual(solr.set_replication_enabled
                                                 ('s'), {})

                        self.assertEqual(solr.set_replication_enabled('s'), 'A')

                        self.assertEqual(solr.set_replication_enabled(False),
                                         'A')

    def test_signal(self):
        '''
        Test to signals Apache Solr to start, stop, or restart.
        '''
        self.assertEqual(solr.signal('signal'),
                         ('signal is an invalid signal. Try: one of: start,'
                         ' stop, or restart'))

    def test_reload_core(self):
        '''
        Test to load a new core from the same configuration as
        an existing registered core.
        '''
        error = ['solr.reload_core can only be called by "multi-core" minions']
        with patch.object(solr, '_check_for_cores',
                          side_effect=[False, True, True, True]):
            with patch.object(solr, '_get_none_or_value',
                              side_effect=[None, True]):
                with patch.object(solr, '_get_return_dict',
                                  return_value={'A': 'a'}):
                    with patch.object(solr, '_format_url',
                                      return_value='A'):
                        with patch.object(solr, '_http_request',
                                          return_value='A'):
                            with patch.dict(solr.__opts__,
                                            {'solr.cores':
                                             MagicMock(return_value='n')}):

                                self.assertIsNone(solr.reload_core())

                                self.assertDictEqual(solr.reload_core(),
                                                     {'A': 'a', 'errors': error,
                                                      'success': False})

                                self.assertEqual(solr.reload_core(), 'A')

    def test_core_status(self):
        '''
        Test to get the status for a given core or all cores
        if no core is specified
        '''
        error = ['solr.reload_core can only be called by "multi-core" minions']
        with patch.object(solr, '_check_for_cores',
                          side_effect=[False, True, True, True]):
            with patch.object(solr, '_get_none_or_value',
                              side_effect=[None, True]):
                with patch.object(solr, '_get_return_dict',
                                  return_value={'A': 'a'}):
                    with patch.object(solr, '_format_url',
                                      return_value='A'):
                        with patch.object(solr, '_http_request',
                                          return_value='A'):
                            with patch.dict(solr.__opts__,
                                            {'solr.cores':
                                             MagicMock(return_value='n')}):

                                self.assertIsNone(solr.core_status())

                                self.assertDictEqual(solr.core_status(),
                                                     {'A': 'a', 'errors': error,
                                                      'success': False})

                                self.assertEqual(solr.core_status(), 'A')

    def test_reload_import_config(self):
        '''
        Test to re-loads the handler config XML file.
        '''
        with patch.object(solr, '_is_master', side_effect=[False, True, True]):
            with patch.object(solr, '_get_none_or_value',
                              side_effect=[None, None, None, True, True]):
                with patch.object(solr, '_get_return_dict',
                                  return_value={'A': 'a'}):
                    with patch.object(solr, '_check_for_cores',
                                      side_effect=[True, False]):
                        with patch.object(solr, '_format_url',
                                          return_value='A'):
                            with patch.object(solr, '_http_request',
                                              return_value='A'):

                                self.assertDictEqual(solr.reload_import_config
                                                     ('h'), {'A': 'a'})

                                self.assertDictEqual(solr.reload_import_config
                                                     ('h'), {'A': 'a'})

                                self.assertEqual(solr.reload_import_config('h'),
                                                 'A')

    def test_abort_import(self):
        '''
        Test to aborts an existing import command to the specified handler.
        '''
        with patch.object(solr, '_is_master', side_effect=[False, True, True]):
            with patch.object(solr, '_get_none_or_value',
                              side_effect=[None, None, None, True, True]):
                with patch.object(solr, '_get_return_dict',
                                  return_value={'A': 'a'}):
                    with patch.object(solr, '_check_for_cores',
                                      side_effect=[True, False]):
                        with patch.object(solr, '_format_url',
                                          return_value='A'):
                            with patch.object(solr, '_http_request',
                                              return_value='A'):

                                self.assertDictEqual(solr.abort_import('h'),
                                                     {'A': 'a'})

                                self.assertDictEqual(solr.abort_import('h'),
                                                     {'A': 'a'})

                                self.assertEqual(solr.abort_import('h'), 'A')

    @patch('salt.modules.solr._format_url', MagicMock(return_value='A'))
    def test_full_import(self):
        '''
        Test to submits an import command to the specified handler using
        specified options.
        '''
        with patch.object(solr, '_is_master', side_effect=[False, True, True,
                                                           True, True, True]):
            with patch.object(solr, '_get_return_dict',
                              return_value={'A': 'a'}):
                with patch.object(solr, '_get_none_or_value',
                                  side_effect=[None, True, True, True, True]):
                    with patch.object(solr, '_check_for_cores',
                                      side_effect=[True, False, False, False,
                                                   False]):
                        with patch.object(solr,
                                          '_pre_index_check',
                                          side_effect=[{'success':
                                                        False},
                                                       {'success': True},
                                                       {'success': True}]):
                            with patch.object(solr,
                                              '_merge_options',
                                              side_effect=[{'clean': True},
                                                           {'clean': False}]):
                                with patch.object(solr,
                                                  'set_replication_enabled',
                                                  return_value={'success':
                                                                False}):
                                    with patch.object(solr,
                                                      '_http_request',
                                                      return_value='A'):

                                        self.assertDictEqual(solr.full_import
                                                             ('h'), {'A': 'a'})

                                        self.assertDictEqual(solr.full_import
                                                             ('h'), {'A': 'a'})

                                        self.assertDictEqual(solr.full_import
                                                             ('h'),
                                                             {'success': False})

                                        self.assertDictEqual(solr.full_import
                                                             ('h'), {'A': 'a'})

                                        self.assertEqual(solr.full_import
                                                         ('h'), 'A')

    @patch('salt.modules.solr._format_url', MagicMock(return_value='A'))
    def test_delta_import(self):
        '''
        Test to submits an import command to the specified handler using
        specified options.
        '''
        with patch.object(solr, '_is_master', side_effect=[False, True, True,
                                                           True, True]):
            with patch.object(solr, '_get_none_or_value',
                              side_effect=[None, True, True, True, True]):
                with patch.object(solr, '_get_return_dict',
                                  return_value={'A': 'a'}):
                    with patch.object(solr,
                                      '_pre_index_check',
                                      side_effect=[{'success': False},
                                                   {'success': True},
                                                   {'success': True},
                                                   {'success': True}]):
                        with patch.object(solr,
                                          '_merge_options',
                                          side_effect=[{'clean': True},
                                                       {'clean': False}]):
                            with patch.object(solr, '_check_for_cores',
                                              side_effect=[True, False]):
                                with patch.object(solr,
                                                  'set_replication_enabled',
                                                  return_value={'success':
                                                                False}):
                                    with patch.object(solr,
                                                      '_http_request',
                                                      return_value='A'):

                                        self.assertDictEqual(solr.delta_import
                                                             ('h'), {'A': 'a'})

                                        self.assertDictEqual(solr.delta_import
                                                             ('h'),
                                                             {'success': False})

                                        self.assertDictEqual(solr.delta_import
                                                             ('h'), {'A': 'a'})

                                        self.assertEqual(solr.delta_import
                                                         ('h'), 'A')

    def test_import_status(self):
        '''
        Test to submits an import command to the specified handler using
        specified options.
        '''
        with patch.object(solr, '_is_master', side_effect=[False, True]):
            with patch.object(solr, '_get_none_or_value',
                              side_effect=[None, True]):
                with patch.object(solr, '_get_return_dict',
                                  return_value={'A': 'a'}):
                    with patch.object(solr, '_format_url',
                                      return_value='A'):
                        with patch.object(solr, '_http_request',
                                          return_value='A'):
                            self.assertDictEqual(solr.import_status('h'),
                                                 {'A': 'a'})

                            self.assertEqual(solr.import_status('h'), 'A')
