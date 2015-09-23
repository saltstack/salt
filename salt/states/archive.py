# -*- coding: utf-8 -*-
'''
Extract an archive

.. versionadded:: 2014.1.0
'''
from __future__ import absolute_import

import logging
import os
import tarfile
from contextlib import closing

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

    .. code-block:: yaml

        graylog2-server:
          archive.extracted:
            - name: /opt/
            - source: https://github.com/downloads/Graylog2/graylog2-server/graylog2-server-0.9.6p1.tar.lzma
            - source_hash: md5=499ae16dcae71eeb7c3a30c75ea7a1a6
            - tar_options: J
            - archive_format: tar
            - if_missing: /opt/graylog2-server-0.9.6p1/

    .. code-block:: yaml

        graylog2-server:
          archive.extracted:
            - name: /opt/
            - source: https://github.com/downloads/Graylog2/graylog2-server/graylog2-server-0.9.6p1.tar.gz
            - source_hash: md5=499ae16dcae71eeb7c3a30c75ea7a1a6
            - archive_format: tar
            - tar_options: v
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

    archive_user:
        user to extract files as

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
                            '{0}.{1}'.format(if_missing.replace('/', '_'),
                                             archive_format))
    if not os.path.exists(filename):
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = \
                'Archive {0} would have been downloaded in cache'.format(source)
            return ret

        log.debug('Archive file {0} is not in cache, download it'.format(source))
        file_result = __salt__['state.single']('file.managed',
                                               filename,
                                               source=source,
                                               source_hash=source_hash,
                                               makedirs=True,
                                               saltenv=__env__)
        log.debug('file.managed: {0}'.format(file_result))
        # get value of first key
        try:
            file_result = file_result[next(file_result.iterkeys())]
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
        log.debug('Archive file {0} is already in cache'.format(name))

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Archive {0} would have been extracted in {1}'.format(
            source, name)
        return ret

    __salt__['file.makedirs'](name, user=archive_user)

    log.debug('Extract {0} in {1}'.format(filename, name))
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
            if __salt__['cmd.retcode']('tar --version | grep bsdtar', python_shell=True) == 0:
                files = results['stderr']
            else:
                files = results['stdout']
            if not files:
                files = 'no tar output so far'

    if archive_user:
        # Recursively set the permissions after extracting as we might not have
        # access to the cachedir
        dir_result = __salt__['state.single']('file.directory',
                                               name,
                                               user=archive_user,
                                               recurse=['user'])
        log.debug('file.directory: {0}'.format(dir_result))

    if len(files) > 0:
        ret['result'] = True
        ret['changes']['directories_created'] = [name]
        if if_missing != name:
            ret['changes']['directories_created'].append(if_missing)
        ret['changes']['extracted_files'] = files
        ret['comment'] = '{0} extracted in {1}'.format(source, name)
        if not keep:
            os.unlink(filename)
    else:
        __salt__['file.remove'](if_missing)
        ret['result'] = False
        ret['comment'] = 'Can\'t extract content of {0}'.format(source)
    return ret
