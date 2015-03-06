# -*- coding: utf-8 -*-
'''
Module for managing container and VM images

.. versionadded:: 2014.7.0
'''
from __future__ import absolute_import

# Import python libs
import os
import pprint
import logging
try:
    from shlex import quote as _cmd_quote  # pylint: disable=E0611
except ImportError:
    from pipes import quote as _cmd_quote

# Import salt libs
import salt.utils
import salt.syspaths


log = logging.getLogger(__name__)

CMD_MAP = {
    'yum': ('yum', 'rpm'),
    'deb': ('debootstrap',),
    'pacman': ('pacman',),
}


def __virtual__():
    '''
    By default, this will be available on all platforms; but not all distros
    will necessarily be supported
    '''
    return True


def bootstrap(platform,
              root,
              img_format='dir',
              fs_format='ext2',
              arch=None,
              flavor=None,
              repo_url=None,
              static_qemu=None):
    '''
    Create an image for a specific platform.

    Please note that this function *MUST* be run as root, as images that are
    created make files belonging to root.

    platform
        Which platform to use to create the image. Currently supported platforms
        are rpm, deb and pacman.

    root
        Local path to create the root of the image filesystem.

    img_format
        Which format to create the image in. By default, just copies files into
        a directory on the local filesystem (``dir``). Future support will exist
        for ``sparse``.

    fs_format
        When using a non-``dir`` img_format, which filesystem to format the
        image to. By default, ``ext2``.

    arch
        Architecture to install packages for, if supported by the underlying
        bootstrap tool. Currently only used for deb.

    flavor
        Which flavor of operating system to install. This correlates to a
        specific directory on the distribution repositories. For instance,
        ``wheezy`` on Debian.

    repo_url
        Mainly important for Debian-based repos. Base URL for the mirror to
        install from. (e.x.: http://ftp.debian.org/debian/)

    static_qemu
        Local path to the static qemu binary required for this arch.
        (e.x.: /usr/bin/qemu-amd64-static)

    pkg_confs
        The location of the conf files to copy into the image, to point the
        installer to the right repos and configuration.

    CLI Examples:

    .. code-block:: bash

        salt myminion genesis.bootstrap pacman /root/arch
        salt myminion genesis.bootstrap rpm /root/redhat
        salt myminion genesis.bootstrap deb /root/wheezy arch=amd64 \
            flavor=wheezy static_qemu=/usr/bin/qemu-x86_64-static

    '''
    if img_format == 'dir':
        # We can just use the root as the root
        if not __salt__['file.directory_exists'](root):
            try:
                __salt__['file.mkdir'](root)
            except Exception as exc:
                return {'Error': pprint.pformat(exc)}
    elif img_format == 'sparse':
        # TODO: Create a sparse file at the specified root
        pass

    if platform in ('rpm', 'yum'):
        return _bootstrap_yum(root)
    elif platform == 'deb':
        return _bootstrap_deb(
            root, arch=arch, flavor=flavor, repo_url=repo_url, static_qemu=static_qemu
        )
    elif platform == 'pacman':
        return _bootstrap_pacman(root)


def _bootstrap_yum(root, pkg_confs='/etc/yum*'):
    '''
    Bootstrap an image using the yum tools

    root
        The root of the image to install to. Will be created as a directory if
        if does not exist. (e.x.: /root/arch)

    pkg_confs
        The location of the conf files to copy into the image, to point yum
        to the right repos and configuration.

    TODO: Set up a pre-install overlay, to copy files into /etc/ and so on,
        which are required for the install to work.
    '''
    _make_nodes(root)
    release_files = [rf for rf in os.listdir('/etc') if rf.endswith('release')]
    __salt__['cmd.run']('cp /etc/resolv/conf {rfs} {root}/etc'.format(root=_cmd_quote(root), rfs=' '.join(release_files)))
    __salt__['cmd.run']('cp -r {rfs} {root}/etc'.format(root=_cmd_quote(root), rfs=' '.join(release_files)))
    __salt__['cmd.run']('cp -r {confs} {root}/etc'.format(root=_cmd_quote(root), confs=_cmd_quote(pkg_confs)))
    __salt__['cmd.run']('yum install --installroot={0} -y yum centos-release iputils'.format(_cmd_quote(root)))
    __salt__['cmd.run']('rpm --root={0} -Uvh http://download.fedoraproject.org/pub/epel/6/i386/epel-release-6-8.noarch.rpm'.format(_cmd_quote(root)))


