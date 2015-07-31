# -*- coding: utf-8 -*-
'''
The module used to execute states in salt. A state is unlike a module
execution in that instead of just executing a command it ensure that a
certain state is present on the system.

The data sent to the state calls is as follows:
    { 'state': '<state module name>',
      'fun': '<state function name>',
      'name': '<the name argument passed to all states>'
      'argn': '<arbitrary argument, can have many of these>'
      }
'''

from __future__ import absolute_import

# Import python libs
import os
import sys
import copy
import site
import fnmatch
import logging
import traceback
import datetime

# Import salt libs
import salt.utils
import salt.loader
import salt.minion
import salt.pillar
import salt.fileclient
import salt.utils.event
import salt.syspaths as syspaths
from salt.utils import context, immutabletypes
from salt.ext.six import string_types
from salt.template import compile_template, compile_template_str
from salt.exceptions import SaltRenderError, SaltReqTimeoutError, SaltException
from salt.utils.odict import OrderedDict, DefaultOrderedDict

# Import third party libs
from salt.ext.six.moves import range

log = logging.getLogger(__name__)


# These are keywords passed to state module functions which are to be used
# by salt in this state module and not on the actual state module function
STATE_REQUISITE_KEYWORDS = frozenset([
    'onchanges',
    'onfail',
    'prereq',
    'prerequired',
    'watch',
    'require',
    'listen',
    ])
STATE_REQUISITE_IN_KEYWORDS = frozenset([
    'onchanges_in',
    'onfail_in',
    'prereq_in',
    'watch_in',
    'require_in',
    'listen_in',
    ])
STATE_RUNTIME_KEYWORDS = frozenset([
    'fun',
    'state',
    'check_cmd',
    'failhard',
    'onlyif',
    'unless',
    'order',
    'reload_modules',
    'reload_grains',
    'reload_pillar',
    'saltenv',
    'use',
    'use_in',
    '__env__',
    '__sls__',
    '__id__',
    '__pub_user',
    '__pub_arg',
    '__pub_jid',
    '__pub_fun',
    '__pub_tgt',
    '__pub_ret',
    '__pub_pid',
    '__pub_tgt_type',
    ])
STATE_INTERNAL_KEYWORDS = STATE_REQUISITE_KEYWORDS.union(STATE_REQUISITE_IN_KEYWORDS).union(STATE_RUNTIME_KEYWORDS)


def _odict_hashable(self):
    return id(self)


OrderedDict.__hash__ = _odict_hashable


def split_low_tag(tag):
    '''
    Take a low tag and split it back into the low dict that it came from
    '''
    state, id_, name, fun = tag.split('_|-')

    return {'state': state,
            '__id__': id_,
            'name': name,
            'fun': fun}


def _gen_tag(low):
    '''
    Generate the running dict tag string from the low data structure
    '''
    return '{0[state]}_|-{0[__id__]}_|-{0[name]}_|-{0[fun]}'.format(low)


def _l_tag(name, id_):
    low = {'name': 'listen_{0}'.format(name),
           '__id__': 'listen_{0}'.format(id_),
           'state': 'Listen_Error',
           'fun': 'Listen_Error'}
    return _gen_tag(low)


def trim_req(req):
    '''
    Trim any function off of a requisite
    '''
    reqfirst = next(iter(req))
    if '.' in reqfirst:
        return {reqfirst.split('.')[0]: req[reqfirst]}
    return req


def state_args(id_, state, high):
    '''
    Return a set of the arguments passed to the named state
    '''
    args = set()
    if id_ not in high:
        return args
    if state not in high[id_]:
        return args
    for item in high[id_][state]:
        if not isinstance(item, dict):
            continue
        if len(item) != 1:
            continue
        args.add(next(iter(item)))
    return args


def find_name(name, state, high):
    '''
    Scan high data for the id referencing the given name
    '''
    ext_id = ''
    if name in high:
        ext_id = name
    else:
        # We need to scan for the name
        for nid in high:
            if state in high[nid]:
                if isinstance(
                        high[nid][state],
                        list):
                    for arg in high[nid][state]:
                        if not isinstance(arg, dict):
                            continue
                        if len(arg) != 1:
                            continue
                        if arg[next(iter(arg))] == name:
                            ext_id = nid
    return ext_id


def format_log(ret):
    '''
    Format the state into a log message
    '''
    msg = ''
    if isinstance(ret, dict):
        # Looks like the ret may be a valid state return
        if 'changes' in ret:
            # Yep, looks like a valid state return
            chg = ret['changes']
            if not chg:
                if ret['comment']:
                    msg = ret['comment']
                else:
                    msg = 'No changes made for {0[name]}'.format(ret)
            elif isinstance(chg, dict):
                if 'diff' in chg:
                    if isinstance(chg['diff'], string_types):
                        msg = 'File changed:\n{0}'.format(chg['diff'])
                if all([isinstance(x, dict) for x in chg.values()]):
                    if all([('old' in x and 'new' in x)
                            for x in chg.values()]):
                        # This is the return data from a package install
                        msg = 'Installed Packages:\n'
                        for pkg in chg:
                            old = chg[pkg]['old'] or 'absent'
                            new = chg[pkg]['new'] or 'absent'
                            msg += '{0!r} changed from {1!r} to ' \
                                   '{2!r}\n'.format(pkg, old, new)
            if not msg:
                msg = str(ret['changes'])
            if ret['result'] is True or ret['result'] is None:
                log.info(msg)
            else:
                log.error(msg)
    else:
        # catch unhandled data
        log.info(str(ret))


def master_compile(master_opts, minion_opts, grains, id_, saltenv):
    '''
    Compile the master side low state data, and build the hidden state file
    '''
    st_ = MasterHighState(master_opts, minion_opts, grains, id_, saltenv)
    return st_.compile_highstate()


def ishashable(obj):
    try:
        hash(obj)
    except TypeError:
        return False
    return True


class StateError(Exception):
    '''
    Custom exception class.
    '''
    pass


class Compiler(object):
    '''
    Class used to compile and manage the High Data structure
    '''
    def __init__(self, opts, renderers):
        self.opts = opts
        self.rend = renderers

    def render_template(self, template, **kwargs):
        '''
        Enforce the states in a template
        '''
        high = compile_template(
            template, self.rend, self.opts['renderer'], **kwargs)
        if not high:
            return high
        return self.pad_funcs(high)

    def pad_funcs(self, high):
        '''
        Turns dot delimited function refs into function strings
        '''
        for name in high:
            if not isinstance(high[name], dict):
                if isinstance(high[name], string_types):
                    # Is this is a short state? It needs to be padded!
                    if '.' in high[name]:
                        comps = high[name].split('.')
                        if len(comps) >= 2:
                            # Merge the comps
                            comps[1] = '.'.join(comps[1:len(comps)])
                        high[name] = {
                            #'__sls__': template,
                            #'__env__': None,
                            comps[0]: [comps[1]]
                        }
                        continue
                    continue
            skeys = set()
            for key in sorted(high[name]):
                if key.startswith('_'):
                    continue
                if not isinstance(high[name][key], list):
                    continue
                if '.' in key:
                    comps = key.split('.')
                    if len(comps) >= 2:
                        # Merge the comps
                        comps[1] = '.'.join(comps[1:len(comps)])
                    # Salt doesn't support state files such as:
                    #
                    # /etc/redis/redis.conf:
                    #   file.managed:
                    #     - user: redis
                    #     - group: redis
                    #     - mode: 644
                    #   file.comment:
                    #     - regex: ^requirepass
                    if comps[0] in skeys:
                        continue
                    high[name][comps[0]] = high[name].pop(key)
                    high[name][comps[0]].append(comps[1])
                    skeys.add(comps[0])
                    continue
                skeys.add(key)
        return high

    def verify_high(self, high):
        '''
        Verify that the high data is viable and follows the data structure
        '''
        errors = []
        if not isinstance(high, dict):
            errors.append('High data is not a dictionary and is invalid')
        reqs = {}
        for name, body in high.items():
            if name.startswith('__'):
                continue
            if not isinstance(name, string_types):
                errors.append(
                    'ID {0!r} in SLS {1!r} is not formed as a string, but is '
                    'a {2}'.format(name, body['__sls__'], type(name).__name__)
                )
            if not isinstance(body, dict):
                err = ('The type {0} in {1} is not formatted as a dictionary'
                       .format(name, body))
                errors.append(err)
                continue
            for state in body:
                if state.startswith('__'):
                    continue
                if not isinstance(body[state], list):
                    errors.append(
                        'State {0!r} in SLS {1!r} is not formed as a list'
                        .format(name, body['__sls__'])
                    )
                else:
                    fun = 0
                    if '.' in state:
                        fun += 1
                    for arg in body[state]:
                        if isinstance(arg, string_types):
                            fun += 1
                            if ' ' in arg.strip():
                                errors.append(('The function "{0}" in state '
                                '"{1}" in SLS "{2}" has '
                                'whitespace, a function with whitespace is '
                                'not supported, perhaps this is an argument '
                                'that is missing a ":"').format(
                                    arg,
                                    name,
                                    body['__sls__']))
                        elif isinstance(arg, dict):
                            # The arg is a dict, if the arg is require or
                            # watch, it must be a list.
                            #
                            # Add the requires to the reqs dict and check them
                            # all for recursive requisites.
                            argfirst = next(iter(arg))
                            if argfirst in ('require', 'watch', 'prereq', 'onchanges'):
                                if not isinstance(arg[argfirst], list):
                                    errors.append(('The {0}'
                                    ' statement in state {1!r} in SLS {2!r} '
                                    'needs to be formed as a list').format(
                                        argfirst,
                                        name,
                                        body['__sls__']
                                        ))
                                # It is a list, verify that the members of the
                                # list are all single key dicts.
                                else:
                                    reqs[name] = {'state': state}
                                    for req in arg[argfirst]:
                                        if not isinstance(req, dict):
                                            err = ('Requisite declaration {0}'
                                            ' in SLS {1} is not formed as a'
                                            ' single key dictionary').format(
                                                req,
                                                body['__sls__'])
                                            errors.append(err)
                                            continue
                                        req_key = next(iter(req))
                                        req_val = req[req_key]
                                        if '.' in req_key:
                                            errors.append((
                                                'Invalid requisite type {0!r} '
                                                'in state {1!r}, in SLS '
                                                '{2!r}. Requisite types must '
                                                'not contain dots, did you '
                                                'mean {3!r}?'.format(
                                                    req_key,
                                                    name,
                                                    body['__sls__'],
                                                    req_key[:req_key.find('.')]
                                                )
                                            ))
                                        if not ishashable(req_val):
                                            errors.append((
                                                'Illegal requisite "{0}", '
                                                'is SLS {1}\n'
                                                ).format(
                                                    str(req_val),
                                                    body['__sls__']))
                                            continue

                                        # Check for global recursive requisites
                                        reqs[name][req_val] = req_key
                                        # I am going beyond 80 chars on
                                        # purpose, this is just too much
                                        # of a pain to deal with otherwise
                                        if req_val in reqs:
                                            if name in reqs[req_val]:
                                                if reqs[req_val][name] == state:
                                                    if reqs[req_val]['state'] == reqs[name][req_val]:
                                                        err = ('A recursive '
                                                        'requisite was found, SLS '
                                                        '"{0}" ID "{1}" ID "{2}"'
                                                        ).format(
                                                                body['__sls__'],
                                                                name,
                                                                req_val
                                                                )
                                                        errors.append(err)
                                # Make sure that there is only one key in the
                                # dict
                                if len(list(arg)) != 1:
                                    errors.append(('Multiple dictionaries '
                                    'defined in argument of state {0!r} in SLS'
                                    ' {1!r}').format(
                                        name,
                                        body['__sls__']))
                    if not fun:
                        if state == 'require' or state == 'watch':
                            continue
                        errors.append(('No function declared in state {0!r} in'
                            ' SLS {1!r}').format(state, body['__sls__']))
                    elif fun > 1:
                        errors.append(
                            'Too many functions declared in state {0!r} in '
                            'SLS {1!r}'.format(state, body['__sls__'])
                        )
        return errors

    def order_chunks(self, chunks):
        '''
        Sort the chunk list verifying that the chunks follow the order
        specified in the order options.
        '''
        cap = 1
        for chunk in chunks:
            if 'order' in chunk:
                if not isinstance(chunk['order'], int):
                    continue

                chunk_order = chunk['order']
                if chunk_order > cap - 1 and chunk_order > 0:
                    cap = chunk_order + 100
        for chunk in chunks:
            if 'order' not in chunk:
                chunk['order'] = cap
                continue

            if not isinstance(chunk['order'], (int, float)):
                if chunk['order'] == 'last':
                    chunk['order'] = cap + 1000000
                else:
                    chunk['order'] = cap
            if 'name_order' in chunk:
                chunk['order'] = chunk['order'] + chunk.pop('name_order') / 10000.0
            if chunk['order'] < 0:
                chunk['order'] = cap + 1000000 + chunk['order']
        chunks.sort(key=lambda chunk: (chunk['order'], '{0[state]}{0[name]}{0[fun]}'.format(chunk)))
        return chunks

    def compile_high_data(self, high):
        '''
        "Compile" the high data as it is retrieved from the CLI or YAML into
        the individual state executor structures
        '''
        chunks = []
        for name, body in high.items():
            if name.startswith('__'):
                continue
            for state, run in body.items():
                funcs = set()
                names = set()
                if state.startswith('__'):
                    continue
                chunk = {'state': state,
                         'name': name}
                if '__sls__' in body:
                    chunk['__sls__'] = body['__sls__']
                if '__env__' in body:
                    chunk['__env__'] = body['__env__']
                chunk['__id__'] = name
                for arg in run:
                    if isinstance(arg, string_types):
                        funcs.add(arg)
                        continue
                    if isinstance(arg, dict):
                        for key, val in arg.items():
                            if key == 'names':
                                names.update(val)
                                continue
                            else:
                                chunk.update(arg)
                if names:
                    name_order = 1
                    for entry in names:
                        live = copy.deepcopy(chunk)
                        if isinstance(entry, dict):
                            low_name = next(iter(entry.keys()))
                            live['name'] = low_name
                            live.update(entry[low_name][0])
                        else:
                            live['name'] = entry
                        live['name_order'] = name_order
                        name_order = name_order + 1
                        for fun in funcs:
                            live['fun'] = fun
                            chunks.append(live)
                else:
                    live = copy.deepcopy(chunk)
                    for fun in funcs:
                        live['fun'] = fun
                        chunks.append(live)
        chunks = self.order_chunks(chunks)
        return chunks

    def apply_exclude(self, high):
        '''
        Read in the __exclude__ list and remove all excluded objects from the
        high data
        '''
        if '__exclude__' not in high:
            return high
        ex_sls = set()
        ex_id = set()
        exclude = high.pop('__exclude__')
        for exc in exclude:
            if isinstance(exc, str):
                # The exclude statement is a string, assume it is an sls
                ex_sls.add(exc)
            if isinstance(exc, dict):
                # Explicitly declared exclude
                if len(exc) != 1:
                    continue
                key = next(iter(exc.keys()))
                if key == 'sls':
                    ex_sls.add(exc['sls'])
                elif key == 'id':
                    ex_id.add(exc['id'])
        # Now the excludes have been simplified, use them
        if ex_sls:
            # There are sls excludes, find the associtaed ids
            for name, body in high.items():
                if name.startswith('__'):
                    continue
                if body.get('__sls__', '') in ex_sls:
                    ex_id.add(name)
        for id_ in ex_id:
            if id_ in high:
                high.pop(id_)
        return high


