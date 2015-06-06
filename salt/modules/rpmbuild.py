'''
Make rpm buld tree
get sources
get spec
make srpm
run mock on the srpm
git srpm a target location
run createrepo on a target location

deps rpmdevtools, createrepo, mock
'''

# Import python libs
import os
import tempfile
import shutil
from salt.ext.six.moves.urllib.parse import urlparse as _urlparse


def _mk_tree():
    '''
    Create the rpm build tree
    '''
    basedir = tempfile.mkdtemp()
    paths = ['BUILD', 'RPMS', 'SOURCES', 'SPECS', 'SRPMS']
    for path in paths:
        full = os.path.join(basedir, 'rpmbuild', path)
        os.makedirs(full)
    return basedir


def _get_spec(tree_base, spec, template, saltenv='base'):
    '''
    Get the spec file and place it in the SPECS dir
    '''
    spec_tgt = os.path.basename(spec)
    dest = os.path.join(tree_base, 'rpmbuild', 'SPECS', spec_tgt)
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
    dest = os.path.join(tree_base, 'rpmbuild', 'SOURCES', sbase)
    if parsed.scheme:
        lsrc = __salt__['cp.get_file'](source, dest, saltenv=saltenv)
    else:
        shutil.copy(source, dest)


def mksrpm(dest_dir, spec, sources, template, saltenv='base'):
    '''
    Create a source rpm from the given 
    '''
    tree_base = _mk_tree()
    spec_path = _get_spec(tree_base, spec, template, saltenv)
    if isinstance(sources, str):
        sources = sources.split(',')
    for src in sources:
        _get_src(tree_base, src, saltenv)
    cmd = 'rpmbuild -bs {0}'.format(spec_path)
    __salt__['cmd.run'](cmd)
    srpms = os.path.join(tree_base, 'rpmbuild', 'SRPMS')
    ret = []
    if not os.path.isdir(dest_dir):
        os.makedirs(dest_dir)
    for fn_ in os.listdir(srpms):
        full = os.path.join(srpms, fn_)
        tgt = os.path.join(dest_dir, fn_)
        shutil.move(full, tgt)
        ret.append(tgt)
    return ret
