# -*- coding: utf-8 -*-
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

# Don't shadow built-in's.
__func_alias__ = {
    'apply_': 'apply'
}


def _mount(path, ftype):
    mpt = None
    if ftype == 'block':
        mpt = tempfile.mkdtemp()
        if not __salt__['mount.mount'](mpt, path):
            os.rmdir(mpt)
            return None
    elif ftype == 'dir':
        return path
    elif ftype == 'file':
        mpt = __salt__['img.mount_image'](path)
        if not mpt:
            return None
    return mpt


def _umount(mpt, ftype):
    if ftype == 'block':
        __salt__['mount.umount'](mpt)
        os.rmdir(mpt)
    elif ftype == 'file':
        __salt__['img.umount_image'](mpt)


def apply_(path, id_=None, config=None, approve_key=True, install=True,
           prep_install=False):
    '''
    Seed a location (disk image, directory, or block device) with the
    minion config, approve the minion's key, and/or install salt-minion.

    CLI Example:

    .. code-block:: bash

        salt 'minion' seed.apply path id [config=config_data] \\
                [gen_key=(true|false)] [approve_key=(true|false)] \\
                [install=(true|false)]

    path
        Full path to the directory, device, or disk image  on the target
        minion's file system.

    id
        Minion id with which to seed the path.

    config
        Minion configuration options. By default, the 'master' option is set to
        the target host's 'master'.

    approve_key
        Request a pre-approval of the generated minion key. Requires
        that the salt-master be configured to either auto-accept all keys or
        expect a signing request from the target host. Default: true.

    install
        Install salt-minion, if absent. Default: true.

    prep_install
        Prepare the bootstrap script, but don't run it. Default: false
    '''
    stats = __salt__['file.stats'](path, follow_symlinks=True)
    if not stats:
        return '{0} does not exist'.format(path)
    ftype = stats['type']
    path = stats['target']
    mpt = _mount(path, ftype)

    if not mpt:
        return '{0} could not be mounted'.format(path)

    tmp = os.path.join(mpt, 'tmp')
    try:
        os.makedirs(tmp)
    except OSError:
        if not os.path.isdir(tmp):
            raise
    cfg_files = mkconfig(config, tmp=tmp, id_=id_, approve_key=approve_key)

    if _check_install(mpt):
        # salt-minion is already installed, just move the config and keys
        # into place
        log.info('salt-minion pre-installed on image, '
                 'configuring as {0}'.format(id_))
        minion_config = salt.config.minion_config(cfg_files['config'])
        pki_dir = minion_config['pki_dir']
        os.rename(cfg_files['privkey'], os.path.join(
            mpt, pki_dir.lstrip('/'), 'minion.pem'))
        os.rename(cfg_files['pubkey'], os.path.join(
            mpt, pki_dir.lstrip('/'), 'minion.pub'))
        os.rename(cfg_files['config'], os.path.join(mpt, 'etc/salt/minion'))
        res = True
    elif install:
        log.info('attempting to install salt-minion to '
                 '{0}'.format(mpt))
        res = _install(mpt)
    elif prep_install:
        _prep_bootstrap(mpt)
        log.info('{0} is ready for salt-minion installation'.format(mpt))
        res = True
    else:
        log.warn('No useful action performed on '
                 '{0}'.format(mpt))
        res = False

    _umount(mpt, ftype)
    return res


def _prep_bootstrap(mpt):
    # Verify that the boostrap script is downloaded
    bs_ = __salt__['config.gather_bootstrap_script']()

    # Copy script into tmp
    shutil.copy(bs_, os.path.join(mpt, 'tmp'))


def mkconfig(config=None, tmp=None, id_=None, approve_key=True):
    '''
    Generate keys and config and put them in a tmp directory.

    CLI Example:

    .. code-block:: bash

        salt 'minion' seed.mkconfig [config=config_data] [tmp=tmp_dir] \\
                [id_=minion_id] [approve_key=(true|false)]
    '''
    if tmp is None:
        tmp = tempfile.mkdtemp()
    if config is None:
        config = {}
    if not 'master' in config and __opts__['master'] != 'salt':
        config['master'] = __opts__['master']
    if id_:
        config['id'] = id_

    # Write the new minion's config to a tmp file
    tmp_config = os.path.join(tmp, 'minion')
    with salt.utils.fopen(tmp_config, 'w+') as fp_:
        fp_.write(yaml.dump(config, default_flow_style=False))

    # Generate keys for the minion
    salt.crypt.gen_keys(tmp, 'minion', 2048)
    pubkeyfn = os.path.join(tmp, 'minion.pub')
    privkeyfn = os.path.join(tmp, 'minion.pem')

    if approve_key:
        with salt.utils.fopen(pubkeyfn) as fp_:
            pubkey = fp_.read()
            __salt__['pillar.ext']({'virtkey': [id_, pubkey]})

    return {'config': tmp_config, 'pubkey': pubkeyfn, 'privkey': privkeyfn}


def _install(mpt):
    '''
    Determine whether salt-minion is installed and, if not,
    install it.
    Return True if install is successful or already installed.
    '''

    _prep_bootstrap(mpt)
    _check_resolv(mpt)
    # Exec the chroot command
    cmd = 'if type salt-minion; then exit 0; '
    cmd += 'else sh /tmp/bootstrap.sh -c /tmp; fi'
    return not _chroot_exec(mpt, cmd)


def _check_resolv(mpt):
    '''
    Check that the resolv.conf is present and populated
    '''
    resolv = os.path.join(mpt, 'etc/resolv.conf')
    replace = False
    if os.path.islink(resolv):
        resolv = os.path.realpath(resolv)
        if not os.path.isdir(os.path.dirname(resolv)):
            os.makedirs(os.path.dirname(resolv))
    if not os.path.isfile(resolv):
        replace = True
    if not replace:
        with salt.utils.fopen(resolv, 'rb') as fp_:
            conts = fp_.read()
            if not 'nameserver' in conts:
                replace = True
    if replace:
        shutil.copy('/etc/resolv.conf', resolv)


def _check_install(root):
    sh_ = '/bin/sh'
    if os.path.isfile(os.path.join(root, 'bin/bash')):
        sh_ = '/bin/bash'

    cmd = ('if ! type salt-minion; then exit 1; fi')
    cmd = 'chroot {0} {1} -c {2!r}'.format(
        root,
        sh_,
        cmd)

    return not __salt__['cmd.retcode'](cmd, output_loglevel='quiet')


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

    cmd = 'chroot {0} {1} -c {2!r}'.format(
        root,
        sh_,
        cmd)
    res = __salt__['cmd.run_all'](cmd, output_loglevel='quiet')

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
        try:
            link = os.path.realpath(root)
            if link.startswith(chroot):
                pids.append(int(os.path.basename(
                    os.path.dirname(root)
                )))
        except OSError:
            pass
    return pids
