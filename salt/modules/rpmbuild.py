# -*- coding: utf-8 -*-
'''
RPM Package builder system

.. versionadded:: 2015.8.0

This system allows for all of the components to build rpms safely in chrooted
environments. This also provides a function to generate yum repositories

This module impliments the pkgbuild interface
'''

# Import python libs
from __future__ import absolute_import, print_function
import errno
import logging
import os
import shutil
import tempfile

# Import salt libs
import salt.utils
from salt.exceptions import SaltInvocationError
from salt.ext.six.moves.urllib.parse import urlparse as _urlparse  # pylint: disable=no-name-in-module,import-error

log = logging.getLogger(__name__)

__virtualname__ = 'pkgbuild'


def __virtual__():
    '''
    Only if rpmdevtools, createrepo and mock are available
    '''
    if salt.utils.which('mock'):
        return __virtualname__
    return False


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
    with salt.utils.fopen(rpmmacros, 'w') as afile:
        afile.write('%_topdir {0}\n'.format(rpmbuilddir))
        afile.write('%signature gpg\n')
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
    # Centos adds that string to rpm names, removing that to have
    # consistent naming on Centos and Redhat
    tgtattrs = tgt.split('-')
    if tgtattrs[1] in ['5', '6', '7']:
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

        deps_list += ' --install {0}'.format(dest)

    return deps_list


def make_src_pkg(dest_dir, spec, sources, env=None, template=None, saltenv='base'):
    '''
    Create a source rpm from the given spec file and sources

    CLI Example:

        salt '*' pkgbuild.make_src_pkg /var/www/html/ https://raw.githubusercontent.com/saltstack/libnacl/master/pkg/rpm/python-libnacl.spec https://pypi.python.org/packages/source/l/libnacl/libnacl-1.3.5.tar.gz

    This example command should build the libnacl SOURCE package and place it in
    /var/www/html/ on the minion
    '''
    _create_rpmmacros()
    tree_base = _mk_tree()
    spec_path = _get_spec(tree_base, spec, template, saltenv)
    if isinstance(sources, str):
        sources = sources.split(',')
    for src in sources:
        _get_src(tree_base, src, saltenv)

    # make source rpms for dist el5, usable with mock on other dists
    cmd = 'rpmbuild --define "_topdir {0}" -bs --define "_source_filedigest_algorithm md5" --define "_binary_filedigest_algorithm md5" --define "dist .el5" {1}'.format(tree_base, spec_path)
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
    if deps_list and not deps_list.isspace():
        cmd = 'mock --root={0} {1}'.format(tgt, deps_list)
        __salt__['cmd.run'](cmd, runas=runas)
        noclean += ' --no-clean'

    for srpm in srpms:
        dbase = os.path.dirname(srpm)
        results_dir = tempfile.mkdtemp()
        try:
            __salt__['cmd.run']('chown {0} -R {1}'.format(runas, dbase))
            __salt__['cmd.run']('chown {0} -R {1}'.format(runas, results_dir))
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
            log.error('Error building from {0}: {1}'.format(srpm, exc))
        finally:
            shutil.rmtree(results_dir)
    shutil.rmtree(deps_dir)
    shutil.rmtree(srpm_build_dir)
    return ret


def make_repo(repodir, keyid=None, env=None):
    '''
    Given the repodir, create a yum repository out of the rpms therein

    CLI Example::

        salt '*' pkgbuild.make_repo /var/www/html/
    '''
    cmd = 'createrepo {0}'.format(repodir)
    __salt__['cmd.run'](cmd)
