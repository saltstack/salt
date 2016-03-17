# -*- coding: utf-8 -*-
'''
Install pkg, dmg and .app applications on Mac OS X minions.

'''

# Import python libs
from __future__ import absolute_import
import os
import logging

import shlex
try:
    import pipes
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)
__virtualname__ = 'macpackage'


if hasattr(shlex, 'quote'):
    _quote = shlex.quote
elif HAS_DEPS and hasattr(pipes, 'quote'):
    _quote = pipes.quote
else:
    _quote = None


def __virtual__():
    '''
    Only work on Mac OS
    '''
    if salt.utils.is_darwin() and _quote is not None:
        return __virtualname__
    return False


def install(pkg, target='LocalSystem', store=False, allow_untrusted=False):
    '''
    Install a pkg file

    CLI Example:

    .. code-block:: bash

        salt '*' macpackage.install test.pkg

    target
        The target in which to install the package to

    store
        Should the package be installed as if it was from the store?

    allow_untrusted
        Allow the installation of untrusted packages?


    '''
    pkg = _quote(pkg)
    target = _quote(target)

    cmd = 'installer -pkg {0} -target {1}'.format(pkg, target)
    if store:
        cmd += ' -store'
    if allow_untrusted:
        cmd += ' -allowUntrusted'

    # We can only use wildcards in python_shell which is
    # sent by the macpackage state
    python_shell = False
    if '*.' in cmd:
        python_shell = True

    return __salt__['cmd.run_all'](cmd, python_shell=python_shell)


def install_app(app, target='/Applications/'):
    '''
    Install an app file

    CLI Example:

    .. code-block:: bash

        salt '*' macpackage.install_app /tmp/tmp.app /Applications/

    app
        The location of the .app file

    target
        The target in which to install the package to


    '''
    app = _quote(app)
    target = _quote(target)

    if not target[-4:] == '.app':
        if app[-1:] == '/':
            base_app = os.path.basename(app[:-1])
        else:
            base_app = os.path.basename(app)

        target = os.path.join(target, base_app)

    if not app[-1] == '/':
        app += '/'

    cmd = 'rsync -a --no-compress --delete {0} {1}'.format(app, target)
    return __salt__['cmd.run'](cmd)


def uninstall_app(app):
    '''
    Uninstall an app file

    CLI Example:

    .. code-block:: bash

        salt '*' macpackage.uninstall_app /Applications/app.app

    app
        The location of the .app file


    '''

    return __salt__['file.remove'](app)


def mount(dmg):
    '''
    Attempt to mount a dmg file to a temporary location and return the
    location of the pkg file inside

    dmg
        The location of the dmg file to mount
    '''

    temp_dir = __salt__['temp.dir'](prefix='dmg-')

    cmd = 'hdiutil attach -readonly -nobrowse -mountpoint {0} "{1}"'.format(temp_dir, dmg)

    return __salt__['cmd.run'](cmd), temp_dir


def unmount(mountpoint):
    '''
    Attempt to unmount a dmg file from a temporary location

    mountpoint
        The location of the mount point
    '''

    cmd = 'hdiutil detach "{0}"'.format(mountpoint)

    return __salt__['cmd.run'](cmd)


def installed_pkgs():
    '''
    Return the list of installed packages on the machine

    '''

    cmd = 'pkgutil --pkgs'

    return __salt__['cmd.run'](cmd).split('\n')


def get_pkg_id(pkg):
    '''
    Attempt to get the package id from a .pkg file

    Returns all of the package ids if the pkg file contains multiple

    pkg
        The location of the pkg file
    '''
    pkg = _quote(pkg)
    package_ids = []

    # Create temp directory
    temp_dir = __salt__['temp.dir'](prefix='pkg-')

    try:
        # List all of the PackageInfo files
        cmd = 'xar -t -f {0} | grep PackageInfo'.format(pkg)
        out = __salt__['cmd.run'](cmd, python_shell=True, output_loglevel='quiet')
        files = out.split('\n')

        if 'Error opening' not in out:
            # Extract the PackageInfo files
            cmd = 'xar -x -f {0} {1}'.format(pkg, ' '.join(files))
            __salt__['cmd.run'](cmd, cwd=temp_dir, output_loglevel='quiet')

            # Find our identifiers
            for f in files:
                i = _get_pkg_id_from_pkginfo(os.path.join(temp_dir, f))
                if len(i):
                    package_ids.extend(i)
        else:
            package_ids = _get_pkg_id_dir(pkg)

    finally:
        # Clean up
        __salt__['file.remove'](temp_dir)

    return package_ids


def get_mpkg_ids(mpkg):
    '''
    Attempt to get the package ids from a mounted .mpkg file

    Returns all of the package ids if the pkg file contains multiple

    pkg
        The location of the mounted mpkg file
    '''
    mpkg = _quote(mpkg)
    package_infos = []
    base_path = os.path.dirname(mpkg)

    # List all of the .pkg files
    cmd = 'find {0} -name *.pkg'.format(base_path)
    out = __salt__['cmd.run'](cmd, python_shell=True)

    pkg_files = out.split('\n')
    for p in pkg_files:
        package_infos.extend(get_pkg_id(p))

    return package_infos


def _get_pkg_id_from_pkginfo(pkginfo):
    # Find our identifiers
    pkginfo = _quote(pkginfo)
    cmd = 'cat {0} | grep -Eo \'identifier="[a-zA-Z.0-9\\-]*"\' | cut -c 13- | tr -d \'"\''.format(pkginfo)
    out = __salt__['cmd.run'](cmd, python_shell=True)

    if 'No such file' not in out:
        return out.split('\n')

    return []


def _get_pkg_id_dir(path):
    path = _quote(os.path.join(path, 'Contents/Info.plist'))
    cmd = '/usr/libexec/PlistBuddy -c "print :CFBundleIdentifier" {0}'.format(path)

    # We can only use wildcards in python_shell which is
    # sent by the macpackage state
    python_shell = False
    if '*.' in cmd:
        python_shell = True

    out = __salt__['cmd.run'](cmd, python_shell=python_shell)

    if 'Does Not Exist' not in out:
        return [out]

    return []
