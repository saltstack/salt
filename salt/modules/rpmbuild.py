# -*- coding: utf-8 -*-
'''
RPM Package builder system

.. versionadded:: 2015.8.0

This system allows for all of the components to build rpms safely in chrooted
environments. This also provides a function to generate yum repositories

This module implements the pkgbuild interface
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import errno
import logging
import os
import shutil
import tempfile
import time
import re
import traceback
import functools

# Import salt libs
from salt.exceptions import SaltInvocationError
import salt.utils.files
import salt.utils.path
import salt.utils.user
import salt.utils.vt

# Import 3rd-party libs
from salt.ext import six
from salt.ext.six.moves.urllib.parse import urlparse as _urlparse  # pylint: disable=no-name-in-module,import-error

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
    Confirm this module is on a RPM based system, and has required utilities
    '''
    missing_util = False
    utils_reqd = ['gpg', 'rpm', 'rpmbuild', 'mock', 'createrepo']
    for named_util in utils_reqd:
        if not salt.utils.path.which(named_util):
            missing_util = True
            break

    if HAS_LIBS and not missing_util:
        if __grains__.get('os_family', False) in ('RedHat', 'Suse'):
            return __virtualname__
        else:
            # The module will be exposed as `rpmbuild` on non-RPM based systems
            return 'rpmbuild'
    else:
        return False, 'The rpmbuild module could not be loaded: requires python-gnupg, gpg, rpm, rpmbuild, mock and createrepo utilities to be installed'


def _create_rpmmacros():
    '''
    Create the .rpmmacros file in user's home directory
    '''
    home = os.path.expanduser('~')
    rpmbuilddir = os.path.join(home, 'rpmbuild')
    if not os.path.isdir(rpmbuilddir):
        os.makedirs(rpmbuilddir)

    mockdir = os.path.join(home, 'mock')
    if not os.path.isdir(mockdir):
        os.makedirs(mockdir)

    rpmmacros = os.path.join(home, '.rpmmacros')
    with salt.utils.files.fopen(rpmmacros, 'w') as afile:
        afile.write(
            salt.utils.stringutils.to_str('%_topdir {0}\n'.format(rpmbuilddir))
        )
        afile.write('%signature gpg\n')
        afile.write('%_source_filedigest_algorithm 8\n')
        afile.write('%_binary_filedigest_algorithm 8\n')
        afile.write('%_gpg_name packaging@saltstack.com\n')


def _mk_tree():
    '''
    Create the rpm build tree
    '''
    basedir = tempfile.mkdtemp()
    paths = ['BUILD', 'RPMS', 'SOURCES', 'SPECS', 'SRPMS']
    for path in paths:
        full = os.path.join(basedir, path)
        os.makedirs(full)
    return basedir


def _get_spec(tree_base, spec, template, saltenv='base'):
    '''
    Get the spec file and place it in the SPECS dir
    '''
    spec_tgt = os.path.basename(spec)
    dest = os.path.join(tree_base, 'SPECS', spec_tgt)
    return __salt__['cp.get_url'](
        spec,
        dest,
        saltenv=saltenv)


def _get_src(tree_base, source, saltenv='base'):
    '''
    Get the named sources and place them into the tree_base
    '''
    parsed = _urlparse(source)
    sbase = os.path.basename(source)
    dest = os.path.join(tree_base, 'SOURCES', sbase)
    if parsed.scheme:
        lsrc = __salt__['cp.get_url'](source, dest, saltenv=saltenv)
    else:
        shutil.copy(source, dest)


def _get_distset(tgt):
    '''
    Get the distribution string for use with rpmbuild and mock
    '''
    # Centos adds 'centos' string to rpm names, removing that to have
    # consistent naming on Centos and Redhat, and allow for Amazon naming
    tgtattrs = tgt.split('-')
    if tgtattrs[0] == 'amzn':
        distset = '--define "dist .{0}1"'.format(tgtattrs[0])
    elif tgtattrs[1] in ['6', '7']:
        distset = '--define "dist .el{0}"'.format(tgtattrs[1])
    else:
        distset = ''

    return distset


