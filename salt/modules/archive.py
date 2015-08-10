# -*- coding: utf-8 -*-
'''
A module to wrap (non-Windows) archive calls

.. versionadded:: 2014.1.0
'''
from __future__ import absolute_import
import os
import contextlib  # For < 2.7 compat

# Import salt libs
from salt.exceptions import SaltInvocationError, CommandExecutionError
from salt.ext.six import string_types, integer_types
import salt.utils

# TODO: Check that the passed arguments are correct

# Don't shadow built-in's.
__func_alias__ = {
    'zip_': 'zip'
}


HAS_ZIPFILE = False
try:
    import zipfile
    HAS_ZIPFILE = True
except ImportError:
    pass


def __virtual__():
    if salt.utils.is_windows():
        return HAS_ZIPFILE
    commands = ('tar', 'gzip', 'gunzip', 'zip', 'unzip', 'rar', 'unrar')
    # If none of the above commands are in $PATH this module is a no-go
    if not any(salt.utils.which(cmd) for cmd in commands):
        return False
    return True


@salt.utils.decorators.which('tar')
def tar(options, tarfile, sources=None, dest=None,
        cwd=None, template=None, runas=None):
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
        passed as a Python list.

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

    if sources:
        cmd.extend(sources)

    return __salt__['cmd.run'](cmd,
                               cwd=cwd,
                               template=template,
                               runas=runas,
                               python_shell=False).splitlines()


@salt.utils.decorators.which('gzip')
def gzip(sourcefile, template=None, runas=None):
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
                               runas=runas,
                               python_shell=False).splitlines()


@salt.utils.decorators.which('gunzip')
def gunzip(gzipfile, template=None, runas=None):
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
                               runas=runas,
                               python_shell=False).splitlines()


@salt.utils.decorators.which('zip')
def cmd_zip(zip_file, sources, template=None, cwd=None, runas=None):
    '''
    .. versionadded:: 2015.5.0
        In versions 2014.7.x and earlier, this function was known as
        ``archive.zip``.

    Uses the ``zip`` command to create zip files. This command is part of the
    `Info-ZIP`_ suite of tools, and is typically packaged as simply ``zip``.

    .. _`Info-ZIP`: http://www.info-zip.org/

    zip_file
        Path of zip file to be created

    sources
        Comma-separated list of sources to include in the zip file. Sources can
        also be passed in a Python list.

    template : None
        Can be set to 'jinja' or another supported template engine to render
        the command arguments before execution:

        .. code-block:: bash

            salt '*' archive.cmd_zip template=jinja /tmp/zipfile.zip /tmp/sourcefile1,/tmp/{{grains.id}}.txt

    cwd : None
        Use this argument along with relative paths in ``sources`` to create
        zip files which do not contain the leading directories. If not
        specified, the zip file will be created as if the cwd was ``/``, and
        creating a zip file of ``/foo/bar/baz.txt`` will contain the parent
        directories ``foo`` and ``bar``. To create a zip file containing just
        ``baz.txt``, the following command would be used:

        .. code-block:: bash

            salt '*' archive.cmd_zip /tmp/baz.zip baz.txt cwd=/foo/bar

        .. versionadded:: 2014.7.1

    runas : None
        Create the zip file as the specified user. Defaults to the user under
        which the minion is running.

        .. versionadded:: 2015.5.0


    CLI Example:

    .. code-block:: bash

        salt '*' archive.cmd_zip /tmp/zipfile.zip /tmp/sourcefile1,/tmp/sourcefile2
    '''
    if isinstance(sources, string_types):
        sources = [s.strip() for s in sources.split(',')]
    cmd = ['zip', '-r']
    cmd.append('{0}'.format(zip_file))
    cmd.extend(sources)
    return __salt__['cmd.run'](cmd,
                               cwd=cwd,
                               template=template,
                               runas=runas,
                               python_shell=False).splitlines()


