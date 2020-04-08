# -*- coding: utf-8 -*-
"""
Test the grains module
"""

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging
import os
import pprint
import time

# Import Salt libs
from salt.ext.six.moves import range

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.helpers import flaky
from tests.support.unit import skipIf

log = logging.getLogger(__name__)


class TestModulesGrains(ModuleCase):
    """
    Test the grains module
    """

    def test_items(self):
        """
        grains.items
        """
        opts = self.minion_opts
        self.assertEqual(
            self.run_function("grains.items")["test_grain"],
            opts["grains"]["test_grain"],
        )

    def test_item(self):
        """
        grains.item
        """
        opts = self.minion_opts
        self.assertEqual(
            self.run_function("grains.item", ["test_grain"])["test_grain"],
            opts["grains"]["test_grain"],
        )

    def test_ls(self):
        """
        grains.ls
        """
        check_for = (
            "cpu_flags",
            "cpu_model",
            "cpuarch",
            "domain",
            "fqdn",
            "fqdns",
            "gid",
            "groupname",
            "host",
            "kernel",
            "kernelrelease",
            "kernelversion",
            "localhost",
            "mem_total",
            "num_cpus",
            "os",
            "os_family",
            "path",
            "pid",
            "ps",
            "pythonpath",
            "pythonversion",
            "saltpath",
            "saltversion",
            "uid",
            "username",
            "virtual",
        )
        lsgrains = self.run_function("grains.ls")
        os = self.run_function("grains.get", ["os"])
        for grain in check_for:
            if os == "Windows" and grain in ["cpu_flags", "gid", "groupname", "uid"]:
                continue
            self.assertTrue(grain in lsgrains)

    @skipIf(
        os.environ.get("TRAVIS_PYTHON_VERSION", None) is not None,
        "Travis environment can't keep up with salt refresh",
    )
    def test_set_val(self):
        """
        test grains.set_val
        """
        self.assertEqual(
            self.run_function("grains.setval", ["setgrain", "grainval"]),
            {"setgrain": "grainval"},
        )
        time.sleep(5)
        ret = self.run_function("grains.item", ["setgrain"])
        if not ret:
            # Sleep longer, sometimes test systems get bogged down
            time.sleep(20)
            ret = self.run_function("grains.item", ["setgrain"])
        self.assertTrue(ret)

    def test_get(self):
        """
        test grains.get
        """
        self.assertEqual(self.run_function("grains.get", ["level1:level2"]), "foo")

    def test_get_core_grains(self):
        """
        test to ensure some core grains are returned
        """
        grains = ("os", "os_family", "osmajorrelease", "osrelease", "osfullname", "id")
        os = self.run_function("grains.get", ["os"])

        for grain in grains:
            get_grain = self.run_function("grains.get", [grain])
            log.debug("Value of '%s' grain: '%s'", grain, get_grain)
            if os == "Arch" and grain in ["osmajorrelease"]:
                self.assertEqual(get_grain, "")
                continue
            if os == "Windows" and grain in ["osmajorrelease"]:
                self.assertEqual(get_grain, "")
                continue

            self.assertTrue(get_grain)

    def test_get_grains_int(self):
        """
        test to ensure int grains
        are returned as integers
        """
        grains = ["num_cpus", "mem_total", "num_gpus", "uid"]
        os = self.run_function("grains.get", ["os"])
        for grain in grains:
            get_grain = self.run_function("grains.get", [grain])
            if os == "Windows" and grain in ["uid"]:
                self.assertEqual(get_grain, "")
                continue
            self.assertIsInstance(
                get_grain, int, msg="grain: {0} is not an int or empty".format(grain)
            )


