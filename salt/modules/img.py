# -*- coding: utf-8 -*-
'''
Virtual machine image management tools
'''

# Import python libs
import logging


# Set up logging
log = logging.getLogger(__name__)


def mount_image(location):
    '''
    Mount the named image and return the mount point

    CLI Example:

    .. code-block:: bash

        salt '*' img.mount_image /tmp/foo
    '''
    if 'guestfs.mount' in __salt__:
        return __salt__['guestfs.mount'](location)
    elif 'qemu_nbd.init' in __salt__:
        mnt = __salt__['qemu_nbd.init'](location)
        if not mnt:
            return ''
        first = mnt.keys()[0]
        __context__['img.mnt_{0}'.format(first)] = mnt
        return first
    return ''

#compatibility for api change
mnt_image = mount_image


def umount_image(mnt):
    '''
    Unmount an image mountpoint

    CLI Example:

    .. code-block:: bash

        salt '*' img.umount_image /mnt/foo
    '''
    if 'qemu_nbd.clear' in __salt__:
        if 'img.mnt_{0}'.format(mnt) in __context__:
            __salt__['qemu_nbd.clear'](__context__['img.mnt_{0}'.format(mnt)])
            return
    __salt__['mount.umount'](mnt)


#def get_image(name):
#    '''
#    Download a vm image from a remote source and add it to the image cache
#    system
#    '''
#    cache_dir = os.path.join(__salt__['config.option']('img.cache'), 'src')
#    parse = urlparse.urlparse(name)
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

        salt '*' qemu_nbd.bootstrap /srv/salt-images/host.qcow 4096 qcow2
    '''
    location = __salt__['img.make_image'](location, size, fmt)
    if not location:
        return ''
    nbd = __salt__['qemu_nbd.connect'](location)
    __salt__['partition.mklabel'](nbd, 'msdos')
    __salt__['partition.mkpart'](nbd, 'primary', 'ext4', 1, -1)
    __salt__['partition.probe'](nbd)
    __salt__['partition.mkfs']('{0}p1'.format(nbd), 'ext4')
    mnt = __salt__['qemu_nbd.mount'](nbd)
    #return __salt__['pkg.bootstrap'](nbd, mnt.keys()[0])
