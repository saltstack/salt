# -*- coding: utf-8 -*-
'''
Archive states.

.. versionadded:: 2014.1.0
'''

import logging
import os
import tarfile
from contextlib import closing

log = logging.getLogger(__name__)


def extracted(name,
              source,
              archive_format,
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
          archive:
            - extracted
            - name: /opt/
            - source: https://github.com/downloads/Graylog2/graylog2-server/graylog2-server-0.9.6p1.tar.lzma
            - source_hash: md5=499ae16dcae71eeb7c3a30c75ea7a1a6
            - tar_options: J
            - archive_format: tar
            - if_missing: /opt/graylog2-server-0.9.6p1/

    .. code-block:: yaml

        graylog2-server:
          archive:
            - extracted
            - name: /opt/
            - source: https://github.com/downloads/Graylog2/graylog2-server/graylog2-server-0.9.6p1.tar.gz
            - source_hash: md5=499ae16dcae71eeb7c3a30c75ea7a1a6
            - archive_format: tar
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

    if_missing
        Some archives, such as tar, extract themselves in a subfolder.
        This directive can be used to validate if the archive had been
        previously extracted.

    tar_options
        Only used for tar format, it need to be the tar argument specific to
        this archive, such as 'J' for LZMA.
        Using this option means that the tar executable on the target will
        be used, which is less platform independent.
        Main operators like -x, --extract, --get, -c, etc. and -f/--file are
        **shoult not be used** here.
        If this option is not set, then the Python tarfile module is used.
        The tarfile module supports gzip and bz2 in Python 2.

    keep
        Keep the archive in the minion's cache
    '''
    ret = {'name': name, 'result': None, 'changes': {}, 'comment': ''}
    valid_archives = ('tar', 'rar', 'zip')

    if archive_format not in valid_archives:
        ret['result'] = False
        ret['comment'] = '{0} is not supported, valids: {1}'.format(
            name, ','.join(valid_archives))
        return ret

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
                            '{0}.{1}'.format(if_missing.replace('/', '_'),
                                             archive_format))
    if not os.path.exists(filename):
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = \
                'Archive {0} would have been downloaded in cache'.format(source)
            return ret

        log.debug('Archive file {0} is not in cache, download it'.format(source))
        data = {
            filename: {
                'file': [
                    'managed',
                    {'name': filename},
                    {'source': source},
                    {'source_hash': source_hash},
                    {'makedirs': True},
                    {'saltenv': __env__}
                ]
            }
        }
        file_result = __salt__['state.high'](data)
        log.debug('file.managed: {0}'.format(file_result))
        # get value of first key
        file_result = file_result[file_result.keys()[0]]
        if not file_result['result']:
            log.debug('failed to download {0}'.format(source))
            return file_result
    else:
        log.debug('Archive file {0} is already in cache'.format(name))

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Archive {0} would have been extracted in {1}'.format(
            source, name)
        return ret

    __salt__['file.makedirs'](name)

    if archive_format in ('zip', 'rar'):
        log.debug('Extract {0} in {1}'.format(filename, name))
        files = __salt__['archive.un{0}'.format(archive_format)](filename,
                                                                 name)
    else:
        if tar_options is None:
            with closing(tarfile.open(filename, 'r')) as tar:
                files = tar.getnames()
                tar.extractall(name)
        else:
            log.debug('Untar {0} in {1}'.format(filename, name))

            results = __salt__['cmd.run_all']('tar {0} -f {1!r}'.format(
                tar_options, filename), cwd=name)
            if results['retcode'] != 0:
                ret['result'] = False
                ret['changes'] = results
                return ret
            if __salt__['cmd.retcode']('tar --version | grep bsdtar') == 0:
                files = results['stderr']
            else:
                files = results['stdout']
            if not files:
                files = 'no tar output so far'
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
