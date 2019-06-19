# coding=utf-8
'''
Local Runner
'''

from __future__ import print_function, absolute_import, unicode_literals
import salt.runner
import salt.utils.platform
import salt.utils.process
import logging

log = logging.getLogger(__name__)


class LocalRunner(salt.runner.Runner):
    '''
    Runner class that changes its default behaviour.
    '''

    def _proc_function(self, fun, low, user, tag, jid, daemonize=True):
        '''
        Same as original _proc_function in AsyncClientMixin,
        except it calls "low" without firing a print event.
        '''
        if daemonize and not salt.utils.platform.is_windows():
            salt.log.setup.shutdown_multiprocessing_logging()
            salt.utils.process.daemonize()
            salt.log.setup.setup_multiprocessing_logging()

        low['__jid__'] = jid
        low['__user__'] = user
        low['__tag__'] = tag

        return self.low(fun, low, print_event=False, full_return=False)
