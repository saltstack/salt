"""
s6 service module

This module is compatible with the :mod:`service <salt.states.service>` states,
so it can be used to maintain services using the ``provider`` argument:

.. code-block:: yaml

    myservice:
      service:
        - running
        - provider: s6

Note that the ``enabled`` argument is not available with this provider.

:codeauthor: Marek Skrobacki <skrobul@skrobul.com>
"""

import os
import re

from salt.exceptions import CommandExecutionError

__func_alias__ = {"reload_": "reload"}

VALID_SERVICE_DIRS = [
    "/service",
    "/etc/service",
]
SERVICE_DIR = None
for service_dir in VALID_SERVICE_DIRS:
    if os.path.exists(service_dir):
        SERVICE_DIR = service_dir
        break


def _service_path(name):
    """
    build service path
    """
    if not SERVICE_DIR:
        raise CommandExecutionError("Could not find service directory.")
    return "{}/{}".format(SERVICE_DIR, name)


def start(name):
    """
    Starts service via s6

    CLI Example:

    .. code-block:: bash

        salt '*' s6.start <service name>
    """
    cmd = "s6-svc -u {}".format(_service_path(name))
    return not __salt__["cmd.retcode"](cmd)


def stop(name):
    """
    Stops service via s6

    CLI Example:

    .. code-block:: bash

        salt '*' s6.stop <service name>
    """
    cmd = "s6-svc -d {}".format(_service_path(name))
    return not __salt__["cmd.retcode"](cmd)


def term(name):
    """
    Send a TERM to service via s6

    CLI Example:

    .. code-block:: bash

        salt '*' s6.term <service name>
    """
    cmd = "s6-svc -t {}".format(_service_path(name))
    return not __salt__["cmd.retcode"](cmd)


def reload_(name):
    """
    Send a HUP to service via s6

    CLI Example:

    .. code-block:: bash

        salt '*' s6.reload <service name>
    """
    cmd = "s6-svc -h {}".format(_service_path(name))
    return not __salt__["cmd.retcode"](cmd)


def restart(name):
    """
    Restart service via s6. This will stop/start service

    CLI Example:

    .. code-block:: bash

        salt '*' s6.restart <service name>
    """
    cmd = "s6-svc -t {}".format(_service_path(name))
    return not __salt__["cmd.retcode"](cmd)


def full_restart(name):
    """
    Calls s6.restart() function

    CLI Example:

    .. code-block:: bash

        salt '*' s6.full_restart <service name>
    """
    restart(name)


def status(name, sig=None):
    """
    Return the status for a service via s6, return pid if running

    CLI Example:

    .. code-block:: bash

        salt '*' s6.status <service name>
    """
    cmd = "s6-svstat {}".format(_service_path(name))
    out = __salt__["cmd.run_stdout"](cmd)
    try:
        pid = re.search(r"up \(pid (\d+)\)", out).group(1)
    except AttributeError:
        pid = ""
    return pid


def available(name):
    """
    Returns ``True`` if the specified service is available, otherwise returns
    ``False``.

    CLI Example:

    .. code-block:: bash

        salt '*' s6.available foo
    """
    return name in get_all()


def missing(name):
    """
    The inverse of s6.available.
    Returns ``True`` if the specified service is not available, otherwise returns
    ``False``.

    CLI Example:

    .. code-block:: bash

        salt '*' s6.missing foo
    """
    return name not in get_all()


def get_all():
    """
    Return a list of all available services

    CLI Example:

    .. code-block:: bash

        salt '*' s6.get_all
    """
    if not SERVICE_DIR:
        raise CommandExecutionError("Could not find service directory.")
    service_list = [
        dirname for dirname in os.listdir(SERVICE_DIR) if not dirname.startswith(".")
    ]
    return sorted(service_list)
