# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals
import logging
import time

log = logging.getLogger(__name__)

# To give us some leeway when making time-calculations
BLUR_FACTOR = 0.95


def wait_for(func, timeout=10, step=1, default=None, func_args=(), func_kwargs=None):
    '''
    Call `func` at regular intervals and Waits until the given function returns
    a truthy value within the given timeout and returns that value.

    @param func:
    @type func: function
    @param timeout:
    @type timeout: int | float
    @param step: Interval at which we should check for the value
    @type step: int | float
    @param default: Value that should be returned should `func` not return a truthy value
    @type default:
    @param func_args: *args for `func`
    @type func_args: list | tuple
    @param func_kwargs: **kwargs for `func`
    @type func_kwargs: dict
    @return: `default` or result of `func`
    '''
    if func_kwargs is None:
        func_kwargs = dict()
    max_time = time.time() + timeout
    # Time moves forward so we might not reenter the loop if we step too long
    step = min(step or 1, timeout) * BLUR_FACTOR

    ret = default
    while time.time() <= max_time:
        call_ret = func(*func_args, **func_kwargs)
        if call_ret:
            ret = call_ret
            break
        else:
            time.sleep(step)

            # Don't allow cases of over-stepping the timeout
            step = min(step, max_time - time.time()) * BLUR_FACTOR
    if time.time() > max_time:
        log.warning("Exceeded waiting time (%s seconds) to exectute %s", timeout, func)
    return ret