@salt.utils.decorators.depends('zipfile', fallback_function=cmd_zip)
def zip_(zip_file, sources, template=None, cwd=None, runas=None):
    '''
    Uses the ``zipfile`` Python module to create zip files

    .. versionchanged:: 2015.5.0
        This function was rewritten to use Python's native zip file support.
        The old functionality has been preserved in the new function
        :mod:`archive.cmd_zip <salt.modules.archive.cmd_zip>`. For versions
        2014.7.x and earlier, see the :mod:`archive.cmd_zip
        <salt.modules.archive.cmd_zip>` documentation.

    zip_file
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

    runas : None
        Create the zip file as the specified user. Defaults to the user under
        which the minion is running.


    CLI Example:

    .. code-block:: bash

        salt '*' archive.zip /tmp/zipfile.zip /tmp/sourcefile1,/tmp/sourcefile2
    '''
    if runas:
        euid = os.geteuid()
        egid = os.getegid()
        uinfo = __salt__['user.info'](runas)
        if not uinfo:
            raise SaltInvocationError(
                'User \'{0}\' does not exist'.format(runas)
            )

    zip_file, sources = _render_filenames(zip_file, sources, None, template)

    if isinstance(sources, string_types):
        sources = [x.strip() for x in sources.split(',')]
    elif isinstance(sources, (float, integer_types)):
        sources = [str(sources)]

    if not cwd:
        for src in sources:
            if not os.path.isabs(src):
                raise SaltInvocationError(
                    'Relative paths require the \'cwd\' parameter'
                )
    else:
        def _bad_cwd():
            raise SaltInvocationError('cwd must be absolute')
        try:
            if not os.path.isabs(cwd):
                _bad_cwd()
        except AttributeError:
            _bad_cwd()

    if runas and (euid != uinfo['uid'] or egid != uinfo['gid']):
        # Change the egid first, as changing it after the euid will fail
        # if the runas user is non-privileged.
        os.setegid(uinfo['gid'])
        os.seteuid(uinfo['uid'])

    try:
        exc = None
        archived_files = []
        with zipfile.ZipFile(zip_file, 'w', zipfile.ZIP_DEFLATED) as zfile:
            for src in sources:
                if cwd:
                    src = os.path.join(cwd, src)
                if os.path.exists(src):
                    if os.path.isabs(src):
                        rel_root = '/'
                    else:
                        rel_root = cwd if cwd is not None else '/'
                    if os.path.isdir(src):
                        for dir_name, sub_dirs, files in os.walk(src):
                            if cwd and dir_name.startswith(cwd):
                                arc_dir = salt.utils.relpath(dir_name, cwd)
                            else:
                                arc_dir = salt.utils.relpath(dir_name,
                                                             rel_root)
                            if arc_dir:
                                archived_files.append(arc_dir + '/')
                                zfile.write(dir_name, arc_dir)
                            for filename in files:
                                abs_name = os.path.join(dir_name, filename)
                                arc_name = os.path.join(arc_dir, filename)
                                archived_files.append(arc_name)
                                zfile.write(abs_name, arc_name)
                    else:
                        if cwd and src.startswith(cwd):
                            arc_name = salt.utils.relpath(src, cwd)
                        else:
                            arc_name = salt.utils.relpath(src, rel_root)
                        archived_files.append(arc_name)
                        zfile.write(src, arc_name)
    except Exception as exc:
        pass
    finally:
        # Restore the euid/egid
        if runas:
            os.seteuid(euid)
            os.setegid(egid)
        if exc is not None:
            # Wait to raise the exception until euid/egid are restored to avoid
            # permission errors in writing to minion log.
            raise CommandExecutionError(
                'Exception encountered creating zipfile: {0}'.format(exc)
            )

    return archived_files


@salt.utils.decorators.which('unzip')
def cmd_unzip(zip_file, dest, excludes=None,
              template=None, options=None, runas=None):
    '''
    .. versionadded:: 2015.5.0
        In versions 2014.7.x and earlier, this function was known as
        ``archive.unzip``.

    Uses the ``unzip`` command to unpack zip files. This command is part of the
    `Info-ZIP`_ suite of tools, and is typically packaged as simply ``unzip``.

    .. _`Info-ZIP`: http://www.info-zip.org/

    zip_file
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

            salt '*' archive.cmd_unzip template=jinja /tmp/zipfile.zip /tmp/{{grains.id}}/ excludes=file_1,file_2

    options : None
        Additional command-line options to pass to the ``unzip`` binary.

    runas : None
        Unpack the zip file as the specified user. Defaults to the user under
        which the minion is running.

        .. versionadded:: 2015.5.0

    options : None
        Additional command-line options to pass to the ``unzip`` binary.


    CLI Example:

    .. code-block:: bash

        salt '*' archive.cmd_unzip /tmp/zipfile.zip /home/strongbad/ excludes=file_1,file_2
    '''
    if isinstance(excludes, string_types):
        excludes = [x.strip() for x in excludes.split(',')]
    elif isinstance(excludes, (float, integer_types)):
        excludes = [str(excludes)]

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
    cmd.extend(['{0}'.format(zip_file), '-d', '{0}'.format(dest)])

    if excludes is not None:
        cmd.append('-x')
        cmd.extend(excludes)
    return __salt__['cmd.run'](cmd,
                               template=template,
                               runas=runas,
                               python_shell=False).splitlines()


