# coding: utf-8
'''
A collection of mixins useful for the various *Client interfaces
'''
from __future__ import print_function
from __future__ import absolute_import
import logging
import multiprocessing

import salt.utils
import salt.utils.event
import salt.utils.jid
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
        if not fun:
            err = 'Must specify a function to run'
            raise salt.exceptions.CommandExecutionError(err)
        if fun not in self.functions:
            err = 'Function {0!r} is unavailable'.format(fun)
            raise salt.exceptions.CommandExecutionError(err)

    def low(self, fun, low):
        '''
        Execute a function from low data
        '''
        jid = low.get('__jid__', salt.utils.jid.gen_jid())
        tag = low.get('__tag__', tagify(jid, prefix=self.tag_prefix))
        data = {'fun': '{0}.{1}'.format(self.client, fun),
                'jid': jid,
                'user': low.get('__user__', 'UNKNOWN'),
                }
        event = salt.utils.event.get_event(
                'master',
                self.opts['sock_dir'],
                self.opts['transport'],
                opts=self.opts,
                listen=False)
        event.fire_event(data, tagify('new', base=tag))

        # TODO: document these, and test that they exist
        # TODO: Other things to inject??
        func_globals = {'__jid__': jid,
                        '__user__': data['user'],
                        '__tag__': tag,
                        '__jid_event__': salt.utils.event.NamespacedEvent(event, tag),
                        }
        # Inject some useful globals to the funciton's global namespace
        for global_key, value in func_globals.iteritems():
            self.functions[fun].func_globals[global_key] = value
        try:
            self._verify_fun(fun)
            l_fun = self.functions[fun]
            f_call = salt.utils.format_call(l_fun, low)
            data['return'] = l_fun(*f_call.get('args', ()), **f_call.get('kwargs', {}))
            data['success'] = True
        except Exception as exc:
            data['return'] = 'Exception occurred in {0} {1}: {2}: {3}'.format(
                            self.client,
                            fun,
                            exc.__class__.__name__,
                            exc,
                            )
            data['success'] = False

        event.fire_event(data, tagify('ret', base=tag))
        # if we fired an event, make sure to delete the event object.
        # This will ensure that we call destroy, which will do the 0MQ linger
        del event
        return data['return']

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
        # pack a few things into low
        low['__jid__'] = jid
        low['__user__'] = user
        low['__tag__'] = tag

        self.low(fun, low)

    def async(self, fun, low, user='UNKNOWN'):
        '''
        Execute the function in a multiprocess and return the event tag to use
        to watch for the return
        '''
        jid = salt.utils.jid.gen_jid()
        tag = tagify(jid, prefix=self.tag_prefix)

        proc = multiprocessing.Process(
                target=self._proc_function,
                args=(fun, low, user, tag, jid))
        proc.start()
        proc.join()  # MUST join, otherwise we leave zombies all over
        return {'tag': tag, 'jid': jid}
