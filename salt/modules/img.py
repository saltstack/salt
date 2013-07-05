'''
Virtual machine image management tools
'''

# Import python libs
import os
import urlparse
import shutil
import yaml

# Import salt libs
import salt.crypt

def mnt_image(location):
    '''
    Mount the named image and return the mount point

    CLI Example::

        salt '*' img.mount_image /tmp/foo
    '''
    if 'guestfs.mount' in __salt__:
        return __salt__['guestfs.mount'](location)
    elif 'qemu_nbd.init' in __salt__:
        mnt = __salt__['qemu_nbd.init'](location)
        __context__['img.mnt_{0}'.format(location)] = mnt
        return mnt.keys()[0]
    return ''


def umount_image(mnt):
    '''
    Unmount an image mountpoint

    CLI Example::

        salt '*' img.umount_image /mnt/foo
    '''
    if 'qemu_nbd.clear' in __salt__:
        if 'img.mnt_{0}'.format(mnt) in __context__:
            __salt__['qemu_nbd.clear'](__context__['img.mnt_{0}'.format(mnt)])
            return
    __salt__['mount.umount'](mnt)


def seed(location, id_='', config=None):
    '''
    Make sure that the image at the given location is mounted, salt is
    installed, keys are seeded, and execute a state run

    CLI Example::

        salt '*' img.seed /tmp/image.qcow2
    '''
    if config is None:
        config = {}
    mpt = mnt_image(location)
    mpt_tmp = os.path.join(mpt, 'tmp')
    __salt__['mount.mount'](
            os.path.join(mpt, 'dev'),
            'udev',
            fstype='devtmpfs')
    __salt__['mount.mount'](
            os.path.join(mpt, 'proc'),
            'proc',
            fstype='proc')
    # Verify that the boostrap script is downloaded
    bs_ = __salt__['config.gather_bootstrap_script']()
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
    c_cmd = 'sh /tmp/bootstrap.sh -c /tmp'
    cmd = 'chroot {0} {1} -c \'{2}\''.format(
            mpt,
            sh_,
            c_cmd)
    __salt__['cmd.run'](cmd)
    __salt__['mount.umount'](os.path.join(mpt, 'proc'))
    __salt__['mount.umount'](os.path.join(mpt, 'dev'))
    umount_image(mpt)


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

    CLI Example::
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
