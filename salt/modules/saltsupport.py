# -*- coding: utf-8 -*-
#
# Author: Bo Maryniuk <bo@suse.de>
#
# Copyright 2018 SUSE LLC
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
'''
:codeauthor: `Bo Maryniuk <bo@suse.de>`

Module to run salt-support within Salt.
'''
# pylint: disable=W0231,W0221

from __future__ import unicode_literals, print_function, absolute_import

import tempfile
import re
import os
import sys
import time
import datetime
import logging

import salt.cli.support.intfunc
import salt.utils.decorators
import salt.utils.path
import salt.cli.support
import salt.exceptions
import salt.utils.stringutils
import salt.defaults.exitcodes
import salt.utils.odict
import salt.utils.dictupdate

from salt.cli.support.collector import SaltSupport, SupportDataCollector

__virtualname__ = 'support'
log = logging.getLogger(__name__)


class LogCollector(object):
    '''
    Output collector.
    '''
    INFO = 'info'
    WARNING = 'warning'
    ERROR = 'error'

    class MessagesList(list):
        def append(self, obj):
            list.append(self, '{} - {}'.format(datetime.datetime.utcnow().strftime('%H:%M:%S.%f')[:-3], obj))
        __call__ = append

    def __init__(self):
        self.messages = {
            self.INFO: self.MessagesList(),
            self.WARNING: self.MessagesList(),
            self.ERROR: self.MessagesList(),
        }

    def msg(self, message, *args, **kwargs):
        title = kwargs.get('title')
        if title:
            message = '{}: {}'.format(title, message)
        self.messages[self.INFO](message)

    def info(self, message, *args, **kwargs):
        self.msg(message)

    def warning(self, message, *args, **kwargs):
        self.messages[self.WARNING](message)

    def error(self, message, *args, **kwargs):
        self.messages[self.ERROR](message)

    def put(self, message, *args, **kwargs):
        self.messages[self.INFO](message)

    def highlight(self, message, *values, **kwargs):
        self.msg(message.format(*values))


