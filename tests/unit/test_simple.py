# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
from tests.support.unit import TestCase, expectedFailure
from tests.support.helpers import ensure_in_syspath

ensure_in_syspath('../')


class SimpleTest(TestCase):
    def test_success(self):
        assert True

    @expectedFailure
    def test_fail(self):
        assert False

if __name__ == '__main__':
    from integration import run_tests
    run_tests(SimpleTest, needs_daemon=False)
