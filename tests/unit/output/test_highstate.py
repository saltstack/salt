# -*- coding: utf-8 -*-
"""
unittests for highstate outputter
"""

# Import Python Libs
from __future__ import absolute_import

import salt.output.highstate as highstate

# Import Salt Libs
import salt.utils.stringutils

# Import 3rd-party libs
from salt.ext import six

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase


class JsonTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.output.highstate
    """

    def setup_loader_modules(self):
        return {
            highstate: {
                "__opts__": {
                    "extension_modules": "",
                    "optimization_order": [0, 1, 2],
                    "color": False,
                }
            }
        }

    def setUp(self):
        self.data = {
            "data": {
                "master": {
                    "salt_|-call_sleep_state_|-call_sleep_state_|-state": {
                        "__id__": "call_sleep_state",
                        "__jid__": "20170418153529810135",
                        "__run_num__": 0,
                        "__sls__": "orch.simple",
                        "changes": {
                            "out": "highstate",
                            "ret": {
                                "minion": {
                                    "module_|-simple-ping_|-test.ping_|-run": {
                                        "__id__": "simple-ping",
                                        "__run_num__": 0,
                                        "__sls__": "simple-ping",
                                        "changes": {"ret": True},
                                        "comment": "Module function test.ping executed",
                                        "duration": 56.179,
                                        "name": "test.ping",
                                        "result": True,
                                        "start_time": "15:35:31.282099",
                                    }
                                },
                                "sub_minion": {
                                    "module_|-simple-ping_|-test.ping_|-run": {
                                        "__id__": "simple-ping",
                                        "__run_num__": 0,
                                        "__sls__": "simple-ping",
                                        "changes": {"ret": True},
                                        "comment": "Module function test.ping executed",
                                        "duration": 54.103,
                                        "name": "test.ping",
                                        "result": True,
                                        "start_time": "15:35:31.005606",
                                    }
                                },
                            },
                        },
                        "comment": "States ran successfully. Updating sub_minion, minion.",
                        "duration": 1638.047,
                        "name": "call_sleep_state",
                        "result": True,
                        "start_time": "15:35:29.762657",
                    }
                }
            },
            "outputter": "highstate",
            "retcode": 0,
        }
        self.addCleanup(delattr, self, "data")

    def test_default_output(self):
        ret = highstate.output(self.data)
        self.assertIn("Succeeded: 1 (changed=1)", ret)
        self.assertIn("Failed:    0", ret)
        self.assertIn("Total states run:     1", ret)

    def test_output_comment_is_not_unicode(self):
        entry = None
        for key in (
            "data",
            "master",
            "salt_|-call_sleep_state_|-call_sleep_state_|-state",
            "changes",
            "ret",
            "minion",
            "module_|-simple-ping_|-test.ping_|-run",
        ):
            if entry is None:
                entry = self.data[key]
                continue
            entry = entry[key]
        if six.PY2:
            entry["comment"] = salt.utils.stringutils.to_unicode(entry["comment"])
        else:
            entry["comment"] = salt.utils.stringutils.to_bytes(entry["comment"])
        ret = highstate.output(self.data)
        self.assertIn("Succeeded: 1 (changed=1)", ret)
        self.assertIn("Failed:    0", ret)
        self.assertIn("Total states run:     1", ret)


# this should all pass the above tests
class JsonNestedTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for nested salt.output.highstate (ie orchestrations calling other orchs)
    """

    def setup_loader_modules(self):
        return {
            highstate: {
                "__opts__": {
                    "extension_modules": "",
                    "color": False,
                    "optimization_order": [0, 1, 2],
                }
            }
        }

    def setUp(self):
        self.data = {
            "outputter": "highstate",
            "data": {
                "local_master": {
                    "salt_|-nested_|-state.orchestrate_|-runner": {
                        "comment": "Runner function 'state.orchestrate' executed.",
                        "name": "state.orchestrate",
                        "__orchestration__": True,
                        "start_time": "09:22:53.158742",
                        "result": True,
                        "duration": 980.694,
                        "__run_num__": 0,
                        "__jid__": "20180326092253538853",
                        "__sls__": "orch.test.nested",
                        "changes": {
                            "return": {
                                "outputter": "highstate",
                                "data": {
                                    "local_master": {
                                        "test_|-always-passes-with-changes_|-oinaosf_|-succeed_with_changes": {
                                            "comment": "Success!",
                                            "name": "oinaosf",
                                            "start_time": "09:22:54.128415",
                                            "result": True,
                                            "duration": 0.437,
                                            "__run_num__": 0,
                                            "__sls__": "orch.test.changes",
                                            "changes": {
                                                "testing": {
                                                    "new": "Something pretended to change",
                                                    "old": "Unchanged",
                                                }
                                            },
                                            "__id__": "always-passes-with-changes",
                                        },
                                        "test_|-always-passes_|-fasdfasddfasdfoo_|-succeed_without_changes": {
                                            "comment": "Success!",
                                            "name": "fasdfasddfasdfoo",
                                            "start_time": "09:22:54.128986",
                                            "result": True,
                                            "duration": 0.25,
                                            "__run_num__": 1,
                                            "__sls__": "orch.test.changes",
                                            "changes": {},
                                            "__id__": "always-passes",
                                        },
                                    }
                                },
                                "retcode": 0,
                            }
                        },
                        "__id__": "nested",
                    }
                }
            },
            "retcode": 0,
        }

        self.addCleanup(delattr, self, "data")

    def test_nested_output(self):
        ret = highstate.output(self.data)
        self.assertIn("Succeeded: 1 (changed=1)", ret)
        self.assertIn("Failed:    0", ret)
        self.assertIn("Total states run:     1", ret)

        # the whitespace is relevant in this case, it is testing that it is nested
        self.assertIn("                        ID: always-passes-with-changes", ret)
        self.assertIn("                   Started: 09:22:54.128415", ret)
        self.assertIn("              Succeeded: 2 (changed=1)", ret)
        self.assertIn("              Failed:    0", ret)
        self.assertIn("              Total states run:     2", ret)
