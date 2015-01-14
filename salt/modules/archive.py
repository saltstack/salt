# -*- coding: utf-8 -*-
'''
A module to wrap (non-Windows) archive calls

.. versionadded:: 2014.1.0
'''

# Import salt libs
from salt.exceptions import SaltInvocationError
from salt.ext.six import string_types
from salt.utils import \
    which as _which, which_bin as _which_bin, is_windows as _is_windows
import salt.utils.decorators as decorators

# TODO: Check that the passed arguments are correct

# Don't shadow built-in's.
__func_alias__ = {
    'zip_': 'zip'
}


def __virtual__():
    if _is_windows():
        return False
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

    Uses the tar command to pack, unpack, etc. tar files


    options
        Options to pass to the tar command

    tarfile
        The filename of the tar archive to pack/unpack

    sources
        Comma delimited list of files to **pack** into the tarfile. Can also be
        passed as a python list.

    dest
        The destination directory into which to **unpack** the tarfile

    cwd : None
        The directory in which the tar command should be executed. If not
        specified, will default to the home directory of the user under which
        the salt minion process is running.

    template : None
        Can be set to 'jinja' or another supported template engine to render
        the command arguments before execution:

        .. code-block:: bash

            salt '*' archive.tar cjvf /tmp/salt.tar.bz2 {{grains.saltpath}} template=jinja

    CLI Examples:

    .. code-block:: bash

        # Create a tarfile
        salt '*' archive.tar cjvf /tmp/tarfile.tar.bz2 /tmp/file_1,/tmp/file_2
        # Unpack a tarfile
        salt '*' archive.tar xf foo.tar dest=/target/directory
    '''
    if not options:
        # Catch instances were people pass an empty string for the "options"
        # argument. Someone would have to be really silly to do this, but we
        # should at least let them know of their silliness.
        raise SaltInvocationError('Tar options can not be empty')

    if isinstance(sources, string_types):
        sources = [s.strip() for s in sources.split(',')]

    cmd = ['tar']
    if dest:
        cmd.extend(['-C', '{0}'.format(dest)])

    cmd.extend(['-{0}'.format(options), '{0}'.format(tarfile)])
    cmd.extend(sources)

    return __salt__['cmd.run'](cmd,
                               cwd=cwd,
                               template=template,
                               python_shell=False).splitlines()


@decorators.which('gzip')
def gzip(sourcefile, template=None):
    '''
    Uses the gzip command to create gzip files

    template : None
        Can be set to 'jinja' or another supported template engine to render
        the command arguments before execution:

        .. code-block:: bash

            salt '*' archive.gzip template=jinja /tmp/{{grains.id}}.txt

    CLI Example:

    .. code-block:: bash

        # Create /tmp/sourcefile.txt.gz
        salt '*' archive.gzip /tmp/sourcefile.txt
    '''
    cmd = ['gzip', '{0}'.format(sourcefile)]
    return __salt__['cmd.run'](cmd,
                               template=template,
                               python_shell=False).splitlines()


@decorators.which('gunzip')
def gunzip(gzipfile, template=None):
    '''
    Uses the gunzip command to unpack gzip files

    template : None
        Can be set to 'jinja' or another supported template engine to render
        the command arguments before execution:

        .. code-block:: bash

            salt '*' archive.gunzip template=jinja /tmp/{{grains.id}}.txt.gz

    CLI Example:

    .. code-block:: bash

        # Create /tmp/sourcefile.txt
        salt '*' archive.gunzip /tmp/sourcefile.txt.gz
    '''
    cmd = ['gunzip', '{0}'.format(gzipfile)]
    return __salt__['cmd.run'](cmd,
                               template=template,
                               python_shell=False).splitlines()


@decorators.which('zip')
def zip_(zipfile, sources, template=None, cwd=None):
    '''
    Uses the ``zip`` command to create zip files. This command is part of the
    `Info-ZIP`_ suite of tools, and is typically packaged as simply ``zip``.

    .. _`Info-ZIP`: http://www.info-zip.org/

    zipfile
        Path of zip file to be created

    sources
        Comma-separated list of sources to include in the zip file. Sources can
        also be passed in a Python list.

    template : None
        Can be set to 'jinja' or another supported template engine to render
        the command arguments before execution:

        .. code-block:: bash

            salt '*' archive.zip template=jinja /tmp/zipfile.zip /tmp/sourcefile1,/tmp/{{grains.id}}.txt

    cwd : None
        Use this argument along with relative paths in ``sources`` to create
        zip files which do not contain the leading directories. If not
        specified, the zip file will be created as if the cwd was ``/``, and
        creating a zip file of ``/foo/bar/baz.txt`` will contain the parent
        directories ``foo`` and ``bar``. To create a zip file containing just
        ``baz.txt``, the following command would be used:

        .. code-block:: bash

            salt '*' archive.zip /tmp/baz.zip baz.txt cwd=/foo/bar

        .. versionadded:: 2014.7.1


    CLI Example:

    .. code-block:: bash

        salt '*' archive.zip /tmp/zipfile.zip /tmp/sourcefile1,/tmp/sourcefile2
    '''
    if isinstance(sources, string_types):
        sources = [s.strip() for s in sources.split(',')]
    cmd = ['zip', '-r']
    cmd.append('{0}'.format(zipfile))
    cmd.extend(sources)
    return __salt__['cmd.run'](cmd,
                               cwd=cwd,
                               template=template,
                               python_shell=False).splitlines()


@decorators.which('unzip')
def unzip(zipfile, dest, excludes=None, template=None, options=None):
    '''
   Uses the ``unzip`` command to unpack zip files. This command is part of the
    `Info-ZIP`_ suite of tools, and is typically packaged as simply ``unzip``.

    .. _`Info-ZIP`: http://www.info-zip.org/

    zipfile
        Path of zip file to be unpacked

    dest
        The destination directory into which the file should be unpacked

    excludes : None
        Comma-separated list of files not to unpack. Can also be passed in a
        Python list.

    template : None
        Can be set to 'jinja' or another supported template engine to render
        the command arguments before execution:

        .. code-block:: bash

            salt '*' archive.unzip template=jinja /tmp/zipfile.zip /tmp/{{grains.id}}/ excludes=file_1,file_2

    options : None
        Additional command-line options to pass to the ``unzip`` binary.


    CLI Example:

    .. code-block:: bash

        salt '*' archive.unzip /tmp/zipfile.zip /home/strongbad/ excludes=file_1,file_2
    '''
    if isinstance(excludes, string_types):
        excludes = [entry.strip() for entry in excludes.split(',')]

    cmd = ['unzip']
    if options:
        try:
            if not options.startswith('-'):
                options = '-{0}'.format(options)
        except AttributeError:
            raise SaltInvocationError(
                'Invalid option(s): {0}'.format(options)
            )
        cmd.append(options)
    cmd.extend(['{0}'.format(zipfile), '-d', '{0}'.format(dest)])

    if excludes is not None:
        cmd.append('-x')
        cmd.extend(excludes)
    return __salt__['cmd.run'](cmd,
                               template=template,
                               python_shell=False).splitlines()


@decorators.which('rar')
def rar(rarfile, sources, template=None, cwd=None):
    '''
    Uses `rar for Linux`_ to create rar files

    .. _`rar for Linux`: http://www.rarlab.com/

    rarfile
        Path of rar file to be created

    sources
        Comma-separated list of sources to include in the rar file. Sources can
        also be passed in a python list.

    cwd : None
        Run the rar command from the specified directory. Use this argument
        along with relative file paths to create rar files which do not
        contain the leading directories. If not specified, this will default
        to the home directory of the user under which the salt minion process
        is running.

        .. versionadded:: 2014.7.1

    template : None
        Can be set to 'jinja' or another supported template engine to render
        the command arguments before execution:

        .. code-block:: bash

            salt '*' archive.rar template=jinja /tmp/rarfile.rar '/tmp/sourcefile1,/tmp/{{grains.id}}.txt'

    CLI Example:

    .. code-block:: bash

        salt '*' archive.rar /tmp/rarfile.rar /tmp/sourcefile1,/tmp/sourcefile2
    '''
    if isinstance(sources, string_types):
        sources = [s.strip() for s in sources.split(',')]
    cmd = ['rar', 'a', '-idp', '{0}'.format(rarfile)]
    cmd.extend(sources)
    return __salt__['cmd.run'](cmd,
                               cwd=cwd,
                               template=template,
                               python_shell=False).splitlines()


@decorators.which_bin(('unrar', 'rar'))
def unrar(rarfile, dest, excludes=None, template=None):
    '''
    Uses `rar for Linux`_ to unpack rar files

    .. _`rar for Linux`: http://www.rarlab.com/

    rarfile
        Name of rar file to be unpacked

    dest
        The destination directory into which to **unpack** the rar file

    template : None
        Can be set to 'jinja' or another supported template engine to render
        the command arguments before execution:

        .. code-block:: bash

            salt '*' archive.unrar template=jinja /tmp/rarfile.rar /tmp/{{grains.id}}/ excludes=file_1,file_2

    CLI Example:

    .. code-block:: bash

        salt '*' archive.unrar /tmp/rarfile.rar /home/strongbad/ excludes=file_1,file_2

    '''
    if isinstance(excludes, string_types):
        excludes = [entry.strip() for entry in excludes.split(',')]

    cmd = [_which_bin(('unrar', 'rar')), 'x', '-idp', '{0}'.format(rarfile)]
    if excludes is not None:
        for exclude in excludes:
            cmd.extend(['-x', '{0}'.format(exclude)])
    cmd.append('{0}'.format(dest))
    return __salt__['cmd.run'](cmd,
                               template=template,
                               python_shell=False).splitlines()
