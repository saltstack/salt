# coding: utf-8
'''
A collection of mixins useful for the various *Client interfaces
'''

# Import Python libs
from __future__ import absolute_import, print_function, with_statement
import fnmatch
import signal
import logging
import weakref
import traceback
import collections
import copy as pycopy

# Import Salt libs
import salt.exceptions
import salt.minion
import salt.utils.args
import salt.utils.doc
import salt.utils.error
import salt.utils.event
import salt.utils.jid
import salt.utils.job
import salt.utils.lazy
import salt.utils.platform
import salt.utils.process
import salt.utils.state
import salt.utils.user
import salt.utils.versions
import salt.transport
import salt.log.setup
from salt.ext import six

# Import 3rd-party libs
import tornado.stack_context

log = logging.getLogger(__name__)

CLIENT_INTERNAL_KEYWORDS = frozenset([
    u'client',
    u'cmd',
    u'eauth',
    u'fun',
    u'kwarg',
    u'match',
    u'token',
    u'__jid__',
    u'__tag__',
    u'__user__',
    u'username',
    u'password'
])


class ClientFuncsDict(collections.MutableMapping):
    '''
    Class to make a read-only dict for accessing runner funcs "directly"
    '''
    def __init__(self, client):
        self.client = client

    def __getattr__(self, attr):
        '''
        Provide access eg. to 'pack'
        '''
        return getattr(self.client.functions, attr)

    def __setitem__(self, key, val):
        raise NotImplementedError()

    def __delitem__(self, key):
        raise NotImplementedError()

    def __getitem__(self, key):
        '''
        Return a function that you can call with regular func params, but
        will do all the _proc_function magic
        '''
        if key not in self.client.functions:
            raise KeyError

        def wrapper(*args, **kwargs):
            low = {u'fun': key,
                   u'args': args,
                   u'kwargs': kwargs,
                   }
            pub_data = {}
            # Copy kwargs keys so we can iterate over and pop the pub data
            kwargs_keys = list(kwargs)

            # pull out pub_data if you have it
            for kwargs_key in kwargs_keys:
                if kwargs_key.startswith(u'__pub_'):
                    pub_data[kwargs_key] = kwargs.pop(kwargs_key)

            async_pub = self.client._gen_async_pub(pub_data.get(u'__pub_jid'))

            user = salt.utils.user.get_specific_user()
            return self.client._proc_function(
                key,
                low,
                user,
                async_pub[u'tag'],  # TODO: fix
                async_pub[u'jid'],  # TODO: fix
                False,  # Don't daemonize
            )
        return wrapper

    def __len__(self):
        return len(self.client.functions)

    def __iter__(self):
        return iter(self.client.functions)