class State(object):
    '''
    Class used to execute salt states
    '''
    def __init__(self, opts, pillar=None, jid=None):
        if 'grains' not in opts:
            opts['grains'] = salt.loader.grains(opts)
        self.opts = opts
        self._pillar_override = pillar
        self.opts['pillar'] = self._gather_pillar()
        self.state_con = {}
        self.load_modules()
        self.active = set()
        self.mod_init = set()
        self.pre = {}
        self.__run_num = 0
        self.jid = jid
        self.instance_id = str(id(self))

    def _gather_pillar(self):
        '''
        Whenever a state run starts, gather the pillar data fresh
        '''
        pillar = salt.pillar.get_pillar(
                self.opts,
                self.opts['grains'],
                self.opts['id'],
                self.opts['environment'],
                pillar=self._pillar_override,
                pillarenv=self.opts.get('pillarenv')
                )
        ret = pillar.compile_pillar()
        if self._pillar_override and isinstance(self._pillar_override, dict):
            ret.update(self._pillar_override)
        return ret

    def _mod_init(self, low):
        '''
        Check the module initialization function, if this is the first run
        of a state package that has a mod_init function, then execute the
        mod_init function in the state module.
        '''
        # ensure that the module is loaded
        self.states['{0}.{1}'.format(low['state'], low['fun'])]  # pylint: disable=W0106
        minit = '{0}.mod_init'.format(low['state'])
        if low['state'] not in self.mod_init:
            if minit in self.states._dict:
                mret = self.states[minit](low)
                if not mret:
                    return
                self.mod_init.add(low['state'])

    def _mod_aggregate(self, low, running, chunks):
        '''
        Execute the aggregation systems to runtime modify the low chunk
        '''
        agg_opt = self.functions['config.option']('state_aggregate')
        if low.get('aggregate') is True:
            agg_opt = low['aggregate']
        if agg_opt is True:
            agg_opt = [low['state']]
        else:
            return low
        if low['state'] in agg_opt and not low.get('__agg__'):
            agg_fun = '{0}.mod_aggregate'.format(low['state'])
            if agg_fun in self.states:
                try:
                    low = self.states[agg_fun](low, chunks, running)
                    low['__agg__'] = True
                except TypeError:
                    log.error('Failed to execute aggregate for state {0}'.format(low['state']))
        return low

    def _run_check(self, low_data):
        '''
        Check that unless doesn't return 0, and that onlyif returns a 0.
        '''
        ret = {'result': False}
        cmd_opts = {}
        if 'shell' in self.opts['grains']:
            cmd_opts['shell'] = self.opts['grains'].get('shell')
        if 'onlyif' in low_data:
            if not isinstance(low_data['onlyif'], list):
                low_data_onlyif = [low_data['onlyif']]
            else:
                low_data_onlyif = low_data['onlyif']
            for entry in low_data_onlyif:
                cmd = self.functions['cmd.retcode'](entry, ignore_retcode=True, python_shell=True, **cmd_opts)
                log.debug('Last command return code: {0}'.format(cmd))
                if cmd != 0 and ret['result'] is False:
                    ret.update({'comment': 'onlyif execution failed',
                                'skip_watch': True,
                                'result': True})
                    return ret
                elif cmd == 0:
                    ret.update({'comment': 'onlyif execution succeeded', 'result': False})
            return ret

        if 'unless' in low_data:
            if not isinstance(low_data['unless'], list):
                low_data_unless = [low_data['unless']]
            else:
                low_data_unless = low_data['unless']
            for entry in low_data_unless:
                cmd = self.functions['cmd.retcode'](entry, ignore_retcode=True, python_shell=True, **cmd_opts)
                log.debug('Last command return code: {0}'.format(cmd))
                if cmd == 0 and ret['result'] is False:
                    ret.update({'comment': 'unless execution succeeded',
                                'skip_watch': True,
                                'result': True})
                elif cmd != 0:
                    ret.update({'comment': 'unless execution failed', 'result': False})
                    return ret

        # No reason to stop, return ret
        return ret

    def _run_check_cmd(self, low_data):
        '''
        Alter the way a successful state run is determined
        '''
        ret = {'result': False}
        cmd_opts = {}
        if 'shell' in self.opts['grains']:
            cmd_opts['shell'] = self.opts['grains'].get('shell')
        for entry in low_data['check_cmd']:
            cmd = self.functions['cmd.retcode'](entry, ignore_retcode=True, python_shell=True, **cmd_opts)
            log.debug('Last command return code: {0}'.format(cmd))
            if cmd == 0 and ret['result'] is False:
                ret.update({'comment': 'check_cmd determined the state succeeded', 'result': True})
            elif cmd != 0:
                ret.update({'comment': 'check_cmd determined the state failed', 'result': False})
                return ret
        return ret

    def load_modules(self, data=None):
        '''
        Load the modules into the state
        '''
        log.info('Loading fresh modules for state activity')
        self.functions = salt.loader.minion_mods(self.opts, self.state_con)
        if isinstance(data, dict):
            if data.get('provider', False):
                if isinstance(data['provider'], str):
                    providers = [{data['state']: data['provider']}]
                elif isinstance(data['provider'], list):
                    providers = data['provider']
                else:
                    providers = {}
                for provider in providers:
                    for mod in provider:
                        funcs = salt.loader.raw_mod(self.opts,
                                provider[mod],
                                self.functions)
                        if funcs:
                            for func in funcs:
                                f_key = '{0}{1}'.format(
                                        mod,
                                        func[func.rindex('.'):]
                                        )
                                self.functions[f_key] = funcs[func]
        self.states = salt.loader.states(self.opts, self.functions)
        self.rend = salt.loader.render(self.opts, self.functions, states=self.states)

    def module_refresh(self):
        '''
        Refresh all the modules
        '''
        log.debug('Refreshing modules...')
        if self.opts['grains'].get('os') != 'MacOS':
            # In case a package has been installed into the current python
            # process 'site-packages', the 'site' module needs to be reloaded in
            # order for the newly installed package to be importable.
            try:
                reload(site)
            except RuntimeError:
                log.error('Error encountered during module reload. Modules were not reloaded.')
        self.load_modules()
        if not self.opts.get('local', False) and self.opts.get('multiprocessing', True):
            self.functions['saltutil.refresh_modules']()

    def check_refresh(self, data, ret):
        '''
        Check to see if the modules for this state instance need to be updated,
        only update if the state is a file or a package and if it changed
        something. If the file function is managed check to see if the file is a
        possible module type, e.g. a python, pyx, or .so. Always refresh if the
        function is recurse, since that can lay down anything.
        '''
        _reload_modules = False
        if data.get('reload_grains', False):
            log.debug('Refreshing grains...')
            self.opts['grains'] = salt.loader.grains(self.opts)
            _reload_modules = True

        if data.get('reload_pillar', False):
            log.debug('Refreshing pillar...')
            self.opts['pillar'] = self._gather_pillar()
            _reload_modules = True

        if data.get('reload_modules', False) or _reload_modules:
            # User explicitly requests a reload
            self.module_refresh()
            return

        if not ret['changes']:
            return

        if data['state'] == 'file':
            if data['fun'] == 'managed':
                if data['name'].endswith(
                    ('.py', '.pyx', '.pyo', '.pyc', '.so')):
                    self.module_refresh()
            elif data['fun'] == 'recurse':
                self.module_refresh()
            elif data['fun'] == 'symlink':
                if 'bin' in data['name']:
                    self.module_refresh()
        elif data['state'] in ('pkg', 'ports'):
            self.module_refresh()

    def verify_ret(self, ret):
        '''
        Verify the state return data
        '''
        if not isinstance(ret, dict):
            raise SaltException(
                    'Malformed state return, return must be a dict'
                    )
        bad = []
        for val in ['name', 'result', 'changes', 'comment']:
            if val not in ret:
                bad.append(val)
        if bad:
            raise SaltException(
                    ('The following keys were not present in the state '
                     'return: {0}'
                     ).format(','.join(bad)))

    def verify_data(self, data):
        '''
        Verify the data, return an error statement if something is wrong
        '''
        errors = []
        if 'state' not in data:
            errors.append('Missing "state" data')
        if 'fun' not in data:
            errors.append('Missing "fun" data')
        if 'name' not in data:
            errors.append('Missing "name" data')
        if data['name'] and not isinstance(data['name'], string_types):
            errors.append(
                'ID {0!r} in SLS {1!r} is not formed as a string, but is '
                'a {2}'.format(
                    data['name'], data['__sls__'], type(data['name']).__name__)
            )
        if errors:
            return errors
        full = data['state'] + '.' + data['fun']
        if full not in self.states:
            if '__sls__' in data:
                errors.append(
                    'State \'{0}\' was not found in SLS \'{1}\''.format(
                        full,
                        data['__sls__']
                        )
                    )
                reason = self.states.missing_fun_string(full)
                if reason:
                    errors.append('Reason: {0}'.format(reason))
            else:
                errors.append(
                        'Specified state \'{0}\' was not found'.format(
                            full
                            )
                        )
        else:
            # First verify that the parameters are met
            aspec = salt.utils.args.get_function_argspec(self.states[full])
            arglen = 0
            deflen = 0
            if isinstance(aspec.args, list):
                arglen = len(aspec.args)
            if isinstance(aspec.defaults, tuple):
                deflen = len(aspec.defaults)
            for ind in range(arglen - deflen):
                if aspec.args[ind] not in data:
                    errors.append(
                        'Missing parameter {0} for state {1}'.format(
                            aspec.args[ind],
                            full
                        )
                    )
        # If this chunk has a recursive require, then it will cause a
        # recursive loop when executing, check for it
        reqdec = ''
        if 'require' in data:
            reqdec = 'require'
        if 'watch' in data:
            # Check to see if the service has a mod_watch function, if it does
            # not, then just require
            # to just require extend the require statement with the contents
            # of watch so that the mod_watch function is not called and the
            # requisite capability is still used
            if '{0}.mod_watch'.format(data['state']) not in self.states:
                if 'require' in data:
                    data['require'].extend(data.pop('watch'))
                else:
                    data['require'] = data.pop('watch')
                reqdec = 'require'
            else:
                reqdec = 'watch'
        if reqdec:
            for req in data[reqdec]:
                reqfirst = next(iter(req))
                if data['state'] == reqfirst:
                    if (fnmatch.fnmatch(data['name'], req[reqfirst])
                            or fnmatch.fnmatch(data['__id__'], req[reqfirst])):
                        err = ('Recursive require detected in SLS {0} for'
                               ' require {1} in ID {2}').format(
                                   data['__sls__'],
                                   req,
                                   data['__id__'])
                        errors.append(err)
        return errors

    def verify_high(self, high):
        '''
        Verify that the high data is viable and follows the data structure
        '''
        errors = []
        if not isinstance(high, dict):
            errors.append('High data is not a dictionary and is invalid')
        reqs = {}
        for name, body in high.items():
            try:
                if name.startswith('__'):
                    continue
            except AttributeError:
                pass
            if not isinstance(name, string_types):
                errors.append(
                    'ID {0!r} in SLS {1!r} is not formed as a string, but '
                    'is a {2}. It may need to be quoted.'.format(
                        name, body['__sls__'], type(name).__name__)
                )
            if not isinstance(body, dict):
                err = ('The type {0} in {1} is not formatted as a dictionary'
                       .format(name, body))
                errors.append(err)
                continue
            for state in body:
                if state.startswith('__'):
                    continue
                if body[state] is None:
                    errors.append(
                        'ID {0!r} in SLS {1!r} contains a short declaration '
                        '({2}) with a trailing colon. When not passing any '
                        'arguments to a state, the colon must be omitted.'
                        .format(name, body['__sls__'], state)
                    )
                    continue
                if not isinstance(body[state], list):
                    errors.append(
                        'State {0!r} in SLS {1!r} is not formed as a list'
                        .format(name, body['__sls__'])
                    )
                else:
                    fun = 0
                    if '.' in state:
                        fun += 1
                    for arg in body[state]:
                        if isinstance(arg, string_types):
                            fun += 1
                            if ' ' in arg.strip():
                                errors.append(('The function "{0}" in state '
                                '"{1}" in SLS "{2}" has '
                                'whitespace, a function with whitespace is '
                                'not supported, perhaps this is an argument '
                                'that is missing a ":"').format(
                                    arg,
                                    name,
                                    body['__sls__']))
                        elif isinstance(arg, dict):
                            # The arg is a dict, if the arg is require or
                            # watch, it must be a list.
                            #
                            # Add the requires to the reqs dict and check them
                            # all for recursive requisites.
                            argfirst = next(iter(arg))
                            if argfirst == 'names':
                                if not isinstance(arg[argfirst], list):
                                    errors.append(
                                        'The \'names\' argument in state '
                                        '{0!r} in SLS {1!r} needs to be '
                                        'formed as a list'
                                        .format(name, body['__sls__'])
                                    )
                            if argfirst in ('require', 'watch', 'prereq', 'onchanges'):
                                if not isinstance(arg[argfirst], list):
                                    errors.append(
                                        'The {0} statement in state {1!r} in '
                                        'SLS {2!r} needs to be formed as a '
                                        'list'.format(argfirst,
                                                      name,
                                                      body['__sls__'])
                                    )
                                # It is a list, verify that the members of the
                                # list are all single key dicts.
                                else:
                                    reqs[name] = {'state': state}
                                    for req in arg[argfirst]:
                                        if not isinstance(req, dict):
                                            err = ('Requisite declaration {0}'
                                            ' in SLS {1} is not formed as a'
                                            ' single key dictionary').format(
                                                req,
                                                body['__sls__'])
                                            errors.append(err)
                                            continue
                                        req_key = next(iter(req))
                                        req_val = req[req_key]
                                        if '.' in req_key:
                                            errors.append((
                                                'Invalid requisite type {0!r} '
                                                'in state {1!r}, in SLS '
                                                '{2!r}. Requisite types must '
                                                'not contain dots, did you '
                                                'mean {3!r}?'.format(
                                                    req_key,
                                                    name,
                                                    body['__sls__'],
                                                    req_key[:req_key.find('.')]
                                                )
                                            ))
                                        if not ishashable(req_val):
                                            errors.append((
                                                'Illegal requisite "{0}", '
                                                'please check your syntax.\n'
                                                ).format(str(req_val)))
                                            continue

                                        # Check for global recursive requisites
                                        reqs[name][req_val] = req_key
                                        # I am going beyond 80 chars on
                                        # purpose, this is just too much
                                        # of a pain to deal with otherwise
                                        if req_val in reqs:
                                            if name in reqs[req_val]:
                                                if reqs[req_val][name] == state:
                                                    if reqs[req_val]['state'] == reqs[name][req_val]:
                                                        err = ('A recursive '
                                                        'requisite was found, SLS '
                                                        '"{0}" ID "{1}" ID "{2}"'
                                                        ).format(
                                                                body['__sls__'],
                                                                name,
                                                                req_val
                                                                )
                                                        errors.append(err)
                                # Make sure that there is only one key in the
                                # dict
                                if len(list(arg)) != 1:
                                    errors.append(
                                        'Multiple dictionaries defined in '
                                        'argument of state {0!r} in SLS {1!r}'
                                        .format(name, body['__sls__'])
                                    )
                    if not fun:
                        if state == 'require' or state == 'watch':
                            continue
                        errors.append(
                            'No function declared in state {0!r} in SLS {1!r}'
                            .format(state, body['__sls__'])
                        )
                    elif fun > 1:
                        errors.append(
                            'Too many functions declared in state {0!r} in '
                            'SLS {1!r}'.format(state, body['__sls__'])
                        )
        return errors

    def verify_chunks(self, chunks):
        '''
        Verify the chunks in a list of low data structures
        '''
        err = []
        for chunk in chunks:
            err += self.verify_data(chunk)
        return err

    def order_chunks(self, chunks):
        '''
        Sort the chunk list verifying that the chunks follow the order
        specified in the order options.
        '''
        cap = 1
        for chunk in chunks:
            if 'order' in chunk:
                if not isinstance(chunk['order'], int):
                    continue

                chunk_order = chunk['order']
                if chunk_order > cap - 1 and chunk_order > 0:
                    cap = chunk_order + 100
        for chunk in chunks:
            if 'order' not in chunk:
                chunk['order'] = cap
                continue

            if not isinstance(chunk['order'], (int, float)):
                if chunk['order'] == 'last':
                    chunk['order'] = cap + 1000000
                else:
                    chunk['order'] = cap
            if 'name_order' in chunk:
                chunk['order'] = chunk['order'] + chunk.pop('name_order') / 10000.0
            if chunk['order'] < 0:
                chunk['order'] = cap + 1000000 + chunk['order']
        chunks.sort(key=lambda chunk: (chunk['order'], '{0[state]}{0[name]}{0[fun]}'.format(chunk)))
        return chunks

    def compile_high_data(self, high):
        '''
        "Compile" the high data as it is retrieved from the CLI or YAML into
        the individual state executor structures
        '''
        chunks = []
        for name, body in high.items():
            if name.startswith('__'):
                continue
            for state, run in body.items():
                funcs = set()
                names = set()
                if state.startswith('__'):
                    continue
                chunk = {'state': state,
                         'name': name}
                if '__sls__' in body:
                    chunk['__sls__'] = body['__sls__']
                if '__env__' in body:
                    chunk['__env__'] = body['__env__']
                chunk['__id__'] = name
                for arg in run:
                    if isinstance(arg, string_types):
                        funcs.add(arg)
                        continue
                    if isinstance(arg, dict):
                        for key, val in arg.items():
                            if key == 'names':
                                names.update(val)
                            elif key == 'state':
                                # Don't pass down a state override
                                continue
                            elif (key == 'name' and
                                  not isinstance(val, string_types)):
                                # Invalid name, fall back to ID
                                chunk[key] = name
                            else:
                                chunk[key] = val
                if names:
                    name_order = 1
                    for entry in names:
                        live = copy.deepcopy(chunk)
                        if isinstance(entry, dict):
                            low_name = next(iter(entry.keys()))
                            live['name'] = low_name
                            live.update(entry[low_name][0])
                        else:
                            live['name'] = entry
                        live['name_order'] = name_order
                        name_order = name_order + 1
                        for fun in funcs:
                            live['fun'] = fun
                            chunks.append(live)
                else:
                    live = copy.deepcopy(chunk)
                    for fun in funcs:
                        live['fun'] = fun
                        chunks.append(live)
        chunks = self.order_chunks(chunks)
        return chunks

    def reconcile_extend(self, high):
        '''
        Pull the extend data and add it to the respective high data
        '''
        errors = []
        if '__extend__' not in high:
            return high, errors
        ext = high.pop('__extend__')
        for ext_chunk in ext:
            for name, body in ext_chunk.items():
                if name not in high:
                    state_type = next(
                        x for x in body if not x.startswith('__')
                    )
                    # Check for a matching 'name' override in high data
                    id_ = find_name(name, state_type, high)
                    if id_:
                        name = id_
                    else:
                        errors.append(
                            'Cannot extend ID \'{0}\' in \'{1}:{2}\'. It is not '
                            'part of the high state.\n'
                            'This is likely due to a missing include statement '
                            'or an incorrectly typed ID.\nEnsure that a '
                            'state with an ID of \'{0}\' is available\nin '
                            'environment \'{1}\' and to SLS \'{2}\''.format(
                                name,
                                body.get('__env__', 'base'),
                                body.get('__sls__', 'base'))
                            )
                        continue
                for state, run in body.items():
                    if state.startswith('__'):
                        continue
                    if state not in high[name]:
                        high[name][state] = run
                        continue
                    # high[name][state] is extended by run, both are lists
                    for arg in run:
                        update = False
                        for hind in range(len(high[name][state])):
                            if isinstance(arg, string_types) and isinstance(high[name][state][hind], string_types):
                                # replacing the function, replace the index
                                high[name][state].pop(hind)
                                high[name][state].insert(hind, arg)
                                update = True
                                continue
                            if isinstance(arg, dict) and isinstance(high[name][state][hind], dict):
                                # It is an option, make sure the options match
                                argfirst = next(iter(arg))
                                if argfirst == next(iter(high[name][state][hind])):
                                    # If argfirst is a requisite then we must merge
                                    # our requisite with that of the target state
                                    if argfirst in STATE_REQUISITE_KEYWORDS:
                                        high[name][state][hind][argfirst].extend(arg[argfirst])
                                    # otherwise, its not a requisite and we are just extending (replacing)
                                    else:
                                        high[name][state][hind] = arg
                                    update = True
                                if (argfirst == 'name' and
                                    next(iter(high[name][state][hind])) == 'names'):
                                    # If names are overwritten by name use the name
                                    high[name][state][hind] = arg
                        if not update:
                            high[name][state].append(arg)
        return high, errors

    def apply_exclude(self, high):
        '''
        Read in the __exclude__ list and remove all excluded objects from the
        high data
        '''
        if '__exclude__' not in high:
            return high
        ex_sls = set()
        ex_id = set()
        exclude = high.pop('__exclude__')
        for exc in exclude:
            if isinstance(exc, str):
                # The exclude statement is a string, assume it is an sls
                ex_sls.add(exc)
            if isinstance(exc, dict):
                # Explicitly declared exclude
                if len(exc) != 1:
                    continue
                key = next(iter(exc.keys()))
                if key == 'sls':
                    ex_sls.add(exc['sls'])
                elif key == 'id':
                    ex_id.add(exc['id'])
        # Now the excludes have been simplified, use them
        if ex_sls:
            # There are sls excludes, find the associated ids
            for name, body in high.items():
                if name.startswith('__'):
                    continue
                sls = body.get('__sls__', '')
                if not sls:
                    continue
                for ex_ in ex_sls:
                    if fnmatch.fnmatch(sls, ex_):
                        ex_id.add(name)
        for id_ in ex_id:
            if id_ in high:
                high.pop(id_)
        return high

    def requisite_in(self, high):
        '''
        Extend the data reference with requisite_in arguments
        '''
        req_in = set([
            'require_in',
            'watch_in',
            'onfail_in',
            'onchanges_in',
            'use',
            'use_in',
            'prereq',
            'prereq_in',
            ])
        req_in_all = req_in.union(
                set([
                    'require',
                    'watch',
                    'onfail',
                    'onchanges',
                    ]))
        extend = {}
        errors = []
        for id_, body in high.items():
            if not isinstance(body, dict):
                continue
            for state, run in body.items():
                if state.startswith('__'):
                    continue
                for arg in run:
                    if isinstance(arg, dict):
                        # It is not a function, verify that the arg is a
                        # requisite in statement
                        if len(arg) < 1:
                            # Empty arg dict
                            # How did we get this far?
                            continue
                        # Split out the components
                        key = next(iter(arg))
                        if key not in req_in:
                            continue
                        rkey = key.split('_')[0]
                        items = arg[key]
                        if isinstance(items, dict):
                            # Formatted as a single req_in
                            for _state, name in items.items():

                                # Not a use requisite_in
                                found = False
                                if name not in extend:
                                    extend[name] = {}
                                if '.' in _state:
                                    errors.append((
                                        'Invalid requisite in {0}: {1} for '
                                        '{2}, in SLS {3!r}. Requisites must '
                                        'not contain dots, did you mean {4!r}?'
                                        .format(
                                            rkey,
                                            _state,
                                            name,
                                            body['__sls__'],
                                            _state[:_state.find('.')]
                                        )
                                    ))
                                    _state = _state.split(".")[0]
                                if _state not in extend[name]:
                                    extend[name][_state] = []
                                extend[name]['__env__'] = body['__env__']
                                extend[name]['__sls__'] = body['__sls__']
                                for ind in range(len(extend[name][_state])):
                                    if next(iter(
                                        extend[name][_state][ind])) == rkey:
                                        # Extending again
                                        extend[name][_state][ind][rkey].append(
                                                {state: id_}
                                                )
                                        found = True
                                if found:
                                    continue
                                # The rkey is not present yet, create it
                                extend[name][_state].append(
                                        {rkey: [{state: id_}]}
                                        )

                        if isinstance(items, list):
                            # Formed as a list of requisite additions
                            for ind in items:
                                if not isinstance(ind, dict):
                                    # Malformed req_in
                                    continue
                                if len(ind) < 1:
                                    continue
                                _state = next(iter(ind))
                                name = ind[_state]
                                if '.' in _state:
                                    errors.append((
                                        'Invalid requisite in {0}: {1} for '
                                        '{2}, in SLS {3!r}. Requisites must '
                                        'not contain dots, did you mean {4!r}?'
                                        .format(
                                            rkey,
                                            _state,
                                            name,
                                            body['__sls__'],
                                            _state[:_state.find('.')]
                                        )
                                    ))
                                    _state = _state.split(".")[0]
                                if key == 'prereq_in':
                                    # Add prerequired to origin
                                    if id_ not in extend:
                                        extend[id_] = {}
                                    if state not in extend[id_]:
                                        extend[id_][state] = []
                                    extend[id_][state].append(
                                            {'prerequired': [{_state: name}]}
                                            )
                                if key == 'prereq':
                                    # Add prerequired to prereqs
                                    ext_id = find_name(name, _state, high)
                                    if not ext_id:
                                        continue
                                    if ext_id not in extend:
                                        extend[ext_id] = {}
                                    if _state not in extend[ext_id]:
                                        extend[ext_id][_state] = []
                                    extend[ext_id][_state].append(
                                            {'prerequired': [{state: id_}]}
                                            )
                                    continue
                                if key == 'use_in':
                                    # Add the running states args to the
                                    # use_in states
                                    ext_id = find_name(name, _state, high)
                                    if not ext_id:
                                        continue
                                    ext_args = state_args(ext_id, _state, high)
                                    if ext_id not in extend:
                                        extend[ext_id] = {}
                                    if _state not in extend[ext_id]:
                                        extend[ext_id][_state] = []
                                    ignore_args = req_in_all.union(ext_args)
                                    for arg in high[id_][state]:
                                        if not isinstance(arg, dict):
                                            continue
                                        if len(arg) != 1:
                                            continue
                                        if next(iter(arg)) in ignore_args:
                                            continue
                                        # Don't use name or names
                                        if next(iter(arg.keys())) == 'name':
                                            continue
                                        if next(iter(arg.keys())) == 'names':
                                            continue
                                        extend[ext_id][_state].append(arg)
                                    continue
                                if key == 'use':
                                    # Add the use state's args to the
                                    # running state
                                    ext_id = find_name(name, _state, high)
                                    if not ext_id:
                                        continue
                                    loc_args = state_args(id_, state, high)
                                    if id_ not in extend:
                                        extend[id_] = {}
                                    if state not in extend[id_]:
                                        extend[id_][state] = []
                                    ignore_args = req_in_all.union(loc_args)
                                    for arg in high[ext_id][_state]:
                                        if not isinstance(arg, dict):
                                            continue
                                        if len(arg) != 1:
                                            continue
                                        if next(iter(arg)) in ignore_args:
                                            continue
                                        # Don't use name or names
                                        if next(iter(arg.keys())) == 'name':
                                            continue
                                        if next(iter(arg.keys())) == 'names':
                                            continue
                                        extend[id_][state].append(arg)
                                    continue
                                found = False
                                if name not in extend:
                                    extend[name] = {}
                                if _state not in extend[name]:
                                    extend[name][_state] = []
                                extend[name]['__env__'] = body['__env__']
                                extend[name]['__sls__'] = body['__sls__']
                                for ind in range(len(extend[name][_state])):
                                    if next(iter(
                                        extend[name][_state][ind])) == rkey:
                                        # Extending again
                                        extend[name][_state][ind][rkey].append(
                                                {state: id_}
                                                )
                                        found = True
                                if found:
                                    continue
                                # The rkey is not present yet, create it
                                extend[name][_state].append(
                                        {rkey: [{state: id_}]}
                                        )
        high['__extend__'] = []
        for key, val in extend.items():
            high['__extend__'].append({key: val})
        req_in_high, req_in_errors = self.reconcile_extend(high)
        errors.extend(req_in_errors)
        return req_in_high, errors

    def call(self, low, chunks=None, running=None):
        '''
        Call a state directly with the low data structure, verify data
        before processing.
        '''
        start_time = datetime.datetime.now()
        log.info('Running state [{0}] at time {1}'.format(low['name'], start_time.time().isoformat()))
        errors = self.verify_data(low)
        if errors:
            ret = {
                'result': False,
                'name': low['name'],
                'changes': {},
                'comment': '',
                }
            for err in errors:
                ret['comment'] += '{0}\n'.format(err)
            ret['__run_num__'] = self.__run_num
            self.__run_num += 1
            format_log(ret)
            self.check_refresh(low, ret)
            return ret
        else:
            ret = {'result': False, 'name': low['name'], 'changes': {}}

        if not low.get('__prereq__'):
            log.info(
                    'Executing state {0[state]}.{0[fun]} for {0[name]}'.format(
                        low
                        )
                    )

        if 'provider' in low:
            self.load_modules(low)

        state_func_name = '{0[state]}.{0[fun]}'.format(low)
        cdata = salt.utils.format_call(
            self.states[state_func_name],
            low,
            initial_ret={'full': state_func_name},
            expected_extra_kws=STATE_INTERNAL_KEYWORDS
        )

        inject_globals = {
            # Pass a copy of the running dictionary, the low state chunks and
            # the current state dictionaries.
            # We pass deep copies here because we don't want any misbehaving
            # state module to change these at runtime.
            '__low__': immutabletypes.freeze(low),
            '__running__': immutabletypes.freeze(running) if running else {},
            '__instance_id__': self.instance_id,
            '__lowstate__': immutabletypes.freeze(chunks) if chunks else {}
        }

        if low.get('__prereq__'):
            test = sys.modules[self.states[cdata['full']].__module__].__opts__['test']
            sys.modules[self.states[cdata['full']].__module__].__opts__['test'] = True
        try:
            # Let's get a reference to the salt environment to use within this
            # state call.
            #
            # If the state function accepts an 'env' keyword argument, it
            # allows the state to be overridden(we look for that in cdata). If
            # that's not found in cdata, we look for what we're being passed in
            # the original data, namely, the special dunder __env__. If that's
            # not found we default to 'base'
            if ('unless' in low and '{0[state]}.mod_run_check'.format(low) not in self.states) or \
                    ('onlyif' in low and '{0[state]}.mod_run_check'.format(low) not in self.states):
                ret.update(self._run_check(low))

            if 'saltenv' in low:
                inject_globals['__env__'] = str(low['saltenv'])
            elif isinstance(cdata['kwargs'].get('env', None), string_types):
                # User is using a deprecated env setting which was parsed by
                # format_call.
                # We check for a string type since module functions which
                # allow setting the OS environ also make use of the "env"
                # keyword argument, which is not a string
                inject_globals['__env__'] = str(cdata['kwargs']['env'])
            elif '__env__' in low:
                # The user is passing an alternative environment using __env__
                # which is also not the appropriate choice, still, handle it
                inject_globals['__env__'] = str(low['__env__'])
            else:
                # Let's use the default environment
                inject_globals['__env__'] = 'base'

            if 'result' not in ret or ret['result'] is False:
                with context.func_globals_inject(self.states[cdata['full']],
                                                 **inject_globals):
                    ret = self.states[cdata['full']](*cdata['args'],
                                                     **cdata['kwargs'])
            if 'check_cmd' in low and '{0[state]}.mod_run_check_cmd'.format(low) not in self.states:
                ret.update(self._run_check_cmd(low))
            self.verify_ret(ret)
        except Exception:
            trb = traceback.format_exc()
            # There are a number of possibilities to not have the cdata
            # populated with what we might have expected, so just be smart
            # enough to not raise another KeyError as the name is easily
            # guessable and fallback in all cases to present the real
            # exception to the user
            if len(cdata['args']) > 0:
                name = cdata['args'][0]
            elif 'name' in cdata['kwargs']:
                name = cdata['kwargs']['name']
            else:
                name = low.get('name', low.get('__id__'))
            ret = {
                'result': False,
                'name': name,
                'changes': {},
                'comment': 'An exception occurred in this state: {0}'.format(
                    trb)
            }
        finally:
            if low.get('__prereq__'):
                sys.modules[self.states[cdata['full']].__module__].__opts__[
                    'test'] = test

        # If format_call got any warnings, let's show them to the user
        if 'warnings' in cdata:
            ret.setdefault('warnings', []).extend(cdata['warnings'])

        if 'provider' in low:
            self.load_modules()

        if low.get('__prereq__'):
            low['__prereq__'] = False
            return ret

        ret['__run_num__'] = self.__run_num
        self.__run_num += 1
        format_log(ret)
        self.check_refresh(low, ret)
        finish_time = datetime.datetime.now()
        ret['start_time'] = start_time.time().isoformat()
        delta = (finish_time - start_time)
        # duration in milliseconds.microseconds
        ret['duration'] = (delta.seconds * 1000000 + delta.microseconds)/1000.0
        log.info('Completed state [{0}] at time {1}'.format(low['name'], finish_time.time().isoformat()))
        return ret

    def call_chunks(self, chunks):
        '''
        Iterate over a list of chunks and call them, checking for requires.
        '''
        running = {}
        for low in chunks:
            if '__FAILHARD__' in running:
                running.pop('__FAILHARD__')
                return running
            tag = _gen_tag(low)
            if tag not in running:
                running = self.call_chunk(low, running, chunks)
                if self.check_failhard(low, running):
                    return running
            self.active = set()
        return running

    def check_failhard(self, low, running):
        '''
        Check if the low data chunk should send a failhard signal
        '''
        tag = _gen_tag(low)
        if (low.get('failhard', False) or self.opts['failhard']
                and tag in running):
            return not running[tag]['result']
        return False

    def check_requisite(self, low, running, chunks, pre=False):
        '''
        Look into the running data to check the status of all requisite
        states
        '''
        present = False
        # If mod_watch is not available make it a require
        if 'watch' in low:
            if '{0}.mod_watch'.format(low['state']) not in self.states:
                if 'require' in low:
                    low['require'].extend(low.pop('watch'))
                else:
                    low['require'] = low.pop('watch')
            else:
                present = True
        if 'require' in low:
            present = True
        if 'prerequired' in low:
            present = True
        if 'prereq' in low:
            present = True
        if 'onfail' in low:
            present = True
        if 'onchanges' in low:
            present = True
        if not present:
            return 'met', ()
        reqs = {
                'require': [],
                'watch': [],
                'prereq': [],
                'onfail': [],
                'onchanges': []}
        if pre:
            reqs['prerequired'] = []
        for r_state in reqs:
            if r_state in low and low[r_state] is not None:
                for req in low[r_state]:
                    req = trim_req(req)
                    found = False
                    for chunk in chunks:
                        req_key = next(iter(req))
                        req_val = req[req_key]
                        if req_val is None:
                            continue
                        if req_key == 'sls':
                            # Allow requisite tracking of entire sls files
                            if fnmatch.fnmatch(chunk['__sls__'], req_val):
                                found = True
                                reqs[r_state].append(chunk)
                            continue
                        if (fnmatch.fnmatch(chunk['name'], req_val) or
                            fnmatch.fnmatch(chunk['__id__'], req_val)):
                            if chunk['state'] == req_key:
                                found = True
                                reqs[r_state].append(chunk)
                    if not found:
                        return 'unmet', ()
        fun_stats = set()
        for r_state, chunks in reqs.items():
            if r_state == 'prereq':
                run_dict = self.pre
            else:
                run_dict = running
            for chunk in chunks:
                tag = _gen_tag(chunk)
                if tag not in run_dict:
                    fun_stats.add('unmet')
                    continue
                if r_state == 'onfail':
                    if run_dict[tag]['result'] is True:
                        fun_stats.add('onfail')
                        continue
                else:
                    if run_dict[tag]['result'] is False:
                        fun_stats.add('fail')
                        continue
                if r_state == 'onchanges':
                    if not run_dict[tag]['changes']:
                        fun_stats.add('onchanges')
                        continue
                if r_state == 'watch' and run_dict[tag]['changes']:
                    fun_stats.add('change')
                    continue
                if r_state == 'prereq' and run_dict[tag]['result'] is None:
                    fun_stats.add('premet')
                if r_state == 'prereq' and not run_dict[tag]['result'] is None:
                    fun_stats.add('pre')
                else:
                    fun_stats.add('met')

        if 'unmet' in fun_stats:
            status = 'unmet'
        elif 'fail' in fun_stats:
            status = 'fail'
        elif 'pre' in fun_stats:
            if 'premet' in fun_stats:
                status = 'met'
            else:
                status = 'pre'
        elif 'onfail' in fun_stats:
            status = 'onfail'
        elif 'onchanges' in fun_stats:
            status = 'onchanges'
        elif 'change' in fun_stats:
            status = 'change'
        else:
            status = 'met'

        return status, reqs

    def event(self, chunk_ret, length):
        '''
        Fire an event on the master bus
        '''
        if not self.opts.get('local') and self.opts.get('state_events', True) and self.opts.get('master_uri'):
            ret = {'ret': chunk_ret,
                   'len': length}
            tag = salt.utils.event.tagify(
                    [self.jid, 'prog', self.opts['id'], str(chunk_ret['__run_num__'])], 'job'
                    )
            preload = {'jid': self.jid}
            self.functions['event.fire_master'](ret, tag, preload=preload)

    def call_chunk(self, low, running, chunks):
        '''
        Check if a chunk has any requires, execute the requires and then
        the chunk
        '''
        low = self._mod_aggregate(low, running, chunks)
        self._mod_init(low)
        tag = _gen_tag(low)
        if not low.get('prerequired'):
            self.active.add(tag)
        requisites = ['require', 'watch', 'prereq', 'onfail', 'onchanges']
        if not low.get('__prereq__'):
            requisites.append('prerequired')
            status, reqs = self.check_requisite(low, running, chunks, True)
        else:
            status, reqs = self.check_requisite(low, running, chunks)
        if status == 'unmet':
            lost = {}
            reqs = []
            for requisite in requisites:
                lost[requisite] = []
                if requisite not in low:
                    continue
                for req in low[requisite]:
                    req = trim_req(req)
                    found = False
                    for chunk in chunks:
                        req_key = next(iter(req))
                        req_val = req[req_key]
                        if req_val is None:
                            continue
                        if req_key == 'sls':
                            # Allow requisite tracking of entire sls files
                            if fnmatch.fnmatch(chunk['__sls__'], req_val):
                                if requisite == 'prereq':
                                    chunk['__prereq__'] = True
                                reqs.append(chunk)
                                found = True
                            continue
                        if (fnmatch.fnmatch(chunk['name'], req_val) or
                            fnmatch.fnmatch(chunk['__id__'], req_val)):
                            if chunk['state'] == req_key:
                                if requisite == 'prereq':
                                    chunk['__prereq__'] = True
                                elif requisite == 'prerequired':
                                    chunk['__prerequired__'] = True
                                reqs.append(chunk)
                                found = True
                    if not found:
                        lost[requisite].append(req)
            if lost['require'] or lost['watch'] or lost['prereq'] or lost['onfail'] or lost['onchanges'] or lost.get('prerequired'):
                comment = 'The following requisites were not found:\n'
                for requisite, lreqs in lost.items():
                    if not lreqs:
                        continue
                    comment += \
                        '{0}{1}:\n'.format(' ' * 19, requisite)
                    for lreq in lreqs:
                        req_key = next(iter(lreq))
                        req_val = lreq[req_key]
                        comment += \
                            '{0}{1}: {2}\n'.format(' ' * 23, req_key, req_val)
                running[tag] = {'changes': {},
                                'result': False,
                                'comment': comment,
                                '__run_num__': self.__run_num,
                                '__sls__': low['__sls__']}
                self.__run_num += 1
                self.event(running[tag], len(chunks))
                return running
            for chunk in reqs:
                # Check to see if the chunk has been run, only run it if
                # it has not been run already
                ctag = _gen_tag(chunk)
                if ctag not in running:
                    if ctag in self.active:
                        if chunk.get('__prerequired__'):
                            # Prereq recusive, run this chunk with prereq on
                            if tag not in self.pre:
                                low['__prereq__'] = True
                                self.pre[ctag] = self.call(low, chunks, running)
                                return running
                            else:
                                return running
                        elif ctag not in running:
                            log.error('Recursive requisite found')
                            running[tag] = {
                                    'changes': {},
                                    'result': False,
                                    'comment': 'Recursive requisite found',
                                    '__run_num__': self.__run_num,
                                    '__sls__': low['__sls__']}
                        self.__run_num += 1
                        self.event(running[tag], len(chunks))
                        return running
                    running = self.call_chunk(chunk, running, chunks)
                    if self.check_failhard(chunk, running):
                        running['__FAILHARD__'] = True
                        return running
            if low.get('__prereq__'):
                status, reqs = self.check_requisite(low, running, chunks)
                self.pre[tag] = self.call(low, chunks, running)
                if not self.pre[tag]['changes'] and status == 'change':
                    self.pre[tag]['changes'] = {'watch': 'watch'}
                    self.pre[tag]['result'] = None
            else:
                running = self.call_chunk(low, running, chunks)
            if self.check_failhard(chunk, running):
                running['__FAILHARD__'] = True
                return running
        elif status == 'met':
            if low.get('__prereq__'):
                self.pre[tag] = self.call(low, chunks, running)
            else:
                running[tag] = self.call(low, chunks, running)
        elif status == 'fail':
            # if the requisite that failed was due to a prereq on this low state
            # show the normal error
            if tag in self.pre:
                running[tag] = self.pre[tag]
                running[tag]['__run_num__'] = self.__run_num
                running[tag]['__sls__'] = low['__sls__']
            # otherwise the failure was due to a requisite down the chain
            else:
                # determine what the requisite failures where, and return
                # a nice error message
                failed_requisites = set()
                # look at all requisite types for a failure
                for req_type, req_lows in reqs.iteritems():
                    for req_low in req_lows:
                        req_tag = _gen_tag(req_low)
                        req_ret = self.pre.get(req_tag, running.get(req_tag))
                        # if there is no run output for the requisite it
                        # can't be the failure
                        if req_ret is None:
                            continue
                        # If the result was False (not None) it was a failure
                        if req_ret['result'] is False:
                            # use SLS.ID for the key-- so its easier to find
                            key = '{sls}.{_id}'.format(sls=req_low['__sls__'],
                                                       _id=req_low['__id__'])
                            failed_requisites.add(key)

                _cmt = 'One or more requisite failed: {0}'.format(
                    ', '.join(str(i) for i in failed_requisites)
                )
                running[tag] = {
                    'changes': {},
                    'result': False,
                    'comment': _cmt,
                    '__run_num__': self.__run_num,
                    '__sls__': low['__sls__']
                }
            self.__run_num += 1
        elif status == 'change' and not low.get('__prereq__'):
            ret = self.call(low, chunks, running)
            if not ret['changes'] and not ret.get('skip_watch', False):
                low = low.copy()
                low['sfun'] = low['fun']
                low['fun'] = 'mod_watch'
                low['__reqs__'] = reqs
                ret = self.call(low, chunks, running)
            running[tag] = ret
        elif status == 'pre':
            pre_ret = {'changes': {},
                       'result': True,
                       'comment': 'No changes detected',
                       '__run_num__': self.__run_num,
                       '__sls__': low['__sls__']}
            running[tag] = pre_ret
            self.pre[tag] = pre_ret
            self.__run_num += 1
        elif status == 'onfail':
            running[tag] = {'changes': {},
                            'result': True,
                            'comment': 'State was not run because onfail req did not change',
                            '__run_num__': self.__run_num,
                            '__sls__': low['__sls__']}
            self.__run_num += 1
        elif status == 'onchanges':
            running[tag] = {'changes': {},
                            'result': True,
                            'comment': 'State was not run because onchanges req did not change',
                            '__run_num__': self.__run_num,
                            '__sls__': low['__sls__']}
            self.__run_num += 1
        else:
            if low.get('__prereq__'):
                self.pre[tag] = self.call(low, chunks, running)
            else:
                running[tag] = self.call(low, chunks, running)
        if tag in running:
            self.event(running[tag], len(chunks))
        return running

    def call_listen(self, chunks, running):
        '''
        Find all of the listen routines and call the associated mod_watch runs
        '''
        listeners = []
        crefs = {}
        for chunk in chunks:
            crefs[(chunk['state'], chunk['name'])] = chunk
            crefs[(chunk['state'], chunk['__id__'])] = chunk
            if 'listen' in chunk:
                listeners.append({(chunk['state'], chunk['name']): chunk['listen']})
            if 'listen_in' in chunk:
                for l_in in chunk['listen_in']:
                    for key, val in l_in.items():
                        listeners.append({(key, val): [{chunk['state']: chunk['name']}]})
        mod_watchers = []
        errors = {}
        for l_dict in listeners:
            for key, val in l_dict.items():
                for listen_to in val:
                    if not isinstance(listen_to, dict):
                        continue
                    for lkey, lval in listen_to.items():
                        if (lkey, lval) not in crefs:
                            rerror = {_l_tag(lkey, lval):
                                         {'comment': 'Referenced state {0}: {1} does not exist'.format(lkey, lval),
                                          'name': 'listen_{0}:{1}'.format(lkey, lval),
                                          'result': False,
                                          'changes': {}}}
                            errors.update(rerror)
                            continue
                        to_tag = _gen_tag(crefs[(lkey, lval)])
                        if to_tag not in running:
                            continue
                        if running[to_tag]['changes']:
                            if key not in crefs:
                                rerror = {_l_tag(key[0], key[1]):
                                             {'comment': 'Referenced state {0}: {1} does not exist'.format(key[0], key[1]),
                                              'name': 'listen_{0}:{1}'.format(key[0], key[1]),
                                              'result': False,
                                              'changes': {}}}
                                errors.update(rerror)
                                continue
                            chunk = crefs[key]
                            low = chunk.copy()
                            low['sfun'] = chunk['fun']
                            low['fun'] = 'mod_watch'
                            low['__id__'] = 'listener_{0}'.format(low['__id__'])
                            for req in STATE_REQUISITE_KEYWORDS:
                                if req in low:
                                    low.pop(req)
                            mod_watchers.append(low)
        ret = self.call_chunks(mod_watchers)
        running.update(ret)
        for err in errors:
            errors[err]['__run_num__'] = self.__run_num
            self.__run_num += 1
        running.update(errors)
        return running

    def call_high(self, high):
        '''
        Process a high data call and ensure the defined states.
        '''
        errors = []
        # If there is extension data reconcile it
        high, ext_errors = self.reconcile_extend(high)
        errors += ext_errors
        errors += self.verify_high(high)
        if errors:
            return errors
        high, req_in_errors = self.requisite_in(high)
        errors += req_in_errors
        high = self.apply_exclude(high)
        # Verify that the high data is structurally sound
        if errors:
            return errors
        # Compile and verify the raw chunks
        chunks = self.compile_high_data(high)

        # Check for any disabled states
        disabled = {}
        if 'state_runs_disabled' in self.opts['grains']:
            _chunks = copy.deepcopy(chunks)
            for low in _chunks:
                state_ = '{0}.{1}'.format(low['state'], low['fun'])
                for pat in self.opts['grains']['state_runs_disabled']:
                    if fnmatch.fnmatch(state_, pat):
                        comment = (
                                    'The state function "{0}" is currently disabled by "{1}", '
                                    'to re-enable, run state.enable {1}.'
                                  ).format(
                                    state_,
                                    pat,
                                  )
                        _tag = _gen_tag(low)
                        disabled[_tag] = {'changes': {},
                                          'result': False,
                                          'comment': comment,
                                          '__run_num__': self.__run_num,
                                          '__sls__': low['__sls__']}
                        self.__run_num += 1
                        chunks.remove(low)
                        break

        # If there are extensions in the highstate, process them and update
        # the low data chunks
        if errors:
            return errors
        ret = dict(list(disabled.items()) + list(self.call_chunks(chunks).items()))
        ret = self.call_listen(chunks, ret)

        def _cleanup_accumulator_data():
            accum_data_path = os.path.join(
                salt.utils.get_accumulator_dir(self.opts['cachedir']),
                self.instance_id
            )
            try:
                os.remove(accum_data_path)
                log.debug('Deleted accumulator data file {0}'.format(
                    accum_data_path)
                )
            except OSError:
                log.debug('File {0} does not exist, no need to cleanup.'.format(
                    accum_data_path)
                )
        _cleanup_accumulator_data()

        return ret

    def render_template(self, high, template):
        errors = []
        if not high:
            return high, errors

        if not isinstance(high, dict):
            errors.append(
                'Template {0} does not render to a dictionary'.format(template)
            )
            return high, errors

        invalid_items = ('include', 'exclude', 'extends')
        for item in invalid_items:
            if item in high:
                errors.append(
                    'The \'{0}\' declaration found on \'{1}\' is invalid when '
                    'rendering single templates'.format(item, template)
                )
                return high, errors

        for name in high:
            if not isinstance(high[name], dict):
                if isinstance(high[name], string_types):
                    # Is this is a short state, it needs to be padded
                    if '.' in high[name]:
                        comps = high[name].split('.')
                        high[name] = {
                            #'__sls__': template,
                            #'__env__': None,
                            comps[0]: [comps[1]]
                        }
                        continue

                    errors.append(
                        'ID {0} in template {1} is not a dictionary'.format(
                            name, template
                        )
                    )
                    continue
            skeys = set()
            for key in sorted(high[name]):
                if key.startswith('_'):
                    continue
                if high[name][key] is None:
                    errors.append(
                        'ID {0!r} in template {1} contains a short '
                        'declaration ({2}) with a trailing colon. When not '
                        'passing any arguments to a state, the colon must be '
                        'omitted.'.format(name, template, key)
                    )
                    continue
                if not isinstance(high[name][key], list):
                    continue
                if '.' in key:
                    comps = key.split('.')
                    # Salt doesn't support state files such as:
                    #
                    # /etc/redis/redis.conf:
                    #   file.managed:
                    #     - user: redis
                    #     - group: redis
                    #     - mode: 644
                    #   file.comment:
                    #     - regex: ^requirepass
                    if comps[0] in skeys:
                        errors.append(
                            'ID {0!r} in template {1!r} contains multiple '
                            'state declarations of the same type'
                            .format(name, template)
                        )
                        continue
                    high[name][comps[0]] = high[name].pop(key)
                    high[name][comps[0]].append(comps[1])
                    skeys.add(comps[0])
                    continue
                skeys.add(key)

        return high, errors

    def call_template(self, template):
        '''
        Enforce the states in a template
        '''
        high = compile_template(
            template, self.rend, self.opts['renderer'])
        if not high:
            return high
        high, errors = self.render_template(high, template)
        if errors:
            return errors
        return self.call_high(high)

    def call_template_str(self, template):
        '''
        Enforce the states in a template, pass the template as a string
        '''
        high = compile_template_str(
            template, self.rend, self.opts['renderer'])
        if not high:
            return high
        high, errors = self.render_template(high, '<template-str>')
        if errors:
            return errors
        return self.call_high(high)


