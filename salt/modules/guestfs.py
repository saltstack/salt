# -*- coding: utf-8 -*-
'''
Interact with virtual machine images via libguestfs

:depends:   - libguestfs
'''
from __future__ import absolute_import, unicode_literals, print_function

# Import Python libs
import os
import tempfile
import hashlib
import logging

# Import Salt libs
import salt.utils.path

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if libguestfs python bindings are installed
    '''
    if salt.utils.path.which('guestmount'):
        return 'guestfs'
    return (False, 'The guestfs execution module cannot be loaded: guestmount binary not in path.')


def mount(location, access='rw', root=None):
    '''
    Mount an image

    CLI Example:

    .. code-block:: bash

        salt '*' guest.mount /srv/images/fedora.qcow
    '''
    if root is None:
        root = os.path.join(
            tempfile.gettempdir(),
            'guest',
            location.lstrip(os.sep).replace('/', '.')
        )
        log.debug('Using root %s', root)
    if not os.path.isdir(root):
        try:
            os.makedirs(root)
        except OSError:
            # Somehow the path already exists
            pass
    while True:
        if os.listdir(root):
            # Stuff is in there, don't use it
            hash_type = getattr(hashlib, __opts__.get('hash_type', 'md5'))
            rand = hash_type(os.urandom(32)).hexdigest()
            root = os.path.join(
                tempfile.gettempdir(),
                'guest',
                location.lstrip(os.sep).replace('/', '.') + rand
            )
            log.debug('Establishing new root as %s', root)
        else:
            break
    cmd = 'guestmount -i -a {0} --{1} {2}'.format(location, access, root)
    __salt__['cmd.run'](cmd, python_shell=False)
    return root
