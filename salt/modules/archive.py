'''
A module to wrap archive calls
'''


def tar(options, tarfile, *sources):
    '''
    Uses the tar command to pack, unpack, etc tar files

    CLI Example::

        salt '*' archive.tar cjvf /tmp/tarfile.tar.bz2 /tmp/file1 /tmp/file2
    '''
    sourcefiles = ' '.join(sources)
    cmd = 'tar -{0} {1} {2}'.format(options, tarfile, sourcefiles)
    out = __salt__['cmd.run'](cmd).strip().split('\n')
    return out


def gzip(sourcefile):
    '''
    Uses the gzip command to create gzip files

    CLI Example to create ``/tmp/sourcefile.txt.gz``::

        salt '*' archive.gzip /tmp/sourcefile.txt
    '''
    cmd = 'gzip {0}'.format(sourcefile)
    out = __salt__['cmd.run'](cmd).strip().split('\n')
    return out


def gunzip(gzipfile):
    '''
    Uses the gunzip command to unpack gzip files

    CLI Example to create ``/tmp/sourcefile.txt``::

        salt '*' archive.gunzip /tmp/sourcefile.txt.gz
    '''
    cmd = 'gunzip {0}'.format(gzipfile)
    out = __salt__['cmd.run'](cmd).strip().split('\n')
    return out


def zip(zipfile, *sources):
    '''
    Uses the zip command to create zip files

    CLI Example::

        salt '*' archive.zip /tmp/zipfile.zip /tmp/sourcefile1 /tmp/sourcefile2
    '''
    sourcefiles = ' '.join(sources)
    cmd = 'zip {0} {1}'.format(zipfile, sourcefiles)
    out = __salt__['cmd.run'](cmd).strip().split('\n')
    return out


def unzip(zipfile, dest, *xfiles):
    '''
    Uses the unzip command to unpack zip files

    CLI Example::

        salt '*' archive.unzip /tmp/zipfile.zip /home/strongbad/ file1 file2
    '''
    xfileslist = ' '.join(xfiles)
    cmd = 'unzip {0} -d {1}'.format(zipfile, dest)
    if xfileslist:
        cmd = cmd + ' -x {0}'.format(xfiles)
    out = __salt__['cmd.run'](cmd).strip().split('\n')
    return out


def rar(rarfile, *sources):
    '''
    Uses the rar command to create rar files
    Uses rar for Linux from http://www.rarlab.com/

    CLI Example::

        salt '*' archive.rar /tmp/rarfile.rar /tmp/sourcefile1 /tmp/sourcefile2
    '''
    sourcefiles = ' '.join(sources)
    cmd = 'rar a -idp {0} {1}'.format(rarfile, sourcefiles)
    out = __salt__['cmd.run'](cmd).strip().split('\n')
    return out


def unrar(rarfile, dest, *xfiles):
    '''
    Uses the unrar command to unpack rar files
    Uses rar for Linux from http://www.rarlab.com/

    CLI Example::

        salt '*' archive.unrar /tmp/rarfile.rar /home/strongbad/ file1 file2
    '''
    xfileslist = ' '.join(xfiles)
    cmd = 'rar x -idp {0}'.format(rarfile, dest)
    if xfileslist:
        cmd = cmd + ' {0}'.format(xfiles)
    cmd = cmd + ' {0}'.format(dest)
    out = __salt__['cmd.run'](cmd).strip().split('\n')
    return out
