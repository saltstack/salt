# -*- coding: utf-8 -*-
'''
Virtual machine image management tools

.. deprecated:: 2016.3.0
'''

# Import python libs
from __future__ import absolute_import
import logging

# Import salt libs
import salt.utils

# Set up logging
log = logging.getLogger(__name__)


def mount_image(location):
    '''
    Mount the named image and return the mount point

    CLI Example:

    .. code-block:: bash

        salt '*' img.mount_image /tmp/foo
    '''
    salt.utils.warn_until(
        'Nitrogen',
        'This function has been deprecated; use "mount.mount" instead. Please '
        'note that in order to use this functionality with "mount.mount" you '
        'must set the "util" argument to either "guestfs" or "qemu_nbd".'
    )

    if 'guestfs.mount' in __salt__:
        util = 'guestfs'
    elif 'qemu_nbd.init' in __salt__:
        util = 'qemu_nbd'
    else:
        util = 'mount'
    return __salt__['mount.mount'](location, util=util)


# compatibility for api change
mnt_image = salt.utils.alias_function(mount_image, 'mnt_image')


def umount_image(mnt):
    '''
    Unmount an image mountpoint

    CLI Example:

    .. code-block:: bash

        salt '*' img.umount_image /mnt/foo
    '''
    salt.utils.warn_until(
        'Nitrogen',
        'This function has been deprecated; use "mount.umount" instead. Please '
        'note that in order to access this functionality with "mount.umount" '
        'you must pass in a "util" argument other than "mount".'
    )
    return __salt__['mount.umount'](mnt, util='qemu_nbd')


#def get_image(name):
#    '''
#    Download a vm image from a remote source and add it to the image cache
#    system
#    '''
#    cache_dir = os.path.join(__salt__['config.option']('img.cache'), 'src')
#    parse = urlparse(name)
#    if __salt__['config.valid_file_proto'](parse.scheme):
#        # Valid scheme to download
#        dest = os.path.join(cache_dir, parse.netloc)
#        sfn = __salt__['file.get_managed'](dest, None, name, )


def bootstrap(location, size, fmt):
    '''
    HIGHLY EXPERIMENTAL
    Bootstrap a virtual machine image

    location:
        The location to create the image

    size:
        The size of the image to create in megabytes

    fmt:
        The image format, raw or qcow2

    CLI Example:

    .. code-block:: bash

        salt '*' img.bootstrap /srv/salt-images/host.qcow 4096 qcow2
    '''
    salt.utils.warn_until(
        'Nitrogen',
        'This functionality has been deprecated; use "genesis.bootstrap" '
        'instead. Please note that the arguments between "img.boostrap" and '
        'genesis.bootstrap have changed.'
    )

    location = __salt__['img.make_image'](location, size, fmt)
    if not location:
        return ''
    nbd = __salt__['qemu_nbd.connect'](location)
    __salt__['partition.mklabel'](nbd, 'msdos')
    __salt__['partition.mkpart'](nbd, 'primary', 'ext4', 1, -1)
    __salt__['partition.probe'](nbd)
    __salt__['partition.mkfs']('{0}p1'.format(nbd), 'ext4')
    mnt = __salt__['qemu_nbd.mount'](nbd)
    #return __salt__['pkg.bootstrap'](nbd, mnt.iterkeys().next())