class BaseHighState(object):
    '''
    The BaseHighState is an abstract base class that is the foundation of
    running a highstate, extend it and add a self.state object of type State.

    When extending this class, please note that ``self.client`` and
    ``self.matcher`` should be instantiated and handled.
    '''
    def __init__(self, opts):
        self.opts = self.__gen_opts(opts)
        self.iorder = 10000
        self.avail = self.__gather_avail()
        self.serial = salt.payload.Serial(self.opts)
        self.building_highstate = {}

    def __gather_avail(self):
        '''
        Gather the lists of available sls data from the master
        '''
        avail = {}
        for saltenv in self._get_envs():
            avail[saltenv] = self.client.list_states(saltenv)
        return avail

    def __gen_opts(self, opts):
        '''
        The options used by the High State object are derived from options
        on the minion and the master, or just the minion if the high state
        call is entirely local.
        '''
        # If the state is intended to be applied locally, then the local opts
        # should have all of the needed data, otherwise overwrite the local
        # data items with data from the master
        if 'local_state' in opts:
            if opts['local_state']:
                return opts
        mopts = self.client.master_opts()
        if not isinstance(mopts, dict):
            # An error happened on the master
            opts['renderer'] = 'yaml_jinja'
            opts['failhard'] = False
            opts['state_top'] = 'salt://top.sls'
            opts['nodegroups'] = {}
            opts['file_roots'] = {'base': [syspaths.BASE_FILE_ROOTS_DIR]}
        else:
            opts['renderer'] = mopts['renderer']
            opts['failhard'] = mopts.get('failhard', False)
            if mopts['state_top'].startswith('salt://'):
                opts['state_top'] = mopts['state_top']
            elif mopts['state_top'].startswith('/'):
                opts['state_top'] = os.path.join('salt://', mopts['state_top'][1:])
            else:
                opts['state_top'] = os.path.join('salt://', mopts['state_top'])
            opts['state_top_saltenv'] = mopts.get('state_top_saltenv', None)
            opts['nodegroups'] = mopts.get('nodegroups', {})
            opts['state_auto_order'] = mopts.get(
                    'state_auto_order',
                    opts['state_auto_order'])
            opts['file_roots'] = mopts['file_roots']
            opts['state_events'] = mopts.get('state_events')
            opts['state_aggregate'] = mopts.get('state_aggregate', opts.get('state_aggregate', False))
            opts['jinja_lstrip_blocks'] = mopts.get('jinja_lstrip_blocks', False)
            opts['jinja_trim_blocks'] = mopts.get('jinja_trim_blocks', False)
        return opts

    def _get_envs(self):
        '''
        Pull the file server environments out of the master options
        '''
        envs = set(['base'])
        if 'file_roots' in self.opts:
            envs.update(list(self.opts['file_roots']))
        return envs.union(set(self.client.envs()))

    def get_tops(self):
        '''
        Gather the top files
        '''
        tops = DefaultOrderedDict(list)
        include = DefaultOrderedDict(list)
        done = DefaultOrderedDict(list)
        # Gather initial top files
        if self.opts['environment']:
            tops[self.opts['environment']] = [
                    compile_template(
                        self.client.cache_file(
                            self.opts['state_top'],
                            self.opts['environment']
                            ),
                        self.state.rend,
                        self.state.opts['renderer'],
                        saltenv=self.opts['environment']
                        )
                    ]
        else:
            if self.opts.get('state_top_saltenv', False):
                saltenv = self.opts['state_top_saltenv']
                tops[saltenv].append(
                        compile_template(
                            self.client.cache_file(
                                self.opts['state_top'],
                                saltenv
                                ),
                            self.state.rend,
                            self.state.opts['renderer'],
                            saltenv=saltenv
                            )
                        )
            else:
                for saltenv in self._get_envs():
                    tops[saltenv].append(
                            compile_template(
                                self.client.cache_file(
                                    self.opts['state_top'],
                                    saltenv
                                    ),
                                self.state.rend,
                                self.state.opts['renderer'],
                                saltenv=saltenv
                                )
                            )

        # Search initial top files for includes
        for saltenv, ctops in tops.items():
            for ctop in ctops:
                if 'include' not in ctop:
                    continue
                for sls in ctop['include']:
                    include[saltenv].append(sls)
                ctop.pop('include')
        # Go through the includes and pull out the extra tops and add them
        while include:
            pops = []
            for saltenv, states in include.items():
                pops.append(saltenv)
                if not states:
                    continue
                for sls_match in states:
                    for sls in fnmatch.filter(self.avail[saltenv], sls_match):
                        if sls in done[saltenv]:
                            continue
                        tops[saltenv].append(
                                compile_template(
                                    self.client.get_state(
                                        sls,
                                        saltenv
                                        ).get('dest', False),
                                    self.state.rend,
                                    self.state.opts['renderer'],
                                    saltenv=saltenv
                                    )
                                )
                        done[saltenv].append(sls)
            for saltenv in pops:
                if saltenv in include:
                    include.pop(saltenv)
        return tops

    def merge_tops(self, tops):
        '''
        Cleanly merge the top files
        '''
        top = DefaultOrderedDict(OrderedDict)
        for ctops in tops.values():
            for ctop in ctops:
                for saltenv, targets in ctop.items():
                    if saltenv == 'include':
                        continue
                    try:
                        for tgt in targets:
                            if tgt not in top[saltenv]:
                                top[saltenv][tgt] = ctop[saltenv][tgt]
                                continue
                            matches = []
                            states = set()
                            for comp in top[saltenv][tgt]:
                                if isinstance(comp, dict):
                                    matches.append(comp)
                                if isinstance(comp, string_types):
                                    states.add(comp)
                            top[saltenv][tgt] = matches
                            top[saltenv][tgt].extend(list(states))
                    except TypeError:
                        raise SaltRenderError('Unable to render top file. No targets found.')
        return top

    def verify_tops(self, tops):
        '''
        Verify the contents of the top file data
        '''
        errors = []
        if not isinstance(tops, dict):
            errors.append('Top data was not formed as a dict')
            # No further checks will work, bail out
            return errors
        for saltenv, matches in tops.items():
            if saltenv == 'include':
                continue
            if not isinstance(saltenv, string_types):
                errors.append(
                    'Environment {0} in top file is not formed as a '
                    'string'.format(saltenv)
                )
            if saltenv == '':
                errors.append('Empty saltenv statement in top file')
            if not isinstance(matches, dict):
                errors.append(
                    'The top file matches for saltenv {0} are not '
                    'formatted as a dict'.format(saltenv)
                )
            for slsmods in matches.values():
                if not isinstance(slsmods, list):
                    errors.append('Malformed topfile (state declarations not '
                                  'formed as a list)')
                    continue
                for slsmod in slsmods:
                    if isinstance(slsmod, dict):
                        # This value is a match option
                        for val in slsmod.values():
                            if not val:
                                errors.append(
                                    'Improperly formatted top file matcher '
                                    'in saltenv {0}: {1} file'.format(
                                        slsmod,
                                        val
                                    )
                                )
                    elif isinstance(slsmod, string_types):
                        # This is a sls module
                        if not slsmod:
                            errors.append(
                                'Environment {0} contains an empty sls '
                                'index'.format(saltenv)
                            )

        return errors

    def get_top(self):
        '''
        Returns the high data derived from the top file
        '''
        tops = self.get_tops()
        return self.merge_tops(tops)

    def top_matches(self, top):
        '''
        Search through the top high data for matches and return the states
        that this minion needs to execute.

        Returns:
        {'saltenv': ['state1', 'state2', ...]}
        '''
        matches = {}
        # pylint: disable=cell-var-from-loop
        for saltenv, body in top.items():
            if self.opts['environment']:
                if saltenv != self.opts['environment']:
                    continue
            for match, data in body.items():
                def _filter_matches(_match, _data, _opts):
                    if isinstance(_data, string_types):
                        _data = [_data]
                    if self.matcher.confirm_top(
                            _match,
                            _data,
                            _opts
                            ):
                        if saltenv not in matches:
                            matches[saltenv] = []
                        for item in _data:
                            if 'subfilter' in item:
                                _tmpdata = item.pop('subfilter')
                                for match, data in _tmpdata.items():
                                    _filter_matches(match, data, _opts)
                            if isinstance(item, string_types):
                                matches[saltenv].append(item)
                _filter_matches(match, data, self.opts['nodegroups'])
        ext_matches = self.client.ext_nodes()
        for saltenv in ext_matches:
            if saltenv in matches:
                matches[saltenv] = list(
                    set(ext_matches[saltenv]).union(matches[saltenv]))
            else:
                matches[saltenv] = ext_matches[saltenv]
        # pylint: enable=cell-var-from-loop
        return matches

    def load_dynamic(self, matches):
        '''
        If autoload_dynamic_modules is True then automatically load the
        dynamic modules
        '''
        if not self.opts['autoload_dynamic_modules']:
            return
        if self.opts.get('local', False):
            syncd = self.state.functions['saltutil.sync_all'](list(matches),
                                                              refresh=False)
        else:
            syncd = self.state.functions['saltutil.sync_all'](list(matches),
                                                              refresh=False)
        if syncd['grains']:
            self.opts['grains'] = salt.loader.grains(self.opts)
            self.state.opts['pillar'] = self.state._gather_pillar()
        self.state.module_refresh()

    def render_state(self, sls, saltenv, mods, matches, local=False):
        '''
        Render a state file and retrieve all of the include states
        '''
        errors = []
        if not local:
            state_data = self.client.get_state(sls, saltenv)
            fn_ = state_data.get('dest', False)
        else:
            fn_ = sls
            if not os.path.isfile(fn_):
                errors.append(
                    'Specified SLS {0} on local filesystem cannot '
                    'be found.'.format(sls)
                )
        if not fn_:
            errors.append(
                'Specified SLS {0} in saltenv {1} is not '
                'available on the salt master or through a configured '
                'fileserver'.format(sls, saltenv)
            )
        state = None
        try:
            state = compile_template(
                fn_, self.state.rend, self.state.opts['renderer'], saltenv,
                sls, rendered_sls=mods
            )
        except SaltRenderError as exc:
            msg = 'Rendering SLS \'{0}:{1}\' failed: {2}'.format(
                saltenv, sls, exc
            )
            log.critical(msg)
            errors.append(msg)
        except Exception as exc:
            msg = 'Rendering SLS {0} failed, render error: {1}'.format(
                sls, exc
            )
            log.critical(
                msg,
                # Show the traceback if the debug logging level is enabled
                exc_info_on_loglevel=logging.DEBUG
            )
            errors.append('{0}\n{1}'.format(msg, traceback.format_exc()))
        try:
            mods.add('{0}:{1}'.format(saltenv, sls))
        except AttributeError:
            pass
        if state:
            if not isinstance(state, dict):
                errors.append(
                    'SLS {0} does not render to a dictionary'.format(sls)
                )
            else:
                include = []
                if 'include' in state:
                    if not isinstance(state['include'], list):
                        err = ('Include Declaration in SLS {0} is not formed '
                               'as a list'.format(sls))
                        errors.append(err)
                    else:
                        include = state.pop('include')

                self._handle_extend(state, sls, saltenv, errors)
                self._handle_exclude(state, sls, saltenv, errors)
                self._handle_state_decls(state, sls, saltenv, errors)

                for inc_sls in include:
                    # inc_sls may take the form of:
                    #   'sls.to.include' <- same as {<saltenv>: 'sls.to.include'}
                    #   {<env_key>: 'sls.to.include'}
                    #   {'_xenv': 'sls.to.resolve'}
                    xenv_key = '_xenv'

                    if isinstance(inc_sls, dict):
                        env_key, inc_sls = inc_sls.popitem()
                    else:
                        env_key = saltenv

                    if env_key not in self.avail:
                        msg = ('Nonexistent saltenv {0!r} found in include '
                               'of {1!r} within SLS \'{2}:{3}\''
                               .format(env_key, inc_sls, saltenv, sls))
                        log.error(msg)
                        errors.append(msg)
                        continue

                    if inc_sls.startswith('.'):
                        p_comps = sls.split('.')
                        if state_data.get('source', '').endswith('/init.sls'):
                            inc_sls = sls + inc_sls
                        else:
                            inc_sls = '.'.join(p_comps[:-1]) + inc_sls

                    if env_key != xenv_key:
                        # Resolve inc_sls in the specified environment
                        if env_key in matches or fnmatch.filter(self.avail[env_key], inc_sls):
                            resolved_envs = [env_key]
                        else:
                            resolved_envs = []
                    else:
                        # Resolve inc_sls in the subset of environment matches
                        resolved_envs = [
                            aenv for aenv in matches
                            if fnmatch.filter(self.avail[aenv], inc_sls)
                        ]

                    # An include must be resolved to a single environment, or
                    # the include must exist in the current environment
                    if len(resolved_envs) == 1 or saltenv in resolved_envs:
                        # Match inc_sls against the available states in the
                        # resolved env, matching wildcards in the process. If
                        # there were no matches, then leave inc_sls as the
                        # target so that the next recursion of render_state
                        # will recognize the error.
                        sls_targets = fnmatch.filter(
                            self.avail[saltenv],
                            inc_sls
                        ) or [inc_sls]

                        for sls_target in sls_targets:
                            r_env = resolved_envs[0] if len(resolved_envs) == 1 else saltenv
                            mod_tgt = '{0}:{1}'.format(r_env, sls_target)
                            if mod_tgt not in mods:
                                nstate, err = self.render_state(
                                    sls_target,
                                    r_env,
                                    mods,
                                    matches
                                )
                                if nstate:
                                    self.merge_included_states(state, nstate, errors)
                                    state.update(nstate)
                                if err:
                                    errors.extend(err)
                    else:
                        msg = ''
                        if not resolved_envs:
                            msg = ('Unknown include: Specified SLS {0}: {1} is not available on the salt '
                                   'master in saltenv(s): {2} '
                                   ).format(env_key,
                                            inc_sls,
                                            ', '.join(matches) if env_key == xenv_key else env_key)
                        elif len(resolved_envs) > 1:
                            msg = ('Ambiguous include: Specified SLS {0}: {1} is available on the salt master '
                                   'in multiple available saltenvs: {2}'
                                   ).format(env_key,
                                            inc_sls,
                                            ', '.join(resolved_envs))
                        log.critical(msg)
                        errors.append(msg)
                try:
                    self._handle_iorder(state)
                except TypeError:
                    log.critical('Could not render SLS {0}. Syntax error detected.'.format(sls))
        else:
            state = {}
        return state, errors

    def _handle_iorder(self, state):
        '''
        Take a state and apply the iorder system
        '''
        if self.opts['state_auto_order']:
            for name in state:
                for s_dec in state[name]:
                    if not isinstance(s_dec, string_types):
                        # PyDSL OrderedDict?
                        continue

                    if not isinstance(state[name], dict):
                        # Include's or excludes as lists?
                        continue
                    if not isinstance(state[name][s_dec], list):
                        # Bad syntax, let the verify seq pick it up later on
                        continue

                    found = False
                    if s_dec.startswith('_'):
                        continue

                    for arg in state[name][s_dec]:
                        if isinstance(arg, dict):
                            if len(arg) > 0:
                                if next(iter(arg.keys())) == 'order':
                                    found = True
                    if not found:
                        if not isinstance(state[name][s_dec], list):
                            # quite certainly a syntax error, managed elsewhere
                            continue
                        state[name][s_dec].append(
                                {'order': self.iorder}
                                )
                        self.iorder += 1
        return state

    def _handle_state_decls(self, state, sls, saltenv, errors):
        '''
        Add sls and saltenv components to the state
        '''
        for name in state:
            if not isinstance(state[name], dict):
                if name == '__extend__':
                    continue
                if name == '__exclude__':
                    continue

                if isinstance(state[name], string_types):
                    # Is this is a short state, it needs to be padded
                    if '.' in state[name]:
                        comps = state[name].split('.')
                        state[name] = {'__sls__': sls,
                                       '__env__': saltenv,
                                       comps[0]: [comps[1]]}
                        continue
                errors.append(
                    'ID {0} in SLS {1} is not a dictionary'.format(name, sls)
                )
                continue
            skeys = set()
            for key in state[name]:
                if key.startswith('_'):
                    continue
                if not isinstance(state[name][key], list):
                    continue
                if '.' in key:
                    comps = key.split('.')
                    # Salt doesn't support state files such as:
                    #
                    #     /etc/redis/redis.conf:
                    #       file.managed:
                    #         - source: salt://redis/redis.conf
                    #         - user: redis
                    #         - group: redis
                    #         - mode: 644
                    #       file.comment:
                    #           - regex: ^requirepass
                    if comps[0] in skeys:
                        errors.append(
                            'ID {0!r} in SLS {1!r} contains multiple state '
                            'declarations of the same type'.format(name, sls)
                        )
                        continue
                    state[name][comps[0]] = state[name].pop(key)
                    state[name][comps[0]].append(comps[1])
                    skeys.add(comps[0])
                    continue
                skeys.add(key)
            if '__sls__' not in state[name]:
                state[name]['__sls__'] = sls
            if '__env__' not in state[name]:
                state[name]['__env__'] = saltenv

    def _handle_extend(self, state, sls, saltenv, errors):
        '''
        Take the extend dec out of state and apply to the highstate global
        dec
        '''
        if 'extend' in state:
            ext = state.pop('extend')
            if not isinstance(ext, dict):
                errors.append(('Extension value in SLS {0!r} is not a '
                               'dictionary').format(sls))
                return
            for name in ext:
                if not isinstance(ext[name], dict):
                    errors.append(('Extension name {0!r} in SLS {1!r} is '
                                   'not a dictionary'
                                   .format(name, sls)))
                    continue
                if '__sls__' not in ext[name]:
                    ext[name]['__sls__'] = sls
                if '__env__' not in ext[name]:
                    ext[name]['__env__'] = saltenv
                for key in ext[name]:
                    if key.startswith('_'):
                        continue
                    if not isinstance(ext[name][key], list):
                        continue
                    if '.' in key:
                        comps = key.split('.')
                        ext[name][comps[0]] = ext[name].pop(key)
                        ext[name][comps[0]].append(comps[1])
            state.setdefault('__extend__', []).append(ext)

    def _handle_exclude(self, state, sls, saltenv, errors):
        '''
        Take the exclude dec out of the state and apply it to the highstate
        global dec
        '''
        if 'exclude' in state:
            exc = state.pop('exclude')
            if not isinstance(exc, list):
                err = ('Exclude Declaration in SLS {0} is not formed '
                       'as a list'.format(sls))
                errors.append(err)
            state.setdefault('__exclude__', []).extend(exc)

    def render_highstate(self, matches):
        '''
        Gather the state files and render them into a single unified salt
        high data structure.
        '''
        highstate = self.building_highstate
        all_errors = []
        mods = set()
        statefiles = []
        for saltenv, states in matches.items():
            for sls_match in states:
                try:
                    statefiles = fnmatch.filter(self.avail[saltenv], sls_match)
                except KeyError:
                    all_errors.extend(['No matching salt environment for environment {0!r} found'.format(saltenv)])
                # if we did not found any sls in the fileserver listing, this
                # may be because the sls was generated or added later, we can
                # try to directly execute it, and if it fails, anyway it will
                # return the former error
                if not statefiles:
                    statefiles = [sls_match]

                for sls in statefiles:
                    r_env = '{0}:{1}'.format(saltenv, sls)
                    if r_env in mods:
                        continue
                    state, errors = self.render_state(
                        sls, saltenv, mods, matches)
                    if state:
                        self.merge_included_states(highstate, state, errors)
                    for i, error in enumerate(errors[:]):
                        if 'is not available' in error:
                            # match SLS foobar in environment
                            this_sls = 'SLS {0} in saltenv'.format(
                                sls_match)
                            if this_sls in error:
                                errors[i] = (
                                    'No matching sls found for {0!r} '
                                    'in env {1!r}'.format(sls_match, saltenv))
                    all_errors.extend(errors)

        self.clean_duplicate_extends(highstate)
        return highstate, all_errors

    def clean_duplicate_extends(self, highstate):
        if '__extend__' in highstate:
            highext = []
            for items in (ext.items() for ext in highstate['__extend__']):
                for item in items:
                    if item not in highext:
                        highext.append(item)
            highstate['__extend__'] = [{t[0]: t[1]} for t in highext]

    def merge_included_states(self, highstate, state, errors):
        # The extend members can not be treated as globally unique:
        if '__extend__' in state:
            highstate.setdefault('__extend__',
                                 []).extend(state.pop('__extend__'))
        if '__exclude__' in state:
            highstate.setdefault('__exclude__',
                                 []).extend(state.pop('__exclude__'))
        for id_ in state:
            if id_ in highstate:
                if highstate[id_] != state[id_]:
                    errors.append((
                            'Detected conflicting IDs, SLS'
                            ' IDs need to be globally unique.\n    The'
                            ' conflicting ID is {0!r} and is found in SLS'
                            ' \'{1}:{2}\' and SLS \'{3}:{4}\'').format(
                                    id_,
                                    highstate[id_]['__env__'],
                                    highstate[id_]['__sls__'],
                                    state[id_]['__env__'],
                                    state[id_]['__sls__'])
                    )
        try:
            highstate.update(state)
        except ValueError:
            errors.append(
                'Error when rendering state with contents: {0}'.format(state)
            )

    def _check_pillar(self, force=False):
        '''
        Check the pillar for errors, refuse to run the state if there are
        errors in the pillar and return the pillar errors
        '''
        if force:
            return True
        if '_errors' in self.state.opts['pillar']:
            return False
        return True

    def matches_whitelist(self, matches, whitelist):
        '''
        Reads over the matches and returns a matches dict with just the ones
        that are in the whitelist
        '''
        if not whitelist:
            return matches
        ret_matches = {}
        if not isinstance(whitelist, list):
            whitelist = whitelist.split(',')
        for env in matches:
            for sls in matches[env]:
                if sls in whitelist:
                    ret_matches[env] = ret_matches[env] if env in ret_matches else []
                    ret_matches[env].append(sls)
        return ret_matches

    def call_highstate(self, exclude=None, cache=None, cache_name='highstate',
                       force=False, whitelist=None):
        '''
        Run the sequence to execute the salt highstate for this minion
        '''
        # Check that top file exists
        tag_name = 'no_|-states_|-states_|-None'
        ret = {tag_name: {
                'result': False,
                'comment': 'No states found for this minion',
                'name': 'No States',
                'changes': {},
                '__run_num__': 0,
        }}
        cfn = os.path.join(
                self.opts['cachedir'],
                '{0}.cache.p'.format(cache_name)
        )

        if cache:
            if os.path.isfile(cfn):
                with salt.utils.fopen(cfn, 'rb') as fp_:
                    high = self.serial.load(fp_)
                    return self.state.call_high(high)
        # File exists so continue
        err = []
        try:
            top = self.get_top()
        except SaltRenderError as err:
            ret[tag_name]['comment'] = 'Unable to render top file: '
            ret[tag_name]['comment'] += err.error
            return ret
        except Exception:
            trb = traceback.format_exc()
            err.append(trb)
            return err
        err += self.verify_tops(top)
        matches = self.top_matches(top)
        if not matches:
            msg = ('No Top file or external nodes data matches found')
            ret[tag_name]['comment'] = msg
            return ret
        matches = self.matches_whitelist(matches, whitelist)
        self.load_dynamic(matches)
        if not self._check_pillar(force):
            err += ['Pillar failed to render with the following messages:']
            err += self.state.opts['pillar']['_errors']
        else:
            high, errors = self.render_highstate(matches)
            if exclude:
                if isinstance(exclude, str):
                    exclude = exclude.split(',')
                if '__exclude__' in high:
                    high['__exclude__'].extend(exclude)
                else:
                    high['__exclude__'] = exclude
            err += errors
        if err:
            return err
        if not high:
            return ret
        cumask = os.umask(0o77)
        try:
            if salt.utils.is_windows():
                # Make sure cache file isn't read-only
                self.state.functions['cmd.run']('attrib -R "{0}"'.format(cfn), output_loglevel='quiet')
            with salt.utils.fopen(cfn, 'w+b') as fp_:
                try:
                    self.serial.dump(high, fp_)
                except TypeError:
                    # Can't serialize pydsl
                    pass
        except (IOError, OSError):
            msg = 'Unable to write to "state.highstate" cache file {0}'
            log.error(msg.format(cfn))

        os.umask(cumask)
        return self.state.call_high(high)

    def compile_highstate(self):
        '''
        Return just the highstate or the errors
        '''
        err = []
        top = self.get_top()
        err += self.verify_tops(top)
        matches = self.top_matches(top)
        high, errors = self.render_highstate(matches)
        err += errors

        if err:
            return err

        return high

    def compile_low_chunks(self):
        '''
        Compile the highstate but don't run it, return the low chunks to
        see exactly what the highstate will execute
        '''
        top = self.get_top()
        matches = self.top_matches(top)
        high, errors = self.render_highstate(matches)

        # If there is extension data reconcile it
        high, ext_errors = self.state.reconcile_extend(high)
        errors += ext_errors

        # Verify that the high data is structurally sound
        errors += self.state.verify_high(high)
        high, req_in_errors = self.state.requisite_in(high)
        errors += req_in_errors
        high = self.state.apply_exclude(high)

        if errors:
            return errors

        # Compile and verify the raw chunks
        chunks = self.state.compile_high_data(high)

        return chunks


