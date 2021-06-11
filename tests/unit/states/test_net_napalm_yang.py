# -*- coding: utf-8 -*-
"""
    :codeauthor: Anthony Shaw <anthonyshaw@apache.org>
"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.states.net_napalm_yang as netyang

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase

TEST_DATA = {"foo": "bar"}


class NetyangTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {netyang: {}}

    def test_managed(self):
        ret = {"changes": {}, "comment": "Loaded.", "name": "test", "result": False}
        parse = MagicMock(return_value="abcdef")
        temp_file = MagicMock(return_value="")
        compliance_report = MagicMock(return_value={"complies": False})
        load_config = MagicMock(return_value={"comment": "Loaded."})
        file_remove = MagicMock()

        with patch("salt.utils.files.fopen"):
            with patch.dict(
                netyang.__salt__,
                {
                    "temp.file": temp_file,
                    "napalm_yang.parse": parse,
                    "napalm_yang.load_config": load_config,
                    "napalm_yang.compliance_report": compliance_report,
                    "file.remove": file_remove,
                },
            ):
                with patch.dict(netyang.__opts__, {"test": False}):
                    self.assertDictEqual(
                        netyang.managed("test", "test", models=("model1",)), ret
                    )
                    assert parse.called
                    assert temp_file.called
                    assert compliance_report.called
                    assert load_config.called
                    assert file_remove.called

    def test_configured(self):
        ret = {"changes": {}, "comment": "Loaded.", "name": "test", "result": False}
        load_config = MagicMock(return_value={"comment": "Loaded."})

        with patch("salt.utils.files.fopen"):
            with patch.dict(netyang.__salt__, {"napalm_yang.load_config": load_config}):
                with patch.dict(netyang.__opts__, {"test": False}):
                    self.assertDictEqual(
                        netyang.configured("test", "test", models=("model1",)), ret
                    )

                    assert load_config.called
