# -*- coding: utf-8 -*-
'''
Debian Package builder system

.. versionadded:: 2015.8.0

This system allows for all of the components to build debs safely in chrooted
environments. This also provides a function to generate debian repositories

This module implements the pkgbuild interface
'''

# import python libs
from __future__ import absolute_import, print_function
import errno
import logging
import os
import tempfile
import shutil
import re
import time
import traceback

# Import salt libs
from salt.ext.six.moves.urllib.parse import urlparse as _urlparse  # pylint: disable=no-name-in-module,import-error
from salt.exceptions import SaltInvocationError, CommandExecutionError
import salt.utils

HAS_LIBS = False

try:
    import gnupg    # pylint: disable=unused-import
    import salt.modules.gpg
    HAS_LIBS = True
except ImportError:
    pass

log = logging.getLogger(__name__)


__virtualname__ = 'pkgbuild'


def __virtual__():
    '''
    Confirm this module is on a Debian based system, and has required utilities
    '''
    if __grains__.get('os_family', False) in ('Kali', 'Debian'):
        missing_util = False
        utils_reqd = ['gpg', 'debuild', 'pbuilder', 'reprepro']
        for named_util in utils_reqd:
            if not salt.utils.which(named_util):
                missing_util = True
                break
        if HAS_LIBS and not missing_util:
            return __virtualname__
        else:
            return False, 'The debbuild module could not be loaded: requires python-gnupg, gpg, debuild, pbuilder and reprepro utilities to be installed'
    else:
        return (False, 'The debbuild module could not be loaded: unsupported OS family')


def _check_repo_sign_utils_support():
    util_name = 'debsign'
    if salt.utils.which(util_name):
        return True
    else:
        raise CommandExecutionError(
            'utility \'{0}\' needs to be installed'.format(util_name)
        )


def _check_repo_gpg_phrase_utils_support():
    util_name = '/usr/lib/gnupg2/gpg-preset-passphrase'
    if __salt__['file.file_exists'](util_name):
        return True
    else:
        raise CommandExecutionError(
            'utility \'{0}\' needs to be installed'.format(util_name)
        )


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
            idiosyncrasies can be found :ref:`here <yaml-idiosyncrasies>`.

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
            idiosyncrasies can be found :ref:`here <yaml-idiosyncrasies>`.

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
            idiosyncrasies can be found :ref:`here <yaml-idiosyncrasies>`.

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

    **Debian**

    .. code-block:: bash

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

    **Debian**

    .. code-block:: bash

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

    cmd = 'pbuilder --create'
    __salt__['cmd.run'](cmd, runas=runas, python_shell=True)

    # use default /var/cache/pbuilder/result
    results_dir = '/var/cache/pbuilder/result'

    # dscs should only contain salt orig and debian tarballs and dsc file
    for dsc in dscs:
        afile = os.path.basename(dsc)
        adist = os.path.join(dest_dir, afile)

        if dsc.endswith('.dsc'):
            dbase = os.path.dirname(dsc)
            try:
                __salt__['cmd.run']('chown {0} -R {1}'.format(runas, dbase))

                cmd = 'pbuilder --update --override-config'
                __salt__['cmd.run'](cmd, runas=runas, python_shell=True)

                cmd = 'pbuilder --build {0}'.format(dsc)
                __salt__['cmd.run'](cmd, runas=runas, python_shell=True)

                # ignore local deps generated package file
                for bfile in os.listdir(results_dir):
                    if bfile != 'Packages':
                        full = os.path.join(results_dir, bfile)
                        bdist = os.path.join(dest_dir, bfile)
                        shutil.copy(full, bdist)
                        ret.setdefault('Packages', []).append(bdist)

            except Exception as exc:
                log.error('Error building from {0}: {1}'.format(dsc, exc))

    # remove any Packages file created for local dependency processing
    for pkgzfile in os.listdir(dest_dir):
        if pkgzfile == 'Packages':
            pkgzabsfile = os.path.join(dest_dir, pkgzfile)
            os.remove(pkgzabsfile)

    shutil.rmtree(dsc_dir)
    return ret


