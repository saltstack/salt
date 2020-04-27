# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging
import time

# Import Salt libs
from salt.utils.timeout import wait_for

# Import test libs
from tests.support.unit import TestCase

log = logging.getLogger(__name__)


def return_something_after(seconds, something=True):
    start = time.time()
    end = start + seconds
    log.debug("Will return %s at %s", something, end)

    def actual():
        t = time.time()
        condition = t >= end
        log.debug("Return something at %s ? %s", t, condition)
        if condition:
            return something
        else:
            return False

    return actual


def return_args_after(seconds):
    start = time.time()
    end = start + seconds

    def actual(*args):
        if time.time() >= end:
            return args
        else:
            return False

    return actual


def return_kwargs_after(seconds):
    start = time.time()
    end = start + seconds

    def actual(**kwargs):
        if time.time() >= end:
            return kwargs
        else:
            return False

    return actual


class WaitForTests(TestCase):
    def setUp(self):
        self.true_after_1s = return_something_after(1)
        self.self_after_1s = return_something_after(1, something=self)

    def tearDown(self):
        del self.true_after_1s
        del self.self_after_1s

    def test_wait_for_true(self):
        ret = wait_for(self.true_after_1s, timeout=2, step=0.5)
        self.assertTrue(ret)

    def test_wait_for_self(self):
        ret = wait_for(self.self_after_1s, timeout=2, step=0.5)
        self.assertEqual(ret, self)

    def test_wait_for_too_long(self):
        ret = wait_for(self.true_after_1s, timeout=0.5, step=0.1, default=False)
        self.assertFalse(ret)

    def test_wait_for_with_big_step(self):
        ret = wait_for(self.true_after_1s, timeout=1.5, step=2)
        self.assertTrue(ret)

    def test_wait_for_custom_args(self):
        args_after_1s = return_args_after(1)
        args = ("one", "two")
        ret = wait_for(args_after_1s, timeout=2, step=0.5, func_args=args)
        self.assertEqual(ret, args)

    def test_wait_for_custom_kwargs(self):
        kwargs_after_1s = return_kwargs_after(1)
        kwargs = {"one": 1, "two": 2}
        ret = wait_for(kwargs_after_1s, timeout=2, step=0.5, func_kwargs=kwargs)
        self.assertEqual(ret, kwargs)

    def test_return_false(self):
        ret = self.true_after_1s()
        self.assertFalse(ret)
