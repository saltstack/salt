#
# Author: Tyler Johnson <tjohnson@saltstack.com>
#

"""
Idem Support
============

This module provides access to idem execution modules

.. versionadded:: 3002
"""
# Function alias to make sure not to shadow built-in's
__func_alias__ = {"exec_": "exec"}
__virtualname__ = "idem"


def __virtual__():
    if "idem.hub" in __utils__:
        return __virtualname__
    else:
        return False, "idem is not available"


def exec_(path, acct_file=None, acct_key=None, acct_profile=None, *args, **kwargs):
    """
    Call an idem execution module

    path
        The idem path of the idem execution module to run

    acct_file
        Path to the acct file used in generating idem ctx parameters.
        Defaults to the value in the ACCT_FILE environment variable.

    acct_key
        Key used to decrypt the acct file.
        Defaults to the value in the ACCT_KEY environment variable.

    acct_profile
        Name of the profile to add to idem's ctx.acct parameter.
        Defaults to the value in the ACCT_PROFILE environment variable.

    args
        Any positional arguments to pass to the idem exec function

    kwargs
        Any keyword arguments to pass to the idem exec function

    CLI Example:

    .. code-block:: bash

        salt '*' idem.exec test.ping

    :maturity:      new
    :depends:       acct, pop, pop-config, idem
    :platform:      all
    """
    hub = __utils__["idem.hub"]()

    coro = hub.idem.ex.run(
        path,
        args,
        {k: v for k, v in kwargs.items() if not k.startswith("__")},
        acct_file=acct_file or hub.OPT.acct.acct_file,
        acct_key=acct_key or hub.OPT.acct.acct_key,
        acct_profile=acct_profile or hub.OPT.acct.acct_profile or "default",
    )

    return hub.pop.Loop.run_until_complete(coro)
