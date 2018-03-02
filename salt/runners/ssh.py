# -*- coding: utf-8 -*-
'''
A Runner module interface on top of the salt-ssh Python API.

This allows for programmatic use from salt-api, the Reactor, Orchestrate, etc.
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.client.ssh.client
import salt.utils.versions


def cmd(tgt,
        fun,
        arg=(),
        timeout=None,
        tgt_type='glob',
        kwarg=None,
        expr_form=None):
    '''
    .. versionadded:: 2015.5.0
    .. versionchanged:: 2017.7.0
        The ``expr_form`` argument has been renamed to ``tgt_type``, earlier
        releases must use ``expr_form``.

    Execute a single command via the salt-ssh subsystem and return all
    routines at once

    A wrapper around the :py:meth:`SSHClient.cmd
    <salt.client.ssh.client.SSHClient.cmd>` method.
    '''
    # remember to remove the expr_form argument from this function when
    # performing the cleanup on this deprecation.
    if expr_form is not None:
        salt.utils.versions.warn_until(
            'Fluorine',
            'the target type should be passed using the \'tgt_type\' '
            'argument instead of \'expr_form\'. Support for using '
            '\'expr_form\' will be removed in Salt Fluorine.'
        )
        tgt_type = expr_form

    client = salt.client.ssh.client.SSHClient(mopts=__opts__)
    return client.cmd(
            tgt,
            fun,
            arg,
            timeout,
            tgt_type,
            kwarg)
