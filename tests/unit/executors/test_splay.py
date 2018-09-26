# -*- coding: utf-8 -*-

from __future__ import absolute_import, print_function, unicode_literals

# Import Salt libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase

import salt.executors.splay as splay_exec


class SplayTestCase(TestCase, LoaderModuleMockMixin):

    def setup_loader_modules(self):
        return {
            splay_exec: {
                '__grains__': {'id': 'foo'},
            }
        }

    def test__get_hash(self):
        # We just want to make sure that this function does not result in an
        # error due to passing a unicode value to bytearray()
        assert splay_exec._get_hash()
