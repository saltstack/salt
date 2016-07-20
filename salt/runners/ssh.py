# -*- coding: utf-8 -*-
'''
A Runner module interface on top of the salt-ssh Python API.

This allows for programmatic use from salt-api, the Reactor, Orchestrate, etc.
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Libs
import salt.client.ssh.client


def cmd(
        tgt,
        fun,
        arg=(),
        timeout=None,
        expr_form='glob',
        kwarg=None):
    '''
    Execute a single command via the salt-ssh subsystem and return all
    routines at once

    .. versionadded:: 2015.5.0

    A wrapper around the :py:meth:`SSHClient.cmd
    <salt.client.ssh.client.SSHClient.cmd>` method.
    '''

    client = salt.client.ssh.client.SSHClient(mopts=__opts__)
    return client.cmd(
            tgt,
            fun,
            arg,
            timeout,
            expr_form,
            kwarg)
