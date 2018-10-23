# -*- coding: utf-8 -*-
'''
Qemu Command Wrapper

The qemu system comes with powerful tools, such as qemu-img and qemu-nbd which
are used here to build up kvm images.
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import glob
import tempfile
import time
import logging

# Import salt libs
import salt.utils.path
import salt.crypt

# Import 3rd-party libs
from salt.ext import six

# Set up logging
log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if qemu-img and qemu-nbd are installed
    '''
    if salt.utils.path.which('qemu-nbd'):
        return 'qemu_nbd'
    return (False, 'The qemu_nbd execution module cannot be loaded: the qemu-nbd binary is not in the path.')


def connect(image):
    '''
    Activate nbd for an image file.

    CLI Example:

    .. code-block:: bash

        salt '*' qemu_nbd.connect /tmp/image.raw
    '''
    if not os.path.isfile(image):
        log.warning('Could not connect image: %s does not exist', image)
        return ''

    if salt.utils.path.which('sfdisk'):
        fdisk = 'sfdisk -d'
    else:
        fdisk = 'fdisk -l'
    __salt__['cmd.run']('modprobe nbd max_part=63')
    for nbd in glob.glob('/dev/nbd?'):
        if __salt__['cmd.retcode']('{0} {1}'.format(fdisk, nbd)):
            while True:
                # Sometimes nbd does not "take hold", loop until we can verify
                __salt__['cmd.run'](
                        'qemu-nbd -c {0} {1}'.format(nbd, image),
                        python_shell=False,
                        )
                if not __salt__['cmd.retcode']('{0} {1}'.format(fdisk, nbd)):
                    break
            return nbd
    log.warning('Could not connect image: %s', image)
    return ''


def mount(nbd, root=None):
    '''
    Pass in the nbd connection device location, mount all partitions and return
    a dict of mount points

    CLI Example:

    .. code-block:: bash

        salt '*' qemu_nbd.mount /dev/nbd0
    '''
    __salt__['cmd.run'](
            'partprobe {0}'.format(nbd),
            python_shell=False,
            )
    ret = {}
    if root is None:
        root = os.path.join(
            tempfile.gettempdir(),
            'nbd',
            os.path.basename(nbd)
        )
    for part in glob.glob('{0}p*'.format(nbd)):
        m_pt = os.path.join(root, os.path.basename(part))
        time.sleep(1)
        mnt = __salt__['mount.mount'](m_pt, part, True)
        if mnt is not True:
            continue
        ret[m_pt] = part
    return ret


def init(image, root=None):
    '''
    Mount the named image via qemu-nbd and return the mounted roots

    CLI Example:

    .. code-block:: bash

        salt '*' qemu_nbd.init /srv/image.qcow2
    '''
    nbd = connect(image)
    if not nbd:
        return ''
    return mount(nbd, root)


def clear(mnt):
    '''
    Pass in the mnt dict returned from nbd_mount to unmount and disconnect
    the image from nbd. If all of the partitions are unmounted return an
    empty dict, otherwise return a dict containing the still mounted
    partitions

    CLI Example:

    .. code-block:: bash

        salt '*' qemu_nbd.clear '{"/mnt/foo": "/dev/nbd0p1"}'
    '''
    ret = {}
    nbds = set()
    for m_pt, dev in six.iteritems(mnt):
        mnt_ret = __salt__['mount.umount'](m_pt)
        if mnt_ret is not True:
            ret[m_pt] = dev
        nbds.add(dev[:dev.rindex('p')])
    if ret:
        return ret
    for nbd in nbds:
        __salt__['cmd.run']('qemu-nbd -d {0}'.format(nbd), python_shell=False)
    return ret
