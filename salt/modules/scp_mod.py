# -*- coding: utf-8 -*-
"""
SCP Module
==========

.. versionadded:: 2019.2.0

Module to copy files via `SCP <https://man.openbsd.org/scp>`_
"""
from __future__ import absolute_import, print_function, unicode_literals

import inspect

# Import python libs
import logging

# Import salt modules
from salt.ext import six

try:
    import scp
    import paramiko

    HAS_SCP = True
except ImportError:
    HAS_SCP = False

__proxyenabled__ = ["*"]
__virtualname__ = "scp"

log = logging.getLogger(__name__)


def __virtual__():
    if not HAS_SCP:
        return False, "Please install SCP for this modules: pip install scp"
    return __virtualname__


def _select_kwargs(**kwargs):
    paramiko_kwargs = {}
    scp_kwargs = {}
    PARAMIKO_KWARGS, _, _, _ = inspect.getargspec(paramiko.SSHClient.connect)
    PARAMIKO_KWARGS.pop(0)  # strip self
    PARAMIKO_KWARGS.append("auto_add_policy")
    SCP_KWARGS, _, _, _ = inspect.getargspec(scp.SCPClient.__init__)
    SCP_KWARGS.pop(0)  # strip self
    SCP_KWARGS.pop(0)  # strip transport arg (it is passed in _prepare_connection)
    for karg, warg in six.iteritems(kwargs):
        if karg in PARAMIKO_KWARGS and warg is not None:
            paramiko_kwargs[karg] = warg
        if karg in SCP_KWARGS and warg is not None:
            scp_kwargs[karg] = warg
    return paramiko_kwargs, scp_kwargs


def _prepare_connection(**kwargs):
    """
    Prepare the underlying SSH connection with the remote target.
    """
    paramiko_kwargs, scp_kwargs = _select_kwargs(**kwargs)
    ssh = paramiko.SSHClient()
    if paramiko_kwargs.pop("auto_add_policy", False):
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(**paramiko_kwargs)
    scp_client = scp.SCPClient(ssh.get_transport(), **scp_kwargs)
    return scp_client


def get(remote_path, local_path="", recursive=False, preserve_times=False, **kwargs):
    """
    Transfer files and directories from remote host to the localhost of the
    Minion.

    remote_path
        Path to retrieve from remote host. Since this is evaluated by scp on the
        remote host, shell wildcards and environment variables may be used.

    recursive: ``False``
        Transfer files and directories recursively.

    preserve_times: ``False``
        Preserve ``mtime`` and ``atime`` of transferred files and directories.

    hostname
        The hostname of the remote device.

    port: ``22``
        The port of the remote device.

    username
        The username required for SSH authentication on the device.

    password
        Used for password authentication. It is also used for private key
        decryption if ``passphrase`` is not given.

    passphrase
        Used for decrypting private keys.

    pkey
        An optional private key to use for authentication.

    key_filename
        The filename, or list of filenames, of optional private key(s) and/or
        certificates to try for authentication.

    timeout
        An optional timeout (in seconds) for the TCP connect.

    socket_timeout: ``10``
        The channel socket timeout in seconds.

    buff_size: ``16384``
        The size of the SCP send buffer.

    allow_agent: ``True``
        Set to ``False`` to disable connecting to the SSH agent.

    look_for_keys: ``True``
        Set to ``False`` to disable searching for discoverable private key
        files in ``~/.ssh/``

    banner_timeout
        An optional timeout (in seconds) to wait for the SSH banner to be
        presented.

    auth_timeout
        An optional timeout (in seconds) to wait for an authentication
        response.

    auto_add_policy: ``False``
        Automatically add the host to the ``known_hosts``.

    CLI Example:

    .. code-block:: bash

        salt '*' scp.get /var/tmp/file /tmp/file hostname=10.10.10.1 auto_add_policy=True
    """
    scp_client = _prepare_connection(**kwargs)
    get_kwargs = {"recursive": recursive, "preserve_times": preserve_times}
    if local_path:
        get_kwargs["local_path"] = local_path
    return scp_client.get(remote_path, **get_kwargs)


def put(
    files,
    remote_path=None,
    recursive=False,
    preserve_times=False,
    saltenv="base",
    **kwargs
):
    """
    Transfer files and directories to remote host.

    files
        A single path or a list of paths to be transferred.

    remote_path
        The path on the remote device where to store the files.

    recursive: ``True``
        Transfer files and directories recursively.

    preserve_times: ``False``
        Preserve ``mtime`` and ``atime`` of transferred files and directories.

    hostname
        The hostname of the remote device.

    port: ``22``
        The port of the remote device.

    username
        The username required for SSH authentication on the device.

    password
        Used for password authentication. It is also used for private key
        decryption if ``passphrase`` is not given.

    passphrase
        Used for decrypting private keys.

    pkey
        An optional private key to use for authentication.

    key_filename
        The filename, or list of filenames, of optional private key(s) and/or
        certificates to try for authentication.

    timeout
        An optional timeout (in seconds) for the TCP connect.

    socket_timeout: ``10``
        The channel socket timeout in seconds.

    buff_size: ``16384``
        The size of the SCP send buffer.

    allow_agent: ``True``
        Set to ``False`` to disable connecting to the SSH agent.

    look_for_keys: ``True``
        Set to ``False`` to disable searching for discoverable private key
        files in ``~/.ssh/``

    banner_timeout
        An optional timeout (in seconds) to wait for the SSH banner to be
        presented.

    auth_timeout
        An optional timeout (in seconds) to wait for an authentication
        response.

    auto_add_policy: ``False``
        Automatically add the host to the ``known_hosts``.

    CLI Example:

    .. code-block:: bash

        salt '*' scp.put /path/to/file /var/tmp/file hostname=server1 auto_add_policy=True
    """
    scp_client = _prepare_connection(**kwargs)
    put_kwargs = {"recursive": recursive, "preserve_times": preserve_times}
    if remote_path:
        put_kwargs["remote_path"] = remote_path
    cached_files = []
    if not isinstance(files, (list, tuple)):
        files = [files]
    for file_ in files:
        cached_file = __salt__["cp.cache_file"](file_, saltenv=saltenv)
        cached_files.append(cached_file)
    return scp_client.put(cached_files, **put_kwargs)