class HighState(BaseHighState):
    '''
    Generate and execute the salt "High State". The High State is the
    compound state derived from a group of template files stored on the
    salt master or in the local cache.
    '''
    # a stack of active HighState objects during a state.highstate run
    stack = []

    def __init__(self, opts, pillar=None, jid=None):
        self.opts = opts
        self.client = salt.fileclient.get_file_client(self.opts)
        BaseHighState.__init__(self, opts)
        self.state = State(self.opts, pillar, jid)
        self.matcher = salt.minion.Matcher(self.opts)

        # tracks all pydsl state declarations globally across sls files
        self._pydsl_all_decls = {}

        # a stack of current rendering Sls objects, maintained and used by the pydsl renderer.
        self._pydsl_render_stack = []

    def push_active(self):
        self.stack.append(self)

    @classmethod
    def pop_active(cls):
        cls.stack.pop()

    @classmethod
    def get_active(cls):
        try:
            return cls.stack[-1]
        except IndexError:
            return None


class MasterState(State):
    '''
    Create a State object for master side compiling
    '''
    def __init__(self, opts, minion):
        State.__init__(self, opts)

    def load_modules(self, data=None):
        '''
        Load the modules into the state
        '''
        log.info('Loading fresh modules for state activity')
        # Load a modified client interface that looks like the interface used
        # from the minion, but uses remote execution
        #
        self.functions = salt.client.FunctionWrapper(
                self.opts,
                self.opts['id']
                )
        # Load the states, but they should not be used in this class apart
        # from inspection
        self.states = salt.loader.states(self.opts, self.functions)
        self.rend = salt.loader.render(self.opts, self.functions, states=self.states)


