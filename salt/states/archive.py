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

# Import salt libs
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
        Directory name where to extract the archive

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
        Some archives, such as tar, extract themselves in a subfolder.
        This directive can be used to validate if the archive had been
        previously extracted.

    tar_options
        Required if used with ``archive_format: tar``, otherwise optional.
        It needs to be the tar argument specific to the archive being extracted,
        such as 'J' for LZMA or 'v' to verbosely list files processed.
        Using this option means that the tar executable on the target will
        be used, which is less platform independent.
        Main operators like -x, --extract, --get, -c and -f/--file
        **should not be used** here.
        If ``archive_format`` is ``zip`` or ``rar`` and this option is not set,
        then the Python tarfile module is used. The tarfile module supports gzip
        and bz2 in Python 2.

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
        log.debug('Archive %s is already in cache', name)

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = '{0} {1} would be extracted to {2}'.format(
                'One of' if not isinstance(source_match, six.string_types)
                    else 'Archive',
                source_match,
                name
            )
        return ret

    __salt__['file.makedirs'](name, user=user, group=group)

    log.debug('Extracting {0} to {1}'.format(filename, name))
    if archive_format == 'zip':
        files = __salt__['archive.unzip'](filename, name)
    elif archive_format == 'rar':
        files = __salt__['archive.unrar'](filename, name)
    else:
        if tar_options is None:
            with closing(tarfile.open(filename, 'r')) as tar:
                files = tar.getnames()
                tar.extractall(name)
        else:
            tar_opts = tar_options.split(' ')

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
            if 'bsdtar' in __salt__['cmd.run']('tar --version', python_shell=False):
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
