# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing libs
from tests.support.case import ShellCase


class TestFunArgs(ShellCase):
    """
    Validate we properly have fun arguments in job cache
    - for direct minion
    - for a minion called via syndic

    XXX: would be nice to be able to salt-call from sub_minion to check the
    args are properly moved up too...
    """

    def run_test(self, minion):
        data = self.run_salt(
            "-v {} test.arg foo bar baz named=arg other=also_named".format(minion)
        )
        jid = data[0].split()[-1]
        job = self.run_run_plus("jobs.print_job", jid)["return"][jid]
        self.assertEqual(
            job["Arguments"],
            [
                "foo",
                "bar",
                "baz",
                {"__kwarg__": True, "named": "arg", "other": "also_named"},
            ],
        )

    def test_minion(self):
        """
        Test we see args for direct minion
        """
        self.run_test("minion")

    def test_sub_minion(self):
        """
        Test we see args for minion via syndic return
        """
        self.run_test("sub_minion")