def _bootstrap_deb(
        root,
        arch,
        flavor,
        repo_url=None,
        static_qemu=None
    ):
    '''
    Bootstrap an image using the Debian tools

    root
        The root of the image to install to. Will be created as a directory if
        if does not exist. (e.x.: /root/wheezy)

    arch
        Architecture of the target image. (e.x.: amd64)

    flavor
        Flavor of Debian to install. (e.x.: wheezy)

    repo_url
        Base URL for the mirror to install from.
        (e.x.: http://ftp.debian.org/debian/)

    static_qemu
        Local path to the static qemu binary required for this arch.
        (e.x.: /usr/bin/qemu-amd64-static)
    '''

    if repo_url is None:
        repo_url = 'http://ftp.debian.org/debian/'

    __salt__['cmd.run'](
        'debootstrap --foreign --arch {arch} {flavor} {root} {url}'.format(
            arch=_cmd_quote(arch),
            flavor=_cmd_quote(flavor),
            root=_cmd_quote(root),
            url=_cmd_quote(repo_url)
        )
    )
    __salt__['cmd.run'](
        'cp {qemu} {root}/usr/bin/'.format(
            qemu=_cmd_quote(static_qemu), root=_cmd_quote(root)
        )
    )
    env = {'DEBIAN_FRONTEND': 'noninteractive',
           'DEBCONF_NONINTERACTIVE_SEEN': 'true',
           'LC_ALL': 'C',
           'LANGUAGE': 'C',
           'LANG': 'C',
           'PATH': '/sbin:/bin:/usr/bin'}
    __salt__['cmd.run'](
        'chroot {root} /debootstrap/debootstrap --second-stage'.format(
            root=_cmd_quote(root)
        ),
        env=env
    )
    __salt__['cmd.run'](
        'chroot {root} dpkg --configure -a'.format(root=_cmd_quote(root)),
        env=env
    )


def _bootstrap_pacman(root, pkg_confs='/etc/pacman*'):
    '''
    Bootstrap an image using the pacman tools

    root
        The root of the image to install to. Will be created as a directory if
        if does not exist. (e.x.: /root/arch)

    pkg_confs
        The location of the conf files to copy into the image, to point pacman
        to the right repos and configuration.
    '''
    _make_nodes(root)
    __salt__['file.mkdir'](
        '{0}/var/lib/pacman/local'.format(root), 'root', 'root', '755'
    )
    pac_files = [rf for rf in os.listdir('/etc') if rf.startswith('pacman.')]
    __salt__['cmd.run']('cp -r {0} {1}/etc'.format(' '.join(pac_files), _cmd_quote(root)))
    __salt__['cmd.run']('pacman --noconfirm -r {0} -Sy pacman'.format(_cmd_quote(root)))


