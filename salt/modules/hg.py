'''
Support for the Mercurial SCM
'''

def revision(cwd, rev='tip', short=False):
    '''
    Returns the long hash of a given identifier (hash, branch, tag, HEAD, etc)

    Usage::

        salt '*' hg.revision /path/to/repo mybranch
    '''
    cmd = 'hg id -i{short} {ref}'.format(
        short = ' --debug' if not short else '',
        rev = ' -r {0}'.format(rev))

    result = __salt__['cmd.run_all'](cmd, cwd=cwd)

    if result['retcode'] == 0:
        return result['stdout'].strip('\n')
    else:
        return ''

def describe(cwd, rev='tip'):
    '''
    Mimick git describe and return an identifier for the given revision

    Usage::

        salt '*' hg.describe /path/to/repo
    '''
    cmd = "hg log -r {0} --template"\
            " '{{latesttag}}-{{latesttagdistance}}-{{node|short}}'".format(rev)
    desc = __salt__['cmd.run_stdout'](cmd, cwd=cwd)

    return desc or revision(cwd, rev, short=True)

def archive(cwd, output, rev='tip', fmt='', prefix=''):
    '''
    Export a tarball from the repository

    If ``prefix`` is not specified it defaults to the basename of the repo
    directory.

    Usage::

        salt '*' hg.archive /path/to/repo /path/to/archive.tar.gz
    '''
    cmd = 'hg archive {output}{rev}{fmt}'.format(
        rev = ' --rev {0}'.format(rev),
        output = output,
        fmt = ' --type {0}'.format(fmt) if fmt else '',
        prefix = ' --prefix "{0}"'.format(prefix if prefix else ''))

    return __salt__['cmd.run'](cmd, cwd=cwd)

def pull(cwd, opts=''):
    '''
    Perform a pull on the given repository

    Usage::

        salt '*' hg.pull /path/to/repo '-u'
    '''
    return __salt__['cmd.run']('hg pull {0}'.format(opts), cwd=cwd)

def update(cwd, rev, force=False):
    '''
    Checkout a given revision

    Usage::

        salt '*' hg.update /path/to/repo somebranch
    '''
    cmd = 'hg update {0}{1}'.format(rev, ' -C' if force else '')
    return __salt__['cmd.run'](cmd, cwd=cwd)

def clone(cwd, repository, opts=''):
    '''
    Clone a new repository

    Usage::

        salt '*' hg.clone /path/to/repo https://bitbucket.org/birkenfeld/sphinx
    '''
    cmd = 'hg clone {0} {1} {2}'.format(repository, cwd, opts)
    return __salt__['cmd.run'](cmd)
