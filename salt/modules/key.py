# -*- coding: utf-8 -*-
'''
Functions to view the minion's public key information
'''

# Import python libs
import os

# Import Salt libs
import salt.utils


def finger():
    '''
    Return the minion's public key fingerprint

    CLI Example:

    .. code-block:: bash

        salt '*' key.finger
    '''
    return salt.utils.pem_finger(
            os.path.join(__opts__['pki_dir'], 'minion.pub')
            )
