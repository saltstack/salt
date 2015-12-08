# -*- coding: utf-8 -*-
'''
Debian Package builder system

.. versionadded:: 2015.8.0

This system allows for all of the components to build debs safely in chrooted
environments. This also provides a function to generate debian repositories

This module impliments the pkgbuild interface
'''

# import python libs
from __future__ import absolute_import, print_function
import errno
import logging
import os
import tempfile
import shutil

# Import salt libs
import salt.utils
from salt.exceptions import SaltInvocationError
from salt.ext.six.moves.urllib.parse import urlparse as _urlparse  # pylint: disable=no-name-in-module,import-error

log = logging.getLogger(__name__)

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


def _get_repo_options_env(env):
    '''
    Get repo environment overrides dictionary to use in repo options process

    env
        A dictionary of variables to define the repository options
        Example:

        .. code-block:: yaml

                - env:
                  - OPTIONS : 'ask-passphrase'

        .. warning::

            The above illustrates a common PyYAML pitfall, that **yes**,
            **no**, **on**, **off**, **true**, and **false** are all loaded as
            boolean ``True`` and ``False`` values, and must be enclosed in
            quotes to be used as strings. More info on this (and other) PyYAML
            idiosyncrasies can be found :doc:`here
            </topics/troubleshooting/yaml_idiosyncrasies>`.

    '''
    env_options = ''
    if env is None:
        return env_options
    if not isinstance(env, dict):
        raise SaltInvocationError(
            '\'env\' must be a Python dictionary'
        )
    for key, value in env.items():
        if key == 'OPTIONS':
            env_options += '{0}\n'.format(value)
    return env_options


def _get_repo_dists_env(env):
    '''
    Get repo environment overrides dictionary to use in repo distributions process

    env
        A dictionary of variables to define the repository distributions
        Example:

        .. code-block:: yaml

                - env:
                  - ORIGIN : 'jessie'
                  - LABEL : 'salt debian'
                  - SUITE : 'main'
                  - VERSION : '8.1'
                  - CODENAME : 'jessie'
                  - ARCHS : 'amd64 i386 source'
                  - COMPONENTS : 'main'
                  - DESCRIPTION : 'SaltStack Debian package repo'

        .. warning::

            The above illustrates a common PyYAML pitfall, that **yes**,
            **no**, **on**, **off**, **true**, and **false** are all loaded as
            boolean ``True`` and ``False`` values, and must be enclosed in
            quotes to be used as strings. More info on this (and other) PyYAML
            idiosyncrasies can be found :doc:`here
            </topics/troubleshooting/yaml_idiosyncrasies>`.

    '''
    # env key with tuple of control information for handling input env dictionary
    # 0 | M - Mandatory, O - Optional, I - Ignore
    # 1 | 'text string for repo field'
    # 2 | 'default value'
    dflts_dict = {
                'OPTIONS': ('I', '', 'processed by _get_repo_options_env'),
                'ORIGIN': ('O', 'Origin', 'SaltStack'),
                'LABEL': ('O', 'Label', 'salt_debian'),
                'SUITE': ('O', 'Suite', 'stable'),
                'VERSION': ('O', 'Version', '8.1'),
                'CODENAME': ('M', 'Codename', 'jessie'),
                'ARCHS': ('M', 'Architectures', 'i386 amd64 source'),
                'COMPONENTS': ('M', 'Components', 'main'),
                'DESCRIPTION': ('O', 'Description', 'SaltStack debian package repo'),
    }

    env_dists = ''
    codename = ''
    dflts_keys = list(dflts_dict.keys())
    if env is None:
        for key, value in dflts_dict.items():
            if dflts_dict[key][0] == 'M':
                env_dists += '{0}: {1}\n'.format(dflts_dict[key][1], dflts_dict[key][2])
                if key == 'CODENAME':
                    codename = dflts_dict[key][2]
        return (codename, env_dists)

    if not isinstance(env, dict):
        raise SaltInvocationError(
            '\'env\' must be a Python dictionary'
        )

    env_man_seen = []
    for key, value in env.items():
        if key in dflts_keys:
            if dflts_dict[key][0] == 'M':
                env_man_seen.append(key)
                if key == 'CODENAME':
                    codename = value
            if dflts_dict[key][0] != 'I':
                env_dists += '{0}: {1}\n'.format(dflts_dict[key][1], value)
        else:
            env_dists += '{0}: {1}\n'.format(key, value)

    ## ensure mandatories are included
    env_keys = list(env.keys())
    for key in env_keys:
        if key in dflts_keys and dflts_dict[key][0] == 'M' and key not in env_man_seen:
            env_dists += '{0}: {1}\n'.format(dflts_dict[key][1], dflts_dict[key][2])
            if key == 'CODENAME':
                codename = value

    return (codename, env_dists)


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
    home = os.path.expanduser('~')
    pbuilderrc = os.path.join(home, '.pbuilderrc')
    if not os.path.isfile(pbuilderrc):
        raise SaltInvocationError(
            'pbuilderrc environment is incorrectly setup'
        )

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


