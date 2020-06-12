# -*- coding: utf-8 -*-
'''
Icinga2 Common Utils
=================

This module provides common functionality for icinga2 module and state.

.. versionadded:: 2018.8.3
'''
# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging
import re

# Import Salt libs
import salt.utils.path
import salt.modules.cmdmod

__salt__ = {
    'cmd.run_all': salt.modules.cmdmod.run_all
}
log = logging.getLogger(__name__)


def get_certs_path():
    icinga2_output = __salt__['cmd.run_all']([salt.utils.path.which('icinga2'),
                                              "--version"], python_shell=False)
    version = re.search(r'r\d+\.\d+', icinga2_output['stdout']).group(0)
    # Return new certs path for icinga2 >= 2.8
    if int(version.split('.')[1]) >= 8:
        return '/var/lib/icinga2/certs/'
    # Keep backwords compatibility with older icinga2
    return '/etc/icinga2/pki/'
