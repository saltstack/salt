# -*- coding: utf-8 -*-
'''
Extract an archive

.. versionadded:: 2014.1.0
'''

# Import Python libs
from __future__ import absolute_import
import errno
import logging
import os
import re
import shlex
import stat
import tarfile
from contextlib import closing

# Import 3rd-party libs
import salt.ext.six as six
from salt.ext.six.moves import shlex_quote as _cmd_quote
from salt.ext.six.moves.urllib.parse import urlparse as _urlparse  # pylint: disable=no-name-in-module

# Import salt libs
import salt.utils
import salt.utils.files
from salt.exceptions import CommandExecutionError, CommandNotFoundError

log = logging.getLogger(__name__)


def _path_is_abs(path):
    '''
    Return a bool telling whether or ``path`` is absolute. If ``path`` is None,
    return ``True``. This function is designed to validate variables which
    optionally contain a file path.
    '''
    if path is None:
        return True
    try:
        return os.path.isabs(path)
    except AttributeError:
        # Non-string data passed
        return False


def _add_explanation(ret, source_hash_trigger, contents_missing):
    '''
    Common code to add additional explanation to the state's comment field,
    both when test=True and not
    '''
    if source_hash_trigger:
        ret['comment'] += ', due to source_hash update'
    elif contents_missing:
        ret['comment'] += ', due to absence of one or more files/dirs'


def _gen_checksum(path):
    return {'hsum': salt.utils.get_hash(path, form=__opts__['hash_type']),
            'hash_type': __opts__['hash_type']}


def _update_checksum(cached_source):
    cached_source_sum = '.'.join((cached_source, 'hash'))
    source_sum = _gen_checksum(cached_source)
    hash_type = source_sum.get('hash_type')
    hsum = source_sum.get('hsum')
    if hash_type and hsum:
        lines = []
        try:
            try:
                with salt.utils.fopen(cached_source_sum, 'r') as fp_:
                    for line in fp_:
                        try:
                            lines.append(line.rstrip('\n').split(':', 1))
                        except ValueError:
                            continue
            except (IOError, OSError) as exc:
                if exc.errno != errno.ENOENT:
                    raise

            with salt.utils.fopen(cached_source_sum, 'w') as fp_:
                for line in lines:
                    if line[0] == hash_type:
                        line[1] = hsum
                    fp_.write('{0}:{1}\n'.format(*line))
                if hash_type not in [x[0] for x in lines]:
                    fp_.write('{0}:{1}\n'.format(hash_type, hsum))
        except (IOError, OSError) as exc:
            log.warning(
                'Failed to update checksum for %s: %s',
                cached_source, exc.__str__()
            )


def _read_cached_checksum(cached_source, form=None):
    if form is None:
        form = __opts__['hash_type']
    path = '.'.join((cached_source, 'hash'))
    try:
        with salt.utils.fopen(path, 'r') as fp_:
            for line in fp_:
                # Should only be one line in this file but just in case it
                # isn't, read only a single line to avoid overuse of memory.
                hash_type, hsum = line.rstrip('\n').split(':', 1)
                if hash_type == form:
                    break
            else:
                return None
    except (IOError, OSError, ValueError):
        return None
    else:
        return {'hash_type': hash_type, 'hsum': hsum}


def _compare_checksum(cached_source, source_sum):
    cached_sum = _read_cached_checksum(
        cached_source,
        form=source_sum.get('hash_type', __opts__['hash_type'])
    )
    return source_sum == cached_sum


def _is_bsdtar():
    return 'bsdtar' in __salt__['cmd.run'](['tar', '--version'],
                                           python_shell=False)


def _cleanup_destdir(name):
    '''
    Attempt to remove the specified directory
    '''
    try:
        os.rmdir(name)
    except OSError:
        pass


