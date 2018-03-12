# -*- coding: utf-8 -*-

from __future__ import absolute_import

# Import Python libs
import re

# Import salt libs
import salt.utils
import salt.utils.files
from salt.exceptions import CommandExecutionError


def key_is_encrypted(key):
    # NOTE: this is a temporary workaround until we can get salt/modules/ssh.py
    # working on Windows.
    try:
        with salt.utils.fopen(key, 'r') as fp_:
            key_data = fp_.read()
    except (IOError, OSError) as exc:
        # Raise a CommandExecutionError
        salt.utils.files.process_read_exception(exc, key)

    is_private_key = re.search(r'BEGIN (?:\w+\s)*PRIVATE KEY', key_data)
    is_encrypted = 'ENCRYPTED' in key_data
    del key_data

    if not is_private_key:
        raise CommandExecutionError('{0} is not a private key'.format(key))

    return is_encrypted
