# -*- coding: utf-8 -*-
'''
Extract an archive

.. versionadded:: 2014.1.0
'''

# Import Python libs
from __future__ import absolute_import
import re
import os
import logging
import tarfile
from contextlib import closing

# Import 3rd-party libs
import salt.ext.six as six
from salt.ext.six.moves import shlex_quote as _cmd_quote

# Import salt libs
import salt.utils
from salt.exceptions import CommandExecutionError
# remove after archive_user deprecation.
from salt.utils import warn_until

log = logging.getLogger(__name__)

__virtualname__ = 'archive'


def __virtual__():
    '''
    Only load if the npm module is available in __salt__
    '''
    return __virtualname__ \
        if [x for x in __salt__ if x.startswith('archive.')] \
        else False


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
              archive_format,
              archive_user=None,
              user=None,
              group=None,
              tar_options=None,
              source_hash=None,
              if_missing=None,
              keep=False):
    '''
    .. versionadded:: 2014.1.0

    State that make sure an archive is extracted in a directory.
    The downloaded archive is erased if successfully extracted.
    The archive is downloaded only if necessary.

    .. note::

        If ``if_missing`` is not defined, this state will check for ``name``
        instead.  If ``name`` exists, it will assume the archive was previously
        extracted successfully and will not extract it again.

    Example, tar with flag for lmza compression:

    .. code-block:: yaml

        graylog2-server:
          archive.extracted:
            - name: /opt/
            - source: https://github.com/downloads/Graylog2/graylog2-server/graylog2-server-0.9.6p1.tar.lzma
            - source_hash: md5=499ae16dcae71eeb7c3a30c75ea7a1a6
            - tar_options: J
            - archive_format: tar
            - if_missing: /opt/graylog2-server-0.9.6p1/

    Example, tar with flag for verbose output:

    .. code-block:: yaml

        graylog2-server:
          archive.extracted:
            - name: /opt/
            - source: https://github.com/downloads/Graylog2/graylog2-server/graylog2-server-0.9.6p1.tar.gz
            - source_hash: md5=499ae16dcae71eeb7c3a30c75ea7a1a6
            - archive_format: tar
            - tar_options: v
            - user: root
            - group: root
            - if_missing: /opt/graylog2-server-0.9.6p1/

    name
        Location where archive should be extracted

    source
        Archive source, same syntax as file.managed source argument.

    source_hash
        Hash of source file, or file with list of hash-to-file mappings.
        It uses the same syntax as the file.managed source_hash argument.

    archive_format
        tar, zip or rar

    archive_user
        The user to own each extracted file.

        .. deprecated:: 2014.7.2
            Replaced by ``user`` parameter

    user
        The user to own each extracted file.

        .. versionadded:: 2015.8.0

    group
        The group to own each extracted file.

        .. versionadded:: 2015.8.0

    if_missing
        If specified, this path will be checked, and if it exists then the
        archive will not be extracted. This can be helpful if the archive
        extracts all files into a subfolder. This path can be either a
        directory or a file, so this option can also be used to check for a
        semaphore file and conditionally skip extraction.

    tar_options
        If ``archive_format`` is set to ``tar``, this option can be used to
        specify a string of additional arguments to pass to the tar command. If
        ``archive_format`` is set to ``tar`` and this option is *not* used,
        then the minion will attempt to use Python's native tarfile_ support to
        extract it. Python's native tarfile_ support can only handle gzip and
        bzip2 compression, however.

        .. versionchanged:: 2015.8.11,2016.3.2
            XZ-compressed archives no longer require ``J`` to manually be set
            in the ``tar_options``, they are now detected automatically and
            Salt will extract them using ``xz-utils``. This is a more
            platform-independent solution, as not all tar implementations
            support the ``J`` argument for extracting archives.

        .. note::
            Main operators like -x, --extract, --get, -c and -f/--file **should
            not be used** here.

            Using this option means that the ``tar`` command will be used,
            which is less platform-independent, so keep this in mind when using
            this option; the options must be valid options for the ``tar``
            implementation on the minion's OS.

        .. _tarfile: https://docs.python.org/2/library/tarfile.html

    keep
        Keep the archive in the minion's cache
    '''
    ret = {'name': name, 'result': None, 'changes': {}, 'comment': ''}
    valid_archives = ('tar', 'rar', 'zip')

    if archive_format not in valid_archives:
        ret['result'] = False
        ret['comment'] = '{0} is not supported, valid formats are: {1}'.format(
            archive_format, ','.join(valid_archives))
        return ret

    # remove this whole block after formal deprecation.
    if archive_user is not None:
        warn_until(
          'Boron',
          'Passing \'archive_user\' is deprecated.'
          'Pass \'user\' instead.'
        )
        if user is None:
            user = archive_user

    if not name.endswith('/'):
        name += '/'

    if if_missing is None:
        if_missing = name
    if (
        __salt__['file.directory_exists'](if_missing)
        or __salt__['file.file_exists'](if_missing)
    ):
        ret['result'] = True
        ret['comment'] = '{0} already exists'.format(if_missing)
        return ret

    log.debug('Input seem valid so far')
    filename = os.path.join(__opts__['cachedir'],
                            'files',
                            __env__,
                            '{0}.{1}'.format(re.sub('[:/\\\\]', '_', if_missing),
                                             archive_format))

    if __opts__['test']:
        source_match = source
    else:
        try:
            source_match = __salt__['file.source_list'](source,
                                                        source_hash,
                                                        __env__)[0]
        except CommandExecutionError as exc:
            ret['result'] = False
            ret['comment'] = exc.strerror
            return ret

    if not os.path.exists(filename):
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = \
                '{0} {1} would be downloaded to cache'.format(
                    'One of' if not isinstance(source_match, six.string_types)
                        else 'Archive',
                    source_match
                )
            return ret

        log.debug('%s is not in cache, downloading it', source_match)
        file_result = __salt__['state.single']('file.managed',
                                               filename,
                                               source=source,
                                               source_hash=source_hash,
                                               makedirs=True,
                                               saltenv=__env__)
        log.debug('file.managed: {0}'.format(file_result))
        # get value of first key
        try:
            file_result = file_result[next(six.iterkeys(file_result))]
        except AttributeError:
            pass

        try:
            if not file_result['result']:
                log.debug('failed to download {0}'.format(source))
                return file_result
        except TypeError:
            if not file_result:
                log.debug('failed to download {0}'.format(source))
                return file_result
    else:
        log.debug('Archive %s is already in cache', source)

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = '{0} {1} would be extracted to {2}'.format(
                'One of' if not isinstance(source_match, six.string_types)
                    else 'Archive',
                source_match,
                name
            )
        return ret

    created_destdir = False
    if __salt__['file.file_exists'](name.rstrip('/')):
        ret['result'] = False
        ret['comment'] = ('{0} exists and is not a directory'
                          .format(name.rstrip('/')))
        return ret
    elif not __salt__['file.directory_exists'](name):
        __salt__['file.makedirs'](name, user=archive_user)
        created_destdir = True

    log.debug('Extracting {0} to {1}'.format(filename, name))
    if archive_format == 'zip':
        files = __salt__['archive.unzip'](filename, name)
    elif archive_format == 'rar':
        files = __salt__['archive.unrar'](filename, name)
    else:
        if tar_options is None:
            try:
                with closing(tarfile.open(filename, 'r')) as tar:
                    files = tar.getnames()
                    tar.extractall(name)
            except tarfile.ReadError:
                if salt.utils.which('xz'):
                    if __salt__['cmd.retcode'](['xz', '-l', filename],
                                               python_shell=False,
                                               ignore_retcode=True) == 0:
                        # XZ-compressed data
                        log.debug(
                            'Tar file is XZ-compressed, attempting '
                            'decompression and extraction using xz-utils '
                            'and the tar command'
                        )
                        # Must use python_shell=True here because not all tar
                        # implementations support the -J flag for decompressing
                        # XZ-compressed data. We need to dump the decompressed
                        # data to stdout and pipe it to tar for extraction.
                        cmd = 'xz --decompress --stdout {0} | tar xvf -'
                        results = __salt__['cmd.run_all'](
                            cmd.format(_cmd_quote(filename)),
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
                            'Failed to read from tar archive using Python\'s '
                            'native tar file support. If archive is '
                            'compressed using something other than gzip or '
                            'bzip2, the \'tar_options\' parameter may be '
                            'required to pass the correct options to the tar '
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
            try:
                tar_opts = tar_options.split(' ')
            except AttributeError:
                tar_opts = str(tar_options).split(' ')

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
                        append_opt = append_opt.replace('x', '').replace('f', '')
                        tar_shortopts = tar_shortopts + append_opt

            tar_cmd.append(tar_shortopts)
            tar_cmd.extend(tar_longopts)
            tar_cmd.extend(['-f', filename])

            results = __salt__['cmd.run_all'](tar_cmd, cwd=name, python_shell=False)
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

    # Recursively set user and group ownership of files after extraction.
    # Note: We do this here because we might not have access to the cachedir.
    if user or group:
        dir_result = __salt__['state.single']('file.directory',
                                               name,
                                               user=user,
                                               group=group,
                                               recurse=['user', 'group'])
        log.debug('file.directory: {0}'.format(dir_result))

    if len(files) > 0:
        ret['result'] = True
        ret['changes']['directories_created'] = [name]
        ret['changes']['extracted_files'] = files
        ret['comment'] = '{0} extracted to {1}'.format(source_match, name)
        if not keep:
            os.unlink(filename)
    else:
        __salt__['file.remove'](if_missing)
        ret['result'] = False
        ret['comment'] = 'Can\'t extract content of {0}'.format(source_match)
    return ret
