'''
A module to wrap archive calls
'''

# Import salt libs
from salt.utils import which as _which
# TODO: Add wrapping to each function to check for existance of the binary
# TODO: Check that the passed arguments are correct


def __virtual__():
    commands = ('tar', 'gzip', 'gunzip', 'zip', 'unzip', 'rar', 'unrar')
    # If none of the above commands are in $PATH this module is a no-go
    if not any(_which(cmd) for cmd in commands):
        return False
    return 'archive'


def tar(options, tarfile, cwd=None, template=None, *sources):
    '''
    Uses the tar command to pack, unpack, etc tar files

    CLI Example::

        salt '*' archive.tar cjvf /tmp/tarfile.tar.bz2 /tmp/file_1 /tmp/file_2
    '''
    sourcefiles = ' '.join(sources)
    cmd = 'tar -{0} {1} {2}'.format(options, tarfile, sourcefiles)
    out = __salt__['cmd.run'](cmd, cwd, template=template).splitlines()
    return out


def gzip(sourcefile, template=None):
    '''
    Uses the gzip command to create gzip files

    CLI Example to create ``/tmp/sourcefile.txt.gz``::

        salt '*' archive.gzip /tmp/sourcefile.txt
    '''
    cmd = 'gzip {0}'.format(sourcefile)
    out = __salt__['cmd.run'](cmd, template=template).splitlines()
    return out


def gunzip(gzipfile, template=None):
    '''
    Uses the gunzip command to unpack gzip files

    CLI Example to create ``/tmp/sourcefile.txt``::

        salt '*' archive.gunzip /tmp/sourcefile.txt.gz
    '''
    cmd = 'gunzip {0}'.format(gzipfile)
    out = __salt__['cmd.run'](cmd, template=template).splitlines()
    return out


def zip(zipfile, template=None, *sources):
    '''
    Uses the zip command to create zip files

    CLI Example::

        salt '*' archive.zip /tmp/zipfile.zip /tmp/sourcefile1 /tmp/sourcefile2
    '''
    sourcefiles = ' '.join(sources)
    cmd = 'zip {0} {1}'.format(zipfile, sourcefiles)
    out = __salt__['cmd.run'](cmd, template=template).splitlines()
    return out


def unzip(zipfile, dest, template=None, *xfiles):
    '''
    Uses the unzip command to unpack zip files

    CLI Example::

        salt '*' archive.unzip /tmp/zipfile.zip /home/strongbad/ file_1 file_2
    '''
    xfileslist = ' '.join(xfiles)
    cmd = 'unzip {0} -d {1}'.format(zipfile, dest)
    if xfileslist:
        cmd = cmd + ' -x {0}'.format(xfiles)
    out = __salt__['cmd.run'](cmd, template=template).splitlines()
    return out


def rar(rarfile, template=None, *sources):
    '''
    Uses the rar command to create rar files
    Uses rar for Linux from http://www.rarlab.com/

    CLI Example::

        salt '*' archive.rar /tmp/rarfile.rar /tmp/sourcefile1 /tmp/sourcefile2
    '''
    # TODO: Check that len(sources) >= 1
    sourcefiles = ' '.join(sources)
    cmd = 'rar a -idp {0} {1}'.format(rarfile, sourcefiles)
    out = __salt__['cmd.run'](cmd, template=template).splitlines()
    return out


def unrar(rarfile, dest, template=None, *xfiles):
    '''
    Uses the unrar command to unpack rar files
    Uses rar for Linux from http://www.rarlab.com/

    CLI Example::

        salt '*' archive.unrar /tmp/rarfile.rar /home/strongbad/ file_1 file_2
    '''
    xfileslist = ' '.join(xfiles)
    cmd = 'rar x -idp {0}'.format(rarfile, dest)
    if xfileslist:
        cmd = cmd + ' {0}'.format(xfiles)
    cmd = cmd + ' {0}'.format(dest)
    out = __salt__['cmd.run'](cmd, template=template).splitlines()
    return out
