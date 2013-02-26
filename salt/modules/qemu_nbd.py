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
import shutil

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
        if not mnt is True:
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
    empy dict, otherwise return a dict containing the still mounted
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
        if not mnt_ret is True:
            ret[m_pt] = dev
        nbds.add(dev[:dev.rindex('p')])
    if ret:
        return ret
    for nbd in nbds:
        __salt__['cmd.run']('qemu-nbd -d {0}'.format(nbd))
    return ret


def seed(location, id_='', config=None):
    '''
    Make sure that the image at the given location is mounted, salt is
    installed, keys are seeded, and execute a state run

    CLI Example::

        salt '*' qemu.seed /tmp/image.qcow2
    '''
    if config is None:
        config = {}
    mnt = init(location)
    mpt = mnt.keys()[0]
    mpt_tmp = os.path.join(mpt, 'tmp')
    __salt__['mount.mount'](
            os.path.join(mpt, 'dev'),
            'udev',
            fstype='devtmpfs')
    # Verify that the boostrap script is downloaded
    bs_ = gather_bootstrap_script()
    # Apply the minion config
    # Generate the minion's key
    salt.crypt.gen_keys(mpt_tmp, 'minion', 2048)
    # TODO Send the key to the master for approval
    # Execute chroot routine
    sh_ = '/bin/sh'
    if os.path.isfile(os.path.join(mpt, 'bin/bash')):
        sh_ = '/bin/bash'
    # Copy script into tmp
    shutil.copy(bs_, os.path.join(mpt, 'tmp'))
    if not 'master' in config:
        config['master'] = __opts__['master']
    if id_:
        config['id'] = id_
    with open(os.path.join(mpt_tmp, 'minion'), 'w+') as fp_:
        fp_.write(yaml.dump(config, default_flow_style=False))
    # Generate the chroot command
    c_cmd = 'sh /tmp/bootstrap.sh'
    cmd = 'chroot {0} {1} -c \'{2}\''.format(
            mpt,
            sh_,
            c_cmd)
    __salt__['cmd.run'](cmd)
    __salt__['mount.umount'](os.path.join(mpt, 'dev'))
    clear(mnt)


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

    CLI Example::
        salt '*' qemu_nbd.bootstrap /srv/salt-images/host.qcow 4096 qcow2
    '''
    location = __salt__['qemu_img.make_image'](location, size, fmt)
    if not location:
        return ''
    nbd = connect(location)
    __salt__['partition.mklabel'](nbd, 'msdos')
    __salt__['partition.mkpart'](nbd, 'primary', 'ext4', 1, -1)
    __salt__['partition.probe'](nbd)
    __salt__['partition.mkfs']('{0}p1'.format(nbd), 'ext4')
    mnt = mount(nbd)
    #return __salt__['pkg.bootstrap'](nbd, mnt.keys()[0])