class SyncClientMixin(object):
    '''
    A mixin for *Client interfaces to abstract common function execution
    '''
    functions = ()

    def functions_dict(self):
        '''
        Return a dict that will mimic the "functions" dict used all over salt.
        It creates a wrapper around the function allowing **kwargs, and if pub_data
        is passed in as kwargs, will re-use the JID passed in
        '''
        return ClientFuncsDict(self)

    def master_call(self, **kwargs):
        '''
        Execute a function through the master network interface.
        '''
        load = kwargs
        load[u'cmd'] = self.client
        channel = salt.transport.Channel.factory(self.opts,
                                                 crypt=u'clear',
                                                 usage=u'master_call')
        ret = channel.send(load)
        if isinstance(ret, collections.Mapping):
            if u'error' in ret:
                salt.utils.error.raise_error(**ret[u'error'])
        return ret

    def cmd_sync(self, low, timeout=None, full_return=False):
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
        event = salt.utils.event.get_master_event(self.opts, self.opts[u'sock_dir'], listen=True)
        job = self.master_call(**low)
        ret_tag = salt.utils.event.tagify(u'ret', base=job[u'tag'])

        if timeout is None:
            timeout = self.opts.get(u'rest_timeout', 300)
        ret = event.get_event(tag=ret_tag, full=True, wait=timeout, auto_reconnect=True)
        if ret is None:
            raise salt.exceptions.SaltClientTimeout(
                u"RunnerClient job '{0}' timed out".format(job[u'jid']),
                jid=job[u'jid'])

        return ret if full_return else ret[u'data'][u'return']

    def cmd(self, fun, arg=None, pub_data=None, kwarg=None, print_event=True, full_return=False):
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
                u'arg must be formatted as a list/tuple'
            )
        if pub_data is None:
            pub_data = {}
        if not isinstance(pub_data, dict):
            raise salt.exceptions.SaltInvocationError(
                u'pub_data must be formatted as a dictionary'
            )
        if kwarg is None:
            kwarg = {}
        if not isinstance(kwarg, dict):
            raise salt.exceptions.SaltInvocationError(
                u'kwarg must be formatted as a dictionary'
            )
        arglist = salt.utils.args.parse_input(
            arg,
            no_parse=self.opts.get(u'no_parse', []))

        # if you were passed kwarg, add it to arglist
        if kwarg:
            kwarg[u'__kwarg__'] = True
            arglist.append(kwarg)

        args, kwargs = salt.minion.load_args_and_kwargs(
            self.functions[fun], arglist, pub_data
        )
        low = {u'fun': fun,
               u'arg': args,
               u'kwarg': kwargs}
        return self.low(fun, low, print_event=print_event, full_return=full_return)

    @property
    def mminion(self):
        if not hasattr(self, u'_mminion'):
            self._mminion = salt.minion.MasterMinion(self.opts, states=False, rend=False)
        return self._mminion

    def low(self, fun, low, print_event=True, full_return=False):
        '''
        Check for deprecated usage and allow until Salt Oxygen.
        '''
        msg = []
        if u'args' in low:
            msg.append(u'call with arg instead')
            low[u'arg'] = low.pop(u'args')
        if u'kwargs' in low:
            msg.append(u'call with kwarg instead')
            low[u'kwarg'] = low.pop(u'kwargs')

        if msg:
            salt.utils.versions.warn_until(u'Oxygen', u' '.join(msg))

        return self._low(fun, low, print_event=print_event, full_return=full_return)

    @property
    def store_job(self):
        '''
        Helper that allows us to turn off storing jobs for different classes
        that may incorporate this mixin.
        '''
        try:
            class_name = self.__class__.__name__.lower()
        except AttributeError:
            log.warning(
                u'Unable to determine class name',
                exc_info_on_loglevel=logging.DEBUG
            )
            return True

        try:
            return self.opts[u'{0}_returns'.format(class_name)]
        except KeyError:
            # No such option, assume this isn't one we care about gating and
            # just return True.
            return True

    def _low(self, fun, low, print_event=True, full_return=False):
        '''
        Execute a function from low data
        Low data includes:
            required:
                - fun: the name of the function to run
            optional:
                - arg: a list of args to pass to fun
                - kwarg: kwargs for fun
                - __user__: user who is running the command
                - __jid__: jid to run under
                - __tag__: tag to run under
        '''
        # fire the mminion loading (if not already done) here
        # this is not to clutter the output with the module loading
        # if we have a high debug level.
        self.mminion  # pylint: disable=W0104
        jid = low.get(u'__jid__', salt.utils.jid.gen_jid(self.opts))
        tag = low.get(u'__tag__', salt.utils.event.tagify(jid, prefix=self.tag_prefix))

        data = {u'fun': u'{0}.{1}'.format(self.client, fun),
                u'jid': jid,
                u'user': low.get(u'__user__', u'UNKNOWN'),
               }

        event = salt.utils.event.get_event(
                u'master',
                self.opts[u'sock_dir'],
                self.opts[u'transport'],
                opts=self.opts,
                listen=False)

        if print_event:
            print_func = self.print_async_event \
                if hasattr(self, u'print_async_event') \
                else None
        else:
            # Suppress printing of return event (this keeps us from printing
            # runner/wheel output during orchestration).
            print_func = None

        namespaced_event = salt.utils.event.NamespacedEvent(
            event,
            tag,
            print_func=print_func
        )

        # TODO: document these, and test that they exist
        # TODO: Other things to inject??
        func_globals = {u'__jid__': jid,
                        u'__user__': data[u'user'],
                        u'__tag__': tag,
                        # weak ref to avoid the Exception in interpreter
                        # teardown of event
                        u'__jid_event__': weakref.proxy(namespaced_event),
                        }

        try:
            self_functions = pycopy.copy(self.functions)
            salt.utils.lazy.verify_fun(self_functions, fun)

            # Inject some useful globals to *all* the function's global
            # namespace only once per module-- not per func
            completed_funcs = []

            for mod_name in six.iterkeys(self_functions):
                if u'.' not in mod_name:
                    continue
                mod, _ = mod_name.split(u'.', 1)
                if mod in completed_funcs:
                    continue
                completed_funcs.append(mod)
                for global_key, value in six.iteritems(func_globals):
                    self.functions[mod_name].__globals__[global_key] = value

            # There are some discrepancies of what a "low" structure is in the
            # publisher world it is a dict including stuff such as jid, fun,
            # arg (a list of args, with kwargs packed in). Historically this
            # particular one has had no "arg" and just has had all the kwargs
            # packed into the top level object. The plan is to move away from
            # that since the caller knows what is an arg vs a kwarg, but while
            # we make the transition we will load "kwargs" using format_call if
            # there are no kwargs in the low object passed in.

            if u'arg' in low and u'kwarg' in low:
                args = low[u'arg']
                kwargs = low[u'kwarg']
            else:
                f_call = salt.utils.args.format_call(
                    self.functions[fun],
                    low,
                    expected_extra_kws=CLIENT_INTERNAL_KEYWORDS
                )
                args = f_call.get(u'args', ())
                kwargs = f_call.get(u'kwargs', {})

            # Update the event data with loaded args and kwargs
            data[u'fun_args'] = list(args) + ([kwargs] if kwargs else [])
            func_globals[u'__jid_event__'].fire_event(data, u'new')

            # Initialize a context for executing the method.
            with tornado.stack_context.StackContext(self.functions.context_dict.clone):
                data[u'return'] = self.functions[fun](*args, **kwargs)
                data[u'success'] = True
                if isinstance(data[u'return'], dict) and u'data' in data[u'return']:
                    # some functions can return boolean values
                    data[u'success'] = salt.utils.state.check_result(data[u'return'][u'data'])
        except (Exception, SystemExit) as ex:
            if isinstance(ex, salt.exceptions.NotImplemented):
                data[u'return'] = str(ex)
            else:
                data[u'return'] = u'Exception occurred in {0} {1}: {2}'.format(
                    self.client,
                    fun,
                    traceback.format_exc(),
                    )
            data[u'success'] = False

        if self.store_job:
            try:
                salt.utils.job.store_job(
                    self.opts,
                    {
                        u'id': self.opts[u'id'],
                        u'tgt': self.opts[u'id'],
                        u'jid': data[u'jid'],
                        u'return': data,
                    },
                    event=None,
                    mminion=self.mminion,
                    )
            except salt.exceptions.SaltCacheError:
                log.error(u'Could not store job cache info. '
                          u'Job details for this run may be unavailable.')

        # Outputters _can_ mutate data so write to the job cache first!
        namespaced_event.fire_event(data, u'ret')

        # if we fired an event, make sure to delete the event object.
        # This will ensure that we call destroy, which will do the 0MQ linger
        log.info(u'Runner completed: %s', data[u'jid'])
        del event
        del namespaced_event
        return data if full_return else data[u'return']

    def get_docs(self, arg=None):
        '''
        Return a dictionary of functions and the inline documentation for each
        '''
        if arg:
            if u'*' in arg:
                target_mod = arg
                _use_fnmatch = True
            else:
                target_mod = arg + u'.' if not arg.endswith(u'.') else arg
                _use_fnmatch = False
            if _use_fnmatch:
                docs = [(fun, self.functions[fun].__doc__)
                        for fun in fnmatch.filter(self.functions, target_mod)]
            else:
                docs = [(fun, self.functions[fun].__doc__)
                        for fun in sorted(self.functions)
                        if fun == arg or fun.startswith(target_mod)]
        else:
            docs = [(fun, self.functions[fun].__doc__)
                    for fun in sorted(self.functions)]
        docs = dict(docs)
        return salt.utils.doc.strip_rst(docs)


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
        if daemonize and not salt.utils.platform.is_windows():
            # Shutdown the multiprocessing before daemonizing
            salt.log.setup.shutdown_multiprocessing_logging()

            salt.utils.process.daemonize()

            # Reconfigure multiprocessing logging after daemonizing
            salt.log.setup.setup_multiprocessing_logging()

        # pack a few things into low
        low[u'__jid__'] = jid
        low[u'__user__'] = user
        low[u'__tag__'] = tag

        return self.low(fun, low, full_return=False)

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

    def _gen_async_pub(self, jid=None):
        if jid is None:
            jid = salt.utils.jid.gen_jid(self.opts)
        tag = salt.utils.event.tagify(jid, prefix=self.tag_prefix)
        return {u'tag': tag, u'jid': jid}

    def async(self, fun, low, user=u'UNKNOWN', pub=None):
        '''
        Execute the function in a multiprocess and return the event tag to use
        to watch for the return
        '''
        async_pub = pub if pub is not None else self._gen_async_pub()

        proc = salt.utils.process.SignalHandlingMultiprocessingProcess(
                target=self._proc_function,
                args=(fun, low, user, async_pub[u'tag'], async_pub[u'jid']))
        with salt.utils.process.default_signals(signal.SIGINT, signal.SIGTERM):
            # Reset current signals before starting the process in
            # order not to inherit the current signal handlers
            proc.start()
        proc.join()  # MUST join, otherwise we leave zombies all over
        return async_pub

    def print_async_event(self, suffix, event):
        '''
        Print all of the events with the prefix 'tag'
        '''
        if not isinstance(event, dict):
            return

        # if we are "quiet", don't print
        if self.opts.get(u'quiet', False):
            return

        # some suffixes we don't want to print
        if suffix in (u'new',):
            return

        try:
            outputter = self.opts.get(u'output', event.get(u'outputter', None) or event.get(u'return').get(u'outputter'))
        except AttributeError:
            outputter = None

        # if this is a ret, we have our own set of rules
        if suffix == u'ret':
            # Check if outputter was passed in the return data. If this is the case,
            # then the return data will be a dict two keys: 'data' and 'outputter'
            if isinstance(event.get(u'return'), dict) \
                    and set(event[u'return']) == set((u'data', u'outputter')):
                event_data = event[u'return'][u'data']
                outputter = event[u'return'][u'outputter']
            else:
                event_data = event[u'return']
        else:
            event_data = {u'suffix': suffix, u'event': event}

        salt.output.display_output(event_data, outputter, self.opts)
