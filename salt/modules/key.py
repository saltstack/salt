# -*- coding: utf-8 -*-
'''
Functions to view the minion's public key information
'''

# Import python libs
import os

# Import Salt libs
import salt.utils

# Don't shadow built-in's.
__func_alias__ = {
    'help_': 'help'
}


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


def help_(cmd=None):
    '''
    Display help for module

    CLI Example:

    .. code-block:: bash

        salt '*' key.help

        salt '*' key.help finger
    '''
    if '__virtualname__' in globals():
        module_name = __virtualname__
    else:
        module_name = __name__.split('.')[-1]

    if cmd is None:
        return __salt__['sys.doc']('{0}' . format(module_name))
    else:
        return __salt__['sys.doc']('{0}.{1}' . format(module_name, cmd))
