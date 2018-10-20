# coding=utf-8
'''
Module to run salt-support within Salt
'''
from __future__ import unicode_literals, print_function, absolute_import

from salt.cli.support.collector import SaltSupport, SupportDataCollector

import salt.utils.decorators
import salt.cli.support
import tempfile
import re
import os
import sys
import time
import logging


__virtualname__ = 'support'
log = logging.getLogger(__name__)


class LogCollector(object):
    '''
    Output collector.
    '''
    INFO = 'info'
    WARNING = 'warning'
    ERROR = 'error'

    def __init__(self):
        self.messages = []

    def msg(self, message, *args, **kwargs):
        self.messages.append({self.INFO: message})

    def info(self, message, *args, **kwargs):
        self.msg(message)

    def warning(self, message, *args, **kwargs):
        self.messages.append({self.WARNING: message})

    def error(self, message, *args, **kwargs):
        self.messages.append({self.ERROR: message})

    def put(self, message, *args, **kwargs):
        self.messages.append({self.INFO: message})

    def highlight(self, message, *args, **kwargs):
        self.msg(message)


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
    def run(self, profile='default', archive=None, output='nested'):
        '''
        Something
        '''
        #self.config['support_profile'] = profile
        self.out = LogCollector()
        self.collector = SupportDataCollector(archive or self._get_default_archive_name(), output)

        self.collector.open()
        self.collect_local_data(profile=profile)
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
        def _cmd(*args, **kw):
            '''
            Call support method as a function from the Salt.
            '''
            kwargs = {}
            if kw.get('__pub_arg'):
                for _kw in kw.get('__pub_arg', []):
                    if isinstance(_kw, dict):
                        kwargs = _kw
                        break

            return obj(*args, **kwargs)
        _cmd.__doc__ = obj.__doc__
        return _cmd

    for m_name in dir(support):
        obj = getattr(support, m_name)
        if getattr(obj, 'external', False):
            setattr(sys.modules[__name__], m_name, _set_function(obj))

    return __virtualname__
