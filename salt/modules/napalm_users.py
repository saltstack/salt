"""
NAPALM Users
============

Manages the configuration of the users on network devices.

:codeauthor: Mircea Ulinic <ping@mirceaulinic.net>
:maturity:   new
:depends:    napalm
:platform:   unix

Dependencies
------------
- :mod:`NAPALM proxy minion <salt.proxy.napalm>`

.. seealso::
    :mod:`Users management state <salt.states.netusers>`

.. versionadded:: 2016.11.0
"""

import inspect
import logging
import os.path

# import NAPALM utils
import salt.utils.napalm
from salt.utils.napalm import proxy_napalm_wrap

log = logging.getLogger(__file__)


# ----------------------------------------------------------------------------------------------------------------------
# module properties
# ----------------------------------------------------------------------------------------------------------------------

__virtualname__ = "users"
__proxyenabled__ = ["napalm"]
__virtual_aliases__ = ("napalm_users",)
# uses NAPALM-based proxy to interact with network devices

# ----------------------------------------------------------------------------------------------------------------------
# property functions
# ----------------------------------------------------------------------------------------------------------------------


def __virtual__():
    """
    NAPALM library must be installed for this module to work and run in a (proxy) minion.
    """
    return salt.utils.napalm.virtual(__opts__, __virtualname__, __file__)


# ----------------------------------------------------------------------------------------------------------------------
# helper functions -- will not be exported
# ----------------------------------------------------------------------------------------------------------------------


def _napalm_template_path(napalm_device, template_name):
    """
    Return the absolute path to a NAPALM-shipped Jinja template (e.g.
    ``set_users``) for the driver backing this proxy, or ``None`` if the driver
    does not ship one.

    NAPALM keeps these config templates in a ``templates`` directory next to
    each driver module and resolves them by walking the driver class MRO
    (concrete driver first, then its bases). ``net.load_template`` used to route
    bare template names into NAPALM's own renderer, but that path was removed in
    the Sodium release; resolving the template to an absolute path lets the
    still-supported Salt rendering pipeline render it instead.
    """
    driver = napalm_device.get("DRIVER") if napalm_device else None
    if driver is None:
        return None
    for klass in type(driver).__mro__:
        try:
            module_file = inspect.getfile(klass)
        except (TypeError, OSError):
            # Built-in types (e.g. ``object``) raise TypeError; classes without
            # an on-disk source (``__main__``, frozen) raise OSError. Neither
            # can ship a template dir, so move on.
            continue
        candidate = os.path.join(
            os.path.dirname(module_file), "templates", f"{template_name}.j2"
        )
        if os.path.isfile(candidate):
            return candidate
    return None


# ----------------------------------------------------------------------------------------------------------------------
# callable functions
# ----------------------------------------------------------------------------------------------------------------------


@proxy_napalm_wrap
def config(**kwargs):  # pylint: disable=unused-argument
    """
    Returns the configuration of the users on the device

    CLI Example:

    .. code-block:: bash

        salt '*' users.config

    Output example:

    .. code-block:: python

        {
            'mircea': {
                'level': 15,
                'password': '$1$0P70xKPa$4jt5/10cBTckk6I/w/',
                'sshkeys': [
                    'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC4pFn+shPwTb2yELO4L7NtQrKOJXNeCl1je\
                    l9STXVaGnRAnuc2PXl35vnWmcUq6YbUEcgUTRzzXfmelJKuVJTJIlMXii7h2xkbQp0YZIEs4P\
                    8ipwnRBAxFfk/ZcDsN3mjep4/yjN56ejk345jhk345jk345jk341p3A/9LIL7l6YewLBCwJj6\
                    D+fWSJ0/YW+7oH17Fk2HH+tw0L5PcWLHkwA4t60iXn16qDbIk/ze6jv2hDGdCdz7oYQeCE55C\
                    CHOHMJWYfN3jcL4s0qv8/u6Ka1FVkV7iMmro7ChThoV/5snI4Ljf2wKqgHH7TfNaCfpU0WvHA\
                    nTs8zhOrGScSrtb mircea@master-roshi'
                ]
            }
        }
    """

    return salt.utils.napalm.call(
        napalm_device, "get_users", **{}  # pylint: disable=undefined-variable
    )