class MasterHighState(HighState):
    '''
    Execute highstate compilation from the master
    '''
    def __init__(self, master_opts, minion_opts, grains, id_,
                 saltenv=None,
                 env=None):
        if isinstance(env, string_types):
            salt.utils.warn_until(
                'Boron',
                'Passing a salt environment should be done using \'saltenv\' '
                'not \'env\'. This functionality will be removed in Salt '
                'Boron.'
            )
            # Backwards compatibility
            saltenv = env
        # Force the fileclient to be local
        opts = copy.deepcopy(minion_opts)
        opts['file_client'] = 'local'
        opts['file_roots'] = master_opts['master_roots']
        opts['renderer'] = master_opts['renderer']
        opts['state_top'] = master_opts['state_top']
        opts['id'] = id_
        opts['grains'] = grains
        HighState.__init__(self, opts)


class RemoteHighState(object):
    '''
    Manage gathering the data from the master
    '''
    def __init__(self, opts, grains):
        self.opts = opts
        self.grains = grains
        self.serial = salt.payload.Serial(self.opts)
        # self.auth = salt.crypt.SAuth(opts)
        self.channel = salt.transport.Channel.factory(self.opts['master_uri'])

    def compile_master(self):
        '''
        Return the state data from the master
        '''
        load = {'grains': self.grains,
                'opts': self.opts,
                'cmd': '_master_state'}
        try:
            return self.channel.send(load, tries=3, timeout=72000)
        except SaltReqTimeoutError:
            return {}
