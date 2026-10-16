"""
Direct call executor module
"""

import salt.utils.secret


def execute(opts, data, func, args, kwargs):
    """
    Directly calls the given function with arguments.

    While the job runs, ``pillar.get`` and friends return real values to code
    that calls them through ``__salt__`` without passing ``unmask``; repr() and
    logging of pillar data stay redacted. Jobs whose own function is a
    ``pillar.*`` function keep the masked default, since their return value is
    what the user sees.
    """
    module = str((data or {}).get("fun") or "").split(".", 1)[0]
    if module == "pillar":
        return func(*args, **kwargs)
    token = salt.utils.secret.mask_values.set(False)
    try:
        return func(*args, **kwargs)
    finally:
        salt.utils.secret.mask_values.reset(token)
