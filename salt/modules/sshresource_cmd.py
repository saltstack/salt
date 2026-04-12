"""
Execution module override for the ``ssh`` resource type.

This module is loaded into the per-type execution-module loader whenever the
``resource_type`` in opts is ``"ssh"``.  It shadows the standard
``salt.modules.cmdmod`` and ``salt.modules.test`` functions for jobs that
are dispatched to SSH resources, delegating the actual work to
:mod:`salt.resource.ssh` via ``__resource_funcs__``.

Because this loader is **only ever used for resource jobs**, there is no need
for the call-time proxy-style guard (``if salt.utils.platform.is_proxy()``).
The managing minion's own jobs continue to use the standard execution modules
loaded in the regular ``self.functions`` loader.

Usage
-----
Any execution module function that should behave differently when targeting
an SSH resource can be implemented here.  Functions not defined in this
module fall through to the standard execution modules in the resource loader.

Example
-------

.. code-block:: bash

    # Ping an SSH resource
    salt -C 'T@ssh:web-01' test.ping

    # Run a shell command on an SSH resource
    salt -C 'T@ssh:web-01' cmd.run 'uptime'
    salt -C 'T@ssh'        cmd.run 'df -h'
"""

import logging

# __resource_funcs__ is injected by the per-type loader at runtime.
# pylint: disable=undefined-variable

log = logging.getLogger(__name__)

__virtualname__ = "cmd"


def __virtual__():
    """
    Load only when this execution-module loader is scoped to the ``ssh``
    resource type.
    """
    if __opts__.get("resource_type") == "ssh":  # pylint: disable=undefined-variable
        return __virtualname__
    return False, "sshresource_cmd: only loads in an ssh-resource-type loader."


# ---------------------------------------------------------------------------
# cmd.* surface
# ---------------------------------------------------------------------------


def run(
    cmd,
    timeout=None,
    **kwargs,
):
    """
    Execute a shell command on the targeted SSH resource and return its
    standard output.

    This is the SSH-resource equivalent of :func:`salt.modules.cmdmod.run`.
    The command is executed directly on the remote host via the SSH Shell
    transport — no Salt thin deployment required.

    :param str cmd: The shell command to run on the remote host.
    :param int timeout: Optional SSH connection timeout in seconds for this
        call.  Overrides the per-resource ``timeout`` configured in Pillar.
    :rtype: str — stdout from the remote command

    CLI Example:

    .. code-block:: bash

        salt -C 'T@ssh:web-01' cmd.run 'uptime'
        salt -C 'T@ssh'        cmd.run 'df -h' timeout=60
    """
    result = __resource_funcs__["ssh.cmd_run"](
        cmd, timeout=timeout
    )  # pylint: disable=undefined-variable
    return result.get("stdout", "")


def run_all(cmd, timeout=None, **kwargs):
    """
    Execute a shell command on the targeted SSH resource and return a dict
    containing ``stdout``, ``stderr``, and ``retcode``.

    This mirrors :func:`salt.modules.cmdmod.run_all` for SSH resources.

    :param str cmd: The shell command to run on the remote host.
    :param int timeout: Optional SSH connection timeout in seconds for this
        call.
    :rtype: dict

    CLI Example:

    .. code-block:: bash

        salt -C 'T@ssh:web-01' cmd.run_all 'uptime'
    """
    return __resource_funcs__["ssh.cmd_run"](
        cmd, timeout=timeout
    )  # pylint: disable=undefined-variable


def retcode(cmd, timeout=None, **kwargs):
    """
    Execute a shell command on the targeted SSH resource and return only the
    exit code.

    :param str cmd: The shell command to run on the remote host.
    :param int timeout: Optional SSH connection timeout in seconds for this
        call.
    :rtype: int

    CLI Example:

    .. code-block:: bash

        salt -C 'T@ssh:web-01' cmd.retcode 'test -f /etc/salt/minion'
    """
    result = __resource_funcs__["ssh.cmd_run"](
        cmd, timeout=timeout
    )  # pylint: disable=undefined-variable
    return result.get("retcode", 1)