def build(runas,
          tgt,
          dest_dir,
          spec,
          sources,
          deps,
          env,
          template,
          saltenv='base',
          log_dir='/var/log/salt/pkgbuild'):  # pylint: disable=unused-argument
    '''
    Given the package destination directory, the tarball containing debian files (e.g. control)
    and package sources, use pbuilder to safely build the platform package

    CLI Example:

    Debian
        salt '*' pkgbuild.make_src_pkg deb-8-x86_64 /var/www/html https://raw.githubusercontent.com/saltstack/libnacl/master/pkg/deb/python-libnacl.control https://pypi.python.org/packages/source/l/libnacl/libnacl-1.3.5.tar.gz

    This example command should build the libnacl package for Debian using pbuilder
    and place it in /var/www/html/ on the minion
    '''
    ret = {}
    try:
        os.makedirs(dest_dir)
    except OSError as exc:
        if exc.errno != errno.EEXIST:
            raise
    dsc_dir = tempfile.mkdtemp()
    try:
        dscs = make_src_pkg(dsc_dir, spec, sources, env, template, saltenv)
    except Exception as exc:
        shutil.rmtree(dsc_dir)
        log.error('Failed to make src package')
        return ret

    # dscs should only contain salt orig and debian tarballs and dsc file
    for dsc in dscs:
        afile = os.path.basename(dsc)
        adist = os.path.join(dest_dir, afile)
        shutil.copy(dsc, adist)

        if dsc.endswith('.dsc'):
            dbase = os.path.dirname(dsc)
            results_dir = tempfile.mkdtemp()
            try:
                __salt__['cmd.run']('chown {0} -R {1}'.format(runas, dbase))
                __salt__['cmd.run']('chown {0} -R {1}'.format(runas, results_dir))

                cmd = 'pbuilder --create'
                __salt__['cmd.run'](cmd, runas=runas, python_shell=True)
                cmd = 'pbuilder --build --buildresult {1} {0}'.format(
                    dsc, results_dir)
                __salt__['cmd.run'](cmd, runas=runas, python_shell=True)

                for bfile in os.listdir(results_dir):
                    full = os.path.join(results_dir, bfile)
                    bdist = os.path.join(dest_dir, bfile)
                    shutil.copy(full, bdist)
                    ret.setdefault('Packages', []).append(bdist)
            except Exception as exc:
                log.error('Error building from {0}: {1}'.format(dsc, exc))
            finally:
                shutil.rmtree(results_dir)
    shutil.rmtree(dsc_dir)
    return ret


def make_repo(repodir, keyid=None, env=None):
    '''
    Given the repodir, create a Debian repository out of the dsc therein

    CLI Example::

        salt '*' pkgbuild.make_repo /var/www/html/
    '''
    repoconf = os.path.join(repodir, 'conf')
    if not os.path.isdir(repoconf):
        os.makedirs(repoconf)

    codename, repocfg_dists = _get_repo_dists_env(env)
    repoconfdist = os.path.join(repoconf, 'distributions')
    with salt.utils.fopen(repoconfdist, 'w') as fow:
        fow.write('{0}'.format(repocfg_dists))

    if keyid is not None:
        with salt.utils.fopen(repoconfdist, 'a') as fow:
            fow.write('SignWith: {0}\n'.format(keyid))

    repocfg_opts = _get_repo_options_env(env)
    repoconfopts = os.path.join(repoconf, 'options')
    with salt.utils.fopen(repoconfopts, 'w') as fow:
        fow.write('{0}'.format(repocfg_opts))

    for debfile in os.listdir(repodir):
        if debfile.endswith('.changes'):
            cmd = 'reprepro -Vb . include {0} {1}'.format(codename, os.path.join(repodir, debfile))
            __salt__['cmd.run'](cmd, cwd=repodir)

        if debfile.endswith('.deb'):
            cmd = 'reprepro -Vb . includedeb {0} {1}'.format(codename, os.path.join(repodir, debfile))
            __salt__['cmd.run'](cmd, cwd=repodir)
