# -*- coding: utf-8 -*-
"""
    :codeauthor: Joao Mesquita <jmesquita@sangoma.com>
"""

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

from salt import fileserver

# Import Salt Testing libs
from tests.support.unit import TestCase


class MapDiffTestCase(TestCase):
    def test_diff_with_diffent_keys(self):
        """
        Test that different maps are indeed reported different
        """
        map1 = {"file1": 1234}
        map2 = {"file2": 1234}
        assert fileserver.diff_mtime_map(map1, map2) is True

    def test_diff_with_diffent_values(self):
        """
        Test that different maps are indeed reported different
        """
        map1 = {"file1": 12345}
        map2 = {"file1": 1234}
        assert fileserver.diff_mtime_map(map1, map2) is True
