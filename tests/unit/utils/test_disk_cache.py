# -*- coding: utf-8 -*-
'''
    tests.unit.utils.disk_cache_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test the salt disk cache objects
'''

# Import python libs
from __future__ import absolute_import
import os.path
import shutil
import tempfile
import time

# Import Salt Testing libs
from tests.support.unit import TestCase

# Import salt libs
from salt.utils import cache


class CacheDiskTestCase(TestCase):

    def test_everything(self):
        '''
        Make sure you can instantiate, add, update, remove, expire
        '''
        try:
            tmpdir = tempfile.mkdtemp()
            path = os.path.join(tmpdir, 'CacheDisk_test')

            # test instantiation
            cd = cache.CacheDisk(0.1, path)
            self.assertIsInstance(cd, cache.CacheDisk)

            # test to make sure it looks like a dict
            self.assertNotIn('foo', cd)
            cd['foo'] = 'bar'
            self.assertIn('foo', cd)
            self.assertEqual(cd['foo'], 'bar')
            del cd['foo']
            self.assertNotIn('foo', cd)

            # test persistence
            cd['foo'] = 'bar'
            cd2 = cache.CacheDisk(0.1, path)
            self.assertIn('foo', cd2)
            self.assertEqual(cd2['foo'], 'bar')

            # test ttl
            time.sleep(0.2)
            self.assertNotIn('foo', cd)
            self.assertNotIn('foo', cd2)

        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
