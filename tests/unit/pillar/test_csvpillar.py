# -*- coding: utf-8 -*-
"""test for pillar csvpillar.py"""

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.pillar.csvpillar as csvpillar
from tests.support.mock import mock_open, patch

# Import Salt Testing libs
from tests.support.unit import TestCase


class CSVPillarTestCase(TestCase):
    def test_001_load_utf8_csv(self):
        fake_csv = "id,foo,bar\r\nminion1,foo1,bar1"
        fake_dict = {"id": "minion1", "foo": "foo1", "bar": "bar1"}
        fopen_mock = mock_open(fake_csv)
        with patch("salt.utils.files.fopen", fopen_mock):
            result = csvpillar.ext_pillar(
                mid="minion1",
                pillar=None,
                path="/fake/path/file.csv",
                idkey="id",
                namespace=None,
            )
            self.assertDictEqual(fake_dict, result)

    def test_002_load_utf8_csv_namespc(self):
        fake_csv = "id,foo,bar\r\nminion1,foo1,bar1"
        fake_dict = {"baz": {"id": "minion1", "foo": "foo1", "bar": "bar1"}}
        fopen_mock = mock_open(fake_csv)
        with patch("salt.utils.files.fopen", fopen_mock):
            result = csvpillar.ext_pillar(
                mid="minion1",
                pillar=None,
                path="/fake/path/file.csv",
                idkey="id",
                namespace="baz",
            )
            self.assertDictEqual(fake_dict, result)
