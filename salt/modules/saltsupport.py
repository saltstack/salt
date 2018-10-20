# coding=utf-8
'''
Module to run salt-support within Salt
'''
from __future__ import unicode_literals, print_function, absolute_import

from salt.cli.support.collector import SaltSupport, SupportDataCollector
import salt.utils.decorators
import tempfile
import os
import sys
import time
import logging


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


class _Util(object):  # This might get moved elsewhere in a future.
    '''
    Utility class.
    '''
    def get_exportable_methods(self):
        '''
        Get exportable methods that are not marked as internal in __doc__.
        :return:
        '''
        exportable = []
        for obj_name in dir(self):
            obj = getattr(self, obj_name)
            if getattr(obj, 'external', False):
                exportable.append((obj_name, obj))

        return exportable


class SaltSupportModule(SaltSupport):
    '''
    Salt Support module class.
    '''
    def setup_config(self):
        '''
        Return current configuration
        :return:
        '''
        return __opts__

    def _get_default_archive_name(self):
        '''
        Create default archive name.

        :return:
        '''
        host = None
        for grain in ['fqdn', 'host', 'localhost', 'nodename']:
            host = __grains__.get(grain)
            if host:
                break
        if not host:
            host = 'localhost'

        return os.path.join(tempfile.gettempdir(),
                            '{hostname}-support-{date}-{time}.bz2'.format(
                                hostname=host, date=time.strftime('%Y%m%d'), time=time.strftime('%H%M%S')))

    @salt.utils.decorators.external
    def run(self, archive=None, output='nested'):
        '''

        :return:
        '''
        self.config = __opts__
        self.config['support_profile'] = 'default'
        self.out = LogCollector()
        self.collector = SupportDataCollector(archive or self._get_default_archive_name(), output)

        self.collector.open()
        self.collect_local_data()
        self.collect_internal_data()
        self.collector.close()

        return {'archive': self.collector.archive_path,
                'messages': self.out.messages}


def __virtual__():
    return True


def run():
    '''

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

    for method_name, obj in support.get_exportable_methods():
        setattr(sys.modules[__name__], method_name, _set_function(obj))

    return True
    return support.run()