@proxy_napalm_wrap
def set_users(
    users, test=False, commit=True, **kwargs
):  # pylint: disable=unused-argument
    """
    Configures users on network devices.

    :param users: Dictionary formatted as the output of the function config()

    :param test: Dry run? If set as True, will apply the config, discard and
        return the changes. Default: False

    :param commit: Commit? (default: True) Sometimes it is not needed to commit
        the config immediately after loading the changes. E.g.: a state loads a
        couple of parts (add / remove / update) and would not be optimal to
        commit after each operation.  Also, from the CLI when the user needs to
        apply the similar changes before committing, can specify commit=False
        and will not discard the config.

    :raise MergeConfigException: If there is an error on the configuration sent.
    :return a dictionary having the following keys:

    - result (bool): if the config was applied successfully. It is `False` only
      in case of failure. In case there are no changes to be applied and
      successfully performs all operations it is still `True` and so will be
      the `already_configured` flag (example below)
    - comment (str): a message for the user
    - already_configured (bool): flag to check if there were no changes applied
    - diff (str): returns the config changes applied

    CLI Example:

    .. code-block:: bash

        salt '*' users.set_users "{'mircea': {}}"
    """

    # pylint: disable=undefined-variable
    template_path = _napalm_template_path(napalm_device, "set_users")
    if template_path is None:
        driver_name = napalm_device.get("DRIVER_NAME") if napalm_device else None
        return {
            "result": False,
            "out": None,
            "comment": (
                f"The 'set_users' template is not available for the"
                f" '{driver_name}' driver."
            ),
        }
    return __salt__["net.load_template"](
        template_path,
        users=users,
        test=test,
        commit=commit,
        inherit_napalm_device=napalm_device,
    )
    # pylint: enable=undefined-variable


@proxy_napalm_wrap
def delete_users(
    users, test=False, commit=True, **kwargs
):  # pylint: disable=unused-argument
    """
    Removes users from the configuration of network devices.

    :param users: Dictionary formatted as the output of the function config()
    :param test: Dry run? If set as True, will apply the config, discard and return the changes. Default: False
    :param commit: Commit? (default: True) Sometimes it is not needed to commit the config immediately
        after loading the changes. E.g.: a state loads a couple of parts (add / remove / update)
        and would not be optimal to commit after each operation.
        Also, from the CLI when the user needs to apply the similar changes before committing,
        can specify commit=False and will not discard the config.
    :raise MergeConfigException: If there is an error on the configuration sent.
    :return a dictionary having the following keys:
        - result (bool): if the config was applied successfully. It is `False`
          only in case of failure. In case there are no changes to be applied
          and successfully performs all operations it is still `True` and so
          will be the `already_configured` flag (example below)
        - comment (str): a message for the user
        - already_configured (bool): flag to check if there were no changes applied
        - diff (str): returns the config changes applied

    CLI Example:

    .. code-block:: bash

        salt '*' users.delete_users "{'mircea': {}}"
    """

    # pylint: disable=undefined-variable
    template_path = _napalm_template_path(napalm_device, "delete_users")
    if template_path is None:
        driver_name = napalm_device.get("DRIVER_NAME") if napalm_device else None
        return {
            "result": False,
            "out": None,
            "comment": (
                f"The 'delete_users' template is not available for the"
                f" '{driver_name}' driver."
            ),
        }
    return __salt__["net.load_template"](
        template_path,
        users=users,
        test=test,
        commit=commit,
        inherit_napalm_device=napalm_device,
    )
    # pylint: enable=undefined-variable
