'''
Qemu Command Wrapper
====================

The qemu system comes with powerful tools, such as qemu-img and qemu-nbd which
are used here to build up kvm images.
'''

# Import python libs
import os
import glob
import tempfile
import time

# Import third party tools
import yaml

# Import salt libs
import salt.utils
import salt.crypt

def __virtual__():
    '''
    Only load if qemu-img and qemu-nbd are installed
    '''
    if salt.utils.which('qemu-nbd'):
        return 'qemu_nbd'
    return False


def connect(image):
    '''
    Activate nbd for an image file.

    CLI Example::

        salt '*' qemu_nbd.connect /tmp/image.raw
    '''
    if not os.path.isfile(image):
        return ''
    __salt__['cmd.run']('modprobe nbd max_part=63')
    for nbd in glob.glob('/dev/nbd?'):
        if __salt__['cmd.retcode']('fdisk -l {0}'.format(nbd)):
            while True:
                # Sometimes nbd does not "take hold", loop until we can verify
                __salt__['cmd.run'](
                        'qemu-nbd -c {0} {1}'.format(nbd, image)
                        )
                if not __salt__['cmd.retcode']('fdisk -l {0}'.format(nbd)):
                    break
            return nbd
    return ''


def mount(nbd):
    '''
    Pass in the nbd connection device location, mount all partitions and return
    a dict of mount points

    CLI Example::

        salt '*' qemu_nbd.mount /dev/nbd0
    '''
    ret = {}
    for part in glob.glob('{0}p*'.format(nbd)):
        root = os.path.join(
                tempfile.gettempdir(),
                'nbd',
                os.path.basename(nbd))
        m_pt = os.path.join(root, os.path.basename(part))
        time.sleep(1)
        mnt = __salt__['mount.mount'](m_pt, part, True)
        if mnt is not True:
            continue
        ret[m_pt] = part
    return ret


def init(image):
    '''
    Mount the named image via qemu-nbd and return the mounted roots

    CLI Example::

        salt '*' qemu_nbd.init /srv/image.qcow2
    '''
    nbd = connect(image)
    if not nbd:
        return ''
    return mount(nbd)


def clear(mnt):
    '''
    Pass in the mnt dict returned from nbd_mount to unmount and disconnect
    the image from nbd. If all of the partitions are unmounted return an
    empty dict, otherwise return a dict containing the still mounted
    partitions

    CLI Example::

        salt '*' qemu_nbd.clear '{/mnt/foo: /dev/nbd0p1}'
    '''
    if isinstance(mnt, str):
        mnt = yaml.load(mnt)
    ret = {}
    nbds = set()
    for m_pt, dev in mnt.items():
        mnt_ret = __salt__['mount.umount'](m_pt)
        if mnt_ret is not True:
            ret[m_pt] = dev
        nbds.add(dev[:dev.rindex('p')])
    if ret:
        return ret
    for nbd in nbds:
        __salt__['cmd.run']('qemu-nbd -d {0}'.format(nbd))
    return ret