def _get_deps(deps, tree_base, saltenv='base'):
    '''
    Get include string for list of dependent rpms to build package
    '''
    deps_list = ''
    if deps is None:
        return deps_list
    if not isinstance(deps, list):
        raise SaltInvocationError(
            '\'deps\' must be a Python list or comma-separated string'
        )
    for deprpm in deps:
        parsed = _urlparse(deprpm)
        depbase = os.path.basename(deprpm)
        dest = os.path.join(tree_base, depbase)
        if parsed.scheme:
            __salt__['cp.get_url'](deprpm, dest, saltenv=saltenv)
        else:
            shutil.copy(deprpm, dest)

        deps_list += ' {0}'.format(dest)

    return deps_list


def make_src_pkg(dest_dir, spec, sources, env=None, template=None, saltenv='base'):
    '''
    Create a source rpm from the given spec file and sources

    CLI Example:

    .. code-block:: bash

        salt '*' pkgbuild.make_src_pkg /var/www/html/ https://raw.githubusercontent.com/saltstack/libnacl/master/pkg/rpm/python-libnacl.spec https://pypi.python.org/packages/source/l/libnacl/libnacl-1.3.5.tar.gz

    This example command should build the libnacl SOURCE package and place it in
    /var/www/html/ on the minion

    .. versionchanged:: 2017.7.0

    .. note::

        using SHA256 as digest and minimum level dist el6

    '''
    _create_rpmmacros()
    tree_base = _mk_tree()
    spec_path = _get_spec(tree_base, spec, template, saltenv)
    if isinstance(sources, six.string_types):
        sources = sources.split(',')
    for src in sources:
        _get_src(tree_base, src, saltenv)

    # make source rpms for dist el6 with SHA256, usable with mock on other dists
    cmd = 'rpmbuild --verbose --define "_topdir {0}" -bs --define "dist .el6" {1}'.format(tree_base, spec_path)
    __salt__['cmd.run'](cmd)
    srpms = os.path.join(tree_base, 'SRPMS')
    ret = []
    if not os.path.isdir(dest_dir):
        os.makedirs(dest_dir)
    for fn_ in os.listdir(srpms):
        full = os.path.join(srpms, fn_)
        tgt = os.path.join(dest_dir, fn_)
        shutil.copy(full, tgt)
        ret.append(tgt)
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
          log_dir='/var/log/salt/pkgbuild'):
    '''
    Given the package destination directory, the spec file source and package
    sources, use mock to safely build the rpm defined in the spec file

    CLI Example:

    .. code-block:: bash

        salt '*' pkgbuild.build mock epel-7-x86_64 /var/www/html https://raw.githubusercontent.com/saltstack/libnacl/master/pkg/rpm/python-libnacl.spec https://pypi.python.org/packages/source/l/libnacl/libnacl-1.3.5.tar.gz

    This example command should build the libnacl package for rhel 7 using user
    mock and place it in /var/www/html/ on the minion
    '''
    ret = {}
    try:
        os.makedirs(dest_dir)
    except OSError as exc:
        if exc.errno != errno.EEXIST:
            raise
    srpm_dir = os.path.join(dest_dir, 'SRPMS')
    srpm_build_dir = tempfile.mkdtemp()
    try:
        srpms = make_src_pkg(srpm_build_dir, spec, sources,
                             env, template, saltenv)
    except Exception as exc:
        shutil.rmtree(srpm_build_dir)
        log.error('Failed to make src package')
        return ret

    distset = _get_distset(tgt)

    noclean = ''
    deps_dir = tempfile.mkdtemp()
    deps_list = _get_deps(deps, deps_dir, saltenv)

    for srpm in srpms:
        dbase = os.path.dirname(srpm)
        results_dir = tempfile.mkdtemp()
        try:
            __salt__['cmd.run']('chown {0} -R {1}'.format(runas, dbase))
            __salt__['cmd.run']('chown {0} -R {1}'.format(runas, results_dir))
            cmd = 'mock --root={0} --resultdir={1} --init'.format(tgt, results_dir)
            __salt__['cmd.run'](cmd, runas=runas)
            if deps_list and not deps_list.isspace():
                cmd = 'mock --root={0} --resultdir={1} --install {2} {3}'.format(tgt, results_dir, deps_list, noclean)
                __salt__['cmd.run'](cmd, runas=runas)
                noclean += ' --no-clean'

            cmd = 'mock --root={0} --resultdir={1} {2} {3} {4}'.format(
                tgt,
                results_dir,
                distset,
                noclean,
                srpm)
            __salt__['cmd.run'](cmd, runas=runas)
            cmd = ['rpm', '-qp', '--queryformat',
                   '{0}/%{{name}}/%{{version}}-%{{release}}'.format(log_dir),
                   srpm]
            log_dest = __salt__['cmd.run_stdout'](cmd, python_shell=False)
            for filename in os.listdir(results_dir):
                full = os.path.join(results_dir, filename)
                if filename.endswith('src.rpm'):
                    sdest = os.path.join(srpm_dir, filename)
                    try:
                        os.makedirs(srpm_dir)
                    except OSError as exc:
                        if exc.errno != errno.EEXIST:
                            raise
                    shutil.copy(full, sdest)
                    ret.setdefault('Source Packages', []).append(sdest)
                elif filename.endswith('.rpm'):
                    bdist = os.path.join(dest_dir, filename)
                    shutil.copy(full, bdist)
                    ret.setdefault('Packages', []).append(bdist)
                else:
                    log_file = os.path.join(log_dest, filename)
                    try:
                        os.makedirs(log_dest)
                    except OSError as exc:
                        if exc.errno != errno.EEXIST:
                            raise
                    shutil.copy(full, log_file)
                    ret.setdefault('Log Files', []).append(log_file)
        except Exception as exc:
            log.error('Error building from %s: %s', srpm, exc)
        finally:
            shutil.rmtree(results_dir)
    shutil.rmtree(deps_dir)
    shutil.rmtree(srpm_build_dir)
    return ret


