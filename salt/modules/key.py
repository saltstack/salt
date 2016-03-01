# -*- coding: utf-8 -*-
'''
Functions to view the minion's public key information
'''
from __future__ import absolute_import

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
            os.path.join(__opts__['pki_dir'], 'minion.pub'),
            sum_type=__opts__['hash_type']
            )


def finger_master():
    '''
    Return the fingerprint of the master's public key on the minion.

    CLI Example:

    .. code-block:: bash

        salt '*' key.finger_master
    '''
    return salt.utils.pem_finger(
            os.path.join(__opts__['pki_dir'], 'minion_master.pub'),
            sum_type=__opts__['hash_type']
            )
