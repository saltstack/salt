'''
RPM Package builder system

This system allows for all of th ecomponents to build rpms safely in chrooted
environments. This also provides a function to generate yum repositories

This module impliments the pkgbuild interface
'''

# Import python libs
import os
import tempfile
import shutil
from salt.ext.six.moves.urllib.parse import urlparse as _urlparse

# Import salt libs
import salt.utils

__virtualname__ = 'pkgbuild'


def __virtual__():
    '''
    Only if rpmdevtools, createrepo and mock are available
    '''
    if salt.utils.which('mock'):
        return __virtualname__


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
    return __salt__['cp.get_file'](
            spec,
            dest,
            saltenv=saltenv,
            template=template)


def _get_src(tree_base, source, saltenv='base'):
    '''
    Get the named sources and place them into the tree_base
    '''
    parsed = _urlparse(source)
    sbase = os.path.basename(source)
    dest = os.path.join(tree_base, 'SOURCES', sbase)
    if parsed.scheme:
        lsrc = __salt__['cp.get_file'](source, dest, saltenv=saltenv)
    else:
        shutil.copy(source, dest)


def make_src_pkg(dest_dir, spec, sources, template=None, saltenv='base'):
    '''
    Create a source rpm from the given spec file and sources

    CLI Example:

        salt '*' pkgbuild.make_src_pkg /var/www/html/ https://raw.githubusercontent.com/saltstack/libnacl/master/pkg/rpm/python-libnacl.spec https://pypi.python.org/packages/source/l/libnacl/libnacl-1.3.5.tar.gz

    This example command should build the libnacl SOURCE package and place it in
    /var/www/html/ on the minion
    '''
    tree_base = _mk_tree()
    spec_path = _get_spec(tree_base, spec, template, saltenv)
    if isinstance(sources, str):
        sources = sources.split(',')
    for src in sources:
        _get_src(tree_base, src, saltenv)
    cmd = 'rpmbuild --define "_topdir {0}" -bs {1}'.format(tree_base, spec_path)
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


def build(runas, tgt, dest_dir, spec, sources, template, saltenv='base'):
    '''
    Given the package destination directory, the spec file source and package
    sources, use mock to safely build the rpm defined in the spec file

    CLI Example:

        salt '*' pkgbuild.make_src_pkg mock epel-7-x86_64 /var/www/html/ https://raw.githubusercontent.com/saltstack/libnacl/master/pkg/rpm/python-libnacl.spec https://pypi.python.org/packages/source/l/libnacl/libnacl-1.3.5.tar.gz

    This example command should build the libnacl package for rhel 7 using user
    "mock" and place it in /var/www/html/ on the minion
    '''
    ret = {}
    if not os.path.isdir(dest_dir):
        try:
            os.makedirs(dest_dir)
        except (IOError, OSError):
            pass
    srpm_dir = tempfile.mkdtemp()
    srpms = make_src_pkg(srpm_dir, spec, sources, template, saltenv)
    for srpm in srpms:
        dbase = os.path.dirname(srpm)
        cmd = 'chown {0} -R {1}'.format(runas, dbase)
        __salt__['cmd.run'](cmd)
        results_dir = tempfile.mkdtemp()
        cmd = 'chown {0} -R {1}'.format(runas, results_dir)
        __salt__['cmd.run'](cmd)
        cmd = 'mock -r {0} --rebuild {1} --resultdir {2}'.format(
                tgt,
                srpm,
                results_dir)
        __salt__['cmd.run'](cmd, runas=runas)
        for rpm in os.listdir(results_dir):
            full = os.path.join(results_dir, rpm)
            if rpm.endswith('src.rpm'):
                sdest = os.path.join(dest_dir, 'SRPMS', rpm)
                if not os.path.isdir(sdest):
                    try:
                        os.makedirs(sdest)
                    except (IOError, OSError):
                        pass
                shutil.copy(full, sdest)
            elif rpm.endswith('.rpm'):
                bdist = os.path.join(dest_dir, rpm)
                shutil.copy(full, bdist)
            else:
                with salt.utils.fopen(full, 'r') as fp_:
                    ret[rpm] = fp_.read()
        shutil.rmtree(results_dir)
    shutil.rmtree(srpm_dir)
    return ret


def make_repo(repodir):
    '''
    Given the repodir, create a yum repository out of the rpms therein

    CLI Example::

        salt '*' pkgbuild.make_repo /var/www/html/
    '''
    cmd = 'createrepo {0}'.format(repodir)
    __salt__['cmd.run'](cmd)