@salt.utils.decorators.depends('zipfile', fallback_function=cmd_unzip)
def unzip(zip_file, dest, excludes=None, template=None, runas=None):
    '''
    Uses the ``zipfile`` Python module to unpack zip files

    .. versionchanged:: 2015.5.0
        This function was rewritten to use Python's native zip file support.
        The old functionality has been preserved in the new function
        :mod:`archive.cmd_unzip <salt.modules.archive.cmd_unzip>`. For versions
        2014.7.x and earlier, see the :mod:`archive.cmd_zip
        <salt.modules.archive.cmd_zip>` documentation.

    zip_file
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

    runas : None
        Unpack the zip file as the specified user. Defaults to the user under
        which the minion is running.

    CLI Example:

    .. code-block:: bash

        salt '*' archive.unzip /tmp/zipfile.zip /home/strongbad/ excludes=file_1,file_2
    '''
    if not excludes:
        excludes = []
    if runas:
        euid = os.geteuid()
        egid = os.getegid()
        uinfo = __salt__['user.info'](runas)
        if not uinfo:
            raise SaltInvocationError(
                'User \'{0}\' does not exist'.format(runas)
            )

    zip_file, dest = _render_filenames(zip_file, dest, None, template)

    if runas and (euid != uinfo['uid'] or egid != uinfo['gid']):
        # Change the egid first, as changing it after the euid will fail
        # if the runas user is non-privileged.
        os.setegid(uinfo['gid'])
        os.seteuid(uinfo['uid'])

    try:
        exc = None
        # Define cleaned_files here so that an exception will not prevent this
        # variable from being defined and cause a NameError in the return
        # statement at the end of the function.
        cleaned_files = []
        with contextlib.closing(zipfile.ZipFile(zip_file, "r")) as zfile:
            files = zfile.namelist()

            if isinstance(excludes, string_types):
                excludes = [x.strip() for x in excludes.split(',')]
            elif isinstance(excludes, (float, integer_types)):
                excludes = [str(excludes)]

            cleaned_files.extend([x for x in files if x not in excludes])
            for target in cleaned_files:
                if target not in excludes:
                    if salt.utils.is_windows() is False:
                        info = zfile.getinfo(target)
                        # Check if zipped file is a symbolic link
                        if info.external_attr == 2716663808L:
                            source = zfile.read(target)
                            os.symlink(source, os.path.join(dest, target))
                            continue
                    zfile.extract(target, dest)
    except Exception as exc:
        pass
    finally:
        # Restore the euid/egid
        if runas:
            os.seteuid(euid)
            os.setegid(egid)
        if exc is not None:
            # Wait to raise the exception until euid/egid are restored to avoid
            # permission errors in writing to minion log.
            raise CommandExecutionError(
                'Exception encountered unpacking zipfile: {0}'.format(exc)
            )

    return cleaned_files


@salt.utils.decorators.which('rar')
def rar(rarfile, sources, template=None, cwd=None, runas=None):
    '''
    Uses `rar for Linux`_ to create rar files

    .. _`rar for Linux`: http://www.rarlab.com/

    rarfile
        Path of rar file to be created

    sources
        Comma-separated list of sources to include in the rar file. Sources can
        also be passed in a Python list.

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
                               runas=runas,
                               python_shell=False).splitlines()


@salt.utils.decorators.which_bin(('unrar', 'rar'))
def unrar(rarfile, dest, excludes=None, template=None, runas=None):
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

    cmd = [salt.utils.which_bin(('unrar', 'rar')),
           'x', '-idp', '{0}'.format(rarfile)]
    if excludes is not None:
        for exclude in excludes:
            cmd.extend(['-x', '{0}'.format(exclude)])
    cmd.append('{0}'.format(dest))
    return __salt__['cmd.run'](cmd,
                               template=template,
                               runas=runas,
                               python_shell=False).splitlines()


def _render_filenames(filenames, zip_file, saltenv, template):
    '''
    Process markup in the :param:`filenames` and :param:`zipfile` variables (NOT the
    files under the paths they ultimately point to) according to the markup
    format provided by :param:`template`.
    '''
    if not template:
        return (filenames, zip_file)

    # render the path as a template using path_template_engine as the engine
    if template not in salt.utils.templates.TEMPLATE_REGISTRY:
        raise CommandExecutionError(
            'Attempted to render file paths with unavailable engine '
            '{0}'.format(template)
        )

    kwargs = {}
    kwargs['salt'] = __salt__
    kwargs['pillar'] = __pillar__
    kwargs['grains'] = __grains__
    kwargs['opts'] = __opts__
    kwargs['saltenv'] = saltenv

    def _render(contents):
        '''
        Render :param:`contents` into a literal pathname by writing it to a
        temp file, rendering that file, and returning the result.
        '''
        # write out path to temp file
        tmp_path_fn = salt.utils.mkstemp()
        with salt.utils.fopen(tmp_path_fn, 'w+') as fp_:
            fp_.write(contents)
        data = salt.utils.templates.TEMPLATE_REGISTRY[template](
            tmp_path_fn,
            to_str=True,
            **kwargs
        )
        salt.utils.safe_rm(tmp_path_fn)
        if not data['result']:
            # Failed to render the template
            raise CommandExecutionError(
                'Failed to render file path with error: {0}'.format(
                    data['data']
                )
            )
        else:
            return data['data']

    filenames = _render(filenames)
    zip_file = _render(zip_file)
    return (filenames, zip_file)
