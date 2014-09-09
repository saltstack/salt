# -*- coding: utf-8 -*-
'''
A module to wrap archive calls

.. versionadded:: 2014.1.0
'''

# Import salt libs
import salt._compat
from salt.utils import which as _which, which_bin as _which_bin
import salt.utils.decorators as decorators

# TODO: Check that the passed arguments are correct

# Don't shadow built-in's.
__func_alias__ = {
    'zip_': 'zip'
}


def __virtual__():
    commands = ('tar', 'gzip', 'gunzip', 'zip', 'unzip', 'rar', 'unrar')
    # If none of the above commands are in $PATH this module is a no-go
    if not any(_which(cmd) for cmd in commands):
        return False
    return True


@decorators.which('tar')
def tar(options, tarfile, sources=None, dest=None, cwd=None, template=None):
    '''
    .. note::

        This function has changed for version 0.17.0. In prior versions, the
        ``cwd`` and ``template`` arguments must be specified, with the source
        directories/files coming as a space-separated list at the end of the
        command. Beginning with 0.17.0, ``sources`` must be a comma-separated
        list, and the ``cwd`` and ``template`` arguments are optional.

    Uses the tar command to pack, unpack, etc tar files


    options:
        Options to pass to the ``tar`` binary.

    tarfile:
        The tar filename to pack/unpack.

    sources:
        Comma delimited list of files to **pack** into the tarfile.

    dest:
        The destination directory to **unpack** the tarfile to.

    cwd:
        The directory in which the tar command should be executed.

    template:
         Template engine name to render the command arguments before execution.

    CLI Example:

    .. code-block:: bash

        salt '*' archive.tar cjvf /tmp/tarfile.tar.bz2 /tmp/file_1,/tmp/file_2


    The template arg can be set to ``jinja`` or another supported template
    engine to render the command arguments before execution. For example:

    .. code-block:: bash

        salt '*' archive.tar cjvf /tmp/salt.tar.bz2 {{grains.saltpath}} template=jinja


    To unpack a tarfile, for example:

    .. code-block:: bash

        salt '*' archive.tar xf foo.tar dest=/target/directory

    '''
    if isinstance(sources, salt._compat.string_types):
        sources = [s.strip() for s in sources.split(',')]

    if dest:
        options = 'C {0} -{1}'.format(dest, options)

    cmd = 'tar -{0} {1}'.format(options, tarfile)
    if sources:
        cmd += ' {0}'.format(' '.join(sources))

    return __salt__['cmd.run'](cmd, cwd=cwd, template=template).splitlines()


@decorators.which('gzip')
def gzip(sourcefile, template=None):
    '''
    Uses the gzip command to create gzip files

    CLI Example to create ``/tmp/sourcefile.txt.gz``:

    .. code-block:: bash

        salt '*' archive.gzip /tmp/sourcefile.txt

    The template arg can be set to 'jinja' or another supported template
    engine to render the command arguments before execution.

    CLI Example:

    .. code-block:: bash

        salt '*' archive.gzip template=jinja /tmp/{{grains.id}}.txt

    '''
    cmd = 'gzip {0}'.format(sourcefile)
    return __salt__['cmd.run'](cmd, template=template).splitlines()


@decorators.which('gunzip')
def gunzip(gzipfile, template=None):
    '''
    Uses the gunzip command to unpack gzip files

    CLI Example to create ``/tmp/sourcefile.txt``:

    .. code-block:: bash

        salt '*' archive.gunzip /tmp/sourcefile.txt.gz

    The template arg can be set to 'jinja' or another supported template
    engine to render the command arguments before execution.

    CLI Example:

    .. code-block:: bash

        salt '*' archive.gunzip template=jinja /tmp/{{grains.id}}.txt.gz

    '''
    cmd = 'gunzip {0}'.format(gzipfile)
    return __salt__['cmd.run'](cmd, template=template).splitlines()


