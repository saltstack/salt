# -*- coding: utf-8 -*-
"""
unit tests for salt.utils.job
"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

import salt.minion

# Import Salt Libs
import salt.utils.job as job

# Import 3rd-party libs
from salt.ext import six

# Import Salt Testing Libs
from tests.support.mock import patch
from tests.support.unit import TestCase, skipIf


class MockMasterMinion(object):
    def return_mock_jobs(self):
        return self.mock_jobs_cache

    opts = {"job_cache": True, "ext_job_cache": None, "master_job_cache": "foo"}
    mock_jobs_cache = {}
    returners = {
        "foo.save_load": lambda *args, **kwargs: True,
        "foo.prep_jid": lambda *args, **kwargs: True,
        "foo.get_load": lambda *args, **kwargs: True,
        "foo.returner": lambda *args, **kwargs: True,
    }

    def __init__(self, *args, **kwargs):
        pass


class JobTest(TestCase):
    """
    Validate salt.utils.job
    """

    @skipIf(not six.PY3, "Can only assertLogs in PY3")
    def test_store_job_exception_handled(self):
        """
        test store_job exception handling
        """
        for func in ["foo.save_load", "foo.prep_jid", "foo.returner"]:

            def raise_exception(*arg, **kwarg):
                raise Exception("expected")

            with patch.object(
                salt.minion, "MasterMinion", MockMasterMinion
            ), patch.dict(MockMasterMinion.returners, {func: raise_exception}), patch(
                "salt.utils.verify.valid_id", return_value=True
            ):
                with self.assertLogs("salt.utils.job", level="CRITICAL") as logged:
                    job.store_job(
                        MockMasterMinion.opts,
                        {
                            "jid": "20190618090114890985",
                            "return": {"success": True},
                            "id": "a",
                        },
                    )
                    self.assertIn(
                        "The specified 'foo' returner threw a stack trace",
                        logged.output[0],
                    )
