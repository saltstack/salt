# -*- coding: utf-8 -*-
"""
tests.unit.returners.test_highstate_return
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for the Highstate Returner Cache.
"""

# Import Python libs
from __future__ import absolute_import

import json
import logging
import os

import salt.returners.highstate_return as highstate

# Import Salt libs
import salt.utils.files

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase

log = logging.getLogger(__name__)


class HighstateReturnerTestCase(TestCase, LoaderModuleMockMixin):
    """
    Tests for the highstate_return returner
    """

    output_file = os.path.join(RUNTIME_VARS.TMP, "highstate_return")

    def tearDown(self):
        os.unlink(self.output_file)

    def setup_loader_modules(self):
        return {
            highstate: {
                "__opts__": {
                    "highstate.report_everything": True,
                    "highstate.report_format": "json",
                    "highstate.report_delivery": "file",
                    "highstate.file_output": self.output_file,
                }
            }
        }

    def test_pipe_in_name(self):
        ret = {
            "fun_args": ["test"],
            "jid": "20180308201402941603",
            "return": {
                "cmd_|-test_|-echo hi | grep h\n_|-run": {
                    "comment": 'Command "echo hi | grep h\n" run',
                    "name": "echo hi | grep h\n",
                    "start_time": "20:14:03.053612",
                    "result": True,
                    "duration": 75.198,
                    "__run_num__": 0,
                    "__sls__": u"test",
                    "changes": {
                        "pid": 1429,
                        "retcode": 0,
                        "stderr": "",
                        "stdout": "hi",
                    },
                    "__id__": "test",
                }
            },
            "retcode": 0,
            "success": True,
            "fun": "state.apply",
            "id": "salt",
            "out": "highstate",
        }
        expected = [
            {
                "stats": [
                    {"total": 1},
                    {"failed": 0, "__style__": "failed"},
                    {"unchanged": 0, "__style__": "unchanged"},
                    {"changed": 1, "__style__": "changed"},
                    {"duration": 75.198},
                ],
            },
            {
                "job": [
                    {"function": "state.apply"},
                    {"arguments": ["test"]},
                    {"jid": "20180308201402941603"},
                    {"success": True},
                    {"retcode": 0},
                ],
            },
            {
                "states": [
                    {
                        "test": [
                            {"function": "cmd.run"},
                            {"name": "echo hi | grep h\n"},
                            {"result": True},
                            {"duration": 75.198},
                            {"comment": 'Command "echo hi | grep h\n" run'},
                            {
                                "changes": [
                                    {"pid": 1429},
                                    {"retcode": 0},
                                    {"stderr": ""},
                                    {"stdout": "hi"},
                                ]
                            },
                            {"started": "20:14:03.053612"},
                        ],
                        "__style__": "changed",
                    }
                ]
            },
        ]
        highstate.returner(ret)
        with salt.utils.files.fopen(self.output_file) as fh_:
            self.assertEqual(json.load(fh_), expected)