def extracted(name,
              source,
              source_hash=None,
              source_hash_name=None,
              source_hash_update=False,
              skip_verify=False,
              password=None,
              options=None,
              list_options=None,
              force=False,
              overwrite=False,
              clean=False,
              user=None,
              group=None,
              if_missing=None,
              keep=False,
              trim_output=False,
              use_cmd_unzip=None,
              extract_perms=True,
              enforce_toplevel=True,
              enforce_ownership_on=None,
              archive_format=None,
              **kwargs):
    '''
    .. versionadded:: 2014.1.0
    .. versionchanged:: 2016.11.0
        This state has been rewritten. Some arguments are new to this release
        and will not be available in the 2016.3 release cycle (and earlier).
        Additionally, the **ZIP Archive Handling** section below applies
        specifically to the 2016.11.0 release (and newer).

    Ensure that an archive is extracted to a specific directory.

    .. important::
        **Changes for 2016.11.0**

        In earlier releases, this state would rely on the ``if_missing``
        argument to determine whether or not the archive needed to be
        extracted. When this argument was not passed, then the state would just
        assume ``if_missing`` is the same as the ``name`` argument (i.e. the
        parent directory into which the archive would be extracted).

        This caused a number of annoyances. One such annoyance was the need to
        know beforehand a path that would result from the extraction of the
        archive, and setting ``if_missing`` to that directory, like so:

        .. code-block:: yaml

            extract_myapp:
              archive.extracted:
                - name: /var/www
                - source: salt://apps/src/myapp-16.2.4.tar.gz
                - user: www
                - group: www
                - if_missing: /var/www/myapp-16.2.4

        If ``/var/www`` already existed, this would effectively make
        ``if_missing`` a required argument, just to get Salt to extract the
        archive.

        Some users worked around this by adding the top-level directory of the
        archive to the end of the ``name`` argument, and then used ``--strip``
        or ``--strip-components`` to remove that top-level dir when extracting:

        .. code-block:: yaml

            extract_myapp:
              archive.extracted:
                - name: /var/www/myapp-16.2.4
                - source: salt://apps/src/myapp-16.2.4.tar.gz
                - user: www
                - group: www

        With the rewrite for 2016.11.0, these workarounds are no longer
        necessary. ``if_missing`` is still a supported argument, but it is no
        longer required. The equivalent SLS in 2016.11.0 would be:

        .. code-block:: yaml

            extract_myapp:
              archive.extracted:
                - name: /var/www
                - source: salt://apps/src/myapp-16.2.4.tar.gz
                - user: www
                - group: www

        Salt now uses a function called :py:func:`archive.list
        <salt.modules.archive.list>` to get a list of files/directories in the
        archive. Using this information, the state can now check the minion to
        see if any paths are missing, and know whether or not the archive needs
        to be extracted. This makes the ``if_missing`` argument unnecessary in
        most use cases.

    .. important::
        **ZIP Archive Handling**

        *Note: this information applies to 2016.11.0 and later.*

        Salt has two different functions for extracting ZIP archives:

        1. :py:func:`archive.unzip <salt.modules.archive.unzip>`, which uses
           Python's zipfile_ module to extract ZIP files.
        2. :py:func:`archive.cmd_unzip <salt.modules.archive.cmd_unzip>`, which
           uses the ``unzip`` CLI command to extract ZIP files.

        Salt will prefer the use of :py:func:`archive.cmd_unzip
        <salt.modules.archive.cmd_unzip>` when CLI options are specified (via
        the ``options`` argument), and will otherwise prefer the
        :py:func:`archive.unzip <salt.modules.archive.unzip>` function. Use
        of :py:func:`archive.cmd_unzip <salt.modules.archive.cmd_unzip>` can be
        forced however by setting the ``use_cmd_unzip`` argument to ``True``.
        By contrast, setting this argument to ``False`` will force usage of
        :py:func:`archive.unzip <salt.modules.archive.unzip>`. For example:

        .. code-block:: yaml

            /var/www:
              archive.extracted:
                - source: salt://foo/bar/myapp.zip
                - use_cmd_unzip: True

        When ``use_cmd_unzip`` is omitted, Salt will choose which extraction
        function to use based on the source archive and the arguments passed to
        the state. When in doubt, simply do not set this argument; it is
        provided as a means of overriding the logic Salt uses to decide which
        function to use.

        There are differences in the features available in both extraction
        functions. These are detailed below.

        - *Command-line options* (only supported by :py:func:`archive.cmd_unzip
          <salt.modules.archive.cmd_unzip>`) - When the ``options`` argument is
          used, :py:func:`archive.cmd_unzip <salt.modules.archive.cmd_unzip>`
          is the only function that can be used to extract the archive.
          Therefore, if ``use_cmd_unzip`` is specified and set to ``False``,
          and ``options`` is also set, the state will not proceed.

        - *Permissions* - Due to an `upstream bug in Python`_, permissions are
          not preserved when the zipfile_ module is used to extract an archive.
          As of the 2016.11.0 release, :py:func:`archive.unzip
          <salt.modules.archive.unzip>` (as well as this state) has an
          ``extract_perms`` argument which, when set to ``True`` (the default),
          will attempt to match the permissions of the extracted
          files/directories to those defined within the archive. To disable
          this functionality and have the state not attempt to preserve the
          permissions from the ZIP archive, set ``extract_perms`` to ``False``:

          .. code-block:: yaml

              /var/www:
                archive.extracted:
                  - source: salt://foo/bar/myapp.zip
                  - extract_perms: False

    .. _`upstream bug in Python`: https://bugs.python.org/issue15795

    name
        Directory into which the archive should be extracted

    source
        Archive to be extracted

        .. note::
            This argument uses the same syntax as its counterpart in the
            :py:func:`file.managed <salt.states.file.managed>` state.

    source_hash
        Hash of source file, or file with list of hash-to-file mappings

        .. note::
            This argument uses the same syntax as its counterpart in the
            :py:func:`file.managed <salt.states.file.managed>` state.

        .. versionchanged:: 2016.11.0
            If this argument specifies the hash itself, instead of a URI to a
            file containing hashes, the hash type can now be omitted and Salt
            will determine the hash type based on the length of the hash. For
            example, both of the below states are now valid, while before only
            the second one would be:

        .. code-block:: yaml

            foo_app:
              archive.extracted:
                - name: /var/www
                - source: https://mydomain.tld/foo.tar.gz
                - source_hash: 3360db35e682f1c5f9c58aa307de16d41361618c

            bar_app:
              archive.extracted:
                - name: /var/www
                - source: https://mydomain.tld/bar.tar.gz
                - source_hash: sha1=5edb7d584b82ddcbf76e311601f5d4442974aaa5

    source_hash_name
        When ``source_hash`` refers to a hash file, Salt will try to find the
        correct hash by matching the filename part of the ``source`` URI. When
        managing a file with a ``source`` of ``salt://files/foo.tar.gz``, then
        the following line in a hash file would match:

        .. code-block:: text

            acbd18db4cc2f85cedef654fccc4a4d8    foo.tar.gz

        This line would also match:

        .. code-block:: text

            acbd18db4cc2f85cedef654fccc4a4d8    ./dir1/foo.tar.gz

        However, sometimes a hash file will include multiple similar paths:

        .. code-block:: text

            37b51d194a7513e45b56f6524f2d51f2    ./dir1/foo.txt
            acbd18db4cc2f85cedef654fccc4a4d8    ./dir2/foo.txt
            73feffa4b7f6bb68e44cf984c85f6e88    ./dir3/foo.txt

        In cases like this, Salt may match the incorrect hash. This argument
        can be used to tell Salt which filename to match, to ensure that the
        correct hash is identified. For example:

        .. code-block:: yaml

            /var/www:
              archive.extracted:
                - source: https://mydomain.tld/dir2/foo.tar.gz
                - source_hash: https://mydomain.tld/hashes
                - source_hash_name: ./dir2/foo.tar.gz

        .. note::
            This argument must contain the full filename entry from the
            checksum file, as this argument is meant to disambiguate matches
            for multiple files that have the same basename. So, in the
            example above, simply using ``foo.txt`` would not match.

        .. versionadded:: 2016.11.0

    source_hash_update
        Set this to ``True`` if archive should be extracted if source_hash has
        changed. This would extract regardless of the ``if_missing`` parameter.

        .. versionadded:: 2016.3.0

    skip_verify : False
        If ``True``, hash verification of remote file sources (``http://``,
        ``https://``, ``ftp://``) will be skipped, and the ``source_hash``
        argument will be ignored.

        .. versionadded:: 2016.3.4

    password
        **For ZIP archives only.** Password used for extraction.

        .. versionadded:: 2016.3.0
        .. versionchanged:: 2016.11.0
          The newly-added :py:func:`archive.is_encrypted
          <salt.modules.archive.is_encrypted>` function will be used to
          determine if the archive is password-protected. If it is, then the
          ``password`` argument will be required for the state to proceed.

    options
        **For tar and zip archives only.**  This option can be used to specify
        a string of additional arguments to pass to the tar/zip command.

        If this argument is not used, then the minion will attempt to use
        Python's native tarfile_/zipfile_ support to extract it. For zip
        archives, this argument is mostly used to overwrite exsiting files with
        ``o``.

        Using this argument means that the ``tar`` or ``unzip`` command will be
        used, which is less platform-independent, so keep this in mind when
        using this option; the CLI options must be valid options for the
        ``tar``/``unzip`` implementation on the minion's OS.

        .. versionadded:: 2016.11.0
        .. versionchanged:: 2015.8.11,2016.3.2
            XZ-compressed tar archives no longer require ``J`` to manually be
            set in the ``options``, they are now detected automatically and
            decompressed using the xz_ CLI command and extracted using ``tar
            xvf``. This is a more platform-independent solution, as not all tar
            implementations support the ``J`` argument for extracting archives.

        .. note::
            For tar archives, main operators like ``-x``, ``--extract``,
            ``--get``, ``-c`` and ``-f``/``--file`` should *not* be used here.

    list_options
        **For tar archives only.** This state uses :py:func:`archive.list
        <salt.modules.archive.list_>` to discover the contents of the source
        archive so that it knows which file paths should exist on the minion if
        the archive has already been extracted. For the vast majority of tar
        archives, :py:func:`archive.list <salt.modules.archive.list_>` "just
        works". Archives compressed using gzip, bzip2, and xz/lzma (with the
        help of the xz_ CLI command) are supported automatically. However, for
        archives compressed using other compression types, CLI options must be
        passed to :py:func:`archive.list <salt.modules.archive.list_>`.

        This argument will be passed through to :py:func:`archive.list
        <salt.modules.archive.list_>` as its ``options`` argument, to allow it
        to successfully list the archive's contents. For the vast majority of
        archives, this argument should not need to be used, it should only be
        needed in cases where the state fails with an error stating that the
        archive's contents could not be listed.

        .. versionadded:: 2016.11.0

    force : False
        If a path that should be occupied by a file in the extracted result is
        instead a directory (or vice-versa), the state will fail. Set this
        argument to ``True`` to force these paths to be removed in order to
        allow the archive to be extracted.

        .. warning::
            Use this option *very* carefully.

        .. versionadded:: 2016.11.0

    overwrite : False
        Set this to ``True`` to force the archive to be extracted. This is
        useful for cases where the filenames/directories have not changed, but
        the content of the files have.

        .. versionadded:: 2016.11.1

    clean : False
        Set this to ``True`` to remove any top-level files and recursively
        remove any top-level directory paths before extracting.

        .. note::
            Files will only be cleaned first if extracting the archive is
            deemed necessary, either by paths missing on the minion, or if
            ``overwrite`` is set to ``True``.

        .. versionadded:: 2016.11.1

    user
        The user to own each extracted file. Not available on Windows.

        .. versionadded:: 2015.8.0
        .. versionchanged:: 2016.3.0
            When used in combination with ``if_missing``, ownership will only
            be enforced if ``if_missing`` is a directory.
        .. versionchanged:: 2016.11.0
            Ownership will be enforced only on the file/directory paths found
            by running :py:func:`archive.list <salt.modules.archive.list_>` on
            the source archive. An alternative root directory on which to
            enforce ownership can be specified using the
            ``enforce_ownership_on`` argument.

    group
        The group to own each extracted file. Not available on Windows.

        .. versionadded:: 2015.8.0
        .. versionchanged:: 2016.3.0
            When used in combination with ``if_missing``, ownership will only
            be enforced if ``if_missing`` is a directory.
        .. versionchanged:: 2016.11.0
            Ownership will be enforced only on the file/directory paths found
            by running :py:func:`archive.list <salt.modules.archive.list_>` on
            the source archive. An alternative root directory on which to
            enforce ownership can be specified using the
            ``enforce_ownership_on`` argument.

    if_missing
        If specified, this path will be checked, and if it exists then the
        archive will not be extracted. This path can be either a directory or a
        file, so this option can also be used to check for a semaphore file and
        conditionally skip extraction.

        .. versionchanged:: 2016.3.0
            When used in combination with either ``user`` or ``group``,
            ownership will only be enforced when ``if_missing`` is a directory.
        .. versionchanged:: 2016.11.0
            Ownership enforcement is no longer tied to this argument, it is
            simply checked for existence and extraction will be skipped if
            if is present.

    keep : False
        For ``source`` archives not local to the minion (i.e. from the Salt
        fileserver or a remote source such as ``http(s)`` or ``ftp``), Salt
        will need to download the archive to the minion cache before they can
        be extracted. After extraction, these source archives will be removed
        unless this argument is set to ``True``.

    trim_output : False
        Useful for archives with many files in them. This can either be set to
        ``True`` (in which case only the first 100 files extracted will be
        in the state results), or it can be set to an integer for more exact
        control over the max number of files to include in the state results.

        .. versionadded:: 2016.3.0

    use_cmd_unzip : False
        Set to ``True`` for zip files to force usage of the
        :py:func:`archive.cmd_unzip <salt.modules.archive.cmd_unzip>` function
        to extract.

        .. versionadded:: 2016.11.0

    extract_perms : True
        **For ZIP archives only.** When using :py:func:`archive.unzip
        <salt.modules.archive.unzip>` to extract ZIP archives, Salt works
        around an `upstream bug in Python`_ to set the permissions on extracted
        files/directories to match those encoded into the ZIP archive. Set this
        argument to ``False`` to skip this workaround.

        .. versionadded:: 2016.11.0

    enforce_toplevel : True
        This option will enforce a single directory at the top level of the
        source archive, to prevent extracting a 'tar-bomb'. Set this argument
        to ``False`` to allow archives with files (or multiple directories) at
        the top level to be extracted.

        .. versionadded:: 2016.11.0

    enforce_ownership_on
        When ``user`` or ``group`` is specified, Salt will default to enforcing
        permissions on the file/directory paths detected by running
        :py:func:`archive.list <salt.modules.archive.list_>` on the source
        archive. Use this argument to specify an alternate directory on which
        ownership should be enforced.

        .. note::
            This path must be within the path specified by the ``name``
            argument.

        .. versionadded:: 2016.11.0

    archive_format
        One of ``tar``, ``zip``, or ``rar``.

        .. versionchanged:: 2016.11.0
            If omitted, the archive format will be guessed based on the value
            of the ``source`` argument.

    .. _tarfile: https://docs.python.org/2/library/tarfile.html
    .. _zipfile: https://docs.python.org/2/library/zipfile.html
    .. _xz: http://tukaani.org/xz/

    **Examples**

    1. tar with lmza (i.e. xz) compression:

       .. code-block:: yaml

           graylog2-server:
             archive.extracted:
               - name: /opt/
               - source: https://github.com/downloads/Graylog2/graylog2-server/graylog2-server-0.9.6p1.tar.lzma
               - source_hash: md5=499ae16dcae71eeb7c3a30c75ea7a1a6

    2. tar archive with flag for verbose output, and enforcement of user/group
       ownership:

       .. code-block:: yaml

           graylog2-server:
             archive.extracted:
               - name: /opt/
               - source: https://github.com/downloads/Graylog2/graylog2-server/graylog2-server-0.9.6p1.tar.gz
               - source_hash: md5=499ae16dcae71eeb7c3a30c75ea7a1a6
               - options: v
               - user: foo
               - group: foo

    3. tar archive, with ``source_hash_update`` set to ``True`` to prevent
       state from attempting extraction unless the ``source_hash`` differs
       from the previous time the archive was extracted:

       .. code-block:: yaml

           graylog2-server:
             archive.extracted:
               - name: /opt/
               - source: https://github.com/downloads/Graylog2/graylog2-server/graylog2-server-0.9.6p1.tar.lzma
               - source_hash: md5=499ae16dcae71eeb7c3a30c75ea7a1a6
               - source_hash_update: True
    '''
    ret = {'name': name, 'result': False, 'changes': {}, 'comment': ''}

    # Remove pub kwargs as they're irrelevant here.
    kwargs = salt.utils.clean_kwargs(**kwargs)

    if not _path_is_abs(name):
        ret['comment'] = '{0} is not an absolute path'.format(name)
        return ret
    else:
        if not name:
            # Empty name, like None, '' etc.
            ret['comment'] = 'Name of the directory path needs to be specified'
            return ret
        # os.path.isfile() returns False when there is a trailing slash, hence
        # our need for first stripping the slash and then adding it back later.
        # Otherwise, we can't properly check if the extraction location both a)
        # exists and b) is a file.
        #
        # >>> os.path.isfile('/tmp/foo.txt')
        # True
        # >>> os.path.isfile('/tmp/foo.txt/')
        # False
        name = name.rstrip('/')
        if os.path.isfile(name):
            ret['comment'] = '{0} exists and is not a directory'.format(name)
            return ret
        # Add back the slash so that file.makedirs properly creates the
        # destdir if it needs to be created. file.makedirs expects a trailing
        # slash in the directory path.
        name += os.sep
    if not _path_is_abs(if_missing):
        ret['comment'] = 'Value for \'if_missing\' is not an absolute path'
        return ret
    if not _path_is_abs(enforce_ownership_on):
        ret['comment'] = ('Value for \'enforce_ownership_on\' is not an '
                          'absolute path')
        return ret
    else:
        if enforce_ownership_on is not None:
            try:
                not_rel = os.path.relpath(enforce_ownership_on,
                                          name).startswith('..' + os.sep)
            except Exception:
                # A ValueError is raised on Windows when the paths passed to
                # os.path.relpath are not on the same drive letter. Using a
                # generic Exception here to keep other possible exception types
                # from making this state blow up with a traceback.
                not_rel = True
            if not_rel:
                ret['comment'] = (
                    'Value for \'enforce_ownership_on\' must be within {0}'
                    .format(name)
                )
                return ret

    if user or group:
        if salt.utils.is_windows():
            ret['comment'] = \
                'User/group ownership cannot be enforced on Windows minions'
            return ret

        if user:
            uid = __salt__['file.user_to_uid'](user)
            if uid == '':
                ret['comment'] = 'User {0} does not exist'.format(user)
                return ret
        else:
            uid = -1

        if group:
            gid = __salt__['file.group_to_gid'](group)
            if gid == '':
                ret['comment'] = 'Group {0} does not exist'.format(group)
                return ret
        else:
            gid = -1
    else:
        # We should never hit the ownership enforcement code unless user or
        # group was specified, but just in case, set uid/gid to -1 to make the
        # os.chown() a no-op and avoid a NameError.
        uid = gid = -1

    if source_hash_update and not source_hash:
        ret.setdefault('warnings', []).append(
            'The \'source_hash_update\' argument is ignored when '
            '\'source_hash\' is not also specified.'
        )

    try:
        source_match = __salt__['file.source_list'](source,
                                                    source_hash,
                                                    __env__)[0]
    except CommandExecutionError as exc:
        ret['result'] = False
        ret['comment'] = exc.strerror
        return ret

    urlparsed_source = _urlparse(source_match)
    source_hash_basename = urlparsed_source.path or urlparsed_source.netloc

    source_is_local = urlparsed_source.scheme in ('', 'file')
    if source_is_local:
        # Get rid of "file://" from start of source_match
        source_match = urlparsed_source.path
        if not os.path.isfile(source_match):
            ret['comment'] = 'Source file \'{0}\' does not exist'.format(source_match)
            return ret

    valid_archive_formats = ('tar', 'rar', 'zip')
    if not archive_format:
        archive_format = salt.utils.files.guess_archive_type(source_hash_basename)
        if archive_format is None:
            ret['comment'] = (
                'Could not guess archive_format from the value of the '
                '\'source\' argument. Please set this archive_format to one '
                'of the following: {0}'.format(', '.join(valid_archive_formats))
            )
            return ret
    try:
        archive_format = archive_format.lower()
    except AttributeError:
        pass
    if archive_format not in valid_archive_formats:
        ret['comment'] = (
            'Invalid archive_format \'{0}\'. Either set it to a supported '
            'value ({1}) or remove this argument and the archive format will '
            'be guesseed based on file extension.'.format(
                archive_format,
                ', '.join(valid_archive_formats),
            )
        )
        return ret

    if options is not None and not isinstance(options, six.string_types):
        options = str(options)

    strip_components = None
    if options and archive_format == 'tar':
        try:
            strip_components = int(
                re.search(
                    r'''--strip(?:-components)?(?:\s+|=)["']?(\d+)["']?''',
                    options
                ).group(1)
            )
        except (AttributeError, ValueError):
            pass

    if archive_format == 'zip':
        if options:
            if use_cmd_unzip is None:
                log.info(
                    'Presence of CLI options in archive.extracted state for '
                    '\'%s\' implies that use_cmd_unzip is set to True.', name
                )
                use_cmd_unzip = True
            elif not use_cmd_unzip:
                # use_cmd_unzip explicitly disabled
                ret['comment'] = (
                    '\'use_cmd_unzip\' cannot be set to False if CLI options '
                    'are being specified (via the \'options\' argument). '
                    'Either remove \'use_cmd_unzip\', or set it to True.'
                )
                return ret
            if use_cmd_unzip:
                if 'archive.cmd_unzip' not in __salt__:
                    ret['comment'] = (
                        'archive.cmd_unzip function not available, unzip might '
                        'not be installed on minion'
                    )
                    return ret
        if password:
            if use_cmd_unzip is None:
                log.info(
                    'Presence of a password in archive.extracted state for '
                    '\'%s\' implies that use_cmd_unzip is set to False.', name
                )
                use_cmd_unzip = False
            elif use_cmd_unzip:
                ret.setdefault('warnings', []).append(
                    'Using a password in combination with setting '
                    '\'use_cmd_unzip\' to True is considered insecure. It is '
                    'recommended to remove the \'use_cmd_unzip\' argument (or '
                    'set it to False) and allow Salt to extract the archive '
                    'using Python\'s built-in ZIP file support.'
                )
    else:
        if password:
            ret['comment'] = \
                'The \'password\' argument is only supported for zip archives'
            return ret

    if archive_format == 'rar':
        if 'archive.unrar' not in __salt__:
            ret['comment'] = (
                'archive.unrar function not available, rar/unrar might '
                'not be installed on minion'
            )
            return ret

    supports_options = ('tar', 'zip')
    if options and archive_format not in supports_options:
        ret['comment'] = (
            'The \'options\' argument is only compatible with the following '
            'archive formats: {0}'.format(', '.join(supports_options))
        )
        return ret

    if trim_output:
        if trim_output is True:
            trim_output = 100
        elif not isinstance(trim_output, (bool, six.integer_types)):
            try:
                # Try to handle cases where trim_output was passed as a
                # string-ified integer.
                trim_output = int(trim_output)
            except TypeError:
                ret['comment'] = (
                    'Invalid value for trim_output, must be True/False or an '
                    'integer'
                )
                return ret

    if source_hash:
        try:
            source_sum = __salt__['file.get_source_sum'](
                 source=source_match,
                 source_hash=source_hash,
                 source_hash_name=source_hash_name,
                 saltenv=__env__)
        except CommandExecutionError as exc:
            ret['comment'] = exc.strerror
            return ret
    else:
        source_sum = {}

    if source_is_local:
        cached_source = source_match
    else:
        cached_source = os.path.join(
            __opts__['cachedir'],
            'files',
            __env__,
            re.sub(r'[:/\\]', '_', source_hash_basename),
        )

        if os.path.isdir(cached_source):
            # Prevent a traceback from attempting to read from a directory path
            salt.utils.rm_rf(cached_source)

    existing_cached_source_sum = _read_cached_checksum(cached_source) \

    if source_is_local:
        # No need to download archive, it's local to the minion
        update_source = False
    else:
        if not os.path.isfile(cached_source):
            # Archive not cached, we need to download it
            update_source = True
        else:
            # Archive is cached, keep=True likely used in prior run. If we need
            # to verify the hash, then we *have* to update the source archive
            # to know whether or not the hash changed. Hence the below
            # statement. bool(source_hash) will be True if source_hash was
            # passed, and otherwise False.
            update_source = bool(source_hash)

    if update_source:
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = (
                'Archive {0} would be downloaded to cache and checked to '
                'discover if extraction is necessary'.format(source_match)
            )
            return ret

        # NOTE: This will result in more than one copy of the source archive on
        # the minion. The reason this is necessary is because if we are
        # tracking the checksum using source_hash_update, we need a location
        # where we can place the checksum file alongside the cached source
        # file, where it won't be overwritten by caching a file with the same
        # name in the same parent dir as the source file. Long term, we should
        # come up with a better solution for this.
        file_result = __states__['file.managed'](cached_source,
                                                 source=source_match,
                                                 source_hash=source_hash,
                                                 source_hash_name=source_hash_name,
                                                 makedirs=True,
                                                 skip_verify=skip_verify)
        log.debug('file.managed: {0}'.format(file_result))

        # Prevent a traceback if errors prevented the above state from getting
        # off the ground.
        if isinstance(file_result, list):
            try:
                ret['comment'] = '\n'.join(file_result)
            except TypeError:
                ret['comment'] = '\n'.join([str(x) for x in file_result])
            return ret

        try:
            if not file_result['result']:
                log.debug('failed to download {0}'.format(source_match))
                return file_result
        except TypeError:
            if not file_result:
                log.debug('failed to download {0}'.format(source_match))
                return file_result

        if source_hash:
            _update_checksum(cached_source)

    else:
        log.debug('Archive %s is already in cache', source_match)

    if archive_format == 'zip' and not password:
        log.debug('Checking %s to see if it is password-protected',
                  source_match)
        # Either use_cmd_unzip was explicitly set to True, or was
        # implicitly enabled by setting the "options" argument.
        try:
            encrypted_zip = __salt__['archive.is_encrypted'](
                cached_source,
                clean=False,
                saltenv=__env__)
        except CommandExecutionError:
            # This would happen if archive_format=zip and the source archive is
            # not actually a zip file.
            pass
        else:
            if encrypted_zip:
                ret['comment'] = (
                    'Archive {0} is password-protected, but no password was '
                    'specified. Please set the \'password\' argument.'.format(
                        source_match
                    )
                )
                return ret

    try:
        contents = __salt__['archive.list'](cached_source,
                                            archive_format=archive_format,
                                            options=list_options,
                                            strip_components=strip_components,
                                            clean=False,
                                            verbose=True)
    except CommandExecutionError as exc:
        contents = None
        errors = []
        if not if_missing:
            errors.append('\'if_missing\' must be set')
        if not enforce_ownership_on and (user or group):
            errors.append(
                'Ownership cannot be managed without setting '
                '\'enforce_ownership_on\'.'
            )
        msg = exc.strerror
        if errors:
            msg += '\n\n'
            if archive_format == 'tar':
                msg += (
                    'If the source archive is a tar archive compressed using '
                    'a compression type not natively supported by the tar '
                    'command, then setting the \'list_options\' argument may '
                    'allow the contents to be listed. Otherwise, if Salt is '
                    'unable to determine the files/directories in the '
                    'archive, the following workaround(s) would need to be '
                    'used for this state to proceed'
                )
            else:
                msg += (
                    'The following workarounds must be used for this state to '
                    'proceed'
                )
            msg += (
                ' (assuming the source file is a valid {0} archive):\n'
                .format(archive_format)
            )

            for error in errors:
                msg += '\n- {0}'.format(error)
        ret['comment'] = msg
        return ret

    if enforce_toplevel and contents is not None \
            and (len(contents['top_level_dirs']) > 1
                 or len(contents['top_level_files']) > 0):
        ret['comment'] = ('Archive does not have a single top-level directory. '
                          'To allow this archive to be extracted, set '
                          '\'enforce_toplevel\' to False. To avoid a '
                          '\'{0}-bomb\' it may also be advisable to set a '
                          'top-level directory by adding it to the \'name\' '
                          'value (for example, setting \'name\' to {1} '
                          'instead of {2}).'.format(
                              archive_format,
                              os.path.join(name, 'some_dir'),
                              name,
                          ))
        return ret

    extraction_needed = overwrite
    contents_missing = False

    # Check to see if we need to extract the archive. Using os.lstat() in a
    # try/except is considerably faster than using os.path.exists(), and we
    # already need to catch an OSError to cover edge cases where the minion is
    # running as a non-privileged user and is trying to check for the existence
    # of a path to which it does not have permission.
    try:
        if_missing_path_exists = os.path.exists(if_missing)
    except TypeError:
        if_missing_path_exists = False

    if not if_missing_path_exists:
        if contents is None:
            try:
                os.lstat(if_missing)
                extraction_needed = False
            except OSError as exc:
                if exc.errno == errno.ENOENT:
                    extraction_needed = True
                else:
                    ret['comment'] = (
                        'Failed to check for existence of if_missing path '
                        '({0}): {1}'.format(if_missing, exc.__str__())
                    )
                    return ret
        else:
            incorrect_type = []
            for path_list, func in \
                    ((contents['dirs'], stat.S_ISDIR),
                     (contents['files'], lambda x: not stat.S_ISLNK(x)
                                         and not stat.S_ISDIR(x)),
                     (contents['links'], stat.S_ISLNK)):
                for path in path_list:
                    full_path = os.path.join(name, path)
                    try:
                        path_mode = os.lstat(full_path.rstrip(os.sep)).st_mode
                        if not func(path_mode):
                            incorrect_type.append(path)
                    except OSError as exc:
                        if exc.errno == errno.ENOENT:
                            extraction_needed = True
                            contents_missing = True
                        elif exc.errno != errno.ENOTDIR:
                            # In cases where a directory path was occupied by a
                            # file instead, all os.lstat() calls to files within
                            # that dir will raise an ENOTDIR OSError. So we
                            # expect these and will only abort here if the
                            # error code is something else.
                            ret['comment'] = exc.__str__()
                            return ret

            if incorrect_type:
                incorrect_paths = '\n\n' + '\n'.join(
                    ['- {0}'.format(x) for x in incorrect_type]
                )
                ret['comment'] = (
                    'The below paths (relative to {0}) exist, but are the '
                    'incorrect type (file instead of directory, symlink '
                    'instead of file, etc.).'.format(name)
                )
                if __opts__['test'] and clean and contents is not None:
                    ret['result'] = None
                    ret['comment'] += (
                        ' Since the \'clean\' option is enabled, the '
                        'destination paths would be cleared and the '
                        'archive would be extracted.{0}'.format(
                            incorrect_paths
                        )
                    )
                    return ret

                # Skip notices of incorrect types if we're cleaning
                if not (clean and contents is not None):
                    if not force:
                        ret['comment'] += (
                            ' To proceed with extraction, set \'force\' to '
                            'True. Note that this will remove these paths '
                            'before extracting.{0}'.format(incorrect_paths)
                        )
                        return ret
                    else:
                        errors = []
                        for path in incorrect_type:
                            full_path = os.path.join(name, path)
                            try:
                                salt.utils.rm_rf(full_path.rstrip(os.sep))
                                ret['changes'].setdefault(
                                    'removed', []).append(full_path)
                                extraction_needed = True
                            except OSError as exc:
                                if exc.errno != errno.ENOENT:
                                    errors.append(exc.__str__())
                        if errors:
                            msg = (
                                'One or more paths existed by were the incorrect '
                                'type (i.e. file instead of directory or '
                                'vice-versa), but could not be removed. The '
                                'following errors were observed:\n'
                            )
                            for error in errors:
                                msg += '\n- {0}'.format(error)
                            ret['comment'] = msg
                            return ret

    if not extraction_needed \
            and source_hash_update \
            and existing_cached_source_sum is not None \
            and not _compare_checksum(cached_source, existing_cached_source_sum):
        extraction_needed = True
        source_hash_trigger = True
    else:
        source_hash_trigger = False

    created_destdir = False

    if extraction_needed:
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = \
                'Archive {0} would be extracted to {1}'.format(
                    source_match,
                    name
                )
            if clean and contents is not None:
                ret['comment'] += ', after cleaning destination path(s)'
            _add_explanation(ret, source_hash_trigger, contents_missing)
            return ret

        if clean and contents is not None:
            errors = []
            log.debug('Cleaning archive paths from within %s', name)
            for path in contents['top_level_dirs'] + contents['top_level_files']:
                full_path = os.path.join(name, path)
                try:
                    log.debug('Removing %s', full_path)
                    salt.utils.rm_rf(full_path.rstrip(os.sep))
                    ret['changes'].setdefault(
                        'removed', []).append(full_path)
                except OSError as exc:
                    if exc.errno != errno.ENOENT:
                        errors.append(exc.__str__())

            if errors:
                msg = (
                    'One or more paths could not be cleaned. The following '
                    'errors were observed:\n'
                )
                for error in errors:
                    msg += '\n- {0}'.format(error)
                ret['comment'] = msg
                return ret

        if not os.path.isdir(name):
            __salt__['file.makedirs'](name, user=user)
            created_destdir = True

        log.debug('Extracting {0} to {1}'.format(cached_source, name))
        try:
            if archive_format == 'zip':
                if use_cmd_unzip:
                    try:
                        files = __salt__['archive.cmd_unzip'](
                            cached_source,
                            name,
                            options=options,
                            trim_output=trim_output,
                            password=password,
                            **kwargs)
                    except (CommandExecutionError, CommandNotFoundError) as exc:
                        ret['comment'] = exc.strerror
                        return ret
                else:
                    files = __salt__['archive.unzip'](cached_source,
                                                      name,
                                                      options=options,
                                                      trim_output=trim_output,
                                                      password=password,
                                                      **kwargs)
            elif archive_format == 'rar':
                try:
                    files = __salt__['archive.unrar'](cached_source,
                                                      name,
                                                      trim_output=trim_output,
                                                      **kwargs)
                except (CommandExecutionError, CommandNotFoundError) as exc:
                    ret['comment'] = exc.strerror
                    return ret
            else:
                if options is None:
                    try:
                        with closing(tarfile.open(cached_source, 'r')) as tar:
                            tar.extractall(name)
                            files = tar.getnames()
                            if trim_output:
                                files = files[:trim_output]
                    except tarfile.ReadError:
                        if salt.utils.which('xz'):
                            if __salt__['cmd.retcode'](
                                    ['xz', '-t', cached_source],
                                    python_shell=False,
                                    ignore_retcode=True) == 0:
                                # XZ-compressed data
                                log.debug(
                                    'Tar file is XZ-compressed, attempting '
                                    'decompression and extraction using XZ Utils '
                                    'and the tar command'
                                )
                                # Must use python_shell=True here because not
                                # all tar implementations support the -J flag
                                # for decompressing XZ-compressed data. We need
                                # to dump the decompressed data to stdout and
                                # pipe it to tar for extraction.
                                cmd = 'xz --decompress --stdout {0} | tar xvf -'
                                results = __salt__['cmd.run_all'](
                                    cmd.format(_cmd_quote(cached_source)),
                                    cwd=name,
                                    python_shell=True)
                                if results['retcode'] != 0:
                                    if created_destdir:
                                        _cleanup_destdir(name)
                                    ret['result'] = False
                                    ret['changes'] = results
                                    return ret
                                if _is_bsdtar():
                                    files = results['stderr']
                                else:
                                    files = results['stdout']
                            else:
                                # Failed to open tar archive and it is not
                                # XZ-compressed, gracefully fail the state
                                if created_destdir:
                                    _cleanup_destdir(name)
                                ret['result'] = False
                                ret['comment'] = (
                                    'Failed to read from tar archive using '
                                    'Python\'s native tar file support. If '
                                    'archive is compressed using something '
                                    'other than gzip or bzip2, the '
                                    '\'options\' argument may be required to '
                                    'pass the correct options to the tar '
                                    'command in order to extract the archive.'
                                )
                                return ret
                        else:
                            if created_destdir:
                                _cleanup_destdir(name)
                            ret['result'] = False
                            ret['comment'] = (
                                'Failed to read from tar archive. If it is '
                                'XZ-compressed, install xz-utils to attempt '
                                'extraction.'
                            )
                            return ret
                else:
                    if not salt.utils.which('tar'):
                        ret['comment'] = (
                            'tar command not available, it might not be '
                            'installed on minion'
                        )
                        return ret

                    tar_opts = shlex.split(options)

                    tar_cmd = ['tar']
                    tar_shortopts = 'x'
                    tar_longopts = []

                    for position, opt in enumerate(tar_opts):
                        if opt.startswith('-'):
                            tar_longopts.append(opt)
                        else:
                            if position > 0:
                                tar_longopts.append(opt)
                            else:
                                append_opt = opt
                                append_opt = append_opt.replace('x', '')
                                append_opt = append_opt.replace('f', '')
                                tar_shortopts = tar_shortopts + append_opt

                    if __grains__['os'].lower() == 'openbsd':
                        tar_shortopts = '-' + tar_shortopts

                    tar_cmd.append(tar_shortopts)
                    tar_cmd.extend(tar_longopts)
                    tar_cmd.extend(['-f', cached_source])

                    results = __salt__['cmd.run_all'](tar_cmd,
                                                      cwd=name,
                                                      python_shell=False)
                    if results['retcode'] != 0:
                        ret['result'] = False
                        ret['changes'] = results
                        return ret
                    if _is_bsdtar():
                        files = results['stderr']
                    else:
                        files = results['stdout']
                    if not files:
                        files = 'no tar output so far'
        except CommandExecutionError as exc:
            ret['comment'] = exc.strerror
            return ret

    # Recursively set user and group ownership of files
    enforce_missing = []
    enforce_failed = []
    if user or group:
        if enforce_ownership_on:
            if os.path.isdir(enforce_ownership_on):
                enforce_dirs = [enforce_ownership_on]
                enforce_files = []
                enforce_links = []
            else:
                enforce_dirs = []
                enforce_files = [enforce_ownership_on]
                enforce_links = []
        else:
            if contents is not None:
                enforce_dirs = contents['top_level_dirs']
                enforce_files = contents['top_level_files']
                enforce_links = contents['top_level_links']

        recurse = []
        if user:
            recurse.append('user')
        if group:
            recurse.append('group')
        recurse_str = ', '.join(recurse)

        owner_changes = dict([
            (x, y) for x, y in (('user', user), ('group', group)) if y
        ])
        for dirname in enforce_dirs:
            full_path = os.path.join(name, dirname)
            if not os.path.isdir(full_path):
                if not __opts__['test']:
                    enforce_missing.append(full_path)
            else:
                log.debug(
                    'Enforcing %s ownership on %s using a file.directory state%s',
                    recurse_str,
                    dirname,
                    ' (dry-run only)' if __opts__['test'] else ''
                )
                dir_result = __states__['file.directory'](full_path,
                                                          user=user,
                                                          group=group,
                                                          recurse=recurse,
                                                          test=__opts__['test'])
                log.debug('file.directory: %s', dir_result)

                if __opts__['test']:
                    if dir_result.get('pchanges'):
                        ret['changes']['updated ownership'] = True
                else:
                    try:
                        if dir_result['result']:
                            if dir_result['changes']:
                                ret['changes']['updated ownership'] = True
                        else:
                            enforce_failed.append(full_path)
                    except (KeyError, TypeError):
                        log.warning(
                            'Bad state return %s for file.directory state on %s',
                            dir_result, dirname
                        )

        for filename in enforce_files + enforce_links:
            full_path = os.path.join(name, filename)
            try:
                # Using os.lstat instead of calling out to
                # __salt__['file.stats'], since we may be doing this for a lot
                # of files, and simply calling os.lstat directly will speed
                # things up a bit.
                file_stat = os.lstat(full_path)
            except OSError as exc:
                if not __opts__['test']:
                    if exc.errno == errno.ENOENT:
                        enforce_missing.append(full_path)
                    enforce_failed.append(full_path)
            else:
                # Earlier we set uid, gid to -1 if we're not enforcing
                # ownership on user, group, as passing -1 to os.chown will tell
                # it not to change that ownership. Since we've done that, we
                # can selectively compare the uid/gid from the values in
                # file_stat, _only if_ the "desired" uid/gid is something other
                # than -1.
                if (uid != -1 and uid != file_stat.st_uid) \
                        or (gid != -1 and gid != file_stat.st_gid):
                    if __opts__['test']:
                        ret['changes']['updated ownership'] = True
                    else:
                        try:
                            os.lchown(full_path, uid, gid)
                            ret['changes']['updated ownership'] = True
                        except OSError:
                            enforce_failed.append(filename)

    if extraction_needed:
        if len(files) > 0:
            if created_destdir:
                ret['changes']['directories_created'] = [name]
            ret['changes']['extracted_files'] = files
            ret['comment'] = '{0} extracted to {1}'.format(source_match, name)
            _add_explanation(ret, source_hash_trigger, contents_missing)
            ret['result'] = True

        else:
            ret['result'] = False
            ret['comment'] = 'Can\'t extract content of {0}'.format(source_match)
    else:
        ret['result'] = True
        if if_missing_path_exists:
            ret['comment'] = '{0} exists'.format(if_missing)
        else:
            ret['comment'] = 'All files in archive are already present'
        if __opts__['test']:
            if ret['changes'].get('updated ownership'):
                ret['result'] = None
                ret['comment'] += (
                    '. Ownership would be updated on one or more '
                    'files/directories.'
                )

    if enforce_missing:
        if not if_missing:
            # If is_missing was used, and both a) the archive had never been
            # extracted, and b) the path referred to by if_missing exists, then
            # enforce_missing would contain paths of top_levle dirs/files that
            # _would_ have been extracted. Since if_missing can be used as a
            # semaphore to conditionally extract, we don't want to make this a
            # case where the state fails, so we only fail the state if
            # is_missing is not used.
            ret['result'] = False
        ret['comment'] += (
            '\n\nWhile trying to enforce user/group ownership, the following '
            'paths were missing:\n'
        )
        for item in enforce_missing:
            ret['comment'] += '\n- {0}'.format(item)

    if enforce_failed:
        ret['result'] = False
        ret['comment'] += (
            '\n\nWhile trying to enforce user/group ownership, Salt was '
            'unable to change ownership on the following paths:\n'
        )
        for item in enforce_failed:
            ret['comment'] += '\n- {0}'.format(item)

    if not source_is_local and not keep:
        for path in (cached_source, __salt__['cp.is_cached'](source_match)):
            if not path:
                continue
            log.debug('Cleaning cached source file %s', path)
            try:
                os.remove(path)
            except OSError as exc:
                if exc.errno != errno.ENOENT:
                    log.error(
                        'Failed to clean cached source file %s: %s',
                        cached_source, exc.__str__()
                    )

    return ret
