# coding: utf-8
'''
A collection of mixins useful for the various *Client interfaces
'''
from __future__ import print_function
import datetime
import logging
import multiprocessing
import time

import salt.utils
import salt.utils.event
from salt.utils.event import tagify
from salt.utils.doc import strip_rst as _strip_rst

log = logging.getLogger(__name__)


class SyncClientMixin(object):
    '''
    A mixin for *Client interfaces to abstract common function execution
    '''
    functions = ()

    def _verify_fun(self, fun):
        '''
        Check that the function passed really exists
        '''
        if fun not in self.functions:
            err = 'Function {0!r} is unavailable'.format(fun)
            raise salt.exceptions.CommandExecutionError(err)

    def low(self, fun, low):
        '''
        Execute a function from low data
        '''
        self._verify_fun(fun)
        l_fun = self.functions[fun]
        f_call = salt.utils.format_call(l_fun, low)
        ret = l_fun(*f_call.get('args', ()), **f_call.get('kwargs', {}))
        return ret

    def get_docs(self, arg=None):
        '''
        Return a dictionary of functions and the inline documentation for each
        '''
        if arg:
            target_mod = arg + '.' if not arg.endswith('.') else arg
            docs = [(fun, self.functions[fun].__doc__)
                    for fun in sorted(self.functions)
                    if fun == arg or fun.startswith(target_mod)]
        else:
            docs = [(fun, self.functions[fun].__doc__)
                    for fun in sorted(self.functions)]
        docs = dict(docs)
        return _strip_rst(docs)


class AsyncClientMixin(object):
    '''
    A mixin for *Client interfaces to enable easy async function execution
    '''
    client = None
    tag_prefix = None

    def _proc_function(self, fun, low, user, tag, jid):
        '''
        Run this method in a multiprocess target to execute the function in a
        multiprocess and fire the return data on the event bus
        '''
        salt.utils.daemonize()
        event = salt.utils.event.get_event(
                'master',
                self.opts['sock_dir'],
                self.opts['transport'],
                listen=False)
        data = {'fun': '{0}.{1}'.format(self.client, fun),
                'jid': jid,
                'user': user,
                }
        event.fire_event(data, tagify('new', base=tag))

        try:
            data['return'] = self.low(fun, low)
            data['success'] = True
        except Exception as exc:
            data['return'] = 'Exception occurred in {0} {1}: {2}: {3}'.format(
                            self.client,
                            fun,
                            exc.__class__.__name__,
                            exc,
                            )
            data['success'] = False
        data['user'] = user
        event.fire_event(data, tagify('ret', base=tag))
        # this is a workaround because process reaping is defeating 0MQ linger
        time.sleep(2.0)  # delay so 0MQ event gets out before runner process reaped

    def async(self, fun, low, user='UNKNOWN'):
        '''
        Execute the function in a multiprocess and return the event tag to use
        to watch for the return
        '''
        jid = '{0:%Y%m%d%H%M%S%f}'.format(datetime.datetime.now())
        tag = tagify(jid, prefix=self.tag_prefix)

        proc = multiprocessing.Process(
                target=self._proc_function,
                args=(fun, low, user, tag, jid))
        proc.start()
        return {'tag': tag, 'jid': jid}
