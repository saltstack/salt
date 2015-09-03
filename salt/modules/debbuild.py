# -*- coding: utf-8 -*-
'''
Debian Package builder system

.. versionadded:: Beryllium

This system allows for all of the components to build debs safely in chrooted
environments. This also provides a function to generate debian repositories

This module impliments the pkgbuild interface
'''

# import python libs
from __future__ import absolute_import, print_function
import os
import tempfile
import shutil
from salt.ext.six.moves.urllib.parse import urlparse as _urlparse  # pylint: disable=no-name-in-module,import-error

# Import salt libs
import salt.utils
from salt.exceptions import SaltInvocationError

# pylint: disable=import-error

__virtualname__ = 'pkgbuild'


def __virtual__():
    '''
    Confirm this module is on a Debian based system
    '''
    if __grains__.get('os_family', False) in ('Kali', 'Debian'):
        return __virtualname__
    return False


def _get_build_env(env):
    '''
    Get build environment overrides dictionary to use in build process
    '''
    env_override = ''
    if env is None:
        return env_override
    if not isinstance(env, dict):
        raise SaltInvocationError(
            '\'env\' must be a Python dictionary'
        )
    for key, value in env.items():
        env_override += '{0}={1}\n'.format(key, value)
        env_override += 'export {0}\n'.format(key)
    return env_override


def _get_repo_env(env):
    '''
    Get repo environment overrides dictionary to use in repo process
    '''
    env_options = ''
    if env is None:
        return env_options
    if not isinstance(env, dict):
        raise SaltInvocationError(
            '\'env\' must be a Python dictionary'
        )
    for key, value in env.items():
        env_options += '{0}\n'.format(value)
    return env_options


def _create_pbuilders(env):
    '''
    Create the .pbuilder family of files in user's home directory

    env
        A list  or dictionary of environment variables to be set prior to execution.
        Example:

        .. code-block:: yaml

                - env:
                  - DEB_BUILD_OPTIONS: 'nocheck'

        .. warning::

            The above illustrates a common PyYAML pitfall, that **yes**,
            **no**, **on**, **off**, **true**, and **false** are all loaded as
            boolean ``True`` and ``False`` values, and must be enclosed in
            quotes to be used as strings. More info on this (and other) PyYAML
            idiosyncrasies can be found :doc:`here
            </topics/troubleshooting/yaml_idiosyncrasies>`.


    '''
    hook_text = '''#!/bin/sh
set -e
cat > "/etc/apt/preferences" << EOF

Package: python-alabaster
Pin: release a=testing
Pin-Priority: 950

Package: python-sphinx
Pin: release a=testing
Pin-Priority: 900

Package: sphinx-common
Pin: release a=testing
Pin-Priority: 900

Package: *
Pin: release a=jessie-backports
Pin-Priority: 750

Package: *
Pin: release a=stable
Pin-Priority: 700

Package: *
Pin: release a=testing
Pin-Priority: 650

Package: *
Pin: release a=unstable
Pin-Priority: 600

Package: *
Pin: release a=experimental
Pin-Priority: 550

EOF
'''

    pbldrc_text = '''DIST="jessie"
if [ -n "${DIST}" ]; then
  TMPDIR=/tmp
  BASETGZ="`dirname $BASETGZ`/$DIST-base.tgz"
  DISTRIBUTION=$DIST
  APTCACHE="/var/cache/pbuilder/$DIST/aptcache"
fi
HOOKDIR="${HOME}/.pbuilder-hooks"
OTHERMIRROR="deb http://ftp.us.debian.org/debian/ stable  main contrib non-free | deb http://ftp.us.debian.org/debian/ testing main contrib non-free | deb http://ftp.us.debian.org/debian/ unstable main contrib non-free"
'''
    home = os.path.expanduser('~')
    pbuilder_hooksdir = os.path.join(home, '.pbuilder-hooks')
    if not os.path.isdir(pbuilder_hooksdir):
        os.makedirs(pbuilder_hooksdir)

    g05hook = os.path.join(pbuilder_hooksdir, 'G05apt-preferences')
    with salt.utils.fopen(g05hook, 'w') as fow:
        fow.write('{0}'.format(hook_text))

    cmd = 'chmod 755 {0}'.format(g05hook)
    __salt__['cmd.run'](cmd)

    pbuilderrc = os.path.join(home, '.pbuilderrc')
    with salt.utils.fopen(pbuilderrc, 'w') as fow:
        fow.write('{0}'.format(pbldrc_text))

    env_overrides = _get_build_env(env)
    if env_overrides and not env_overrides.isspace():
        with salt.utils.fopen(pbuilderrc, 'a') as fow:
            fow.write('{0}'.format(env_overrides))


