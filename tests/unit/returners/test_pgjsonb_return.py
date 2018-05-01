# -*- coding: utf-8 -*-
'''
tests.unit.returners.pgjsonb_test
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for the PGJsonb returner (pgjsonb).
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import shutil
import time
import logging
import tempfile
import time

# Import Salt Testing libs
from tests.integration import AdaptedConfigurationTestCaseMixin
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.paths import TMP
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    NO_MOCK,
    NO_MOCK_REASON,
    patch
)

# Import Salt libs
import salt.utils.files
import salt.utils.jid
import salt.utils.job
import salt.utils.platform
import salt.returners.pgjsonb as pgjsonb
from salt.ext import six

log = logging.getLogger(__name__)


@skipIf(NO_MOCK, NO_MOCK_REASON)
class PGJsonbCleanOldJobsTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Tests for the local_cache.clean_old_jobs function.
    '''
    def setup_loader_modules(self):
        return {pgjsonb: {'__opts__': {'keep_jobs': 1, 'archive_jobs': 0}}}

    def test_clean_old_jobs_purge(self):
        '''
        Tests that the function returns None when no jid_root is found.
        '''
        connect_mock = MagicMock()
        with patch.object(pgjsonb, '_get_serv', connect_mock):
            with patch.dict(pgjsonb.__salt__, {'config.option': MagicMock()}):
                ret = pgjsonb.clean_old_jobs()
                self.assertEqual(ret, None)

    def test_clean_old_jobs_archive(self):
        '''
        Tests that the function returns None when no jid_root is found.
        '''
        connect_mock = MagicMock()
        with patch.object(pgjsonb, '_get_serv', connect_mock):
            with patch.dict(pgjsonb.__salt__, {'config.option': MagicMock()}):
                with patch.dict(pgjsonb.__opts__, {'archive_jobs': 1}):
                    ret = pgjsonb.clean_old_jobs()
                    self.assertEqual(ret, None)
