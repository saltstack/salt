# -*- coding: utf-8 -*-
'''
A module to wrap (non-Windows) archive calls

.. versionadded:: 2014.1.0
'''
from __future__ import absolute_import
import os
from salt.exceptions import CommandExecutionError

from salt.ext.six import string_types

# Import salt libs
from salt.utils import \
    which as _which, which_bin as _which_bin, is_windows as _is_windows
import salt.utils.decorators as decorators
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
    if _is_windows():
        return HAS_ZIPFILE
    commands = ('tar', 'gzip', 'gunzip', 'zip', 'unzip', 'rar', 'unrar')
    # If none of the above commands are in $PATH this module is a no-go
    if not any(_which(cmd) for cmd in commands):
        return False
    return True


@decorators.which('tar')
def tar(options, tarfile, sources=None, dest=None, cwd=None, template=None, runas=None):
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
    if isinstance(sources, string_types):
        sources = [s.strip() for s in sources.split(',')]

    if dest:
        options = 'C {0} -{1}'.format(dest, options)

    cmd = 'tar -{0} {1}'.format(options, tarfile)
    if sources:
        cmd += ' {0}'.format(' '.join(sources))

    return __salt__['cmd.run'](cmd, cwd=cwd, template=template, runas=runas).splitlines()


@decorators.which('gzip')
def gzip(sourcefile, template=None, runas=None):
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
    return __salt__['cmd.run'](cmd, template=template, runas=runas).splitlines()


@decorators.which('gunzip')
def gunzip(gzipfile, template=None, runas=None):
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
    return __salt__['cmd.run'](cmd, template=template, runas=runas).splitlines()


@decorators.which('zip')
def cmd_zip_(zipfile, sources, template=None, runas=None):
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
    if isinstance(sources, string_types):
        sources = [s.strip() for s in sources.split(',')]
    cmd = 'zip {0} {1}'.format(zipfile, ' '.join(sources))
    return __salt__['cmd.run'](cmd, template=template, runas=runas).splitlines()


@decorators.depends('zipfile', fallback_function=cmd_zip_)
def zip_(archive, sources, template=None, runas=None):
    '''
    Uses the zipfile module to create zip files

    CLI Example:

    .. code-block:: bash

        salt '*' archive.zip /tmp/zipfile.zip /tmp/sourcefile1,/tmp/sourcefile2

    The template arg can be set to 'jinja' or another supported template
    engine to render the command arguments before execution.

    For example:

    .. code-block:: bash

        salt '*' archive.zip template=jinja /tmp/zipfile.zip /tmp/sourcefile1,/tmp/{{grains.id}}.txt

    '''
    (archive, sources) = _render_filenames(archive, sources, None, template)

    if isinstance(sources, string_types):
        sources = [s.strip() for s in sources.split(',')]

    archived_files = []
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for src in sources:
            if os.path.exists(src):
                if os.path.isdir(src):
                    rel_root = os.path.abspath(os.path.join(src, os.pardir))
                    for dir_name, sub_dirs, files in os.walk(src):
                        for filename in files:
                            abs_name = os.path.abspath(os.path.join(dir_name, filename))
                            arc_name = os.path.join(os.path.relpath(dir_name, rel_root), filename)
                            archived_files.append(arc_name)
                            zf.write(abs_name, arc_name)
                else:
                    archived_files.append(src)
                    zf.write(src)

    return archived_files


@decorators.which('unzip')
def unzip_cmd(zipfile, dest, excludes=None, template=None, options=None, runas=None):
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
    if isinstance(excludes, string_types):
        excludes = [entry.strip() for entry in excludes.split(',')]

    if options:
        cmd = 'unzip -{0} {1} -d {2}'.format(options, zipfile, dest)
    else:
        cmd = 'unzip {0} -d {1}'.format(zipfile, dest)

    if excludes is not None:
        cmd += ' -x {0}'.format(' '.join(excludes))
    return __salt__['cmd.run'](cmd, template=template, runas=runas).splitlines()


@decorators.depends('zipfile', fallback_function=unzip_cmd)
def unzip(archive, dest, excludes=None, template=None, options=None, runas=None):
    '''
    Uses the zipfile module to unpack zip files

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
    (archive, dest) = _render_filenames(archive, dest, None, template)
    with zipfile.ZipFile(archive) as zf:
        files = zf.namelist()
        if excludes is None:
            zf.extractall(dest)
            return files

        excludes = excludes.split(",")
        cleaned_files = [x for x in files if x not in excludes]
        for f in cleaned_files:
            if f not in excludes:
                zf.extract(f, dest)
        return cleaned_files


@decorators.which('rar')
def rar(rarfile, sources, template=None, runas=None):
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
    if isinstance(sources, string_types):
        sources = [s.strip() for s in sources.split(',')]
    cmd = 'rar a -idp {0} {1}'.format(rarfile, ' '.join(sources))
    return __salt__['cmd.run'](cmd, template=template, runas=runas).splitlines()


@decorators.which_bin(('unrar', 'rar'))
def unrar(rarfile, dest, excludes=None, template=None, runas=None):
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
    if isinstance(excludes, string_types):
        excludes = [entry.strip() for entry in excludes.split(',')]

    cmd = [_which_bin(('unrar', 'rar')), 'x', '-idp', rarfile]
    if excludes is not None:
        for exclude in excludes:
            cmd.extend(['-x', exclude])
    cmd.append(dest)
    return __salt__['cmd.run'](' '.join(cmd), template=template, runas=runas).splitlines()


def _render_filenames(filenames, zipfile, saltenv, template):
    '''
    Process markup in the :param:`filenames` and :param:`zipfile` variables (NOT the
    files under the paths they ultimately point to) according to the markup
    format provided by :param:`template`.
    '''
    if not template:
        return (filenames, zipfile)

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
    zipfile = _render(zipfile)
    return (filenames, zipfile)