class GrainsAppendTestCase(ModuleCase):
    """
    Tests written specifically for the grains.append function.
    """

    GRAIN_KEY = "salttesting-grain-key"
    GRAIN_VAL = "my-grain-val"

    def setUp(self):
        # Start off with an empty list
        self.run_function("grains.setval", [self.GRAIN_KEY, []])
        if not self.wait_for_grain(self.GRAIN_KEY, []):
            raise Exception("Failed to set grain")
        self.addCleanup(self.cleanup_grain)

    def cleanup_grain(self):
        self.run_function("grains.setval", [self.GRAIN_KEY, []])
        if not self.wait_for_grain(self.GRAIN_KEY, []):
            raise Exception("Failed to set grain")

    def test_grains_append(self):
        """
        Tests the return of a simple grains.append call.
        """
        ret = self.run_function("grains.append", [self.GRAIN_KEY, self.GRAIN_VAL])
        self.assertEqual(ret[self.GRAIN_KEY], [self.GRAIN_VAL])

    def test_grains_append_val_already_present(self):
        """
        Tests the return of a grains.append call when the value is already
        present in the grains list.
        """
        msg = "The val {0} was already in the list " "salttesting-grain-key".format(
            self.GRAIN_VAL
        )

        # First, make sure the test grain is present
        ret = self.run_function("grains.append", [self.GRAIN_KEY, self.GRAIN_VAL])
        self.assertEqual(ret[self.GRAIN_KEY], [self.GRAIN_VAL])

        # Now try to append again
        ret = self.run_function("grains.append", [self.GRAIN_KEY, self.GRAIN_VAL])
        self.assertTrue(self.wait_for_grain(self.GRAIN_KEY, [self.GRAIN_VAL]))
        if not ret or isinstance(ret, dict):
            # Sleep for a bit, sometimes the second "append" runs too quickly
            time.sleep(5)
            ret = self.run_function("grains.append", [self.GRAIN_KEY, self.GRAIN_VAL])

        assert msg == ret

    @flaky
    def test_grains_append_val_is_list(self):
        """
        Tests the return of a grains.append call when val is passed in as a list.
        """
        # Start off with an empty list, don't know if the flaky decorator runs the setUp function or not...
        self.run_function("grains.setval", [self.GRAIN_KEY, []])
        second_grain = self.GRAIN_VAL + "-2"
        ret = self.run_function(
            "grains.append", [self.GRAIN_KEY, [self.GRAIN_VAL, second_grain]]
        )
        self.assertEqual(ret[self.GRAIN_KEY], [self.GRAIN_VAL, second_grain])

    def test_grains_append_call_twice(self):
        """
        Tests the return of a grains.append call when the value is already present
        but also ensure the grain is not listed twice.
        """
        # First, add the test grain.
        append_1 = self.run_function("grains.append", [self.GRAIN_KEY, self.GRAIN_VAL])

        # Call the function again, which results in a string message, as tested in
        # test_grains_append_val_already_present above.
        append_2 = self.run_function("grains.append", [self.GRAIN_KEY, self.GRAIN_VAL])

        # Now make sure the grain doesn't show up twice.
        grains = self.run_function("grains.items")
        count = 0
        for grain in grains:
            if grain == self.GRAIN_KEY:
                count += 1

        # We should only have hit the grain key once.
        self.assertEqual(
            count,
            1,
            msg="Count did not match({}!=1) while looking for key '{}'.\nFirst append return:\n{}\nSecond append return:\n{}".format(
                count,
                self.GRAIN_KEY,
                pprint.pformat(append_1),
                pprint.pformat(append_2),
            ),
        )

    def wait_for_grain(self, key, val, timeout=60, sleep=0.3):
        start = time.time()
        while time.time() - start <= timeout:
            ret = self.run_function("grains.get", [key])
            if ret == val:
                return True
            time.sleep(sleep)
        return False

    def test_grains_remove_add(self):
        second_grain = self.GRAIN_VAL + "-2"
        ret = self.run_function("grains.get", [self.GRAIN_KEY])
        self.assertEqual(ret, [])

        for i in range(10):
            ret = self.run_function("grains.setval", [self.GRAIN_KEY, []])
            self.assertEqual(ret[self.GRAIN_KEY], [])
            self.wait_for_grain(self.GRAIN_KEY, [])
            ret = self.run_function("grains.append", [self.GRAIN_KEY, self.GRAIN_VAL])
            self.assertEqual(ret[self.GRAIN_KEY], [self.GRAIN_VAL])
            self.assertEqual(ret[self.GRAIN_KEY], [self.GRAIN_VAL])

            ret = self.run_function("grains.setval", [self.GRAIN_KEY, []])
            self.wait_for_grain(self.GRAIN_KEY, [])
            self.assertTrue(self.wait_for_grain(self.GRAIN_KEY, []))
            ret = self.run_function(
                "grains.append", [self.GRAIN_KEY, [self.GRAIN_VAL, second_grain]]
            )
            self.assertEqual(ret[self.GRAIN_KEY], [self.GRAIN_VAL, second_grain])
            self.assertEqual(ret[self.GRAIN_KEY], [self.GRAIN_VAL, second_grain])