class SaltSupportModule(SaltSupport):
    '''
    Salt Support module class.
    '''
    def __init__(self):
        '''
        Constructor
        '''
        self.config = self.setup_config()

    def setup_config(self):
        '''
        Return current configuration
        :return:
        '''
        return __opts__

    def _get_archive_name(self, archname=None):
        '''
        Create default archive name.

        :return:
        '''
        archname = re.sub('[^a-z0-9]', '', (archname or '').lower()) or 'support'
        for grain in ['fqdn', 'host', 'localhost', 'nodename']:
            host = __grains__.get(grain)
            if host:
                break
        if not host:
            host = 'localhost'

        return os.path.join(tempfile.gettempdir(),
                            '{hostname}-{archname}-{date}-{time}.bz2'.format(archname=archname,
                                                                             hostname=host,
                                                                             date=time.strftime('%Y%m%d'),
                                                                             time=time.strftime('%H%M%S')))

    @salt.utils.decorators.external
    def profiles(self):
        '''
        Get list of profiles.

        :return:
        '''
        return {
            'standard': salt.cli.support.get_profiles(self.config),
            'custom': [],
        }

    @salt.utils.decorators.external
    def archives(self):
        '''
        Get list of existing archives.
        :return:
        '''
        arc_files = []
        tmpdir = tempfile.gettempdir()
        for filename in os.listdir(tmpdir):
            mtc = re.match(r'\w+-\w+-\d+-\d+\.bz2', filename)
            if mtc and len(filename) == mtc.span()[-1]:
                arc_files.append(os.path.join(tmpdir, filename))

        return arc_files

    @salt.utils.decorators.external
    def last_archive(self):
        '''
        Get the last available archive
        :return:
        '''
        archives = {}
        for archive in self.archives():
            archives[int(archive.split('.')[0].split('-')[-1])] = archive

        return archives and archives[max(archives)] or None

    @salt.utils.decorators.external
    def delete_archives(self, *archives):
        '''
        Delete archives
        :return:
        '''
        # Remove paths
        _archives = []
        for archive in archives:
            _archives.append(os.path.basename(archive))
        archives = _archives[:]

        ret = {'files': {}, 'errors': {}}
        for archive in self.archives():
            arc_dir = os.path.dirname(archive)
            archive = os.path.basename(archive)
            if archives and archive in archives or not archives:
                archive = os.path.join(arc_dir, archive)
                try:
                    os.unlink(archive)
                    ret['files'][archive] = 'removed'
                except Exception as err:
                    ret['errors'][archive] = str(err)
                    ret['files'][archive] = 'left'

        return ret

    def format_sync_stats(self, cnt):
        '''
        Format stats of the sync output.

        :param cnt:
        :return:
        '''
        stats = salt.utils.odict.OrderedDict()
        if cnt.get('retcode') == salt.defaults.exitcodes.EX_OK:
            for line in cnt.get('stdout', '').split(os.linesep):
                line = line.split(': ')
                if len(line) == 2:
                    stats[line[0].lower().replace(' ', '_')] = line[1]
            cnt['transfer'] = stats
            del cnt['stdout']

        # Remove empty
        empty_sections = []
        for section in cnt:
            if not cnt[section] and section != 'retcode':
                empty_sections.append(section)
        for section in empty_sections:
            del cnt[section]

        return cnt

    @salt.utils.decorators.depends('rsync')
    @salt.utils.decorators.external
    def sync(self, group, name=None, host=None, location=None, move=False, all=False):
        '''
        Sync the latest archive to the host on given location.

        CLI Example:

        .. code-block:: bash

            salt '*' support.sync group=test
            salt '*' support.sync group=test name=/tmp/myspecial-12345-67890.bz2
            salt '*' support.sync group=test name=/tmp/myspecial-12345-67890.bz2 host=allmystuff.lan
            salt '*' support.sync group=test name=/tmp/myspecial-12345-67890.bz2 host=allmystuff.lan location=/opt/

        :param group: name of the local directory to which sync is going to put the result files
        :param name: name of the archive. Latest, if not specified.
        :param host: name of the destination host for rsync. Default is master, if not specified.
        :param location: local destination directory, default temporary if not specified
        :param move: move archive file[s]. Default is False.
        :param all: work with all available archives. Default is False (i.e. latest available)

        :return:
        '''
        tfh, tfn = tempfile.mkstemp()
        processed_archives = []
        src_uri = uri = None

        last_arc = self.last_archive()
        if name:
            archives = [name]
        elif all:
            archives = self.archives()
        elif last_arc:
            archives = [last_arc]
        else:
            archives = []

        for name in archives:
            err = None
            if not name:
                err = 'No support archive has been defined.'
            elif not os.path.exists(name):
                err = 'Support archive "{}" was not found'.format(name)
            if err is not None:
                log.error(err)
                raise salt.exceptions.SaltInvocationError(err)

            if not uri:
                src_uri = os.path.dirname(name)
                uri = '{host}:{loc}'.format(host=host or __opts__['master'],
                                            loc=os.path.join(location or tempfile.gettempdir(), group))

            os.write(tfh, salt.utils.stringutils.to_bytes(os.path.basename(name)))
            os.write(tfh, salt.utils.stringutils.to_bytes(os.linesep))
            processed_archives.append(name)
            log.debug('Syncing %s to %s', name, uri)
        os.close(tfh)

        if not processed_archives:
            raise salt.exceptions.SaltInvocationError('No archives found to transfer.')

        ret = __salt__['rsync.rsync'](src=src_uri, dst=uri, additional_opts=['--stats', '--files-from={}'.format(tfn)])
        ret['files'] = {}
        for name in processed_archives:
            if move:
                salt.utils.dictupdate.update(ret, self.delete_archives(name))
                log.debug('Deleting %s', name)
                ret['files'][name] = 'moved'
            else:
                ret['files'][name] = 'copied'

        try:
            os.unlink(tfn)
        except (OSError, IOError) as err:
            log.error('Cannot remove temporary rsync file %s: %s', tfn, err)

        return self.format_sync_stats(ret)

    @salt.utils.decorators.external
    def run(self, profile='default', pillar=None, archive=None, output='nested'):
        '''
        Run Salt Support on the minion.

        profile
            Set available profile name. Default is "default".

        pillar
            Set available profile from the pillars.

        archive
            Override archive name. Default is "support". This results to "hostname-support-YYYYMMDD-hhmmss.bz2".

        output
            Change the default outputter. Default is "nested".

        CLI Example:

        .. code-block:: bash

            salt '*' support.run
            salt '*' support.run profile=network
            salt '*' support.run pillar=something_special
        '''
        class outputswitch(object):
            '''
            Output switcher on context
            '''
            def __init__(self, output_device):
                self._tmp_out = output_device
                self._orig_out = None

            def __enter__(self):
                self._orig_out = salt.cli.support.intfunc.out
                salt.cli.support.intfunc.out = self._tmp_out

            def __exit__(self, *args):
                salt.cli.support.intfunc.out = self._orig_out

        self.out = LogCollector()
        with outputswitch(self.out):
            self.collector = SupportDataCollector(archive or self._get_archive_name(archname=archive), output)
            self.collector.out = self.out
            self.collector.open()
            self.collect_local_data(profile=profile, profile_source=__pillar__.get(pillar))
            self.collect_internal_data()
            self.collector.close()

        return {'archive': self.collector.archive_path,
                'messages': self.out.messages}


def __virtual__():
    '''
    Set method references as module functions aliases
    :return:
    '''
    support = SaltSupportModule()

    def _set_function(obj):
        '''
        Create a Salt function for the SaltSupport class.
        '''
        def _cmd(*args, **kwargs):
            '''
            Call support method as a function from the Salt.
            '''
            _kwargs = {}
            for kw in kwargs:
                if not kw.startswith('__'):
                    _kwargs[kw] = kwargs[kw]
            return obj(*args, **_kwargs)
        _cmd.__doc__ = obj.__doc__
        return _cmd

    for m_name in dir(support):
        obj = getattr(support, m_name)
        if getattr(obj, 'external', False):
            setattr(sys.modules[__name__], m_name, _set_function(obj))

    return __virtualname__
