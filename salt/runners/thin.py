# -*- coding: utf-8 -*-
'''
The thin runner is used to manage the salt thin systems.

Salt Thin is a transport-less version of Salt that can be used to run routines
in a standalone way. This runner has tools which generate the standalone salt
system for easy consumption.
'''

# Import python libs
from __future__ import print_function
from __future__ import absolute_import

# Import Salt libs
import salt.utils.thin


def generate(extra_mods='', overwrite=False, so_mods=''):
    '''
    Generate the salt-thin tarball and print the location of the tarball
    Optional additional mods to include (e.g. mako) can be supplied as a comma
    delimited string.  Permits forcing an overwrite of the output file as well.

    CLI Example:

    .. code-block:: bash

        salt-run thin.generate
        salt-run thin.generate mako
        salt-run thin.generate mako,wempy 1
        salt-run thin.generate overwrite=1
    '''
    return salt.utils.thin.gen_thin(__opts__['cachedir'], extra_mods, overwrite, so_mods)