def _make_nodes(root):
    '''
    Make the minimum number of nodes inside of /dev/. Based on:

    https://wiki.archlinux.org/index.php/Linux_Containers
    '''
    dirs = (
        ('{0}/etc'.format(root), 'root', 'root', '755'),
        ('{0}/dev'.format(root), 'root', 'root', '755'),
        ('{0}/dev/pts'.format(root), 'root', 'root', '755'),
        ('{0}/dev/shm'.format(root), 'root', 'root', '1755'),
    )

    nodes = (
        ('{0}/dev/null'.format(root), 'c', 1, 3, 'root', 'root', '666'),
        ('{0}/dev/zero'.format(root), 'c', 1, 5, 'root', 'root', '666'),
        ('{0}/dev/random'.format(root), 'c', 1, 8, 'root', 'root', '666'),
        ('{0}/dev/urandom'.format(root), 'c', 1, 9, 'root', 'root', '666'),
        ('{0}/dev/tty'.format(root), 'c', 5, 0, 'root', 'root', '666'),
        ('{0}/dev/tty0'.format(root), 'c', 4, 0, 'root', 'root', '666'),
        ('{0}/dev/console'.format(root), 'c', 5, 1, 'root', 'root', '600'),
        ('{0}/dev/full'.format(root), 'c', 1, 7, 'root', 'root', '666'),
        ('{0}/dev/initctl'.format(root), 'p', 0, 0, 'root', 'root', '600'),
        ('{0}/dev/ptmx'.format(root), 'c', 5, 2, 'root', 'root', '666'),
    )

    for path in dirs:
        __salt__['file.mkdir'](*path)

    for path in nodes:
        __salt__['file.mknod'](*path)


def avail_platforms():
    '''
    Return which platforms are available

    CLI Example:

    .. code-block:: bash

        salt myminion genesis.avail_platforms
    '''
    ret = {}
    for platform in CMD_MAP:
        ret[platform] = True
        for cmd in CMD_MAP[platform]:
            if not salt.utils.which(cmd):
                ret[platform] = False
    return ret


def pack(name, root, path=None, pack_format='tar', compress='bzip2'):
    '''
    Pack up a directory structure, into a specific format

    CLI Examples:

    .. code-block:: bash

        salt myminion genesis.pack centos /root/centos
        salt myminion genesis.pack centos /root/centos pack_format='tar'
    '''
    if pack_format == 'tar':
        _tar(name, root, path, compress)


def unpack(name, dest=None, path=None, pack_format='tar', compress='bz2'):
    '''
    Unpack an image into a directory structure

    CLI Example:

    .. code-block:: bash

        salt myminion genesis.unpack centos /root/centos
    '''
    if pack_format == 'tar':
        _untar(name, dest, path, compress)


def _tar(name, root, path=None, compress='bzip2'):
    '''
    Pack up image in a tar format
    '''
    if path is None:
        path = os.path.join(salt.syspaths.BASE_FILE_ROOTS_DIR, 'img')
    if not __salt__['file.directory_exists'](path):
        try:
            __salt__['file.mkdir'](path)
        except Exception as exc:
            return {'Error': pprint.pformat(exc)}

    compression, ext = _compress(compress)

    tarfile = '{0}/{1}.tar.{2}'.format(path, name, ext)
    out = __salt__['archive.tar'](
        options='{0}pcf'.format(compression),
        tarfile=tarfile,
        sources='.',
        dest=root,
    )


def _untar(name, dest=None, path=None, compress='bz2'):
    '''
    Unpack a tarball to be used as a container
    '''
    if path is None:
        path = os.path.join(salt.syspaths.BASE_FILE_ROOTS_DIR, 'img')

    if not dest:
        dest = path

    if not __salt__['file.directory_exists'](dest):
        try:
            __salt__['file.mkdir'](dest)
        except Exception as exc:
            return {'Error': pprint.pformat(exc)}

    compression, ext = _compress(compress)

    tarfile = '{0}/{1}.tar.{2}'.format(path, name, ext)
    out = __salt__['archive.tar'](
        options='{0}xf'.format(compression),
        tarfile=tarfile,
        dest=dest,
    )


def _compress(compress):
    '''
    Resolve compression flags
    '''
    if compress in ('bz2', 'bzip2', 'j'):
        compression = 'j'
        ext = 'bz2'
    elif compress in ('gz', 'gzip', 'z'):
        compression = 'z'
        ext = 'gz'
    elif compress in ('xz', 'a', 'J'):
        compression = 'J'
        ext = 'xz'

    return compression, ext
