"""
Transactional executor module

.. versionadded:: 3004

"""

import os

import salt.utils.path

# Functions that are mapped into an equivalent one in
# transactional_update module
DELEGATION_MAP = {
    "state.single": "transactional_update.single",
    "state.sls": "transactional_update.sls",
    "state.apply": "transactional_update.apply",
    "state.highstate": "transactional_update.highstate",
}

# By default, all modules and functions are executed outside the
# transaction.  The next two sets will enumerate the exceptions that
# will be routed to transactional_update.call()
DEFAULT_DELEGATED_MODULES = [
    "ansible",
    "cabal",
    "chef",
    "cmd",
    "composer",
    "cp",
    "cpan",
    "cyg",
    "file",
    "freeze",
    "nix",
    "npm",
    "pip",
    "pkg",
    "puppet",
    "pyenv",
    "rbenv",
    "scp",
]
DEFAULT_DELEGATED_FUNCTIONS = []


def __virtual__():
    if salt.utils.path.which("transactional-update"):
        return True
    else:
        return (False, "transactional_update executor requires a transactional system")


def execute(opts, data, func, args, kwargs):
    """Delegate into transactional_update module

    The ``transactional_update`` module support the execution of
    functions inside a transaction, as support apply a state (via
    ``apply``, ``sls``, ``single`` or ``highstate``).

    This execution module can be used to route some Salt modules and
    functions to be executed inside the transaction snapshot.

    Add this executor in the minion configuration file:

    .. code-block:: yaml

        module_executors:
          - transactional_update
          - direct_call

    Or use the command line parameter:

    .. code-block:: bash

        salt-call --module-executors='[transactional_update, direct_call]' test.version

    You can also schedule a reboot if needed:

    .. code-block:: bash

        salt-call --module-executors='[transactional_update]' state.sls stuff activate_transaction=True

    There are some configuration parameters supported:

    .. code-block:: yaml

       # Replace the list of default modules that all the functions
       # are delegated to `transactional_update.call()`
       delegated_modules: [cmd, pkg]

       # Replace the list of default functions that are delegated to
       # `transactional_update.call()`
       delegated_functions: [pip.install]

       # Expand the default list of modules
       add_delegated_modules: [ansible]

       # Expand the default list of functions
       add_delegated_functions: [file.copy]

    """
    inside_transaction = os.environ.get("TRANSACTIONAL_UPDATE")

    fun = data["fun"]
    module, _ = fun.split(".")

    delegated_modules = set(opts.get("delegated_modules", DEFAULT_DELEGATED_MODULES))
    delegated_functions = set(
        opts.get("delegated_functions", DEFAULT_DELEGATED_FUNCTIONS)
    )
    if "executor_opts" in data:
        delegated_modules |= set(data["executor_opts"].get("add_delegated_modules", []))
        delegated_functions |= set(
            data["executor_opts"].get("add_delegated_functions", [])
        )
    else:
        delegated_modules |= set(opts.get("add_delegated_modules", []))
        delegated_functions |= set(opts.get("add_delegated_functions", []))

    if fun in DELEGATION_MAP and not inside_transaction:
        result = __executors__["direct_call.execute"](
            opts, data, __salt__[DELEGATION_MAP[fun]], args, kwargs
        )
    elif (
        module in delegated_modules or fun in delegated_functions
    ) and not inside_transaction:
        result = __salt__["transactional_update.call"](fun, *args, **kwargs)
    else:
        result = __executors__["direct_call.execute"](opts, data, func, args, kwargs)

    return result
