# -*- coding: utf-8 -*-
# see  tests/integration/client/test_runner.py


def call_other_runner():
    return __salt__['testrunner2.other_runner']()


def return_globals():
    return list(globals().keys())
