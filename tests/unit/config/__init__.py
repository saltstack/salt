# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf
import tests.support.mock as mock

import salt.config
import salt.syspaths


class ConfigTest(TestCase):

    def test_validate_bad_pillar_roots(self):
        expected = salt.config._expand_glob_path(
            [salt.syspaths.BASE_PILLAR_ROOTS_DIR]
        )
        with mock.patch('salt.config._normalize_roots') as mk:
            ret = salt.config._validate_pillar_roots(None)
            assert not mk.called
        assert ret == {'base': expected}

    def test_validate_bad_file_roots(self):
        expected = salt.config._expand_glob_path(
            [salt.syspaths.BASE_FILE_ROOTS_DIR]
        )
        with mock.patch('salt.config._normalize_roots') as mk:
            ret = salt.config._validate_file_roots(None)
            assert not mk.called
        assert ret == {'base': expected}
