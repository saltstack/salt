# -*- coding: utf-8 -*-
'''
    integration.loader.interfaces
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test Salt's loader
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
from tests.support.unit import TestCase

# Import Salt libs
import salt.ext.six as six
from salt.config import minion_config
import salt.loader

# TODO: the rest of the public interfaces


class RawModTest(TestCase):
    '''
    Test the interface of raw_mod
    '''
    def setUp(self):
        self.opts = minion_config(None)

    def tearDown(self):
        del self.opts

    def test_basic(self):
        testmod = salt.loader.raw_mod(self.opts, 'test', None)
        for k, v in six.iteritems(testmod):
            self.assertEqual(k.split('.')[0], 'test')

    def test_bad_name(self):
        testmod = salt.loader.raw_mod(self.opts, 'module_we_do_not_have', None)
        self.assertEqual(testmod, {})