def _mk_tree():
    '''
    Create the debian build area
    '''
    basedir = tempfile.mkdtemp()
    return basedir


def _get_spec(tree_base, spec, template, saltenv='base'):
    '''
    Get the spec file (tarball of the debian sub-dir to use)
    and place it in build area

    '''
    spec_tgt = os.path.basename(spec)
    dest = os.path.join(tree_base, spec_tgt)
    return __salt__['cp.get_url'](spec, dest, saltenv=saltenv)


def _get_src(tree_base, source, saltenv='base'):
    '''
    Get the named sources and place them into the tree_base
    '''
    parsed = _urlparse(source)
    sbase = os.path.basename(source)
    dest = os.path.join(tree_base, sbase)
    if parsed.scheme:
        __salt__['cp.get_url'](source, dest, saltenv=saltenv)
    else:
        shutil.copy(source, dest)


def make_src_pkg(dest_dir, spec, sources, env=None, template=None, saltenv='base'):
    '''
    Create a platform specific source package from the given platform spec/control file and sources

    CLI Example:

    Debian
        salt '*' pkgbuild.make_src_pkg /var/www/html/ https://raw.githubusercontent.com/saltstack/libnacl/master/pkg/deb/python-libnacl.control.tar.xz https://pypi.python.org/packages/source/l/libnacl/libnacl-1.3.5.tar.gz

    This example command should build the libnacl SOURCE package and place it in
    /var/www/html/ on the minion
    '''
    _create_pbuilders(env)
    tree_base = _mk_tree()
    ret = []
    if not os.path.isdir(dest_dir):
        os.makedirs(dest_dir)

    spec_pathfile = _get_spec(tree_base, spec, template, saltenv)

    # build salt equivalents from scratch
    if isinstance(sources, str):
        sources = sources.split(',')
    for src in sources:
        _get_src(tree_base, src, saltenv)

    #.dsc then assumes sources already build
    if spec_pathfile.endswith('.dsc'):
        for efile in os.listdir(tree_base):
            full = os.path.join(tree_base, efile)
            trgt = os.path.join(dest_dir, efile)
            shutil.copy(full, trgt)
            ret.append(trgt)

        trgt = os.path.join(dest_dir, os.path.basename(spec_pathfile))
        shutil.copy(spec_pathfile, trgt)
        ret.append(trgt)

        return ret

    # obtain name of 'python setup.py sdist' generated tarball, extract the version
    # and manipulate the name for debian use (convert minix and add '+ds')
    salttarball = None
    for afile in os.listdir(tree_base):
        if afile.startswith('salt-') and afile.endswith('.tar.gz'):
            salttarball = afile
            break
    else:
        return ret

    frontname = salttarball.split('.tar.gz')
    salttar_name = frontname[0]
    k = salttar_name.rfind('-')
    debname = salttar_name[:k] + '_' + salttar_name[k+1:]
    debname += '+ds'
    debname_orig = debname + '.orig.tar.gz'
    abspath_debname = os.path.join(tree_base, debname)

    cmd = 'tar -xvzf {0}'.format(salttarball)
    __salt__['cmd.run'](cmd, cwd=tree_base)
    cmd = 'mv {0} {1}'.format(salttar_name, debname)
    __salt__['cmd.run'](cmd, cwd=tree_base)
    cmd = 'tar -cvzf {0} {1}'.format(os.path.join(tree_base, debname_orig), debname)
    __salt__['cmd.run'](cmd, cwd=tree_base)
    cmd = 'rm -f {0}'.format(salttarball)
    __salt__['cmd.run'](cmd, cwd=tree_base)
    cmd = 'cp {0}  {1}'.format(spec_pathfile, abspath_debname)
    __salt__['cmd.run'](cmd, cwd=abspath_debname)
    cmd = 'tar -xvJf {0}'.format(spec_pathfile)
    __salt__['cmd.run'](cmd, cwd=abspath_debname)
    cmd = 'rm -f {0}'.format(os.path.basename(spec_pathfile))
    __salt__['cmd.run'](cmd, cwd=abspath_debname)
    cmd = 'debuild -S -uc -us'
    __salt__['cmd.run'](cmd, cwd=abspath_debname, python_shell=True)

    cmd = 'rm -fR {0}'.format(abspath_debname)
    __salt__['cmd.run'](cmd)

    for dfile in os.listdir(tree_base):
        if not dfile.endswith('.build'):
            full = os.path.join(tree_base, dfile)
            trgt = os.path.join(dest_dir, dfile)
            shutil.copy(full, trgt)
            ret.append(trgt)

    return ret