def make_repo(repodir,
              keyid=None,
              env=None,
              use_passphrase=False,
              gnupghome='/etc/salt/gpgkeys',
              runas='root',
              timeout=15.0):
    '''
    Make a package repository and optionally sign packages present

    Given the repodir, create a ``yum`` repository out of the rpms therein
    and optionally sign it and packages present, the name is directory to
    turn into a repo. This state is best used with onchanges linked to
    your package building states.

    repodir
        The directory to find packages that will be in the repository.

    keyid
        .. versionchanged:: 2016.3.0

        Optional Key ID to use in signing packages and repository.
        Utilizes Public and Private keys associated with keyid which have
        been loaded into the minion's Pillar data.

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

        .. note::

            This parameter is not used for making ``yum`` repositories.

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

        salt '*' pkgbuild.make_repo /var/www/html/

    '''
    SIGN_PROMPT_RE = re.compile(r'Enter pass phrase: ', re.M)

    define_gpg_name = ''
    local_keyid = None
    local_uids = None
    phrase = ''

    if keyid is not None:
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
        # retrieve specified key and preset passphrase
        local_keys = __salt__['gpg.list_keys'](user=runas, gnupghome=gnupghome)
        for gpg_key in local_keys:
            if keyid == gpg_key['keyid'][8:]:
                local_uids = gpg_key['uids']
                local_keyid = gpg_key['keyid']
                break

        if local_keyid is None:
            raise SaltInvocationError(
                'The key ID \'{0}\' was not found in GnuPG keyring at \'{1}\''
                .format(keyid, gnupghome)
            )

        if use_passphrase:
            phrase = __salt__['pillar.get']('gpg_passphrase')

        if local_uids:
            define_gpg_name = '--define=\'%_signature gpg\' --define=\'%_gpg_name {0}\''.format(
                local_uids[0]
            )

        # need to update rpm with public key
        cmd = 'rpm --import {0}'.format(pkg_pub_key_file)
        __salt__['cmd.run'](cmd, runas=runas, use_vt=True)

        ## sign_it_here
        # interval of 0.125 is really too fast on some systems
        interval = 0.5
        for file in os.listdir(repodir):
            if file.endswith('.rpm'):
                abs_file = os.path.join(repodir, file)
                number_retries = timeout / interval
                times_looped = 0
                error_msg = 'Failed to sign file {0}'.format(abs_file)
                cmd = 'rpm {0} --addsign {1}'.format(define_gpg_name, abs_file)
                preexec_fn = functools.partial(salt.utils.user.chugid_and_umask, runas, None)
                try:
                    stdout, stderr = None, None
                    proc = salt.utils.vt.Terminal(
                        cmd,
                        shell=True,
                        preexec_fn=preexec_fn,
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
                finally:
                    proc.close(terminate=True, kill=True)

    cmd = 'createrepo --update {0}'.format(repodir)
    return __salt__['cmd.run_all'](cmd, runas=runas)