def make_repo(repodir,
              keyid=None,
              env=None,
              use_passphrase=False,
              gnupghome='/etc/salt/gpgkeys',
              runas='root',
              timeout=15.0):
    '''
    Make a package repository and optionally sign it and packages present

    Given the repodir (directory to create repository in), create a Debian
    repository and optionally sign it and packages present. This state is
    best used with onchanges linked to your package building states.

    repodir
        The directory to find packages that will be in the repository.

    keyid
        .. versionchanged:: 2016.3.0

        Optional Key ID to use in signing packages and repository.
        Utilizes Public and Private keys associated with keyid which have
        been loaded into the minion's Pillar data. Leverages gpg-agent and
        gpg-preset-passphrase for caching keys, etc.

        For example, contents from a Pillar data file with named Public
        and Private keys as follows:

        .. code-block:: yaml

            gpg_pkg_priv_key: |
              -----BEGIN PGP PRIVATE KEY BLOCK-----
              Version: GnuPG v1

              lQO+BFciIfQBCADAPCtzx7I5Rl32escCMZsPzaEKWe7bIX1em4KCKkBoX47IG54b
              w82PCE8Y1jF/9Uk2m3RKVWp3YcLlc7Ap3gj6VO4ysvVz28UbnhPxsIkOlf2cq8qc
              .
              .
              Ebe+8JCQTwqSXPRTzXmy/b5WXDeM79CkLWvuGpXFor76D+ECMRPv/rawukEcNptn
              R5OmgHqvydEnO4pWbn8JzQO9YX/Us0SMHBVzLC8eIi5ZIopzalvX
              =JvW8
              -----END PGP PRIVATE KEY BLOCK-----

            gpg_pkg_priv_keyname: gpg_pkg_key.pem

            gpg_pkg_pub_key: |
              -----BEGIN PGP PUBLIC KEY BLOCK-----
              Version: GnuPG v1

              mQENBFciIfQBCADAPCtzx7I5Rl32escCMZsPzaEKWe7bIX1em4KCKkBoX47IG54b
              w82PCE8Y1jF/9Uk2m3RKVWp3YcLlc7Ap3gj6VO4ysvVz28UbnhPxsIkOlf2cq8qc
              .
              .
              bYP7t5iwJmQzRMyFInYRt77wkJBPCpJc9FPNebL9vlZcN4zv0KQta+4alcWivvoP
              4QIxE+/+trC6QRw2m2dHk6aAeq/J0Sc7ilZufwnNA71hf9SzRIwcFXMsLx4iLlki
              inNqW9c=
              =s1CX
              -----END PGP PUBLIC KEY BLOCK-----

            gpg_pkg_pub_keyname: gpg_pkg_key.pub

    env
        .. versionchanged:: 2016.3.0

        A dictionary of environment variables to be utilized in creating the
        repository.

    use_passphrase : False
        .. versionadded:: 2016.3.0

        Use a passphrase with the signing key presented in ``keyid``.
        Passphrase is received from Pillar data which could be passed on the
        command line with ``pillar`` parameter. For example:

        .. code-block:: bash

            pillar='{ "gpg_passphrase" : "my_passphrase" }'

    gnupghome : /etc/salt/gpgkeys
        .. versionadded:: 2016.3.0

        Location where GPG related files are stored, used with ``keyid``.

    runas : root
        .. versionadded:: 2016.3.0

        User to create the repository as, and optionally sign packages.

        .. note::

            Ensure the user has correct permissions to any files and
            directories which are to be utilized.

    timeout : 15.0
        .. versionadded:: 2016.3.4

        Timeout in seconds to wait for the prompt for inputting the passphrase.

    CLI Example:

    .. code-block:: bash

        salt '*' pkgbuild.make_repo /var/www/html

    '''
    res = {'retcode': 1,
            'stdout': '',
            'stderr': 'initialization value'}

    SIGN_PROMPT_RE = re.compile(r'Enter passphrase: ', re.M)
    REPREPRO_SIGN_PROMPT_RE = re.compile(r'Passphrase: ', re.M)

    repoconf = os.path.join(repodir, 'conf')
    if not os.path.isdir(repoconf):
        os.makedirs(repoconf)

    codename, repocfg_dists = _get_repo_dists_env(env)
    repoconfdist = os.path.join(repoconf, 'distributions')
    with salt.utils.fopen(repoconfdist, 'w') as fow:
        fow.write('{0}'.format(repocfg_dists))

    repocfg_opts = _get_repo_options_env(env)
    repoconfopts = os.path.join(repoconf, 'options')
    with salt.utils.fopen(repoconfopts, 'w') as fow:
        fow.write('{0}'.format(repocfg_opts))

    local_fingerprint = None
    local_keyid = None
    phrase = ''

    # preset passphase and interaction with gpg-agent
    gpg_info_file = '{0}/gpg-agent-info-salt'.format(gnupghome)
    gpg_tty_info_file = '{0}/gpg-tty-info-salt'.format(gnupghome)
    gpg_tty_info_dict = {}

    # test if using older than gnupg 2.1, env file exists
    older_gnupg = __salt__['file.file_exists'](gpg_info_file)

    # interval of 0.125 is really too fast on some systems
    interval = 0.5

    if keyid is not None:
        with salt.utils.fopen(repoconfdist, 'a') as fow:
            fow.write('SignWith: {0}\n'.format(keyid))

        ## import_keys
        pkg_pub_key_file = '{0}/{1}'.format(gnupghome, __salt__['pillar.get']('gpg_pkg_pub_keyname', None))
        pkg_priv_key_file = '{0}/{1}'.format(gnupghome, __salt__['pillar.get']('gpg_pkg_priv_keyname', None))

        if pkg_pub_key_file is None or pkg_priv_key_file is None:
            raise SaltInvocationError(
                'Pillar data should contain Public and Private keys associated with \'keyid\''
            )
        try:
            __salt__['gpg.import_key'](user=runas, filename=pkg_pub_key_file, gnupghome=gnupghome)
            __salt__['gpg.import_key'](user=runas, filename=pkg_priv_key_file, gnupghome=gnupghome)

        except SaltInvocationError:
            raise SaltInvocationError(
                'Public and Private key files associated with Pillar data and \'keyid\' '
                '{0} could not be found'
                .format(keyid)
            )

        # gpg keys should have been loaded as part of setup
        # retrieve specified key, obtain fingerprint and preset passphrase
        local_keys = __salt__['gpg.list_keys'](user=runas, gnupghome=gnupghome)
        for gpg_key in local_keys:
            if keyid == gpg_key['keyid'][8:]:
                local_fingerprint = gpg_key['fingerprint']
                local_keyid = gpg_key['keyid']
                break

        if local_keyid is None:
            raise SaltInvocationError(
                'The key ID \'{0}\' was not found in GnuPG keyring at \'{1}\''
                .format(keyid, gnupghome)
            )

        _check_repo_sign_utils_support()

        if use_passphrase:
            _check_repo_gpg_phrase_utils_support()
            phrase = __salt__['pillar.get']('gpg_passphrase')

        if older_gnupg:
            with salt.utils.fopen(gpg_info_file, 'r') as fow:
                gpg_raw_info = fow.readlines()

            for gpg_info_line in gpg_raw_info:
                gpg_info = gpg_info_line.split('=')
                gpg_info_dict = {gpg_info[0]: gpg_info[1]}
                __salt__['environ.setenv'](gpg_info_dict)
                break
        else:
            with salt.utils.fopen(gpg_tty_info_file, 'r') as fow:
                gpg_raw_info = fow.readlines()

            for gpg_tty_info_line in gpg_raw_info:
                gpg_tty_info = gpg_tty_info_line.split('=')
                gpg_tty_info_dict = {gpg_tty_info[0]: gpg_tty_info[1]}
                __salt__['environ.setenv'](gpg_tty_info_dict)
                break

            ## sign_it_here
            for file in os.listdir(repodir):
                if file.endswith('.dsc'):
                    abs_file = os.path.join(repodir, file)
                    number_retries = timeout / interval
                    times_looped = 0
                    error_msg = 'Failed to debsign file {0}'.format(abs_file)
                    cmd = 'debsign --re-sign -k {0} {1}'.format(keyid, abs_file)
                    try:
                        stdout, stderr = None, None
                        proc = salt.utils.vt.Terminal(
                            cmd,
                            shell=True,
                            stream_stdout=True,
                            stream_stderr=True
                        )
                        while proc.has_unread_data:
                            stdout, stderr = proc.recv()
                            if stdout and SIGN_PROMPT_RE.search(stdout):
                                # have the prompt for inputting the passphrase
                                proc.sendline(phrase)
                            else:
                                times_looped += 1

                            if times_looped > number_retries:
                                raise SaltInvocationError(
                                    'Attemping to sign file {0} failed, timed out after {1} seconds'
                                    .format(abs_file, int(times_looped * interval))
                                )
                            time.sleep(interval)

                        proc_exitstatus = proc.exitstatus
                        if proc_exitstatus != 0:
                            raise SaltInvocationError(
                                'Signing file {0} failed with proc.status {1}'
                                .format(abs_file, proc_exitstatus)
                            )
                    except salt.utils.vt.TerminalException as err:
                        trace = traceback.format_exc()
                        log.error(error_msg, err, trace)
                        res = {'retcode': 1,
                                'stdout': '',
                                'stderr': trace}
                    finally:
                        proc.close(terminate=True, kill=True)

        if use_passphrase:
            cmd = '/usr/lib/gnupg2/gpg-preset-passphrase --verbose --forget {0}'.format(local_fingerprint)
            __salt__['cmd.run'](cmd, runas=runas)

            cmd = '/usr/lib/gnupg2/gpg-preset-passphrase --verbose --preset --passphrase "{0}" {1}'.format(phrase, local_fingerprint)
            __salt__['cmd.run'](cmd, runas=runas)

    for debfile in os.listdir(repodir):
        abs_file = os.path.join(repodir, debfile)
        if debfile.endswith('.changes'):
            os.remove(abs_file)

        if debfile.endswith('.dsc'):
            if older_gnupg:
                if local_keyid is not None:
                    cmd = 'debsign --re-sign -k {0} {1}'.format(keyid, abs_file)
                    __salt__['cmd.run'](cmd, cwd=repodir, use_vt=True)

                cmd = 'reprepro --ignore=wrongdistribution --component=main -Vb . includedsc {0} {1}'.format(codename, abs_file)
                __salt__['cmd.run'](cmd, cwd=repodir, use_vt=True)
            else:
                number_retries = timeout / interval
                times_looped = 0
                error_msg = 'Failed to reprepro includedsc file {0}'.format(abs_file)
                cmd = 'reprepro --ignore=wrongdistribution --component=main -Vb . includedsc {0} {1}'.format(codename, abs_file)
                try:
                    stdout, stderr = None, None
                    proc = salt.utils.vt.Terminal(
                            cmd,
                            shell=True,
                            cwd=repodir,
                            env=gpg_tty_info_dict,
                            stream_stdout=True,
                            stream_stderr=True
                            )
                    while proc.has_unread_data:
                        stdout, stderr = proc.recv()
                        if stdout and REPREPRO_SIGN_PROMPT_RE.search(stdout):
                            # have the prompt for inputting the passphrase
                            proc.sendline(phrase)
                        else:
                            times_looped += 1

                        if times_looped > number_retries:
                            raise SaltInvocationError(
                                'Attemping to reprepro includedsc for file {0} failed, timed out after {1} loops'
                                .format(abs_file, int(times_looped * interval))
                             )
                        time.sleep(interval)

                    proc_exitstatus = proc.exitstatus
                    if proc_exitstatus != 0:
                        raise SaltInvocationError(
                             'Reprepro includedsc for codename {0} and file {1} failed with proc.status {2}'.format(codename, abs_file, proc_exitstatus)
                             )
                except salt.utils.vt.TerminalException as err:
                    trace = traceback.format_exc()
                    log.error(error_msg, err, trace)
                    res = {'retcode': 1,
                            'stdout': '',
                            'stderr': trace}
                finally:
                    proc.close(terminate=True, kill=True)

        if debfile.endswith('.deb'):
            cmd = 'reprepro --ignore=wrongdistribution --component=main -Vb . includedeb {0} {1}'.format(codename, abs_file)
            res = __salt__['cmd.run_all'](cmd, cwd=repodir, use_vt=True)

    if use_passphrase and local_keyid is not None:
        cmd = '/usr/lib/gnupg2/gpg-preset-passphrase --forget {0}'.format(local_fingerprint)
        res = __salt__['cmd.run_all'](cmd, runas=runas)

    return res