def build(runas, tgt, dest_dir, spec, sources, deps, env, template, saltenv='base'):
    '''
    Given the package destination directory, the tarball containing debian files (e.g. control)
    and package sources, use pbuilder to safely build the platform package

    CLI Example:

    Debian
        salt '*' pkgbuild.make_src_pkg deb-8-x86_64 /var/www/html/ https://raw.githubusercontent.com/saltstack/libnacl/master/pkg/deb/python-libnacl.control https://pypi.python.org/packages/source/l/libnacl/libnacl-1.3.5.tar.gz

    This example command should build the libnacl package for Debian using pbuilder
    and place it in /var/www/html/ on the minion
    '''
    ret = {}
    if not os.path.isdir(dest_dir):
        try:
            os.makedirs(dest_dir)
        except (IOError, OSError):
            pass
    dsc_dir = tempfile.mkdtemp()
    dscs = make_src_pkg(dsc_dir, spec, sources, env, template, saltenv)

    # dscs should only contain salt orig and debian tarballs and dsc file
    for dsc in dscs:
        afile = os.path.basename(dsc)
        adist = os.path.join(dest_dir, afile)
        shutil.copy(dsc, adist)

        if dsc.endswith('.dsc'):
            dbase = os.path.dirname(dsc)
            cmd = 'chown {0} -R {1}'.format(runas, dbase)
            __salt__['cmd.run'](cmd)

            results_dir = tempfile.mkdtemp()
            cmd = 'chown {0} -R {1}'.format(runas, results_dir)
            __salt__['cmd.run'](cmd)

            cmd = 'pbuilder --create'
            __salt__['cmd.run'](cmd, runas=runas, python_shell=True)
            cmd = 'pbuilder --build --buildresult {1} {0}'.format(dsc, results_dir)
            __salt__['cmd.run'](cmd, runas=runas, python_shell=True)

            for bfile in os.listdir(results_dir):
                full = os.path.join(results_dir, bfile)
                bdist = os.path.join(dest_dir, bfile)
                shutil.copy(full, bdist)
            shutil.rmtree(results_dir)
    shutil.rmtree(dsc_dir)
    return ret


def make_repo(repodir, keyid=None, env=None):
    '''
    Given the repodir, create a Debian repository out of the dsc therein

    CLI Example::

        salt '*' pkgbuild.make_repo /var/www/html/
    '''
    repocfg_text = '''Origin: SaltStack
Label: salt_debian
Suite: unstable
Codename: jessie
Architectures: i386 amd64 source
Components: contrib
Description: SaltStack debian package repo
Pull: jessie
'''
    repoconf = os.path.join(repodir, 'conf')
    if not os.path.isdir(repoconf):
        os.makedirs(repoconf)

    repoconfdist = os.path.join(repoconf, 'distributions')
    with salt.utils.fopen(repoconfdist, 'w') as fow:
        fow.write('{0}'.format(repocfg_text))

    if keyid is not None:
        with salt.utils.fopen(repoconfdist, 'a') as fow:
            fow.write('SignWith: {0}\n'.format(keyid))

    repocfg_opts = _get_repo_env(env)
    repoconfopts = os.path.join(repoconf, 'options')
    with salt.utils.fopen(repoconfopts, 'w') as fow:
        fow.write('{0}'.format(repocfg_opts))

    for debfile in os.listdir(repodir):
        if debfile.endswith('.changes'):
            cmd = 'reprepro -Vb . include jessie {0}'.format(os.path.join(repodir, debfile))
            __salt__['cmd.run'](cmd, cwd=repodir)

        if debfile.endswith('.deb'):
            cmd = 'reprepro -Vb . includedeb jessie {0}'.format(os.path.join(repodir, debfile))
            __salt__['cmd.run'](cmd, cwd=repodir)
