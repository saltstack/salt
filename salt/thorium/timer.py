"""
Allow flow-based timers inside Thorium formulas.

These timers keep state across multiple Thorium evaluation cycles, which makes
them useful for cooldowns, delayed reactions, and rate limiting.
"""

import time


def hold(name, seconds):
    """
    Wait for a given period of time, then fire a result of True, requiring
    this state allows for an action to be blocked for evaluation based on
    time.

    A common pattern is to require a ``check.*`` state first and then require
    this timer from the action state so the action only runs after the hold
    period has elapsed.

    USAGE:

    .. code-block:: yaml

        hold_on_a_moment:
          timer.hold:
            - seconds: 30

        cooldown:
          timer.hold:
            - seconds: 900
            - require:
              - check: repeated_failures
    """
    ret = {"name": name, "result": False, "comment": "", "changes": {}}
    start = time.time()
    if "timer" not in __context__:
        __context__["timer"] = {}
    if name not in __context__["timer"]:
        __context__["timer"][name] = start
    if (start - __context__["timer"][name]) > seconds:
        ret["result"] = True
        __context__["timer"][name] = start
    return ret
