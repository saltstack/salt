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
Module to run salt-support within Salt.
'''
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
import salt.cli.support
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
            list.append(self, '{} - {}'.format(datetime.datetime.utcnow().strftime('%T.%f')[:-3], obj))
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
            mtc = re.match('\w+-\w+-\d+-\d+\.bz2', filename)
            if mtc and len(filename) == mtc.span()[-1]:
                arc_files.append(os.path.join(tmpdir, filename))

        return arc_files

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

        ret = {'failed': 0, 'deleted': 0, 'errors': {}}
        for archive in self.archives():
            arc_dir = os.path.dirname(archive)
            archive = os.path.basename(archive)
            if archives and archive in archives or not archives:
                archive = os.path.join(arc_dir, archive)
                try:
                    os.unlink(archive)
                    ret['deleted'] += 1
                except Exception as err:
                    ret['errors'][archive] = str(err)
                    ret['failed'] += 1

        return ret

    @salt.utils.decorators.external
    def run(self, profile='default', pillar=None, archive=None, output='nested'):
        '''
        Something
        '''
        self.out = LogCollector()

        self.collector = SupportDataCollector(archive or self._get_archive_name(archname=archive), output)
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
