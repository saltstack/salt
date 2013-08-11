'''
Virtual machine image management tools
'''

# Import python libs
import os
import glob
import urlparse
import shutil
import yaml
import logging

# Import salt libs
import salt.crypt
import salt.utils
import salt.config


# Set up logging
log = logging.getLogger(__name__)


def mount_image(location):
    '''
    Mount the named image and return the mount point

    CLI Example::

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

    CLI Example::

        salt '*' img.umount_image /mnt/foo
    '''
    if 'qemu_nbd.clear' in __salt__:
        if 'img.mnt_{0}'.format(mnt) in __context__:
            __salt__['qemu_nbd.clear'](__context__['img.mnt_{0}'.format(mnt)])
            return
    __salt__['mount.umount'](mnt)


def seed(location, id_, config=None, approve_key=True, install=True):
    '''
    Make sure that the image at the given location is mounted, salt is
    installed, keys are seeded, and execute a state run

    CLI Example::

        salt '*' img.seed /tmp/image.qcow2 host1
    '''
    if config is None:
        config = {}
    if not 'master' in config:
        config['master'] = __opts__['master']
    config['id'] = id_

    mpt = mount_image(location)
    if not mpt:
        return False

    mpt_tmp = os.path.join(mpt, 'tmp')

    # Write the new minion's config to a tmp file
    tmp_config = os.path.join(mpt_tmp, 'minion')
    with salt.utils.fopen(tmp_config, 'w+') as fp_:
        fp_.write(yaml.dump(config, default_flow_style=False))

    # Generate keys for the minion
    salt.crypt.gen_keys(mpt_tmp, 'minion', 2048)
    pubkeyfn = os.path.join(mpt_tmp, 'minion.pub')
    privkeyfn = os.path.join(mpt_tmp, 'minion.pem')
    with salt.utils.fopen(pubkeyfn) as fp_:
        pubkey = fp_.read()

    if approve_key:
        __salt__['pillar.ext']({'virtkey': {'name': id_, 'key': pubkey}})
    res = _check_install(mpt)
    if res:
        # salt-minion is already installed, just move the config and keys into place
        log.info('salt-minion pre-installed on image, '
                 'configuring as {0}'.format(id_))
        minion_config = salt.config.minion_config(tmp_config)
        pki_dir = minion_config['pki_dir']
        os.rename(privkeyfn, os.path.join(mpt, pki_dir.lstrip('/'), 'minion.pem'))
        os.rename(pubkeyfn, os.path.join(mpt, pki_dir.lstrip('/'), 'minion.pub'))
        os.rename(tmp_config, os.path.join(mpt, 'etc/salt/minion'))
    elif install:
        log.info('attempting to install salt-minion on image: '
                 '{0}'.format(location))
        res = _install(mpt)
    else:
        log.error('failed to configure salt-minion on image: '
                 '{0}'.format(location))
        res = False
    umount_image(mpt)
    return res


def _install(mpt):
    '''
    Determine whether salt-minion is installed and, if not,
    install it
    Return True if install is successful or already installed
    '''

    # Verify that the boostrap script is downloaded
    bs_ = __salt__['config.gather_bootstrap_script']()
    # Apply the minion config
    # TODO Send the key to the master for approval
    # Copy script into tmp
    shutil.copy(bs_, os.path.join(mpt, 'tmp'))
    # Exec the chroot command
    cmd = 'if type salt-minion; then exit 0; '
    cmd += 'else sh /tmp/bootstrap.sh -c /tmp; fi'
    return (not _chroot_exec(mpt, cmd))


def _check_install(root):
    cmd = 'if ! type salt-minion; then exit 1; fi'
    return (not _chroot_exec(root, cmd))


def _chroot_exec(root, cmd):
    '''
    chroot into a directory and run a cmd
    '''
    __salt__['mount.mount'](
            os.path.join(root, 'dev'),
            'udev',
            fstype='devtmpfs')
    __salt__['mount.mount'](
            os.path.join(root, 'proc'),
            'proc',
            fstype='proc')

    # Execute chroot routine
    sh_ = '/bin/sh'
    if os.path.isfile(os.path.join(root, 'bin/bash')):
        sh_ = '/bin/bash'

    cmd = 'chroot {0} {1} -c \'{2}\''.format(
            root,
            sh_,
            cmd)
    res = __salt__['cmd.run_all'](cmd, quiet=True)

    # Kill processes running in the chroot
    for i in range(6):
        pids = _chroot_pids(root)
        if not pids:
            break
        for pid in pids:
            # use sig 15 (TERM) for first 3 attempts, then 9 (KILL)
            sig = 15 if i < 3 else 9
            os.kill(pid, sig)

    if _chroot_pids(root):
        log.error('Processes running in chroot could not be killed, '
                  'filesystem will remain mounted')

    __salt__['mount.umount'](os.path.join(root, 'proc'))
    __salt__['mount.umount'](os.path.join(root, 'dev'))
    log.info(res)
    return res['retcode']


def _chroot_pids(chroot):
    pids = []
    for root in glob.glob('/proc/[0-9]*/root'):
        link = os.path.realpath(root)
        if link.startswith(chroot):
            pids.append(int(os.path.basename(
                os.path.dirname(root)
            )))
    return pids


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
