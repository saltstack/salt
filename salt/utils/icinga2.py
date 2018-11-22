# -*- coding: utf-8 -*-
'''
Icinga2 Common Utils
=================

This module provides common functionality for icinga2 module and state.

.. versionadded:: 2018.8.3
'''

# Import python libs
import logging
import subprocess
import re

# Import Salt libs
import salt.utils.path

log = logging.getLogger(__name__)


def execute(cmd, ret_code=False):
    process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    if ret_code:
        return process.wait()
    output, error = process.communicate()
    if output:
        log.debug(output)
        return output
    log.debug(error)
    return error


def get_certs_path():
    icinga2_output = execute([salt.utils.path.which('icinga2'), "--version"])
    version = re.search('r\d+\.\d+', icinga2_output).group(0)
    # Return new certs path for icinga2 >= 2.8
    if int(version.split('.')[1]) >= 8:
        return '/var/lib/icinga2/certs/'
    # Keep backwords compatibility with older icinga2
    return '/etc/icinga2/pki/'

