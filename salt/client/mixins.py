# coding: utf-8
'''
A collection of mixins useful for the various *Client interfaces
'''
from __future__ import print_function
from __future__ import absolute_import
import collections
import logging
import traceback
import multiprocessing
import weakref

import salt.exceptions
import salt.utils
import salt.utils.event
import salt.utils.jid
import salt.utils.job
import salt.transport
from salt.utils.error import raise_error
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

    def master_call(self, **kwargs):
        '''
        Execute a function through the master network interface.
        '''
        load = kwargs
        load['cmd'] = self.client
        channel = salt.transport.Channel.factory(self.opts,
                                                 crypt='clear',
                                                 usage='master_call')
        ret = channel.send(load)
        if isinstance(ret, collections.Mapping):
            if 'error' in ret:
                raise_error(**ret['error'])
        return ret

    def cmd_sync(self, low, timeout=None):
        '''
        Execute a runner function synchronously; eauth is respected

        This function requires that :conf_master:`external_auth` is configured
        and the user is authorized to execute runner functions: (``@runner``).

        .. code-block:: python

            runner.eauth_sync({
                'fun': 'jobs.list_jobs',
                'username': 'saltdev',
                'password': 'saltdev',
                'eauth': 'pam',
            })
        '''
        event = salt.utils.event.get_master_event(self.opts, self.opts['sock_dir'])
        job = self.master_call(**low)
        ret_tag = salt.utils.event.tagify('ret', base=job['tag'])

        if timeout is None:
            timeout = 300
        ret = event.get_event(tag=ret_tag, full=True, wait=timeout)
        if ret is None:
            raise salt.exceptions.SaltClientTimeout(
                "RunnerClient job '{0}' timed out".format(job['jid']),
                jid=job['jid'])

        return ret['data']['return']

    def cmd(self, fun, arg=None, pub_data=None, kwarg=None):
        '''
        Execute a function

        .. code-block:: python

            >>> opts = salt.config.master_config('/etc/salt/master')
            >>> runner = salt.runner.RunnerClient(opts)
            >>> runner.cmd('jobs.list_jobs', [])
            {
                '20131219215650131543': {
                    'Arguments': [300],
                    'Function': 'test.sleep',
                    'StartTime': '2013, Dec 19 21:56:50.131543',
                    'Target': '*',
                    'Target-type': 'glob',
                    'User': 'saltdev'
                },
                '20131219215921857715': {
                    'Arguments': [300],
                    'Function': 'test.sleep',
                    'StartTime': '2013, Dec 19 21:59:21.857715',
                    'Target': '*',
                    'Target-type': 'glob',
                    'User': 'saltdev'
                },
            }

        '''
        if arg is None:
            arg = tuple()
        if not isinstance(arg, list) and not isinstance(arg, tuple):
            raise salt.exceptions.SaltInvocationError(
                'arg must be formatted as a list/tuple'
            )
        if pub_data is None:
            pub_data = {}
        if not isinstance(pub_data, dict):
            raise salt.exceptions.SaltInvocationError(
                'pub_data must be formatted as a dictionary'
            )
        if kwarg is None:
            kwarg = {}
        if not isinstance(kwarg, dict):
            raise salt.exceptions.SaltInvocationError(
                'kwarg must be formatted as a dictionary'
            )
        arglist = salt.utils.args.parse_input(arg)

        # if you were passed kwarg, add it to arglist
        if kwarg:
            kwarg['__kwarg__'] = True
            arglist.append(kwarg)

        args, kwargs = salt.minion.load_args_and_kwargs(
            self.functions[fun], arglist, pub_data
        )
        low = {'fun': fun,
               'args': args,
               'kwargs': kwargs}
        return self.low(fun, low)

    def low(self, fun, low):
        '''
        Execute a function from low data
        Low data includes:
            required:
                - fun: the name of the function to run
            optional:
                - args: a list of args to pass to fun
                - kwargs: kwargs for fun
                - __user__: user who is running the command
                - __jid__: jid to run under
                - __tag__: tag to run under
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

        namespaced_event = salt.utils.event.NamespacedEvent(event,
                                                            tag,
                                                            print_func=self.print_async_event if hasattr(self, 'print_async_event') else None)
        # TODO: document these, and test that they exist
        # TODO: Other things to inject??
        func_globals = {'__jid__': jid,
                        '__user__': data['user'],
                        '__tag__': tag,
                        # weak ref to avoid the Exception in interpreter teardown
                        # of event
                        '__jid_event__': weakref.proxy(namespaced_event),
                        }

        func_globals['__jid_event__'].fire_event(data, 'new')

        # Inject some useful globals to *all* the funciton's global namespace
        # only once per module-- not per func
        completed_funcs = []
        for mod_name, mod_func in self.functions.iteritems():
            mod, _ = mod_name.split('.', 1)
            if mod in completed_funcs:
                continue
            completed_funcs.append(mod)
            for global_key, value in func_globals.iteritems():
                self.functions[mod_name].func_globals[global_key] = value
        try:
            self._verify_fun(fun)

            # There are some descrepencies of what a "low" structure is
            # in the publisher world it is a dict including stuff such as jid,
            # fun, arg (a list of args, with kwargs packed in). Historically
            # this particular one has had no "arg" and just has had all the
            # kwargs packed into the top level object. The plan is to move away
            # from that since the caller knows what is an arg vs a kwarg, but
            # while we make the transition we will load "kwargs" using format_call
            # if there are no kwargs in the low object passed in
            f_call = None
            if 'args' not in low:
                f_call = salt.utils.format_call(self.functions[fun], low)
                args = f_call.get('args', ())
            else:
                args = low['args']
            if 'kwargs' not in low:
                if f_call is None:
                    f_call = salt.utils.format_call(self.functions[fun], low)
                kwargs = f_call.get('kwargs', {})

                # throw a warning for the badly formed low data if we found
                # kwargs using the old mechanism
                if kwargs:
                    salt.utils.warn_until(
                        'Boron',
                        'kwargs must be passed inside the low under "kwargs"'
                    )
            else:
                kwargs = low['kwargs']

            data['return'] = self.functions[fun](*args, **kwargs)
            data['success'] = True
        except (Exception, SystemExit) as exc:
            data['return'] = 'Exception occurred in {0} {1}: {2}'.format(
                            self.client,
                            fun,
                            traceback.format_exc(),
                            )
            data['success'] = False

        namespaced_event.fire_event(data, 'ret')
        salt.utils.job.store_job(
            self.opts,
            {'id': self.opts['id'], 'tgt': self.opts['id'],
             'jid': data['jid'], 'return': data},
            event=None)
        # if we fired an event, make sure to delete the event object.
        # This will ensure that we call destroy, which will do the 0MQ linger
        del event
        del namespaced_event
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

    def _proc_function(self, fun, low, user, tag, jid, daemonize=True):
        '''
        Run this method in a multiprocess target to execute the function in a
        multiprocess and fire the return data on the event bus
        '''
        if daemonize:
            salt.utils.daemonize()

        # pack a few things into low
        low['__jid__'] = jid
        low['__user__'] = user
        low['__tag__'] = tag

        return self.low(fun, low)

    def cmd_async(self, low):
        '''
        Execute a function asynchronously; eauth is respected

        This function requires that :conf_master:`external_auth` is configured
        and the user is authorized

        .. code-block:: python

            >>> wheel.cmd_async({
                'fun': 'key.finger',
                'match': 'jerry',
                'eauth': 'auto',
                'username': 'saltdev',
                'password': 'saltdev',
            })
            {'jid': '20131219224744416681', 'tag': 'salt/wheel/20131219224744416681'}
        '''
        return self.master_call(**low)

    def _gen_async_pub(self):
        jid = salt.utils.jid.gen_jid()
        tag = tagify(jid, prefix=self.tag_prefix)
        return {'tag': tag, 'jid': jid}

    def async(self, fun, low, user='UNKNOWN'):
        '''
        Execute the function in a multiprocess and return the event tag to use
        to watch for the return
        '''
        async_pub = self._gen_async_pub()

        proc = multiprocessing.Process(
                target=self._proc_function,
                args=(fun, low, user, async_pub['tag'], async_pub['jid']))
        proc.start()
        proc.join()  # MUST join, otherwise we leave zombies all over
        return async_pub

    def print_async_event(self, suffix, event):
        '''
        Print all of the events with the prefix 'tag'
        '''
        # some suffixes we don't want to print
        if suffix in ('new', ):
            return

        # TODO: clean up this event print out. We probably want something
        # more general, since this will get *really* messy as
        # people use more events that don't quite fit into this mold
        if suffix == 'ret':  # for "ret" just print out return
            salt.output.display_output(event['return'], None, self.opts)
        elif isinstance(event, dict) and 'outputter' in event and event['outputter'] is not None:
            print(self.outputters[event['outputter']](event['data']))
        # otherwise fall back on basic printing
        else:
            print('{tag}: {event}'.format(tag=suffix,
                                          event=event))