@decorators.which('zip')
def zip_(zipfile, sources, template=None):
    '''
    Uses the zip command to create zip files

    CLI Example:

    .. code-block:: bash

        salt '*' archive.zip /tmp/zipfile.zip /tmp/sourcefile1,/tmp/sourcefile2

    The template arg can be set to 'jinja' or another supported template
    engine to render the command arguments before execution.

    For example:

    .. code-block:: bash

        salt '*' archive.zip template=jinja /tmp/zipfile.zip /tmp/sourcefile1,/tmp/{{grains.id}}.txt

    '''
    if isinstance(sources, salt._compat.string_types):
        sources = [s.strip() for s in sources.split(',')]
    cmd = 'zip {0} {1}'.format(zipfile, ' '.join(sources))
    return __salt__['cmd.run'](cmd, template=template).splitlines()


@decorators.which('unzip')
def unzip(zipfile, dest, excludes=None, template=None, options=None):
    '''
    Uses the unzip command to unpack zip files

    options:
        Options to pass to the ``unzip`` binary.

    CLI Example:

    .. code-block:: bash

        salt '*' archive.unzip /tmp/zipfile.zip /home/strongbad/ excludes=file_1,file_2

    The template arg can be set to 'jinja' or another supported template
    engine to render the command arguments before execution.

    For example:

    .. code-block:: bash

        salt '*' archive.unzip template=jinja /tmp/zipfile.zip /tmp/{{grains.id}}/ excludes=file_1,file_2

    '''
    if isinstance(excludes, salt._compat.string_types):
        excludes = [entry.strip() for entry in excludes.split(',')]

    if options:
        cmd = 'unzip -{0} {1} -d {2}'.format(options, zipfile, dest)
    else:
        cmd = 'unzip {0} -d {1}'.format(zipfile, dest)

    if excludes is not None:
        cmd += ' -x {0}'.format(' '.join(excludes))
    return __salt__['cmd.run'](cmd, template=template).splitlines()


@decorators.which('rar')
def rar(rarfile, sources, template=None):
    '''
    Uses the rar command to create rar files
    Uses rar for Linux from http://www.rarlab.com/

    CLI Example:

    .. code-block:: bash

        salt '*' archive.rar /tmp/rarfile.rar /tmp/sourcefile1,/tmp/sourcefile2

    The template arg can be set to 'jinja' or another supported template
    engine to render the command arguments before execution.

    For example:

    .. code-block:: bash

        salt '*' archive.rar template=jinja /tmp/rarfile.rar /tmp/sourcefile1,/tmp/{{grains.id}}.txt


    '''
    if isinstance(sources, salt._compat.string_types):
        sources = [s.strip() for s in sources.split(',')]
    cmd = 'rar a -idp {0} {1}'.format(rarfile, ' '.join(sources))
    return __salt__['cmd.run'](cmd, template=template).splitlines()


@decorators.which_bin(('unrar', 'rar'))
def unrar(rarfile, dest, excludes=None, template=None):
    '''
    Uses the unrar command to unpack rar files
    Uses rar for Linux from http://www.rarlab.com/

    CLI Example:

    .. code-block:: bash

        salt '*' archive.unrar /tmp/rarfile.rar /home/strongbad/ excludes=file_1,file_2

    The template arg can be set to 'jinja' or another supported template
    engine to render the command arguments before execution.

    For example:

    .. code-block:: bash

        salt '*' archive.unrar template=jinja /tmp/rarfile.rar /tmp/{{grains.id}}/ excludes=file_1,file_2

    '''
    if isinstance(excludes, salt._compat.string_types):
        excludes = [entry.strip() for entry in excludes.split(',')]

    cmd = [_which_bin(('unrar', 'rar')), 'x', '-idp', rarfile]
    if excludes is not None:
        for exclude in excludes:
            cmd.extend(['-x', exclude])
    cmd.append(dest)
    return __salt__['cmd.run'](' '.join(cmd), template=template).splitlines()
