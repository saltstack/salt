'''
Virtual machine image management tools
'''

# Import python libs
import os
import glob
import shutil
import yaml
import logging
import tempfile

# Import salt libs
import salt.crypt
import salt.utils
import salt.config


# Set up logging
log = logging.getLogger(__name__)


def image(location, id_=None, config=None, approve_key=True, install=True):
    '''
    Seed a disk image with salt-minion config. Optionally, approve the minion's
    key and/or install salt-minion.

    CLI Example:

    .. code-block:: bash

        salt 'minion' seed.image location id [config=config_data] \
                [approve_key=(true|false)] [install=(true|false)]

    location
        Full path to the image file on the target minion's file system.

    id
        Minion id with which to seed the img.

    config
        Minion configuration options. By default, the 'master' option is set to
        the target host's 'master'.

    approve_key
        Whether to request a pre-approval of the generated minion key. Requires
        that the salt-master be configured to either auto-accept all keys or
        expect a signing request from the target host.

    install
        Whether to install salt-minion, if absent.
    '''
    mpt = __salt__['img.mount_image'](location)
    if not mpt:
        return False
    ret = _seed(location, id_, config, approve_key, install)
    __salt__['img.umount_image'](mpt)
    return ret


def device(location, id_=None, config=None, approve_key=True, install=True):
    '''
    Seed a device (e.g., a LVM volume) with salt-minion config. Optionally,
    approve the minion's key and/or install salt-minion.

    CLI Example:

    .. code-block:: bash

        salt 'minion' seed.device location id [config=config_data] \
                [approve_key=(true|false)] [install=(true|false)]

    location
        Path to the device on the target minion's file system.

    id
        Minion id with which to seed the device.

    config
        Minion configuration options. By default, the 'master' option is set
        to the target host's 'master'.

    approve_key
        Whether to request a pre-approval of the generated minion key. Requires
        that the salt-master be configured to either auto-accept all keys or
        expect a signing request from the target host.

    install
        Whether to install salt-minion, if absent.
    '''
    mpt = tempfile.mkdtemp()
    if not __salt__['mount.mount'](mpt, location):
        os.rmdir(mpt)
        return False
    ret = _seed(mpt, id_, config, approve_key, install)
    __salt__['mount.umount'](mpt)
    os.rmdir(mpt)
    return ret


def directory(location, id_=None, config=None, approve_key=True, install=True):
    '''
    Seed a directory with salt-minion config. Optionally,
    approve the minion's key and/or install salt-minion.

    CLI Example:

    .. code-block:: bash

        salt 'minion' seed.directory location id [config=config_data] \
                [approve_key=(true|false)] [install=(true|false)]

    location
        Full path to the image file on the target minion's file system.

    id
        Minion id with which to seed the directory.

    config
        Minion configuration options. By default, the 'master' option is set to
        the target host's 'master'.

    approve_key
        Whether to request a pre-approval of the generated minion key. Requires
        that the salt-master be configured to either auto-accept all keys or
        expect a signing request from the target host.

    install
        Whether to install salt-minion, if absent.
    '''
    return _seed(location, id_, config, approve_key, install)


def _seed(location, id_, config, approve_key, install):
    if config is None:
        config = {}
    if not 'master' in config:
        config['master'] = __opts__['master']
    if id_:
        config['id'] = id_

    tmp = os.path.join(location, 'tmp')

    # Write the new minion's config to a tmp file
    tmp_config = os.path.join(tmp, 'minion')
    with salt.utils.fopen(tmp_config, 'w+') as fp_:
        fp_.write(yaml.dump(config, default_flow_style=False))

    # Generate keys for the minion
    salt.crypt.gen_keys(tmp, 'minion', 2048)
    pubkeyfn = os.path.join(tmp, 'minion.pub')
    privkeyfn = os.path.join(tmp, 'minion.pem')
    with salt.utils.fopen(pubkeyfn) as fp_:
        pubkey = fp_.read()

    if approve_key:
        __salt__['pillar.ext']({'virtkey': {'name': id_, 'key': pubkey}})
    res = _check_install(location)
    if res:
        # salt-minion is already installed, just move the config and keys
        # into place
        log.info('salt-minion pre-installed on image, '
                 'configuring as {0}'.format(id_))
        minion_config = salt.config.minion_config(tmp_config)
        pki_dir = minion_config['pki_dir']
        os.rename(privkeyfn, os.path.join(location,
                                          pki_dir.lstrip('/'),
                                          'minion.pem'))
        os.rename(pubkeyfn, os.path.join(location,
                                         pki_dir.lstrip('/'),
                                         'minion.pub'))
        os.rename(tmp_config, os.path.join(location, 'etc/salt/minion'))
    elif install:
        log.info('attempting to install salt-minion: '
                 '{0}'.format(location))
        res = _install(location)
    else:
        log.error('failed to configure salt-minion: '
                  '{0}'.format(location))
        res = False
    return res


def _install(mpt):
    '''
    Determine whether salt-minion is installed and, if not,
    install it.
    Return True if install is successful or already installed
    '''

    # Verify that the boostrap script is downloaded
    bs_ = __salt__['config.gather_bootstrap_script']()
    log.warn('bootstrap: {0}'.format(bs_))
    # Apply the minion config
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
